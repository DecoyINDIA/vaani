"""Table-driven test suite for relative date and colloquial time resolution (W1-13)."""

from __future__ import annotations

from datetime import date

import pytest
from app.booking.relative_date import parse_colloquial_time, resolve

# Thursday, 12 November 2026
BASE_TODAY = date(2026, 11, 12)


@pytest.mark.parametrize(
    ("phrase", "expected"),
    [
        ("next month", date(2026, 11, 12)),
        ("I am satisfied", date(2026, 11, 12)),
        ("aajkal busy hoon", date(2026, 11, 12)),
        ("kal", date(2026, 11, 13)),
        ("kal subah", date(2026, 11, 13)),
        ("parso", date(2026, 11, 14)),
        ("day after tomorrow", date(2026, 11, 14)),
        ("monday", date(2026, 11, 16)),
        ("agle somvar", date(2026, 11, 16)),
        ("thursday", date(2026, 11, 19)),
        ("sat ko", date(2026, 11, 14)),
        ("15 november", date(2026, 11, 15)),
        ("nov 20th", date(2026, 11, 20)),
        ("5 jan", date(2027, 1, 5)),
        ("20 tarikh", date(2026, 11, 20)),
        ("5 tarikh", date(2026, 12, 5)),
        ("२० तारीख", date(2026, 11, 20)),
        ("20/11", date(2026, 11, 20)),
        ("aaj", date(2026, 11, 12)),
        ("कल", date(2026, 11, 13)),
        ("କାଲି", date(2026, 11, 13)),
    ],
)
def test_relative_date_resolution_table(phrase: str, expected: date) -> None:
    assert resolve(phrase, today=BASE_TODAY, lang="en") == expected


@pytest.mark.parametrize(
    ("phrase", "expected"),
    [
        ("subah 10 baje", "10:00"),
        ("shaam 4 baje", "16:00"),
        ("4 baje", "16:00"),
        ("10 baje", "10:00"),
        ("dopahar 12", "12:00"),
        ("7:30 pm", "19:30"),
        ("namaste", None),
    ],
)
def test_parse_colloquial_time_table(phrase: str, expected: str | None) -> None:
    assert parse_colloquial_time(phrase) == expected
