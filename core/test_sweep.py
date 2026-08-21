"""
Self-tests for core/sweep.py.

    python3 core/test_sweep.py

Plain asserts and fakes, no test runner, same as the self-test at the bottom of
misri.py. Nothing here touches the network: Gmail and Calendar are stubbed and
the Claude extraction call is not exercised at all.

What that leaves unverified is the extraction itself -- whether Claude returns
sensible occurrences for a real announcement. These tests cover everything
downstream of it, which is where a silent wrong answer would actually corrupt
the calendar: the idempotency stamp, the Hijri/Gregorian cross-check, the
ambiguity gates, ayyam fan-out, correction ordering, and the Gmail retry rules.
"""

from __future__ import annotations

import base64
import sys
from datetime import date, timedelta
from pathlib import Path

from googleapiclient.errors import HttpError

import sweep
from generate import uid as generate_uid
from sweep import (
    Occurrence,
    Resolved,
    SweepError,
    _body_text,
    already_swept,
    check_kabisa,
    classify,
    fetch,
    hijri_delta,
    plan,
    rebuild_description,
    resolve,
    timing,
    with_backoff,
)

REPO = Path(__file__).parent.parent
CONFIG = REPO / "jamaats" / "nj-burhani" / "config.yaml"

failures: list[str] = []
checks = 0


def eq(label: str, got, want) -> None:
    global checks
    checks += 1
    if got != want:
        failures.append(f"  {label}: got {got!r}, want {want!r}")


def raises(label: str, call, contains: str) -> None:
    global checks
    checks += 1
    try:
        call()
    except SweepError as e:
        if contains.lower() not in str(e).lower():
            failures.append(f"  {label}: message lacks {contains!r}: {e}")
        return
    failures.append(f"  {label}: expected SweepError, none raised")


def b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode()


def occurrence(**overrides) -> Occurrence:
    """A well-formed occurrence. 19mi Safar 1448H = 2 Aug 2026 is a real
    VERIFIED_ANCHORS pair, so the cross-check is anchored on known-good data."""
    base = dict(
        miqaat_id="chehlum",
        miqaat_text="Chehlum waaz",
        hijri_year=1448,
        hijri_month=2,
        hijri_day=19,
        gregorian_date="2026-08-02",
        start_time="18:45",
        venue="Masjid uz Zainee",
        confidence="high",
        evidence="Sunday 2 August, 6:45pm",
    )
    base.update(overrides)
    return Occurrence(**base)


MAIL = {"date": date(2026, 7, 28), "kind": "per-miqaat", "subject": "Chehlum waaz"}


# --- Routing -----------------------------------------------------------------


def test_classify(cfg):
    eq("roundup", classify("Safar ul Muzaffar 1448H Miqaat Monthly Schedule", cfg), "roundup")
    eq("time change", classify("Time change: Chehlum waaz", cfg), "correction")
    eq("correction dash", classify("Correction- Milad un Nabi", cfg), "correction")
    eq("correction colon", classify("Correction: venue", cfg), "correction")
    eq("plain mail", classify("Chehlum waaz this Sunday", cfg), "per-miqaat")


# --- Idempotency -------------------------------------------------------------


def test_idempotency():
    eq("stamp same day", already_swept("source: announcement 2026-08-02", date(2026, 8, 2)), True)
    eq("stamp newer", already_swept("source: announcement 2026-08-05", date(2026, 8, 2)), True)
    eq("stamp older", already_swept("source: announcement 2026-08-01", date(2026, 8, 2)), False)
    eq("still generated", already_swept("source: generated", date(2026, 8, 2)), False)
    eq("no description", already_swept("", date(2026, 8, 2)), False)

    original = (
        "19mi Safar ul Muzaffar 1448H\n"
        "Niyaz jaman then waaz.\n"
        "TENTATIVE - projected from prior years.\n"
        "Confirm against the jamaat announcement.\n"
        "source: generated"
    )
    promoted = rebuild_description(original, source="announcement 2026-08-02", review=None)
    eq(
        "description rebuild",
        promoted,
        "19mi Safar ul Muzaffar 1448H\nNiyaz jaman then waaz.\nsource: announcement 2026-08-02",
    )
    # The important property: sweeping twice must not accumulate lines.
    eq(
        "rebuild is idempotent",
        rebuild_description(promoted, source="announcement 2026-08-02", review=None),
        promoted,
    )


