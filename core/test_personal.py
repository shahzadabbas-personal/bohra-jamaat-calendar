"""
Self-tests for core/personal.py.

    python3 core/test_personal.py

Plain asserts, no test runner, same as test_dates.py.
"""

from __future__ import annotations

from datetime import date

from personal import occurrences, parse_hijri, render


def fails(text: str) -> bool:
    try:
        parse_hijri(text)
    except ValueError:
        return True
    return False


def test_parse() -> None:
    # Short names, full names, the "mi" suffix and any capitalisation.
    assert parse_hijri("23 Safar") == (2, 23)
    assert parse_hijri("23mi Safar ul Muzaffar") == (2, 23)
    assert parse_hijri("23 safar") == (2, 23)
    assert parse_hijri("13 Rabi ul Akhar") == (4, 13)
    assert parse_hijri("12 Rabi ul Awwal") == (3, 12)
    assert parse_hijri("1 Zilhaj") == (12, 1)
    assert parse_hijri("27 Rajab") == (7, 27)


def test_parse_rejects() -> None:
    assert fails("30 Safar"), "Safar always has 29 days"
    assert fails("31 Moharram")
    assert fails("0 Rajab")
    assert fails("5 Smarch")
    assert fails("Safar 23x")
    # Rabi and Jamadil each name two months, so the second word is required.
    assert fails("12 Rabi")


def test_occurrences() -> None:
    # One per Hijri year. Worked out by hand from the anchor, not the
    # converter: 1 Moharram 1448H is 15 Jun 2026, and 23 Safar is 30 + 22
    # days later.
    got = occurrences(2, 23, 1448, 1450)
    assert [m.year for m in got] == [1448, 1449, 1450]
    assert got[0].gregorian == date(2026, 8, 6)
    assert str(got[0]) == "23mi Safar ul Muzaffar 1448H"


def test_30_zilhaj() -> None:
    # Zilhaj has 30 days in a kabisa year and 29 otherwise. 1448H and 1450H are
    # kabisa, 1449H is not, so the 1449H date falls back to 29mi.
    got = occurrences(12, 30, 1448, 1450)
    assert [(m.year, m.day) for m in got] == [(1448, 30), (1449, 29), (1450, 30)]


def test_render() -> None:
    entries = [
        {"name": "Ammi's birthday", "hijri": "23 Safar"},
        {"name": "Wedding anniversary", "hijri": "30 Zilhaj"},
    ]
    ics = render(entries, 1448, 1450)
    lines = ics.split("\r\n")
    assert ics.count("BEGIN:VEVENT") == 6, "two entries, three years each"
    uids = [l for l in lines if l.startswith("UID:")]
    assert len(set(uids)) == len(uids), "UIDs must be unique"
    assert "SUMMARY:Ammi's birthday" in lines
    assert "DTSTART;VALUE=DATE:20260806" in lines
    assert "DESCRIPTION:23mi Safar ul Muzaffar 1448H" in lines
    # SEQUENCE keeps a re-import ahead of an event edited by hand in Google.
    assert sum(l.startswith("SEQUENCE:") for l in lines) == 6


def test_uid_follows_name() -> None:
    # Fixing a wrong date must move the event on re-import, not duplicate it,
    # so the UID depends on the name and year but not the date.
    uid = lambda ics: [l for l in ics.split("\r\n") if l.startswith("UID:")]
    before = render([{"name": "Ammi's birthday", "hijri": "23 Safar"}], 1448, 1448)
    after = render([{"name": "Ammi's birthday", "hijri": "24 Safar"}], 1448, 1448)
    assert uid(before) == uid(after)


def test_duplicate_names() -> None:
    # Two entries with one name would share UIDs and overwrite each other.
    entries = [
        {"name": "Birthday", "hijri": "23 Safar"},
        {"name": "Birthday", "hijri": "1 Rajab"},
    ]
    try:
        render(entries, 1448, 1448)
    except ValueError:
        return
    raise AssertionError("duplicate names must be refused")


if __name__ == "__main__":
    test_parse()
    test_parse_rejects()
    test_occurrences()
    test_30_zilhaj()
    test_render()
    test_uid_follows_name()
    test_duplicate_names()
    print("OK: personal tests pass.")
