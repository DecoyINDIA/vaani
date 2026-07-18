"""Relative-date + colloquial-time resolver (TRD §4.3) — the India rule.

"kal" (yesterday/tomorrow), "parso", "agle [weekday]" are ambiguous -> resolver
picks the FUTURE interpretation. Colloquial 12-hour forms ("shaam ko 4 baje",
"subah 10", "dopahar") and Indic numerals are parsed; times render back as
"4:00 PM (shaam)". The agent MUST echo weekday + date for confirmation before any
booking tool call (enforced by the booking tool's date_confirmed contract).
"""

from __future__ import annotations

from datetime import date


def resolve(phrase: str, *, today: date, lang: str) -> date:
    raise NotImplementedError("relative-date resolver — 06-engineering-plan task 4.3")
