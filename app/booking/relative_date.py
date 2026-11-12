"""Relative-date + colloquial-time resolver (TRD §4.3) — the India rule.

"kal" (yesterday/tomorrow), "parso", "agle [weekday]" are ambiguous -> resolver
picks the FUTURE interpretation. Colloquial 12-hour forms ("shaam ko 4 baje",
"subah 10", "dopahar") and Indic numerals are parsed; times render back as
"4:00 PM (shaam)". The agent MUST echo weekday + date for confirmation before any
booking tool call (enforced by the booking tool's date_confirmed contract).
"""

from __future__ import annotations

import re
from datetime import date, timedelta


def normalize_numerals(text: str) -> str:
    """Map Devanagari and Odia numerals to standard ASCII digits."""
    devanagari = "०१२३४५६७८९"
    odia = "୦୧୨୩୪୫୬୭୮୯"
    for i in range(10):
        text = text.replace(devanagari[i], str(i))
        text = text.replace(odia[i], str(i))
    return text


def _has(phrase: str, keyword: str) -> bool:
    if keyword.isascii():
        return re.search(rf"(?<![a-z]){re.escape(keyword)}(?![a-z])", phrase) is not None
    return keyword in phrase  # Devanagari / Odia: substring is correct


MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


def resolve(phrase: str, *, today: date, lang: str) -> date:
    """Resolve a relative date phrase into an absolute date (always future/today)."""
    phrase = normalize_numerals(phrase).lower().strip()

    # 1. Explicit today check
    today_keywords = ["today", "aaj", "aj", "आज", "ଆଜି"]
    if any(_has(phrase, k) for k in today_keywords):
        return today

    # 2. Match longer phrase first: "day after tomorrow" contains "tomorrow"
    parso_keywords = [
        "day after tomorrow",
        "parso",
        "parshon",
        "paradina",
        "ପରଦିନ",
        "परसों",
    ]
    if any(_has(phrase, k) for k in parso_keywords):
        return today + timedelta(days=2)

    tomorrow_keywords = ["kal", "tomorrow", "kali", "କାଲି", "कल", "kal subah", "kal shaam"]
    if any(_has(phrase, k) for k in tomorrow_keywords):
        return today + timedelta(days=1)

    # 3. Weekdays
    weekdays_map = {
        0: [
            "somvar", "somvara", "somwar", "somwara", "somabara",
            "monday", "mon", "ସୋମବାର", "सोमवार",
        ],
        1: [
            "mangalvar", "mangalvara", "mangalwar", "mangalwara", "mangalabara",
            "tuesday", "tue", "ମଙ୍ଗଳବାର", "मंगलवार",
        ],
        2: [
            "budhvar", "budhvara", "budhwar", "budhwara", "budhabara",
            "wednesday", "wed", "ବୁଧବାର", "बुधवार",
        ],
        3: [
            "guruvar", "guruvara", "guruwar", "guruwara", "gurubara",
            "veervar", "veerwar", "thursday", "thu", "ଗୁରୁବାର", "गुरुवार",
        ],
        4: [
            "shukravar", "shukravara", "shukrawar", "shukrawara", "sukrabara",
            "friday", "fri", "ଶୁକ୍ରବାର", "शुक्रवार",
        ],
        5: [
            "shanivar", "shanivara", "shaniwar", "shaniwara", "sanibara",
            "saturday", "sat", "ଶନିବାର", "शनिवार",
        ],
        6: [
            "ravivar", "ravivara", "raviwar", "raviwara", "rabibara",
            "itvar", "itwar", "sunday", "sun", "ରବିବାର", "रविवार",
        ],
    }

    target_weekday = None
    for w_idx, keywords in weekdays_map.items():
        if any(_has(phrase, k) for k in keywords):
            target_weekday = w_idx
            break

    if target_weekday is not None:
        current_weekday = today.weekday()
        days_ahead = (target_weekday - current_weekday) % 7

        next_keywords = ["next", "agle", "asanta", "ଆସନ୍ତା", "अगले"]
        is_next = any(_has(phrase, k) for k in next_keywords)

        if days_ahead == 0:
            days_ahead = 7
        elif is_next:
            pass

        return today + timedelta(days=days_ahead)

    # 4. Month names: e.g. "15 november", "nov 20th", "5 jan"
    month_pattern = (
        r"(?:january|jan|february|feb|march|mar|april|apr|may|june|jun|july|jul|"
        r"august|aug|september|sept|sep|october|oct|november|nov|december|dec)"
    )

    m_day_month = re.search(
        rf"(?<![a-z\d])(\d{{1,2}})(?:st|nd|rd|th)?\s+({month_pattern})(?![a-z])",
        phrase,
    )
    if m_day_month:
        day_str, month_str = m_day_month.groups()
        m_num = MONTHS.get(month_str)
        if m_num:
            try:
                cand = date(today.year, m_num, int(day_str))
                return cand if cand >= today else date(today.year + 1, m_num, int(day_str))
            except ValueError:
                pass

    m_month_day = re.search(
        rf"(?<![a-z])({month_pattern})\s+(\d{{1,2}})(?:st|nd|rd|th)?(?![a-z\d])",
        phrase,
    )
    if m_month_day:
        month_str, day_str = m_month_day.groups()
        m_num = MONTHS.get(month_str)
        if m_num:
            try:
                cand = date(today.year, m_num, int(day_str))
                return cand if cand >= today else date(today.year + 1, m_num, int(day_str))
            except ValueError:
                pass

    # 5. Tarikh parsing: e.g. "20 tarikh", "5 tarikh", "२० तारीख"
    m_tarikh = re.search(
        r"(?<!\d)(\d{1,2})\s*(?:tarikh|tareekh|tarik|तारीख|ତାରିଖ)", phrase
    )
    if m_tarikh:
        day_num = int(m_tarikh.group(1))
        try:
            cand = date(today.year, today.month, day_num)
            if cand >= today:
                return cand
            if today.month == 12:
                return date(today.year + 1, 1, day_num)
            return date(today.year, today.month + 1, day_num)
        except ValueError:
            pass

    # 6. Try absolute date parsing (e.g. DD/MM/YYYY or DD-MM-YYYY)
    match = re.search(r"(\d{1,2})[-/](\d{1,2})[-/](\d{4})", phrase)
    if match:
        day, month, year = map(int, match.groups())
        try:
            return date(year, month, day)
        except ValueError:
            pass

    match_short = re.search(r"(\d{1,2})[-/](\d{1,2})", phrase)
    if match_short:
        day, month = map(int, match_short.groups())
        try:
            resolved = date(today.year, month, day)
            return resolved if resolved >= today else date(today.year + 1, month, day)
        except ValueError:
            pass

    return today


