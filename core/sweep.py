"""
Promote generated miqaat events to announced times.

    python3 core/sweep.py jamaats/nj-burhani              # dry run, prints a plan
    python3 core/sweep.py jamaats/nj-burhani --apply      # writes to Google Calendar

`generate.py` produces dates from the tabular Misri calendar. Those dates are
computable; the time a jamaat actually holds the program is not. This reads the
jamaat's own announcement emails and patches the live calendar with real times.

Extraction is done by Claude, not by regex. Anjuman-e-Burhani's mail format is
clean enough that regex would work for them and would break the first time
someone else forked the repo.

Three kinds of mail are handled:

  roundup      "<Month> <Year>H Miqaat Monthly Schedule" -- a whole Hijri month
  per-miqaat   a single confirmation, usually with the final maghrib time
  correction   "Time change:" / "Correction-" follow-ups

Corrections need no special merge logic. Mail is processed oldest to newest and
each write overwrites the last, so a correction that arrives later simply wins.

Idempotency lives in the event description: `source: generated` until an
announcement lands, then `source: announcement <YYYY-MM-DD>`. A re-sweep skips
any event already carrying a stamp at or after the mail's own date. Without
that, every run re-edits every event and mails a notification to every
subscriber.

Ambiguity is never guessed. If the miqaat cannot be matched to the catalog, if
Claude reports low confidence, or if the Hijri and Gregorian dates in the mail
disagree, the event is left exactly as it is and flagged for a human.

PRIVACY: message bodies are held in memory for the length of one API call and
are never written to disk, never logged, and never copied into an event. Only
the extracted fields and a short bounded evidence snippet leave this process.
Jamaat mailing lists carry member names, especially in funeral notices.
"""

from __future__ import annotations

import argparse
import random
import re
import sys
import time
from base64 import urlsafe_b64decode
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Literal

import anthropic
from pydantic import BaseModel

from generate import load, uid
from misri import MONTHS, from_gregorian, to_gregorian

CATALOG = Path(__file__).parent / "catalog.yaml"

MODEL = "claude-opus-5"

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]

# Gmail 5xx and 429 are transient and documented as such. 401/403/404 are not --
# retrying a bad credential just burns time and looks like a hang.
RETRY_STATUS = frozenset({429, 500, 502, 503, 504})

CORRECTION_PREFIXES = ("time change", "correction-", "correction:", "corrected")


class SweepError(Exception):
    """Fatal. The run stops and reports rather than writing a guess."""


# --- Extraction schema -------------------------------------------------------
#
# One mail yields a LIST of occurrences, which is what makes the monthly roundup
# and multi-day ayyam programs fall out of the same code path: a roundup returns
# a dozen, an ayyam returns one per day, a single confirmation returns one.


class Occurrence(BaseModel):
    miqaat_id: str | None
    miqaat_text: str
    hijri_year: int | None
    hijri_month: int | None
    hijri_day: int | None
    gregorian_date: str | None
    start_time: str | None
    venue: str | None
    confidence: Literal["high", "medium", "low"]
    evidence: str


class Extraction(BaseModel):
    occurrences: list[Occurrence]


