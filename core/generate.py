"""
Generate an ICS file of miqaat events for one jamaat.

    python3 core/generate.py jamaats/nj-burhani --years 5 --out nj.ics

Google Calendar has no Hijri recurrence rule, so every occurrence is emitted as
its own VEVENT. UIDs are deterministic (jamaat + miqaat + hijri year), which
makes re-import idempotent: regenerating and re-importing updates events in
place rather than duplicating them.
"""

from __future__ import annotations

import argparse
import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from misri import MONTHS, MisriDate, from_gregorian, month_length, to_gregorian

CATALOG = Path(__file__).parent / "catalog.yaml"

# Every event on a shared calendar reads as real, so the honest signal about an
# unverified timing belongs in the description rather than in STATUS. A member
# seeing "tentative" reads it as "might not happen" or "I have not replied yet" --
# neither of which is what it meant. The sweep removes these lines once an
# announcement confirms the event.
TIMING_CAVEAT = "Timing not yet confirmed against the jamaat announcement."
DATE_CAVEAT = (
    "Date varies by year and is projected from prior years. "
    "Verify against the printed taqweem."
)


def load(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def esc(text: str) -> str:
    """Escape per RFC 5545."""
    return (
        str(text)
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def fold(line: str) -> str:
    """RFC 5545 caps content lines at 75 octets."""
    out, first = [], True
    while len(line.encode()) > 75:
        cut = 75 if first else 74
        while len(line[:cut].encode()) > (75 if first else 74):
            cut -= 1
        out.append(line[:cut] if first else " " + line[:cut])
        line, first = line[cut:], False
    out.append(line if first else " " + line)
    return "\r\n".join(out)


def uid(jamaat_id: str, miqaat_id: str, hy: int, seq: int = 0) -> str:
    raw = f"{jamaat_id}:{miqaat_id}:{hy}:{seq}"
    digest = hashlib.sha1(raw.encode()).hexdigest()[:16]
    return f"{digest}@bohra-miqaat-calendar"


WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}


def days_in(spec: dict, hy: int, month: int) -> list[int]:
    """Which Hijri days of this month the entry falls on.

    Most entries are a single fixed day. `day_range` spans several. `weekday`
    anchors to a weekday instead -- Aakhri Jumoa is the last Friday of
    Shehrullah, which lands on a different Hijri day every year.
    """
    if spec.get("weekday"):
        target = WEEKDAYS[spec["weekday"].lower()]
        matches = [
            d for d in range(1, month_length(hy, month) + 1)
            if to_gregorian(hy, month, d).weekday() == target
        ]
        which = spec.get("which", "last")
        return [matches[-1]] if which == "last" else [matches[0]]
    if spec.get("day_range"):
        first, last = spec["day_range"]
        return list(range(first, last + 1))
    return [spec["day"]]


def expand(cfg: dict, catalog: dict, start_year: int, years: int) -> list[dict]:
    by_id = {m["id"]: m for m in catalog["miqaats"]}
    defaults = cfg.get("defaults", {})
    jid = cfg["jamaat"]["id"]
    events = []

    for entry in cfg.get("observes", []):
        mid = entry["id"]
        if mid not in by_id:
            raise KeyError(f"'{mid}' is not in catalog.yaml")
        spec = by_id[mid]

        def opt(key, fallback=None):
            return entry.get(key, defaults.get(key, fallback))

        offset = opt("observed_offset", 0)
        start_time = opt("start_time", "19:00")
        duration = opt("duration_minutes", 150)
        location = opt("location", "")
        confirmed = entry.get("confirmed", True)
        note = entry.get("note") or spec.get("note") or ""

        monthly = spec.get("recurrence") == "monthly"
        # A monthly majlis can still skip a month: Shehrullah has its own
        # nightly programme, so there is no 16mi raat darees during it.
        skip = set(spec.get("skip_months", []))

        for hy in range(start_year, start_year + years):
            months = range(1, 13) if monthly else [spec["month"]]
            for month in months:
                if month in skip:
                    continue
                for day in days_in(spec, hy, month):
                    canonical = MisriDate(hy, month, day)
                    observed = canonical.gregorian + timedelta(days=offset)
                    span = spec.get("duration_days", 1)

                    # The UID seq has to stay stable and unique per occurrence:
                    # by Hijri month for a monthly majlis, by Hijri day across a
                    # range, 0 otherwise. sweep.py mirrors this exactly.
                    seq = month if monthly else (day if spec.get("day_range") else 0)
                    name = spec["name"]
                    if spec.get("day_range"):
                        name = f"{name} ({day}mi)"

                    events.append(
                        {
                            "uid": uid(jid, mid, hy, seq),
                            "summary": name,
                            "date": observed,
                            "start_time": start_time,
                            "duration": duration,
                            "span_days": span,
                            "location": location,
                            "canonical": canonical,
                            "confirmed": confirmed,
                            "note": note,
                            "source": "generated",
                        }
                    )
    return sorted(events, key=lambda e: e["date"])


def render(events: list[dict], cfg: dict) -> str:
    tz = cfg["jamaat"]["timezone"]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//bohra-miqaat-calendar//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{esc(cfg['jamaat']['name'])} Miqaat",
        f"X-WR-TIMEZONE:{tz}",
    ]

    for e in events:
        c = e["canonical"]
        desc_parts = [f"{c.day}mi {c.month_name} {c.year}H"]
        if e["note"]:
            desc_parts.append(e["note"])
        if not e["confirmed"]:
            desc_parts.append(DATE_CAVEAT)
        if e["source"] == "generated":
            desc_parts.append(TIMING_CAVEAT)
        desc_parts.append(f"source: {e['source']}")

        lines += ["BEGIN:VEVENT", f"UID:{e['uid']}", f"DTSTAMP:{stamp}"]

        if e["duration"] == 0:
            d = e["date"]
            end = d + timedelta(days=e["span_days"])
            lines += [
                f"DTSTART;VALUE=DATE:{d:%Y%m%d}",
                f"DTEND;VALUE=DATE:{end:%Y%m%d}",
            ]
        else:
            hh, mm = (int(x) for x in e["start_time"].split(":"))
            begin = datetime.combine(e["date"], datetime.min.time()).replace(
                hour=hh, minute=mm
            )
            finish = begin + timedelta(minutes=e["duration"])
            lines += [
                f"DTSTART;TZID={tz}:{begin:%Y%m%dT%H%M%S}",
                f"DTEND;TZID={tz}:{finish:%Y%m%dT%H%M%S}",
            ]

        lines += [
            fold(f"SUMMARY:{esc(e['summary'])}"),
            fold(f"DESCRIPTION:{esc(chr(10).join(desc_parts))}"),
        ]
        if e["location"]:
            lines.append(fold(f"LOCATION:{esc(e['location'])}"))
        lines += [
            # Always CONFIRMED: this is whether the program happens, not whether
            # a member is attending and not how sure we are of the time.
            "STATUS:CONFIRMED",
            "TRANSP:TRANSPARENT",
            "END:VEVENT",
        ]

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("jamaat_dir", type=Path)
    p.add_argument("--years", type=int, default=5)
    p.add_argument("--start-year", type=int, default=None, help="Hijri year")
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args()

    cfg = load(args.jamaat_dir / "config.yaml")
    catalog = load(CATALOG)

    start = args.start_year or from_gregorian(datetime.now().date())[0]
    events = expand(cfg, catalog, start, args.years)

    out = args.out or (args.jamaat_dir / f"{cfg['jamaat']['id']}.ics")
    # newline="" is load-bearing on Windows. RFC 5545 requires CRLF and render()
    # emits it, but text mode would translate the \n half again and write \r\r\n,
    # which Google Calendar rejects with "unable to process your iCal file".
    out.write_text(render(events, cfg), encoding="utf-8", newline="")

    # Check what actually landed on disk, not what we meant to write. A calendar
    # that fails to import reports "0 of 0 events" and nothing here would have
    # noticed: this script happily printed a success line while producing a file
    # Google could not read.
    written = out.read_bytes()
    if b"\r\r\n" in written or written.count(b"\n") != written.count(b"\r\n"):
        raise SystemExit(f"{out} has malformed line endings; RFC 5545 requires CRLF")

    unverified = sum(1 for e in events if e["source"] == "generated")
    print(f"{len(events)} events, {start}H-{start + args.years - 1}H -> {out}")
    if unverified:
        print(f"{unverified} carry generated timings (run sweep.py to confirm them)")


if __name__ == "__main__":
    main()
