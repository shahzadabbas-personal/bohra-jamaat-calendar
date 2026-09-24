"""
Generate an ICS file with the Misri date on every day, for one jamaat.

    python3 core/dates.py jamaats/nj-burhani

This is a separate calendar from the miqaat one on purpose. The sweep writes
only to the miqaat calendar, and `sweep.py --prune` deletes anything in that
calendar it does not recognise, so daily date events there would be pruned.
Members add both calendars to see miqaats and dates together, or the miqaat one
alone.

Each label is the Hijri date during daylight. After maghrib it is already the
next Hijri day, which the event description says.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

from generate import esc, fold, load, uid, write_ics
from misri import VERIFIED_THROUGH, MisriDate, from_gregorian, month_length

DAYLIGHT_NOTE = "Hijri date during daylight. From maghrib it is the next day."


def days(start_year: int, end_year: int) -> list[MisriDate]:
    """Every Misri date from 1 Moharram of start_year to the end of end_year."""
    return [
        MisriDate(hy, month, day)
        for hy in range(start_year, end_year + 1)
        for month in range(1, 13)
        for day in range(1, month_length(hy, month) + 1)
    ]


def render(dates: list[MisriDate], cfg: dict) -> str:
    jid = cfg["jamaat"]["id"]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//bohra-miqaat-calendar//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{esc(cfg['jamaat']['name'])} Bohra Dates",
        f"X-WR-TIMEZONE:{cfg['jamaat']['timezone']}",
    ]
    for m in dates:
        g = m.gregorian
        lines += [
            "BEGIN:VEVENT",
            # The seq packs month and day so each date gets its own UID.
            f"UID:{uid(jid, 'misri-date', m.year, m.month * 100 + m.day)}",
            f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:{g:%Y%m%d}",
            f"DTEND;VALUE=DATE:{g + timedelta(days=1):%Y%m%d}",
            fold(f"SUMMARY:{esc(m)}"),
            fold(f"DESCRIPTION:{esc(DAYLIGHT_NOTE)}"),
            "TRANSP:TRANSPARENT",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("jamaat_dir", type=Path)
    p.add_argument("--start-year", type=int, default=None, help="Hijri year")
    p.add_argument("--through", type=int, default=VERIFIED_THROUGH, help="Hijri year")
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args()

    # A wrong date on every day of a shared calendar is worse than no date, so
    # the unverified part of the kabisa cycle is refused rather than warned about.
    if args.through > VERIFIED_THROUGH:
        raise SystemExit(
            f"Dates after {VERIFIED_THROUGH}H are unverified; see core/misri.py"
        )

    cfg = load(args.jamaat_dir / "config.yaml")
    start = args.start_year or from_gregorian(datetime.now().date())[0]
    dates = days(start, args.through)

    out = args.out or (args.jamaat_dir / f"{cfg['jamaat']['id']}-dates.ics")
    write_ics(out, render(dates, cfg))
    print(
        f"{len(dates)} days, {dates[0]} to {dates[-1]} "
        f"({out.stat().st_size // 1024} KB) -> {out}"
    )


if __name__ == "__main__":
    main()
