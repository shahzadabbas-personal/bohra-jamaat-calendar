"""
Generate a private ICS of your own Hijri dates: birthdays, anniversaries, urus.

    python3 core/personal.py personal/events.yaml

Copy personal/events.template.yaml to personal/events.yaml and fill it in. Only
the template is committed; your own file and the ICS stay on your machine.

Import the result into a private Google Calendar of your own, not a shared one.
Re-importing updates events in place, because each UID comes from the entry's
name and year. Renaming an entry therefore leaves the old event behind, and
deleting an entry never removes its event: delete those by hand in the calendar.

Dates are entered as Hijri day and month, so nothing here converts a past year.
The converter only places them in 1448H onwards, the verified range.
"""

from __future__ import annotations

import argparse
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from generate import esc, fold, load, uid, write_ics
from misri import MONTHS, VERIFIED_THROUGH, MisriDate, from_gregorian, month_length

FILLER = {"ul", "il", "al", "el"}

# Spellings people write besides the ones in MONTHS.
EXTRA_NAMES = {
    "muharram": 1,
    "rabi aakhar": 4,
    "rabi akhir": 4,
    "jamadal ula": 5,
    "jamadal ukhra": 6,
    "shaban": 8,
    "ramazan": 9,
    "ramadan": 9,
    "zilqad": 11,
    "zilhaj": 12,
    "zilhajj": 12,
}


def normalise(text: str) -> str:
    words = re.sub(r"[-']", " ", text.lower()).split()
    return " ".join(w for w in words if w not in FILLER)


def month_names() -> dict[str, int]:
    names = dict(EXTRA_NAMES)
    for n, full in enumerate(MONTHS, start=1):
        words = normalise(full).split()
        names[" ".join(words)] = n
        # Rabi and Jamadil each name two months, so they need their second word.
        short = words[:2] if words[0] in ("rabi", "jamadil") else words[:1]
        names[" ".join(short)] = n
    return names


NAMES = month_names()


def parse_hijri(text: str) -> tuple[int, int]:
    """'23 Safar' or '23mi Safar ul Muzaffar' -> (month, day)."""
    match = re.fullmatch(r"\s*(\d{1,2})(?:mi)?\s+(.+?)\s*", text)
    if not match:
        raise ValueError(f"{text!r}: write it as day then month, like '23 Safar'")
    day, month_text = int(match[1]), match[2]
    month = NAMES.get(normalise(month_text))
    if month is None:
        raise ValueError(f"{text!r}: unknown month {month_text!r}")
    # 1448H is kabisa, so this is the longest each month ever runs.
    longest = month_length(1448, month)
    if not 1 <= day <= longest:
        raise ValueError(f"{text!r}: {MONTHS[month - 1]} has {longest} days at most")
    return month, day


def occurrences(month: int, day: int, start_year: int, end_year: int) -> list[MisriDate]:
    # Only 30mi Zilhaj can overflow, in a common year, and it falls back to 29mi.
    return [
        MisriDate(hy, month, min(day, month_length(hy, month)))
        for hy in range(start_year, end_year + 1)
    ]


def render(entries: list[dict], start_year: int, end_year: int) -> str:
    names = [e.get("name") for e in entries]
    for n, entry in enumerate(entries, start=1):
        if not entry.get("name") or not entry.get("hijri"):
            raise ValueError(f"entry {n} needs both a name and a hijri date")
    duplicates = {n for n in names if names.count(n) > 1}
    if duplicates:
        raise ValueError(f"each name must be unique: {', '.join(sorted(duplicates))}")

    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    # Tested on 24 Sep 2026: Google moved a re-imported event by UID alone, with
    # or without SEQUENCE. It is kept for an event someone edited by hand, which
    # raises Google's own count; minutes since the epoch always count higher,
    # without keeping any state between runs.
    sequence = int(now.timestamp()) // 60
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//bohra-miqaat-calendar//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:My Bohra dates",
    ]
    for entry in entries:
        month, day = parse_hijri(str(entry["hijri"]))
        for m in occurrences(month, day, start_year, end_year):
            g = m.gregorian
            lines += [
                "BEGIN:VEVENT",
                f"UID:{uid('personal', entry['name'], m.year)}",
                f"DTSTAMP:{stamp}",
                f"SEQUENCE:{sequence}",
                f"DTSTART;VALUE=DATE:{g:%Y%m%d}",
                f"DTEND;VALUE=DATE:{g + timedelta(days=1):%Y%m%d}",
                fold(f"SUMMARY:{esc(entry['name'])}"),
                fold(f"DESCRIPTION:{esc(m)}"),
                "TRANSP:TRANSPARENT",
                "END:VEVENT",
            ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("events_file", type=Path)
    p.add_argument("--start-year", type=int, default=None, help="Hijri year")
    p.add_argument("--through", type=int, default=VERIFIED_THROUGH, help="Hijri year")
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args()

    if args.through > VERIFIED_THROUGH:
        raise SystemExit(
            f"Dates after {VERIFIED_THROUGH}H are unverified; see core/misri.py"
        )

    entries = (load(args.events_file) or {}).get("events") or []
    if not entries:
        raise SystemExit(f"No events in {args.events_file}")
    start = args.start_year or from_gregorian(datetime.now().date())[0]
    if start > args.through:
        raise SystemExit(f"Start year {start}H is after {args.through}H; nothing to write")
    try:
        text = render(entries, start, args.through)
    except ValueError as e:
        raise SystemExit(str(e))

    out = args.out or args.events_file.with_name("personal.ics")
    write_ics(out, text)
    print(f"{len(entries)} entries, {start}H to {args.through}H -> {out}")


if __name__ == "__main__":
    main()