SYSTEM_PROMPT = """\
You read Dawoodi Bohra jamaat announcement emails and extract the miqaat \
programs they announce.

Return one entry per program OCCURRENCE, not per miqaat. A monthly schedule \
email announces many programs; return all of them. A multi-day ayyam program \
(an urus with three days of majlis, say) is several occurrences that share a \
miqaat_id but fall on different dates -- return one entry per day, each with \
that day's own time.

miqaat_id must be chosen from the catalog list given below, or be null. Match on \
meaning, not on string similarity: "Milad un Nabi (SAW) ni waaz" and "Milad \
Mubarak of Rasulullah" are both milad-un-nabi. If the program is not clearly one \
of the catalog entries -- a general bethak, a fundraiser, a class -- set \
miqaat_id to null. A wrong match is far worse than a null.

hijri_year, hijri_month (1-12) and hijri_day are the Hijri date AS THE EMAIL \
STATES IT for that occurrence. Do not convert or correct it; if the email gives \
no Hijri date, use null. Month order is: {months}.

gregorian_date is the date the program is HELD, as YYYY-MM-DD. start_time is \
24-hour HH:MM, the time the program itself begins. If the email gives a maghrib \
time and a separate program time, use the program time. If only a maghrib time \
is given, use that. If no time is given, use null -- do not infer one from a \
previous year or from a typical time.

venue is the masjid or hall name if stated, otherwise null.

confidence is your confidence in THIS occurrence:
  high    date and time both stated plainly and unambiguously
  medium  something required inference, or the wording was loose
  low     you are guessing at any of the date, the time, or the miqaat identity

evidence is a VERBATIM excerpt of at most 200 characters containing only the \
date, time and venue for this occurrence. It is shown to a human reviewer. \
Never include names of community members, family names, condolence or funeral \
wording, phone numbers, or email addresses -- these emails carry personal \
information about members and the excerpt may be published to a shared \
calendar. If you cannot excerpt the timing without including such details, \
return an empty string.

Catalog:
{catalog}
"""


# --- Retry -------------------------------------------------------------------


def with_backoff(call, what: str, attempts: int = 5):
    """Gmail and Calendar throw transient 5xx under load. Retry those only."""
    from googleapiclient.errors import HttpError

    for attempt in range(attempts):
        try:
            return call()
        except HttpError as e:
            status = getattr(e.resp, "status", None)
            if status not in RETRY_STATUS:
                raise
            problem = f"HTTP {status}"
        except (ConnectionError, TimeoutError, OSError) as e:
            problem = type(e).__name__

        if attempt == attempts - 1:
            raise SweepError(
                f"{what}: {problem} after {attempts} attempts. "
                f"This is a transport failure, NOT an empty result -- "
                f"do not read it as 'no announcements'."
            )
        delay = min(60.0, 2.0**attempt) + random.uniform(0, 1)
        print(f"  {what}: {problem}, retrying in {delay:.1f}s", file=sys.stderr)
        time.sleep(delay)


# --- Gmail -------------------------------------------------------------------


