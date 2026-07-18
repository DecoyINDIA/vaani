"""Node 1 — language detection (TRD §4.3).

lingua + script heuristics. Hinglish (Latin-script Hindi) is its own register:
hi-Latn. Voice notes transcribed by the same STT (Phase 2); STT confidence <0.75
-> ask to type or escalate.
"""

from __future__ import annotations

import re
from typing import Any
from lingua import Language, LanguageDetectorBuilder

# Build the detector once globally
_detector = LanguageDetectorBuilder.from_languages(Language.ENGLISH, Language.HINDI).build()


async def lang_detect(state: dict[str, Any]) -> dict[str, Any]:
    """Node 1 — language detection (TRD §4.3).

    lingua + script heuristics. Hinglish (Latin-script Hindi) is its own register:
    hi-Latn. Voice notes transcribed by the same STT (Phase 2); STT confidence <0.75
    -> ask to type or escalate.
    """
    text = state.get("text", "").strip()
    if not text:
        return {"lang": "en"}

    # 1. Devanagari script -> Hindi (hi)
    if re.search(r"[\u0900-\u097f]", text):
        return {"lang": "hi"}

    # 2. Odia script -> Odia (or)
    if re.search(r"[\u0b00-\u0b7f]", text):
        return {"lang": "or"}

    # 3. Latin script -> English (en) or Hinglish (hi-Latn)
    text_lower = text.lower()
    
    # Common Hindi words in Latin script (Hinglish indicators)
    hinglish_markers = {
        "hai", "hain", "hein", "kya", "ko", "se", "ki", "ka", "ke", "baje",
        "mujhe", "mera", "meri", "aap", "dijiye", "mil", "sakta", "sakte", "rha",
        "raha", "kar", "karna", "karne", "parso", "kal", "aaj", "namaste", "ji",
        "karo", "kijiye", "kab", "ab", "tum", "ter", "mera", "apna", "apni"
    }
    
    words = re.findall(r"[a-z']+", text_lower)
    if any(w in hinglish_markers for w in words):
        return {"lang": "hi-Latn"}

    # Lingua fallback
    try:
        detected = _detector.detect_language_of(text)
        if detected == Language.HINDI:
            return {"lang": "hi-Latn"}
        elif detected == Language.ENGLISH:
            return {"lang": "en"}
    except Exception:
        pass

    return {"lang": "en"}

