"""Tests for internationalization, string lookup, and WhatsApp flow localization (W2-01)."""

from __future__ import annotations

import re
import string
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from app.booking.timefmt import DEFAULT_TIMEZONE, format_local
from app.i18n import LANGS, normalize_lang, t
from app.i18n.strings import STRINGS
from app.workers.inbound import _render_slot_label


def test_strings_have_all_languages() -> None:
    """Every key in STRINGS must define translations for all supported LANGS."""
    for key, translations in STRINGS.items():
        for lang in LANGS:
            assert lang in translations, f"Key '{key}' is missing translation for '{lang}'"
            assert isinstance(translations[lang], str)
            assert len(translations[lang].strip()) > 0, f"Key '{key}' has empty string for '{lang}'"


def test_parameters_match_across_languages() -> None:
    """Every format parameter in English must also appear in hi, hi-Latn, and or translations."""
    formatter = string.Formatter()
    for key, translations in STRINGS.items():
        en_template = translations["en"]
        en_params = {
            field_name
            for _, field_name, _, _ in formatter.parse(en_template)
            if field_name is not None
        }

        for lang in ("hi", "hi-Latn", "or"):
            target_template = translations[lang]
            target_params = {
                field_name
                for _, field_name, _, _ in formatter.parse(target_template)
                if field_name is not None
            }
            assert en_params == target_params, (
                f"Key '{key}' parameters mismatch in '{lang}': expected {en_params}, got {target_params}"
            )


def test_ui_strings_whatsapp_limits() -> None:
    """WhatsApp button titles <= 20 chars, section titles <= 24 chars."""
    limits: dict[str, int] = {
        "ui.choose_time": 20,
        "ui.slots_title": 24,
        "ui.confirm": 20,
        "ui.choose_again": 20,
        "ui.cancel_yes": 20,
        "ui.cancel_keep": 20,
    }
    for key, limit in limits.items():
        for lang in LANGS:
            text = STRINGS[key][lang]
            assert len(text) <= limit, (
                f"UI string '{key}' in '{lang}' is {len(text)} chars, exceeds WhatsApp limit of {limit}: '{text}'"
            )


def test_format_local_length_and_formatting() -> None:
    """Across all 7 weekdays and 12 months, localized dates must be <= 24 characters."""
    tz = ZoneInfo(DEFAULT_TIMEZONE)
    # Test dates across the entire year 2026
    sample_dates = [
        datetime(2026, month, day, hour, 0, tzinfo=UTC)
        for month, day in [
            (1, 5),   # Jan
            (2, 10),  # Feb
            (3, 15),  # Mar
            (4, 20),  # Apr
            (5, 25),  # May
            (6, 1),   # Jun
            (7, 7),   # Jul
            (8, 14),  # Aug
            (9, 21),  # Sep
            (10, 28), # Oct
            (11, 12), # Nov
            (12, 31), # Dec
        ]
        for hour in (9, 14)
    ]

    for dt in sample_dates:
        for lang in LANGS:
            formatted = format_local(dt, tz, lang=lang)
            assert len(formatted) <= 24, (
                f"format_local length {len(formatted)} > 24 for lang '{lang}', date {dt}: '{formatted}'"
            )

    # Specific format verification for Nov 12, 10:00 AM IST
    fixed_dt = datetime(2026, 11, 12, 4, 30, tzinfo=UTC)  # 10:00 AM IST, Thursday
    assert format_local(fixed_dt, tz, lang="en") == "Thu 12 Nov, 10:00 AM"
    assert format_local(fixed_dt, tz, lang="hi-Latn") == "Thu 12 Nov, 10:00 AM"
    assert format_local(fixed_dt, tz, lang="hi") == "गुरु 12 नव, 10:00 AM"
    assert format_local(fixed_dt, tz, lang="or") == "ଗୁରୁ 12/11, 10:00 AM"


def test_normalize_lang() -> None:
    assert normalize_lang("en") == "en"
    assert normalize_lang("hi") == "hi"
    assert normalize_lang("hi-Latn") == "hi-Latn"
    assert normalize_lang("or") == "or"
    assert normalize_lang("Hinglish") == "hi-Latn"
    assert normalize_lang("hindi") == "hi"
    assert normalize_lang("odia") == "or"
    assert normalize_lang("unknown") == "en"
    assert normalize_lang(None) == "en"