def parse_colloquial_time(phrase: str) -> str | None:
    """Parse colloquial time phrases into 24h 'HH:MM' format."""
    phrase = normalize_numerals(phrase).lower().strip()

    # Detect AM/PM indicators
    pm_indicators = [
        "shaam",
        "dopahar",
        "evening",
        "afternoon",
        "pm",
        "ସନ୍ଧ୍ୟା",
        "ଶ୍ୟାମ",
        "ଦ୍ୱିପ୍ରହର",
        "शाम",
        "दोपहर",
    ]
    am_indicators = ["subah", "morning", "am", "ସକାଳ", "सुबह"]

    is_pm = any(_has(phrase, k) for k in pm_indicators)
    is_am = any(_has(phrase, k) for k in am_indicators)

    # When both an AM word and a PM word are present, AM wins
    if is_am:
        is_pm = False

    numbers = re.findall(r"\d+", phrase)
    if not numbers:
        return None

    hour = int(numbers[0])
    minute = 0
    if len(numbers) > 1:
        # Check if the second number is minutes (if close to the first, e.g. "4 30" or "4:30")
        if ":" in phrase or " " in phrase:
            minute = int(numbers[1])

    # If it's a 12-hour format, resolve AM/PM
    if hour <= 12:
        if is_pm and hour < 12:
            hour += 12
        elif is_am and hour == 12:
            hour = 0
        elif not is_am and not is_pm:
            # Default heuristics: 9 to 12 is AM (morning), 1 to 8 is PM (afternoon/evening)
            if 1 <= hour <= 8:
                hour += 12

    if 0 <= hour < 24 and 0 <= minute < 60:
        return f"{hour:02d}:{minute:02d}"
    return None


def format_colloquial_time(time_str: str, lang: str) -> str:
    """Format 24h 'HH:MM' time back into colloquial '4:00 PM (shaam)' form."""
    try:
        hour, minute = map(int, time_str.split(":"))
    except ValueError:
        return time_str

    period = "AM"
    colloquial = "subah"
    
    if hour >= 12:
        period = "PM"
        if 12 <= hour < 16:
            colloquial = "dopahar"
        else:
            colloquial = "shaam"
        if hour > 12:
            hour -= 12
    elif hour == 0:
        hour = 12

    # Language translations for colloquial label
    translations = {
        "hi": {"subah": "subah", "dopahar": "dopahar", "shaam": "shaam"},
        "hi-Latn": {"subah": "subah", "dopahar": "dopahar", "shaam": "shaam"},
        "or": {"subah": "sakala", "dopahar": "dwiprahara", "shaam": "sandhya"},
        "en": {"subah": "morning", "dopahar": "afternoon", "shaam": "evening"}
    }

    lang_trans = translations.get(lang, translations["en"])
    colloquial_label = lang_trans.get(colloquial, colloquial)

    return f"{hour}:{minute:02d} {period} ({colloquial_label})"