# --- Cross-check and ambiguity gates -----------------------------------------


def test_resolve(ids):
    good = resolve(occurrence(), MAIL, ids)
    eq("clean occurrence resolves", (good.ok, good.when), (True, date(2026, 8, 2)))
    eq("anchor delta is zero", hijri_delta(occurrence(), date(2026, 8, 2)), 0)

    def problems(**overrides):
        return resolve(occurrence(**overrides), MAIL, ids).problems

    # Every one of these must block the write.
    eq("no catalog match blocks", bool(problems(miqaat_id=None)), True)
    eq("unknown id blocks", bool(problems(miqaat_id="not-a-miqaat")), True)
    eq("low confidence blocks", bool(problems(confidence="low")), True)
    eq("missing date blocks", bool(problems(gregorian_date=None)), True)
    eq("unparseable date blocks", bool(problems(gregorian_date="2 Aug 2026")), True)
    eq("unparseable time blocks", bool(problems(start_time="6:45pm")), True)
    eq("hijri disagreement blocks", bool(problems(gregorian_date="2026-08-03")), True)

    # These must not.
    eq("medium confidence passes", problems(confidence="medium"), [])
    eq("missing time passes", problems(start_time=None), [])
    eq("missing hijri passes", problems(hijri_year=None, hijri_month=None, hijri_day=None), [])


# --- Kabisa halt -------------------------------------------------------------


def shifted_roundup(days: int, hijri_days=(5, 10, 15, 20)) -> list[Resolved]:
    mail = {"date": date(2027, 5, 1), "kind": "roundup", "subject": "Moharram 1449H"}
    out = []
    for day in hijri_days:
        when = sweep.to_gregorian(1449, 1, day) + timedelta(days=days)
        occ = occurrence(
            miqaat_id="ashura",
            hijri_year=1449,
            hijri_month=1,
            hijri_day=day,
            gregorian_date=when.isoformat(),
        )
        out.append(Resolved(occ=occ, mail=mail, when=when))
    return out


def test_kabisa():
    # A whole month shifted the same way is a converter bug, not an observance.
    raises("uniform month shift halts", lambda: check_kabisa(shifted_roundup(1)), "KABISA_REMAINDERS")

    # A single miqaat out by a day is an observed_offset question. Must not halt.
    lone = shifted_roundup(1)[:1] + shifted_roundup(0)[1:]
    check_kabisa(lone)
    checks_ok("lone mismatch does not halt")

    # An aligned month must not halt.
    check_kabisa(shifted_roundup(0))
    checks_ok("aligned month does not halt")

    # Per-miqaat mail is not evidence about the cycle, however it lines up.
    per_miqaat = [
        Resolved(occ=r.occ, mail={**r.mail, "kind": "per-miqaat"}, when=r.when)
        for r in shifted_roundup(1)
    ]
    check_kabisa(per_miqaat)
    checks_ok("per-miqaat mail never halts")

    # Too few data points to be sure it is the whole month.
    check_kabisa(shifted_roundup(1, hijri_days=(5, 10)))
    checks_ok("two occurrences do not halt")


def checks_ok(_label: str) -> None:
    global checks
    checks += 1


# --- Planning ----------------------------------------------------------------


