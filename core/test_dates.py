"""
Self-tests for core/dates.py.

    python3 core/test_dates.py

Plain asserts, no test runner, same as test_sweep.py.
"""

from __future__ import annotations

from datetime import timedelta
from itertools import pairwise

from dates import days, render
from misri import VERIFIED_ANCHORS, year_length

CFG = {"jamaat": {"id": "test", "name": "Test Jamaat", "timezone": "UTC"}}


def test_every_day_once() -> None:
    dates = days(1448, 1450)
    assert len(dates) == sum(year_length(y) for y in (1448, 1449, 1450))
    # One date per Gregorian day, no gaps and no repeats, across month and
    # year boundaries.
    for a, b in pairwise(dates):
        assert b.gregorian - a.gregorian == timedelta(days=1), (a, b)
    assert str(dates[0]) == "1mi Moharram ul Haraam 1448H"
    assert dates[0].gregorian.isoformat() == "2026-06-15"


def test_anchors() -> None:
    by_gregorian = {m.gregorian: m for m in days(1447, 1448)}
    for y, m, d, g in VERIFIED_ANCHORS:
        got = by_gregorian[g]
        assert (got.year, got.month, got.day) == (y, m, d), (g, got)


def test_render() -> None:
    dates = days(1448, 1448)
    ics = render(dates, CFG)
    assert ics.count("BEGIN:VEVENT") == len(dates)
    uids = [l for l in ics.split("\r\n") if l.startswith("UID:")]
    assert len(set(uids)) == len(uids), "UIDs must be unique"
    assert "DTSTART;VALUE=DATE:20260924\r\n" in ics
    assert "SUMMARY:13mi Rabi ul Akhar 1448H\r\n" in ics
    assert "X-WR-CALNAME:Test Jamaat Bohra Dates" in ics


if __name__ == "__main__":
    test_every_day_once()
    test_anchors()
    test_render()
    print("OK: dates tests pass.")