def test_t_lookup_and_fallback() -> None:
    # Valid key and language
    assert "समय चुनें" in t("ui.choose_time", "hi")
    # Missing key raises KeyError
    with pytest.raises(KeyError):
        t("nonexistent.key", "en")
    # Parameter interpolation
    res = t("booking.booked", "en", when="tomorrow 10 AM")
    assert res == "Your appointment is booked for tomorrow 10 AM."


def test_no_prohibited_inline_copy_in_inbound_worker() -> None:
    """Acceptance criteria: prohibited English literals must not appear inline in inbound.py."""
    pattern = re.compile(
        r'"(Your appointment|Please choose|That slot|Choose a|Confirm |I could not|You have|Sorry, I can|Cancel your|Okay, your)'
    )
    inbound_path = Path(__file__).resolve().parent.parent / "app" / "workers" / "inbound.py"
    with open(inbound_path, encoding="utf-8") as f:
        matches = [
            (idx + 1, line.strip())
            for idx, line in enumerate(f)
            if pattern.search(line)
        ]

    assert len(matches) == 0, f"Found prohibited inline copy in inbound.py: {matches}"


def test_render_slot_label_compatibility() -> None:
    """Test legacy formatted labels vs new ISO timestamps."""
    tz = ZoneInfo(DEFAULT_TIMEZONE)
    # Legacy formatted label should pass through unchanged
    legacy_label = "Thu 12 Nov, 10:00 AM"
    assert _render_slot_label(legacy_label, tz, lang="hi") == legacy_label

    # ISO format timestamp should format into requested language
    iso_stamp = "2026-11-12T10:00:00+05:30"
    rendered_hi = _render_slot_label(iso_stamp, tz, lang="hi")
    assert "गुरु" in rendered_hi
    assert "नव" in rendered_hi

    rendered_en = _render_slot_label(iso_stamp, tz, lang="en")
    assert "Thu 12 Nov" in rendered_en


@pytest.mark.asyncio
async def test_language_persistence_and_short_word_protection() -> None:
    """Non-Latin or >= 3 words sets lang; short Latin tokens ('ok', 'yes') do not overwrite."""
    import json

    from app.models.base import get_db, mongo_id_candidates
    from app.models.collections import Contacts, Conversations
    from app.workers.inbound import process_event

    db = get_db()
    for col in await db.list_collection_names():
        if not col.startswith("system."):
            await db[col].delete_many({})

    tenant_id = "t_i18n_lang"
    wa_id = "919876500001"
    await db["tenants"].insert_one(
        {"_id": tenant_id, "name": "Lang Clinic", "timezone": "Asia/Kolkata", "status": "active"}
    )
    contact_res = await db["contacts"].insert_one(
        {
            "tenant_id": tenant_id,
            "wa_id": wa_id,
            "phone": wa_id,
            "name": "Hindi Patient",
            "last_inbound_ts": datetime.now(UTC).replace(tzinfo=None),
        }
    )
    contact_id = str(contact_res.inserted_id)

    # 1. Hindi message with non-Latin text -> lang should become "hi"
    payload_1 = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "contacts": [{"wa_id": wa_id, "profile": {"name": "Hindi Patient"}}],
                            "messages": [{"from": wa_id, "id": "msg-hi-1", "type": "text", "text": {"body": "नमस्ते"}}],
                        }
                    }
                ]
            }
        ]
    }
    await process_event({"tenant_id": tenant_id, "message_id": "msg-hi-1", "payload": json.dumps(payload_1)})

    conv = await Conversations(tenant_id).find_one({"contact_id": contact_id})
    assert conv is not None
    assert conv.get("lang") == "hi"

    contact = await Contacts(tenant_id).find_one({"_id": {"$in": mongo_id_candidates(contact_id)}})
    assert contact is not None
    assert contact.get("lang_pref") == "hi"

    # 2. Short Latin text like "ok" (< 3 words, no non-Latin) -> should NOT flip lang to "en"
    payload_2 = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "contacts": [{"wa_id": wa_id, "profile": {"name": "Hindi Patient"}}],
                            "messages": [{"from": wa_id, "id": "msg-hi-2", "type": "text", "text": {"body": "ok"}}],
                        }
                    }
                ]
            }
        ]
    }
    await process_event({"tenant_id": tenant_id, "message_id": "msg-hi-2", "payload": json.dumps(payload_2)})

    conv = await Conversations(tenant_id).find_one({"contact_id": contact_id})
    assert conv is not None
    assert conv.get("lang") == "hi"


