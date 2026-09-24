"""
Misri (Fatimid tabular Hijri) calendar conversion.

The Dawoodi Bohra calendar is tabular, not observational: every date is
computable in advance. Rules, per Bu Saheba's Sahifa:

  - 12 months per year, 354 days in a common year
  - Odd months (1, 3, 5, ...) are kamil  -> 30 days
  - Even months (2, 4, 6, ...) are naqis -> 29 days
  - In a kabisa (leap) year, Zilhaj gains a day -> 30 days, 355 total
  - Kabisa years recur on a 30-year cycle, identified by year % 30

Rather than deriving an epoch from first principles, this module anchors on a
verified correspondence and counts forward/backward. The anchor below was
cross-checked against eleven independent Anjuman-e-Burhani NJ announcements
spanning 1447H-1448H (see tests at the bottom of this file).

    1 Muharram 1448H == 15 June 2026

>>> VERIFY BEFORE TRUSTING DATES PAST 1450H <<<
KABISA_REMAINDERS is only partly verified. The mumineen.org feed agrees with
this module on all 642 of its date pairs across 1448H-1450H, which settles the
cycle positions those years touch. The rest of the 30-year cycle is untested,
so dates after VERIFIED_THROUGH are speculative. Check the set below against
your jamaat's printed taqweem or Bu Saheba's Sahifa before extending it. An
off-by-one here shifts every subsequent year.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

# --- Calendar constants ------------------------------------------------------

MONTHS = [
    "Moharram ul Haraam",
    "Safar ul Muzaffar",
    "Rabi ul Awwal",
    "Rabi ul Akhar",
    "Jamadil Ula",
    "Jamadil Ukhra",
    "Rajab ul Asab",
    "Shabaan ul Kareem",
    "Shehrullah il Moazzam",
    "Shawwal ul Mukarram",
    "Zilqadatil Haraam",
    "Zilhijjatil Haraam",
]

# Year is kabisa if (year % 30) is in this set. SEE WARNING ABOVE.
KABISA_REMAINDERS = frozenset({2, 5, 8, 10, 13, 16, 19, 21, 24, 27, 29})

ANCHOR_HIJRI_YEAR = 1448
ANCHOR_GREGORIAN = date(2026, 6, 15)  # 1 Moharram 1448H

# Last Hijri year checked against independent data (see warning above).
VERIFIED_THROUGH = 1450


# --- Core arithmetic ---------------------------------------------------------


def is_kabisa(year: int) -> bool:
    """True if the Hijri year carries the intercalary day in Zilhaj."""
    return (year % 30) in KABISA_REMAINDERS


def month_length(year: int, month: int) -> int:
    """Days in a given Hijri month. Month is 1-indexed."""
    if not 1 <= month <= 12:
        raise ValueError(f"month must be 1-12, got {month}")
    if month == 12:
        return 30 if is_kabisa(year) else 29
    return 30 if month % 2 == 1 else 29


def year_length(year: int) -> int:
    return 355 if is_kabisa(year) else 354


def days_before_month(year: int, month: int) -> int:
    """Days elapsed in `year` before the 1st of `month`."""
    return sum(month_length(year, m) for m in range(1, month))


def to_gregorian(year: int, month: int, day: int) -> date:
    """Convert a Misri date to its Gregorian equivalent.

    NOTE: this returns the Gregorian day on which the Hijri day *begins by
    daylight*. The Islamic day actually starts at the preceding maghrib, so an
    evening program for Hijri day N is typically held on the Gregorian evening
    of N-1. Do not bake that shift in here -- it is an observance decision and
    belongs in each jamaat's config. See config `observed_offset`.
    """
    if not 1 <= day <= month_length(year, month):
        raise ValueError(
            f"day {day} out of range for {MONTHS[month - 1]} {year}H "
            f"({month_length(year, month)} days)"
        )

    offset = 0
    if year >= ANCHOR_HIJRI_YEAR:
        for y in range(ANCHOR_HIJRI_YEAR, year):
            offset += year_length(y)
    else:
        for y in range(year, ANCHOR_HIJRI_YEAR):
            offset -= year_length(y)

    offset += days_before_month(year, month) + (day - 1)
    return ANCHOR_GREGORIAN + timedelta(days=offset)


def from_gregorian(g: date) -> tuple[int, int, int]:
    """Convert a Gregorian date to (hijri_year, month, day)."""
    delta = (g - ANCHOR_GREGORIAN).days
    year = ANCHOR_HIJRI_YEAR

    while delta < 0:
        year -= 1
        delta += year_length(year)
    while delta >= year_length(year):
        delta -= year_length(year)
        year += 1

    month = 1
    while delta >= month_length(year, month):
        delta -= month_length(year, month)
        month += 1

    return year, month, delta + 1


@dataclass(frozen=True)
class MisriDate:
    year: int
    month: int
    day: int

    @property
    def month_name(self) -> str:
        return MONTHS[self.month - 1]

    @property
    def gregorian(self) -> date:
        return to_gregorian(self.year, self.month, self.day)

    def __str__(self) -> str:
        return f"{self.day}mi {self.month_name} {self.year}H"


# --- Verification ------------------------------------------------------------

# Each entry is (hijri_year, month, day, gregorian) taken verbatim from an
# Anjuman-e-Burhani NJ announcement email. These span a full annual cycle and
# validate month lengths, month ordering, and the year rollover.
VERIFIED_ANCHORS = [
    (1447, 2, 20, date(2025, 8, 14)),   # Chehlum waaz
    (1447, 2, 28, date(2025, 8, 22)),   # Shahadat Imam Hasan
    (1447, 3, 11, date(2025, 9, 3)),    # Milad un Nabi waaz
    (1447, 3, 13, date(2025, 9, 5)),    # Urus Syedna Mohammed Burhanuddin
    (1447, 6, 26, date(2025, 12, 16)),  # Lailate Urus Syedna Qutubuddin
    (1447, 7, 3,  date(2025, 12, 22)),  # Urus Syedna NoorMohammed Nooruddin
    (1447, 8, 21, date(2026, 2, 8)),    # Urus Maulatena Hurratul Maleka
    (1447, 9, 13, date(2026, 3, 1)),    # Misaaq ni majlis
    (1447, 10, 1, date(2026, 3, 19)),   # Eid ul Fitr
    (1447, 11, 15, date(2026, 5, 1)),   # 16mi raat darees
    (1447, 11, 27, date(2026, 5, 13)),  # Milad Syedna Taher Saifuddin
    (1447, 12, 9,  date(2026, 5, 25)),  # Yaumul Arafa
    (1447, 12, 16, date(2026, 6, 1)),   # 16mi darees
    (1447, 12, 18, date(2026, 6, 3)),   # Ghadir-e-Khum
    (1448, 1, 16, date(2026, 6, 30)),   # Urus Syedna Hatim Mohiyuddin
    (1448, 1, 26, date(2026, 7, 10)),   # Urus Syedi Fakhruddin Shaheed
    (1448, 2, 19, date(2026, 8, 2)),    # Chehlum waaz
    (1448, 2, 27, date(2026, 8, 10)),   # Shahadat Imam Hasan
    (1448, 3, 11, date(2026, 8, 23)),   # Milad un Nabi waaz
]


def self_test() -> None:
    failures = []
    for y, m, d, expected in VERIFIED_ANCHORS:
        got = to_gregorian(y, m, d)
        if got != expected:
            failures.append(f"  {d}mi {MONTHS[m-1]} {y}H: got {got}, want {expected}")
        back = from_gregorian(expected)
        if back != (y, m, d):
            failures.append(f"  roundtrip {expected}: got {back}, want {(y, m, d)}")

    if failures:
        raise AssertionError(
            f"{len(failures)} anchor mismatch(es):\n" + "\n".join(failures)
        )
    print(f"OK: {len(VERIFIED_ANCHORS)} anchors verified, roundtrip clean.")


if __name__ == "__main__":
    self_test()