def test_ayyam_fanout(cfg, ids):
    """A three-day urus must become three dated events, not one."""
    resolutions = []
    for offset, when in enumerate(["2026-08-25", "2026-08-26", "2026-08-27"]):
        occ = occurrence(
            miqaat_id="urus-mohammed-burhanuddin",
            miqaat_text="Urus Mubarak ayyam",
            hijri_month=3,
            hijri_day=13 + offset,
            gregorian_date=when,
            start_time=f"18:{30 + offset * 5}",
        )
        # These days do not line up with 13mi Rabi ul Awwal; only the fan-out
        # matters here, so resolve without the cross-check getting in the way.
        resolutions.append(Resolved(occ=occ, mail=MAIL, when=date.fromisoformat(when)))

    actions = plan(resolutions, cfg)
    eq("ayyam yields three actions", len(actions), 3)
    eq("ayyam seq numbering", [a.seq for a in actions], [0, 1, 2])
    eq("ayyam uids are distinct", len({a.event_uid for a in actions}), 3)
    eq("ayyam dates in order", [str(a.when) for a in actions],
       ["2026-08-25", "2026-08-26", "2026-08-27"])
    # Day one must land on the event generate.py already emitted, or the sweep
    # would insert a duplicate alongside it.
    eq(
        "day one matches generate.py uid",
        actions[0].event_uid,
        generate_uid("nj-burhani", "urus-mohammed-burhanuddin", 1448, 0),
    )


def test_correction_wins(cfg, ids):
    early = resolve(occurrence(start_time="18:45"), {**MAIL, "date": date(2026, 7, 20)}, ids)
    late = resolve(
        occurrence(start_time="20:15"),
        {"date": date(2026, 7, 30), "kind": "correction", "subject": "Time change:"},
        ids,
    )
    actions = plan([early, late], cfg)
    eq("correction collapses to one event", len(actions), 1)
    eq("later mail wins", actions[0].start_time, "20:15")

    # Order of arrival in the list must not change the outcome.
    eq("order independent", plan([late, early], cfg)[0].start_time, "20:15")


def test_ambiguous_never_promotes(cfg, ids):
    flagged = resolve(occurrence(confidence="low"), MAIL, ids)
    actions = plan([flagged], cfg)
    eq("ambiguous becomes review", [a.verb for a in actions], ["review"])
    eq("review carries a reason", bool(actions[0].reason), True)


def test_timing(cfg):
    eq("per-entry start time", timing(cfg, "milad-un-nabi")[0], "18:45")
    eq("falls back to default", timing(cfg, "urus-fakhruddin-shaheed")[0], "19:00")
    eq("all-day duration", timing(cfg, "ashara-mubaraka")[1], 0)
    eq("unknown id uses defaults", timing(cfg, "not-in-config"), ("19:00", 150))


# --- Gmail transport ---------------------------------------------------------


class FakeResponse:
    def __init__(self, status: int):
        self.status = status
        self.reason = ""


def http_error(status: int) -> HttpError:
    return HttpError(FakeResponse(status), b"{}")


def test_backoff():
    attempts = [0]

    def flaky():
        attempts[0] += 1
        if attempts[0] < 3:
            raise http_error(503)
        return "ok"

    eq("retries through 503", with_backoff(flaky, "test"), "ok")
    eq("stopped once it worked", attempts[0], 3)

    # A bad credential must fail immediately rather than look like a hang.
    tries = [0]

    def denied():
        tries[0] += 1
        raise http_error(403)

    try:
        with_backoff(denied, "test")
        failures.append("  403: expected HttpError, none raised")
    except HttpError:
        pass
    eq("403 is not retried", tries[0], 1)

    raises(
        "exhausted retries say it is not an empty result",
        lambda: with_backoff(lambda: (_ for _ in ()).throw(http_error(500)), "gmail list"),
        "not an empty result",
    )


