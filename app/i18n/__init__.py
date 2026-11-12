"""Localization utilities and string lookup (W2-01)."""

from __future__ import annotations

from typing import Any

from app.i18n.strings import STRINGS

LANGS: tuple[str, ...] = ("en", "hi", "hi-Latn", "or")


def normalize_lang(value: str | None) -> str:
    """Normalize language code to one of LANGS, defaulting to 'en'."""
    if not value or not isinstance(value, str):
        return "en"
    val = value.strip()
    if val in LANGS:
        return val
    # Handle common prefixes / aliases
    val_lower = val.lower()
    if val_lower in ("hi-latn", "hinglish"):
        return "hi-Latn"
    if val_lower.startswith("hi"):
        return "hi"
    if val_lower.startswith("or") or val_lower == "odia":
        return "or"
    return "en"


def t(key: str, lang: str = "en", **params: Any) -> str:
    """Translate a string key into target language with fallback to English.

    Raises KeyError if the key is not in STRINGS.
    """
    if key not in STRINGS:
        raise KeyError(f"Missing i18n key: '{key}'")
    translations = STRINGS[key]
    normalized = normalize_lang(lang)
    raw_template = translations.get(normalized) or translations.get("en")
    if raw_template is None:
        raise KeyError(f"No translation or English fallback for key: '{key}'")
    return raw_template.format(**params)
