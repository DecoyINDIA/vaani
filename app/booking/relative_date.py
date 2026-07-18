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
from typing import Any

def normalize_numerals(text: str) -> str:
    """Map Devanagari and Odia numerals to standard ASCII digits."""
    devanagari = "०१२३४५६७८९"
    odia = "୦୧୨୩୪୫୬୭୮୯"
    for i in range(10):
        text = text.replace(devanagari[i], str(i))
        text = text.replace(odia[i], str(i))
    return text


def resolve(phrase: str, *, today: date, lang: str) -> date:
    """Resolve a relative date phrase into an absolute date (always future/today)."""
    phrase = normalize_numerals(phrase).lower().strip()

    # 1. Tomorrow
    tomorrow_keywords = ["kal", "tomorrow", "kali", "କାଲି", "कल", "kal subah", "kal shaam"]
    if any(k in phrase for k in tomorrow_keywords):
        return today + timedelta(days=1)

    # 2. Day after tomorrow
    parso_keywords = ["parso", "parshon", "paradina", "ପରଦିନ", "परसों"]
    if any(k in phrase for k in parso_keywords):
        return today + timedelta(days=2)

    # 3. Weekdays
    weekdays_map = {
        0: ["somvar", "somvara", "somabara", "monday", "mon", "ସୋମବାର", "सोमवार"],
        1: ["mangalvar", "mangalvara", "mangalabara", "tuesday", "tue", "ମଙ୍ଗଳବାର", "मंगलवार"],
        2: ["budhvar", "budhvara", "budhabara", "wednesday", "wed", "ବୁଧବାର", "बुधवार"],
        3: ["guruvar", "guruvara", "gurubara", "veervar", "thursday", "thu", "ଗୁରୁବାର", "गुरुवार"],
        4: ["shukravar", "shukravara", "sukrabara", "friday", "fri", "ଶୁକ୍ରବାର", "शुक्रवार"],
        5: ["shanivar", "shanivara", "sanibara", "saturday", "sat", "ଶନିବାର", "शनिवार"],
        6: ["ravivar", "ravivara", "rabibara", "itvar", "sunday", "sun", "ରବିବାର", "रविवार"]
    }

    target_weekday = None
    for w_idx, keywords in weekdays_map.items():
        if any(k in phrase for k in keywords):
            target_weekday = w_idx
            break

    if target_weekday is not None:
        current_weekday = today.weekday()
        days_ahead = (target_weekday - current_weekday) % 7
        
        # Check if "next" or "agle" or "asanta" is in phrase
        next_keywords = ["next", "agle", "asanta", "ଆସନ୍ତା", "अगले"]
        is_next = any(k in phrase for k in next_keywords)
        
        if days_ahead == 0:
            days_ahead = 7
        elif is_next:
            # If they say "next Monday" and today is Tuesday (6 days ahead), they might mean upcoming Monday.
            # But to be safe and enforce "future interpretation", we keep it or add 7 if they explicitly say "next".
            # Let's add 7 if they explicitly say next and it's less than 7 days, or keep it. Let's just return upcoming.
            pass
            
        return today + timedelta(days=days_ahead)

    # 4. Try absolute date parsing (e.g. DD/MM/YYYY or DD-MM-YYYY)
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
            return date(today.year, month, day)
        except ValueError:
            pass

    return today


def parse_colloquial_time(phrase: str) -> str | None:
    """Parse colloquial time phrases into 24h 'HH:MM' format."""
    phrase = normalize_numerals(phrase).lower().strip()

    # Detect AM/PM indicators
    pm_indicators = [
        "shaam", "dopahar", "evening", "afternoon", "pm", "सନ୍ଧ୍ୟା", "ଶ୍ୟାମ", 
        "ଦ୍ୱିପ୍ରହର", "शाम", "दोपहर", "baje", "bajey"
    ]
    am_indicators = ["subah", "morning", "am", "ସକାଳ", "सुबह"]

    is_pm = any(k in phrase for k in pm_indicators)
    is_am = any(k in phrase for k in am_indicators)

    # Specific override: "shaam ko 4 baje" -> PM, "subah 10" -> AM
    # Check for numbers in phrase
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