def test_body_extraction():
    multipart = {
        "mimeType": "multipart/alternative",
        "parts": [
            {"mimeType": "text/plain", "body": {"data": b64("Chehlum waaz, 6:45pm")}},
            {"mimeType": "text/html", "body": {"data": b64("<p>ignore me</p>")}},
        ],
    }
    eq("prefers text/plain", _body_text(multipart), "Chehlum waaz, 6:45pm")

    html = {
        "mimeType": "text/html",
        "body": {"data": b64("<style>p{color:red}</style><p>Waaz</p><br>6:45pm")},
    }
    stripped = _body_text(html)
    eq("html tags removed", "<" not in stripped, True)
    eq("html css removed", "color:red" not in stripped, True)
    eq("html text kept", "Waaz" in stripped and "6:45pm" in stripped, True)

    eq("no body at all", _body_text({"mimeType": "text/plain", "body": {}}), "")


class FakeGmail:
    """Minimal stand-in for the Gmail resource chain."""

    SUBJECTS = {
        "m1": ("Safar ul Muzaffar 1448H Miqaat Monthly Schedule", "1753600000000"),
        "m2": ("Teejia majlis for marhum", "1753700000000"),
        "m3": ("Time change: Chehlum waaz", "1753800000000"),
    }

    def __init__(self, matched: list[str], mailbox: list[str]):
        self.matched, self.mailbox = matched, mailbox

    def users(self):
        return self

    def messages(self):
        return self

    def list(self, userId, q, maxResults):
        hits = self.matched if "from:" in q else self.mailbox
        return _Executable({"messages": [{"id": i} for i in hits]})

    def get(self, userId, id, format):
        subject, stamp = self.SUBJECTS[id]
        return _Executable(
            {
                "internalDate": stamp,
                "payload": {
                    "mimeType": "text/plain",
                    "headers": [{"name": "Subject", "value": subject}],
                    "body": {"data": b64("body text")},
                },
            }
        )


class _Executable:
    def __init__(self, payload):
        self.payload = payload

    def execute(self):
        return self.payload


def test_fetch(cfg):
    since = date(2026, 7, 20)

    mails = fetch(FakeGmail(["m1", "m2", "m3"], ["anything"]), cfg, since)
    eq("ignore_subjects drops teejia", len(mails), 2)
    eq("kinds routed", [m["kind"] for m in mails], ["roundup", "correction"])
    eq("oldest first", mails[0]["date"] <= mails[1]["date"], True)

    # Genuinely quiet week: no announcements, but the mailbox is alive.
    eq("quiet week returns nothing", fetch(FakeGmail([], ["anything"]), cfg, since), [])

    # Nothing from anyone means the credential or mailbox is broken. Reporting
    # that as "no announcements" is how a calendar goes stale unnoticed.
    raises(
        "dead mailbox is not a quiet week",
        lambda: fetch(FakeGmail([], []), cfg, since),
        "no mail at all",
    )


# --- Runner ------------------------------------------------------------------


def self_test() -> None:
    sweep.time.sleep = lambda _seconds: None  # do not really wait out the backoff

    cfg = sweep.load(CONFIG)
    catalog = sweep.load(sweep.CATALOG)
    ids = {m["id"] for m in catalog["miqaats"]}

    test_classify(cfg)
    test_idempotency()
    test_resolve(ids)
    test_kabisa()
    test_ayyam_fanout(cfg, ids)
    test_correction_wins(cfg, ids)
    test_ambiguous_never_promotes(cfg, ids)
    test_timing(cfg)
    test_backoff()
    test_body_extraction()
    test_fetch(cfg)

    if failures:
        raise AssertionError(
            f"{len(failures)} of {checks} checks failed:\n" + "\n".join(failures)
        )
    print(f"OK: {checks} sweep checks passed.")
    print("NOTE: the Claude extraction call is not covered. Sweep a real week in")
    print("      dry run before trusting --apply.")


if __name__ == "__main__":
    try:
        self_test()
    except AssertionError as e:
        print(e, file=sys.stderr)
        sys.exit(1)