@pytest.mark.asyncio
async def test_hindi_cancel_flow_localized() -> None:
    """When a Hindi conversation cancels, the confirmation prompt and buttons are in Hindi."""
    import json
    from datetime import timedelta

    from app.models.base import get_db, mongo_id_candidates
    from app.models.collections import Bookings, Conversations, Messages, Slots
    from app.workers.inbound import process_event

    db = get_db()
    for col in await db.list_collection_names():
        if not col.startswith("system."):
            await db[col].delete_many({})

    tenant_id = "t_i18n_cancel"
    wa_id = "919876500002"
    await db["tenants"].insert_one(
        {"_id": tenant_id, "name": "Hindi Cancel Clinic", "timezone": "Asia/Kolkata", "status": "active"}
    )
    contact_res = await db["contacts"].insert_one(
        {
            "tenant_id": tenant_id,
            "wa_id": wa_id,
            "phone": wa_id,
            "name": "Hindi Patient",
            "lang_pref": "hi",
            "last_inbound_ts": datetime.now(UTC).replace(tzinfo=None),
        }
    )
    contact_id = str(contact_res.inserted_id)

    future_start = (datetime.now(UTC) + timedelta(days=2)).replace(hour=10, minute=0, second=0, microsecond=0, tzinfo=None)
    slot_res = await Slots(tenant_id).insert_one(
        {
            "practitioner_id": "dr_cancel_hi",
            "start": future_start,
            "end": future_start + timedelta(minutes=30),
            "status": "booked",
        }
    )
    slot_id = str(slot_res.inserted_id)
    booking_res = await Bookings(tenant_id).insert_one(
        {
            "slot_id": slot_id,
            "contact_id": contact_id,
            "service": "Consultation",
            "status": "confirmed",
            "request_id": "req-hi-booking",
            "ts": datetime.now(UTC).replace(tzinfo=None),
        }
    )
    booking_id = str(booking_res.inserted_id)
    await Slots(tenant_id).update_one({"_id": slot_res.inserted_id}, {"$set": {"booking_id": booking_id}})

    # Trigger cancel with Hindi text
    payload_1 = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "contacts": [{"wa_id": wa_id, "profile": {"name": "Hindi Patient"}}],
                            "messages": [{"from": wa_id, "id": "msg-hi-cancel-1", "type": "text", "text": {"body": "अपॉइंटमेंट रद्द करें"}}],
                        }
                    }
                ]
            }
        ]
    }
    await process_event({"tenant_id": tenant_id, "message_id": "msg-hi-cancel-1", "payload": json.dumps(payload_1)})

    # Confirm flow is in awaiting_confirmation
    conv = await Conversations(tenant_id).find_one({"contact_id": contact_id})
    assert conv is not None
    assert conv.get("cancel_flow") is not None
    assert conv["cancel_flow"]["stage"] == "awaiting_confirmation"

    # Confirm interactive outbound was stored
    interactive_msg = await Messages(tenant_id).find_one({"direction": "outbound", "type": "interactive"})
    assert interactive_msg is not None
    assert interactive_msg.get("flow") == "cancel_confirmation"

    # Now tap confirm (in Hindi)
    payload_2 = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "contacts": [{"wa_id": wa_id, "profile": {"name": "Hindi Patient"}}],
                            "messages": [
                                {
                                    "from": wa_id,
                                    "id": "msg-hi-cancel-2",
                                    "type": "interactive",
                                    "interactive": {"type": "button_reply", "button_reply": {"id": "cancel:confirm", "title": "हाँ, रद्द करें"}},
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }
    await process_event({"tenant_id": tenant_id, "message_id": "msg-hi-cancel-2", "payload": json.dumps(payload_2)})

    booking_after = await Bookings(tenant_id).find_one({"_id": {"$in": mongo_id_candidates(booking_id)}})
    assert booking_after["status"] == "cancelled"

    last_msg = await Messages(tenant_id).find_one({"direction": "outbound", "type": "text"}, sort=[("ts", -1)])
    assert last_msg is not None
    assert "रद्द कर दिया गया है" in last_msg["text"]