def google_services(creds_dir: Path):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    token = creds_dir / "token.json"
    secret = creds_dir / "credentials.json"
    creds = None

    if token.exists():
        creds = Credentials.from_authorized_user_file(str(token), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not secret.exists():
                raise SweepError(
                    f"No Google credentials. Put an OAuth desktop client at "
                    f"{secret} (both it and token.json are gitignored)."
                )
            creds = InstalledAppFlow.from_client_secrets_file(
                str(secret), SCOPES
            ).run_local_server(port=0)
        token.write_text(creds.to_json(), encoding="utf-8")

    return (
        build("gmail", "v1", credentials=creds, cache_discovery=False),
        build("calendar", "v3", credentials=creds, cache_discovery=False),
    )


def _body_text(payload: dict) -> str:
    """Prefer text/plain; fall back to crudely stripped HTML."""
    if payload.get("mimeType") == "text/plain":
        data = payload.get("body", {}).get("data")
        if data:
            return urlsafe_b64decode(data).decode("utf-8", errors="replace")

    for part in payload.get("parts", []):
        text = _body_text(part)
        if text:
            return text

    if payload.get("mimeType") == "text/html":
        data = payload.get("body", {}).get("data")
        if data:
            html = urlsafe_b64decode(data).decode("utf-8", errors="replace")
            html = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
            html = re.sub(r"<br\s*/?>|</p>|</tr>|</div>", "\n", html, flags=re.I)
            return re.sub(r"<[^>]+>", " ", html)
    return ""


def fetch(gmail, cfg: dict, since: date) -> list[dict]:
    """Announcement mail in the window, oldest first.

    An empty announcement result is only believable if the mailbox is otherwise
    live. A query that returns nothing because auth silently degraded looks
    identical to a quiet week, and treating the two the same is how a jamaat
    ends up with a stale calendar and nobody noticing.
    """
    senders = cfg["sources"].get("announcement_senders") or []
    if not senders:
        raise SweepError("config sources.announcement_senders is empty")

    after = since.strftime("%Y/%m/%d")
    query = "from:(" + " OR ".join(senders) + f") after:{after}"

    listed = with_backoff(
        lambda: gmail.users()
        .messages()
        .list(userId="me", q=query, maxResults=200)
        .execute(),
        what="gmail list",
    )
    ids = [m["id"] for m in listed.get("messages", [])]

    if not ids:
        control = with_backoff(
            lambda: gmail.users()
            .messages()
            .list(userId="me", q=f"after:{after}", maxResults=1)
            .execute(),
            what="gmail control query",
        )
        if not control.get("messages"):
            raise SweepError(
                f"No mail AT ALL since {after}, from any sender. The mailbox or "
                f"the credential is not working. Refusing to report this as "
                f"'no announcements this week'."
            )
        print(f"No announcements since {after} (mailbox is live, {len(ids)} matched).")
        return []

    ignore = [s.lower() for s in cfg["sources"].get("ignore_subjects") or []]
    mails = []

    for mid in ids:
        msg = with_backoff(
            lambda mid=mid: gmail.users()
            .messages()
            .get(userId="me", id=mid, format="full")
            .execute(),
            what=f"gmail get {mid}",
        )
        headers = {
            h["name"].lower(): h["value"] for h in msg["payload"].get("headers", [])
        }
        subject = headers.get("subject", "")
        if any(frag in subject.lower() for frag in ignore):
            continue

        received = datetime.fromtimestamp(int(msg["internalDate"]) / 1000).date()
        mails.append(
            {
                "id": mid,
                "subject": subject,
                "date": received,
                "body": _body_text(msg["payload"]),
                "kind": classify(subject, cfg),
            }
        )

    mails.sort(key=lambda m: m["date"])
    return mails


def classify(subject: str, cfg: dict) -> str:
    """Routing is deterministic; only the extraction needs judgement."""
    low = subject.lower().strip()
    if any(low.startswith(p) for p in CORRECTION_PREFIXES):
        return "correction"
    roundup = (cfg["sources"].get("monthly_schedule_subject") or "").lower()
    if roundup and roundup in low:
        return "roundup"
    return "per-miqaat"


# --- Extraction --------------------------------------------------------------


def extract(client, catalog: dict, mail: dict) -> list[Occurrence]:
    listing = "\n".join(f"  {m['id']}: {m['name']}" for m in catalog["miqaats"])
    system = SYSTEM_PROMPT.format(
        months=", ".join(f"{i + 1}={m}" for i, m in enumerate(MONTHS)),
        catalog=listing,
    )
    response = client.messages.parse(
        model=MODEL,
        max_tokens=16000,
        system=system,
        thinking={"type": "adaptive"},
        messages=[
            {
                "role": "user",
                "content": (
                    f"Email kind: {mail['kind']}\n"
                    f"Received: {mail['date']}\n"
                    f"Subject: {mail['subject']}\n\n"
                    f"{mail['body']}"
                ),
            }
        ],
        output_format=Extraction,
    )
    if response.stop_reason == "refusal":
        raise SweepError(f"extraction refused for {mail['subject']!r}")
    return response.parsed_output.occurrences


# --- Validation --------------------------------------------------------------


@dataclass
class Resolved:
    occ: Occurrence
    mail: dict
    when: date | None = None
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


def resolve(occ: Occurrence, mail: dict, known_ids: set[str]) -> Resolved:
    """Cross-check one occurrence. The mail carries both calendars, so misri.py
    verifies here rather than converting."""
    r = Resolved(occ=occ, mail=mail)

    if not occ.miqaat_id:
        r.problems.append(f"no catalog match for {occ.miqaat_text!r}")
    elif occ.miqaat_id not in known_ids:
        r.problems.append(f"{occ.miqaat_id!r} is not in catalog.yaml")
    if occ.confidence == "low":
        r.problems.append("low confidence")

    if occ.gregorian_date:
        try:
            r.when = date.fromisoformat(occ.gregorian_date)
        except ValueError:
            r.problems.append(f"unparseable date {occ.gregorian_date!r}")
    else:
        r.problems.append("no date given")

    delta = hijri_delta(occ, r.when)
    if delta:
        r.problems.append(
            f"stated Hijri date is {delta:+d} day(s) from the stated Gregorian one"
        )

    if occ.start_time and not re.fullmatch(r"[0-2]\d:[0-5]\d", occ.start_time):
        r.problems.append(f"unparseable time {occ.start_time!r}")
    return r


def hijri_delta(occ: Occurrence, when: date | None) -> int | None:
    """Days between the Hijri and Gregorian dates the mail states together."""
    if when is None or None in (occ.hijri_year, occ.hijri_month, occ.hijri_day):
        return None
    try:
        return (when - to_gregorian(occ.hijri_year, occ.hijri_month, occ.hijri_day)).days
    except (ValueError, IndexError):
        return None


def check_kabisa(resolutions: list[Resolved]) -> None:
    """A whole Hijri month off by the same amount is not an observance decision.

    One miqaat a day out is an `observed_offset` question. An entire month out by
    the same amount in the same direction means KABISA_REMAINDERS is wrong, and
    every year after the anchor is wrong with it. Halt -- do not write dates on
    top of a broken converter.
    """
    months: dict[tuple[int, int], list[int]] = {}
    for r in resolutions:
        if r.mail["kind"] != "roundup":
            continue
        delta = hijri_delta(r.occ, r.when)
        if delta is not None and r.occ.hijri_year and r.occ.hijri_month:
            months.setdefault((r.occ.hijri_year, r.occ.hijri_month), []).append(delta)

    for (hy, hm), deltas in months.items():
        if len(deltas) >= 4 and len(set(deltas)) == 1 and deltas[0] != 0:
            raise SweepError(
                f"HALT: all {len(deltas)} announced dates in {MONTHS[hm - 1]} {hy}H "
                f"are {deltas[0]:+d} day(s) from what misri.py computes.\n"
                f"A whole month shifting together is a KABISA_REMAINDERS error, "
                f"not an observance difference. Fix the kabisa set in core/misri.py "
                f"against the printed taqweem before sweeping again."
            )


# --- Calendar ----------------------------------------------------------------

STAMP = re.compile(r"^source:\s*announcement\s+(\d{4}-\d{2}-\d{2})", re.M)


def already_swept(description: str, mail_date: date) -> bool:
    """True if this event already carries a stamp at or after this mail."""
    match = STAMP.search(description or "")
    return bool(match) and date.fromisoformat(match.group(1)) >= mail_date


def rebuild_description(existing: str, *, source: str, review: str | None) -> str:
    """Keep the human-written lines; replace the machine-managed ones."""
    keep = [
        line
        for line in (existing or "").split("\n")
        if not line.startswith("source:")
        and not line.startswith("NEEDS REVIEW")
        and not line.startswith("TENTATIVE -")
        and not line.startswith("Confirm against")
    ]
    while keep and not keep[-1].strip():
        keep.pop()
    if review:
        keep.append(f"NEEDS REVIEW: {review}")
    keep.append(f"source: {source}")
    return "\n".join(keep)


def find_event(calendar, calendar_id: str, event_uid: str) -> dict | None:
    found = with_backoff(
        lambda: calendar.events()
        .list(calendarId=calendar_id, iCalUID=event_uid, maxResults=2, showDeleted=False)
        .execute(),
        what=f"calendar lookup {event_uid}",
    )
    items = found.get("items", [])
    return items[0] if items else None


def timing(cfg: dict, miqaat_id: str) -> tuple[str, int]:
    """The jamaat's own default time and length for this miqaat."""
    defaults = cfg.get("defaults", {})
    entry = next(
        (e for e in cfg.get("observes", []) if e["id"] == miqaat_id), {}
    )
    start = entry.get("start_time", defaults.get("start_time", "19:00"))
    minutes = entry.get("duration_minutes", defaults.get("duration_minutes", 150))
    return start, minutes


# --- Planning ----------------------------------------------------------------


@dataclass
class Action:
    verb: str  # promote | insert | review | skip
    miqaat_id: str
    when: date
    event_uid: str
    start_time: str | None
    reason: str = ""
    evidence: str = ""
    mail_date: date | None = None
    seq: int = 0
    day: int = 1
    of_days: int = 1


def observance_offset(cfg: dict, miqaat_id: str) -> int:
    defaults = cfg.get("defaults", {})
    entry = next((e for e in cfg.get("observes", []) if e["id"] == miqaat_id), {})
    return entry.get("observed_offset", defaults.get("observed_offset", 0))


def hijri_for(occ: Occurrence, when: date, cfg: dict, miqaat_id: str) -> tuple[int, int]:
    """The Hijri year and month generate.py used when it built this event's UID.

    Prefer what the mail states. Plenty of announcements give only a Gregorian
    date ("Waaz on Milad un Nabi - Sunday, 8/23"), and falling back to zero there
    produces a UID that matches nothing, so the sweep inserts a duplicate beside
    the real event instead of promoting it. Convert instead -- undoing the
    jamaat's observance offset first, because generate.py numbered the event from
    the canonical day, not the day the program runs.
    """
    if occ.hijri_year and occ.hijri_month:
        return occ.hijri_year, occ.hijri_month
    hy, hm, _ = from_gregorian(when - timedelta(days=observance_offset(cfg, miqaat_id)))
    return hy, hm


def plan(resolutions: list[Resolved], cfg: dict, catalog: dict) -> list[Action]:
    """Group by miqaat and Hijri year so multi-day ayyam fan out over seq."""
    jid = cfg["jamaat"]["id"]
    # generate.py numbers a monthly majlis by its Hijri month rather than 0, so
    # the sweep has to use the same convention or it will not find the event.
    monthly = {m["id"] for m in catalog["miqaats"] if m.get("recurrence") == "monthly"}
    actions: list[Action] = []
    groups: dict[tuple[str, int], list[Resolved]] = {}

    for r in resolutions:
        if not r.ok:
            actions.append(
                Action(
                    verb="review",
                    miqaat_id=r.occ.miqaat_id or r.occ.miqaat_text,
                    when=r.when or r.mail["date"],
                    event_uid="",
                    start_time=r.occ.start_time,
                    reason="; ".join(r.problems),
                    evidence=r.occ.evidence,
                    mail_date=r.mail["date"],
                )
            )
            continue
        groups.setdefault((r.occ.miqaat_id, r.when.year), []).append(r)

    for (miqaat_id, _), members in groups.items():
        members.sort(key=lambda r: r.when)
        seen: dict[date, Resolved] = {}
        for r in members:
            # Later mail wins for the same day, so a correction beats the
            # confirmation it corrects. Compare mail dates rather than trusting
            # the order these arrived in.
            prior = seen.get(r.when)
            if prior is None or r.mail["date"] >= prior.mail["date"]:
                seen[r.when] = r
        days = sorted(seen)
        for index, when in enumerate(days):
            r = seen[when]
            hy, hm = hijri_for(r.occ, when, cfg, miqaat_id)
            # A monthly majlis is keyed by Hijri month. Anything else is keyed by
            # its position in the ayyam: day one is the event generate.py already
            # emitted, later days are genuinely new.
            seq = hm if miqaat_id in monthly else index
            actions.append(
                Action(
                    verb="promote",
                    miqaat_id=miqaat_id,
                    when=when,
                    event_uid=uid(jid, miqaat_id, hy, seq),
                    start_time=r.occ.start_time,
                    evidence=r.occ.evidence,
                    mail_date=r.mail["date"],
                    seq=seq,
                    day=index + 1,
                    of_days=len(days),
                )
            )
    return actions


def apply(calendar, calendar_id: str, cfg: dict, actions: list[Action], write: bool):
    tz = cfg["jamaat"]["timezone"]
    counts = {"promoted": 0, "inserted": 0, "flagged": 0, "skipped": 0}

    for a in actions:
        if a.verb == "review":
            counts["flagged"] += 1
            print(f"  REVIEW  {a.miqaat_id} {a.when}  ({a.reason})")
            if a.evidence:
                print(f"          evidence: {a.evidence}")
            continue

        event = find_event(calendar, calendar_id, a.event_uid)
        if event and already_swept(event.get("description", ""), a.mail_date):
            counts["skipped"] += 1
            continue

        default_time, minutes = timing(cfg, a.miqaat_id)
        start_time = a.start_time or default_time
        hh, mm = (int(x) for x in start_time.split(":"))
        begins = datetime.combine(a.when, datetime.min.time()).replace(hour=hh, minute=mm)
        ends = begins + timedelta(minutes=minutes or 150)

        body = {
            "start": {"dateTime": begins.isoformat(), "timeZone": tz},
            "end": {"dateTime": ends.isoformat(), "timeZone": tz},
            "status": "confirmed",
            "description": rebuild_description(
                (event or {}).get("description", ""),
                source=f"announcement {a.mail_date}",
                review=None,
            ),
        }

        if event:
            counts["promoted"] += 1
            print(f"  PROMOTE {a.miqaat_id} {a.when} {start_time}")
            if write:
                with_backoff(
                    lambda e=event, b=body: calendar.events()
                    .patch(
                        calendarId=calendar_id,
                        eventId=e["id"],
                        body=b,
                        sendUpdates="none",
                    )
                    .execute(),
                    what=f"calendar patch {a.event_uid}",
                )
        else:
            # A day of a multi-day ayyam that generate.py emitted as one block.
            counts["inserted"] += 1
            label = f"  (day {a.day} of {a.of_days})" if a.of_days > 1 else ""
            print(f"  INSERT  {a.miqaat_id} {a.when} {start_time}{label}")
            if write:
                body |= {
                    "iCalUID": a.event_uid,
                    "summary": a.miqaat_id,
                    "location": cfg.get("defaults", {}).get("location", ""),
                }
                with_backoff(
                    lambda b=body: calendar.events()
                    .insert(calendarId=calendar_id, body=b, sendUpdates="none")
                    .execute(),
                    what=f"calendar insert {a.event_uid}",
                )
    return counts


# --- Entry point -------------------------------------------------------------


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("jamaat_dir", type=Path)
    p.add_argument("--since", type=date.fromisoformat, default=None)
    p.add_argument("--days", type=int, default=8, help="window if --since is absent")
    p.add_argument("--apply", action="store_true", help="actually write; default is a dry run")
    args = p.parse_args()

    cfg = load(args.jamaat_dir / "config.yaml")
    catalog = load(CATALOG)
    known_ids = {m["id"] for m in catalog["miqaats"]}

    calendar_id = cfg["jamaat"].get("calendar_id")
    if not calendar_id:
        raise SweepError(
            f"Set `calendar_id` under `jamaat:` in "
            f"{args.jamaat_dir / 'config.yaml'} (Google Calendar settings -> "
            f"Integrate calendar -> Calendar ID)."
        )

    since = args.since or (date.today() - timedelta(days=args.days))
    gmail, calendar = google_services(args.jamaat_dir)
    mails = fetch(gmail, cfg, since)
    if not mails:
        return

    print(f"{len(mails)} announcement(s) since {since}")
    client = anthropic.Anthropic()

    resolutions = []
    for mail in mails:
        occurrences = extract(client, catalog, mail)
        print(f"  {mail['date']} [{mail['kind']}] {mail['subject'][:60]} "
              f"-> {len(occurrences)} occurrence(s)")
        resolutions += [resolve(o, mail, known_ids) for o in occurrences]
        mail["body"] = ""  # done with it; do not keep bodies around

    check_kabisa(resolutions)

    actions = plan(resolutions, cfg, catalog)
    print(f"\n{'APPLYING' if args.apply else 'DRY RUN'} ({len(actions)} action(s)):")
    counts = apply(calendar, calendar_id, cfg, actions, write=args.apply)

    print(
        f"\n{counts['promoted']} promoted, {counts['inserted']} inserted, "
        f"{counts['flagged']} flagged for review, {counts['skipped']} already current"
    )
    if not args.apply and (counts["promoted"] or counts["inserted"]):
        print("Dry run -- nothing was written. Re-run with --apply.")
    if counts["flagged"]:
        print("Flagged events were NOT modified. A wrong time is worse than no time.")


if __name__ == "__main__":
    try:
        main()
    except SweepError as e:
        print(f"\nsweep failed: {e}", file=sys.stderr)
        sys.exit(1)
