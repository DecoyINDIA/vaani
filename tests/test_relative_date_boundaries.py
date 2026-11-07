from __future__ import annotations

from datetime import date

from app.booking.relative_date import resolve


def test_day_after_tomorrow_precedes_tomorrow_match() -> None:
    assert resolve("day after tomorrow", today=date(2026, 11, 7), lang="en") == date(2026, 11, 9)


def test_short_date_rolls_across_year_and_normalizes_indic_digits() -> None:
    today = date(2026, 12, 31)
    assert resolve("०१/०१", today=today, lang="hi") == date(2027, 1, 1)
    assert resolve("୦୧/୦୧", today=today, lang="or") == date(2027, 1, 1)
