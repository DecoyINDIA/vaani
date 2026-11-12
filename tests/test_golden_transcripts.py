"""Replay scripted WhatsApp conversations through process_event and assert exact outbound messages (W2-08)."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from app.agent.templates import TEMPLATES
from app.i18n.strings import STRINGS
from app.models.base import get_db, mongo_id_candidates
from app.models.collections import (
    Bookings,
    Contacts,
    Conversations,
    Escalations,
    KbEntries,
    Practitioners,
    Slots,
    Tenants,
    Users,
)
from app.workers.inbound import process_event

from tests.golden_support import (
    WhatsAppRecorder,
    make_button_reply_payload,
    make_list_reply_payload,
    make_media_payload,
    make_text_payload,
    wa_recorder,
)

GOLDEN_DIR = Path(__file__).parent / "golden"
SCENARIO_FILES = sorted(list(GOLDEN_DIR.glob("*.*.json")), key=lambda p: p.name)

# Ensure pytest registers wa_recorder
_ = wa_recorder


@pytest.fixture(autouse=True)
async def clean_db() -> None:
    """Clean all non-system collections before each scenario run."""
    db = get_db()
    for name in await db.list_collection_names():
        if not name.startswith("system."):
            await db[name].delete_many({})


def get_template_string(key: str, lang: str) -> str:
    """Look up localized string template from STRINGS or TEMPLATES."""
    if key in STRINGS:
        table = STRINGS[key]
        return table.get(lang) or table.get("en", "")
    if key in TEMPLATES:
        table = TEMPLATES[key]
        return table.get(lang) or table.get("en", "")
    if key == "medical_refusal" and "restricted_advice_refusal" in TEMPLATES:
        table = TEMPLATES["restricted_advice_refusal"]
        return table.get(lang) or table.get("en", "")
    raise KeyError(f"Unknown template or string key: {key}")


def template_to_regex(template_str: str) -> re.Pattern[str]:
    """Compile a string template with {placeholders} to a regex pattern."""
    parts = re.split(r"\{[a-zA-Z_0-9]+\}", template_str)
    escaped_parts = [re.escape(part) for part in parts]
    pattern = "^" + ".+?".join(escaped_parts) + "$"
    return re.compile(pattern, re.DOTALL)


def check_global_assertions(msg: dict[str, Any], tenant_name: str) -> None:
    """Apply global safety and contract assertions to every outbound message."""
    body = msg.get("body", {})
    msg_type = body.get("type")

    texts_to_check: list[str] = []

    if msg_type == "text":
        texts_to_check.append(body.get("text", {}).get("body", ""))
    elif msg_type == "interactive":
        interactive = body.get("interactive", {})
        texts_to_check.append(interactive.get("body", {}).get("text", ""))
        action = interactive.get("action", {})
        if interactive.get("type") == "button":
            for b in action.get("buttons", []):
                btn_title = b.get("reply", {}).get("title", "")
                assert len(btn_title) <= 20, (
                    f"Button title '{btn_title}' exceeds 20 chars ({len(btn_title)})"
                )
        elif interactive.get("type") == "list":
            btn_label = action.get("button", "")
            assert len(btn_label) <= 20, (
                f"List button label '{btn_label}' exceeds 20 chars ({len(btn_label)})"
            )
            for sec in action.get("sections", []):
                sec_title = sec.get("title", "")
                assert len(sec_title) <= 24, (
                    f"Section title '{sec_title}' exceeds 24 chars ({len(sec_title)})"
                )
                for r in sec.get("rows", []):
                    row_title = r.get("title", "")
                    assert len(row_title) <= 24, (
                        f"Row title '{row_title}' exceeds 24 chars ({len(row_title)})"
                    )

    for text in texts_to_check:
        assert "[source_ref" not in text, f"Leaked internal citation tag in text: {text!r}"
        assert "Sharma" not in text, f"Hardcoded legacy clinic identity 'Sharma' found: {text!r}"
        assert not re.search(r"\d{4}-\d{2}-\d{2}T", text), (
            f"Raw unrendered ISO datetime found in outbound message: {text!r}"
        )


@pytest.mark.parametrize("scenario_file", SCENARIO_FILES, ids=lambda p: p.stem)
async def test_golden_transcript(
    scenario_file: Path,
    wa_recorder: WhatsAppRecorder,
) -> None:
    """Replay scenario through process_event and assert outbound messages and final state."""
    content = json.loads(scenario_file.read_text(encoding="utf-8"))
    scenario_name = scenario_file.stem
    lang = content.get("lang", "en")
    tenant_override = content.get("tenant", {})
    tenant_name = tenant_override.get("name", "Apex Clinic")
    locale_default = tenant_override.get("locale_default", lang)

    # Unique IDs for isolation
    tenant_id = f"t_{scenario_name}".replace("-", "_")
    safe_hash = abs(hash(scenario_name)) % 10000000
    wa_id = f"91987{safe_hash:07d}"
    staff_wa_id = f"91999{safe_hash:07d}"
    practitioner_id = f"doc_{tenant_id}"

    # 1. Seed Tenant
    await Tenants(tenant_id).insert_one(
        {
            "_id": tenant_id,
            "name": tenant_name,
            "locale_default": locale_default,
            "timezone": "Asia/Kolkata",
            "whatsapp": {
                "phone_number_id": f"phone_{tenant_id}",
                "access_token_env": "TEST_TOKEN",
            },
            "business_profile": {
                "business_type": "clinic",
                "staff_term": "doctor",
                "customer_term": "patient",
            },
        }
    )

    # 2. Seed Staff User (for escalation alerts)
    await Users(tenant_id).insert_one(
        {
            "tenant_id": tenant_id,
            "name": "Clinic Staff",
            "role": "staff",
            "status": "active",
            "phone": staff_wa_id,
            "wa_id": staff_wa_id,
        }
    )

    # 3. Seed Practitioner
    await Practitioners(tenant_id).insert_one(
        {
            "_id": practitioner_id,
            "tenant_id": tenant_id,
            "name": "Dr. Roy",
            "specialty": "Dentist",
            "is_active": True,
        }
    )

    # 4. Seed Slots (tomorrow at 10:00, 11:00, 14:00, 15:00, 16:00 in Asia/Kolkata)
    tz = ZoneInfo("Asia/Kolkata")
    tomorrow = (datetime.now(tz) + timedelta(days=1)).date()
    for hour in [10, 11, 14, 15, 16]:
        slot_start = datetime(tomorrow.year, tomorrow.month, tomorrow.day, hour, 0, tzinfo=tz)
        slot_end = slot_start + timedelta(minutes=30)
        await Slots(tenant_id).insert_one(
            {
                "tenant_id": tenant_id,
                "practitioner_id": practitioner_id,
                "service_id": "consultation",
                "service_name": "Consultation",
                "start": slot_start.astimezone(UTC).replace(tzinfo=None),
                "end": slot_end.astimezone(UTC).replace(tzinfo=None),
                "status": "open",
            }
        )

    # 5. Seed KB Entry (for FAQ fees)
    await KbEntries(tenant_id).insert_one(
        {
            "tenant_id": tenant_id,
            "key": "faq_fees",
            "question": "What is the consultation fee?",
            "answer": "The consultation fee is Rs 500.",
        }
    )

    # 6. Optional setup: seed existing booking
    patient_contact_id: str | None = None
    if content.get("setup", {}).get("seed_booking"):
        contact_res = await Contacts(tenant_id).insert_one(
            {
                "tenant_id": tenant_id,
                "wa_id": wa_id,
                "name": "Test Patient",
                "lang_pref": lang,
                "last_inbound_ts": datetime.now(UTC).replace(tzinfo=None),
                "created_at": datetime.now(UTC).replace(tzinfo=None),
            }
        )
        patient_contact_id = str(contact_res.inserted_id)

        # Grab one open slot and book it
        seeded_slot = await Slots(tenant_id).find_one({"status": "open"})
        assert seeded_slot is not None
        await Slots(tenant_id).update_one(
            {"_id": seeded_slot["_id"]},
            {"$set": {"status": "booked"}},
        )

        await Bookings(tenant_id).insert_one(
            {
                "tenant_id": tenant_id,
                "contact_id": patient_contact_id,
                "slot_id": str(seeded_slot["_id"]),
                "practitioner_id": practitioner_id,
                "status": "confirmed",
                "created_at": datetime.now(UTC).replace(tzinfo=None),
            }
        )

    # 7. Execute scenario steps sequentially
    steps = content.get("steps", [])
    for step_idx, step in enumerate(steps):
        send_data = step.get("send", {})
        expect_data = step.get("expect", [])
        msg_id = f"wamid.{scenario_name}.{step_idx}"

        # Resolve payload
        if "text" in send_data:
            payload = make_text_payload(
                wa_id=wa_id,
                text=send_data["text"],
                msg_id=msg_id,
            )
        elif "tap" in send_data:
            tap_val = send_data["tap"]
            if tap_val in ("slot:first", "slot:last"):
                # Find last outbound interactive list
                last_list = next(
                    (
                        m for m in reversed(wa_recorder.messages)
                        if m.get("body", {}).get("type") == "interactive"
                        and m.get("body", {}).get("interactive", {}).get("type") == "list"
                    ),
                    None,
                )
                assert last_list is not None, "Cannot resolve slot tap: no prior list message found"
                rows = (
                    last_list["body"]["interactive"]["action"]["sections"][0]["rows"]
                )
                assert rows, "Prior list message has no rows"
                target_row = rows[0] if tap_val == "slot:first" else rows[-1]
                payload = make_list_reply_payload(
                    wa_id=wa_id,
                    slot_id=target_row["id"],
                    title=target_row["title"],
                    msg_id=msg_id,
                )
            elif str(tap_val).startswith("slot:"):
                payload = make_list_reply_payload(
                    wa_id=wa_id,
                    slot_id=tap_val,
                    title=tap_val,
                    msg_id=msg_id,
                )
            else:
                payload = make_button_reply_payload(
                    wa_id=wa_id,
                    button_id=tap_val,
                    title=tap_val,
                    msg_id=msg_id,
                )
        elif "media" in send_data:
            payload = make_media_payload(
                wa_id=wa_id,
                media_type=send_data["media"],
                msg_id=msg_id,
            )
        else:
            raise ValueError(f"Step {step_idx} has unsupported send shape: {send_data}")

        start_count = len(wa_recorder.messages)
        await process_event(
            {
                "tenant_id": tenant_id,
                "message_id": msg_id,
                "payload": json.dumps(payload),
            }
        )
        step_messages = wa_recorder.messages[start_count:]

        # Global assertions on every outbound message
        for msg in step_messages:
            check_global_assertions(msg, tenant_name)

        # Match step expectations
        assert len(step_messages) == len(expect_data), (
            f"Step {step_idx}: expected {len(expect_data)} outbound messages, got {len(step_messages)}: {step_messages}"
        )

        for exp_idx, (exp, actual) in enumerate(zip(expect_data, step_messages, strict=True)):
            kind = exp.get("kind")
            actual_body = actual.get("body", {})
            actual_type = actual_body.get("type")

            if kind == "text":
                assert actual_type == "text", (
                    f"Step {step_idx} msg {exp_idx}: expected text message, got {actual_type}"
                )
                text_val = actual_body.get("text", {}).get("body", "")
                if "key" in exp:
                    template_str = get_template_string(exp["key"], lang)
                    regex = template_to_regex(template_str)
                    assert regex.search(text_val.strip()), (
                        f"Step {step_idx} msg {exp_idx}: text {text_val!r} did not match template {template_str!r} (regex: {regex.pattern})"
                    )
                if "contains" in exp:
                    assert exp["contains"] in text_val, (
                        f"Step {step_idx} msg {exp_idx}: text {text_val!r} does not contain {exp['contains']!r}"
                    )

            elif kind == "list":
                assert actual_type == "interactive", (
                    f"Step {step_idx} msg {exp_idx}: expected interactive list, got {actual_type}"
                )
                interactive = actual_body.get("interactive", {})
                assert interactive.get("type") == "list", (
                    f"Step {step_idx} msg {exp_idx}: expected interactive type 'list', got {interactive.get('type')}"
                )
                action = interactive.get("action", {})
                rows = action.get("sections", [{}])[0].get("rows", [])
                if "min_rows" in exp:
                    assert len(rows) >= exp["min_rows"], (
                        f"Step {step_idx} msg {exp_idx}: expected at least {exp['min_rows']} rows, got {len(rows)}"
                    )
                if "button_key" in exp:
                    btn_expected = get_template_string(exp["button_key"], lang)
                    assert action.get("button", "").strip() == btn_expected.strip(), (
                        f"Step {step_idx} msg {exp_idx}: button label '{action.get('button')}' != '{btn_expected}'"
                    )
                if "body_key" in exp:
                    body_template = get_template_string(exp["body_key"], lang)
                    regex = template_to_regex(body_template)
                    prompt_text = interactive.get("body", {}).get("text", "")
                    assert regex.search(prompt_text.strip()), (
                        f"Step {step_idx} msg {exp_idx}: prompt {prompt_text!r} did not match {body_template!r}"
                    )

            elif kind == "buttons":
                assert actual_type == "interactive", (
                    f"Step {step_idx} msg {exp_idx}: expected interactive button, got {actual_type}"
                )
                interactive = actual_body.get("interactive", {})
                assert interactive.get("type") == "button", (
                    f"Step {step_idx} msg {exp_idx}: expected interactive type 'button', got {interactive.get('type')}"
                )
                buttons = interactive.get("action", {}).get("buttons", [])
                if "ids" in exp:
                    actual_ids = [b.get("reply", {}).get("id") for b in buttons]
                    assert actual_ids == exp["ids"], (
                        f"Step {step_idx} msg {exp_idx}: button IDs {actual_ids} != {exp['ids']}"
                    )
                if "body_key" in exp:
                    body_template = get_template_string(exp["body_key"], lang)
                    regex = template_to_regex(body_template)
                    prompt_text = interactive.get("body", {}).get("text", "")
                    assert regex.search(prompt_text.strip()), (
                        f"Step {step_idx} msg {exp_idx}: prompt {prompt_text!r} did not match {body_template!r}"
                    )

            elif kind == "template":
                assert actual_type == "template", (
                    f"Step {step_idx} msg {exp_idx}: expected template, got {actual_type}"
                )
                if "name" in exp:
                    actual_name = actual_body.get("template", {}).get("name")
                    assert actual_name == exp["name"], (
                        f"Step {step_idx} msg {exp_idx}: template name '{actual_name}' != '{exp['name']}'"
                    )

            elif kind == "none":
                pass
            else:
                raise ValueError(f"Unknown expectation kind: {kind}")

    # 8. Check final post-conditions
    final_checks = content.get("final", {})
    if "bookings_confirmed" in final_checks:
        confirmed_count = await Bookings(tenant_id).count_documents({"status": "confirmed"})
        assert confirmed_count == final_checks["bookings_confirmed"], (
            f"Expected {final_checks['bookings_confirmed']} confirmed bookings, found {confirmed_count}"
        )

    if "bookings_cancelled" in final_checks:
        cancelled_count = await Bookings(tenant_id).count_documents({"status": "cancelled"})
        assert cancelled_count == final_checks["bookings_cancelled"], (
            f"Expected {final_checks['bookings_cancelled']} cancelled bookings, found {cancelled_count}"
        )

    if "conversation_state" in final_checks:
        contact = await Contacts(tenant_id).find_one({"wa_id": wa_id})
        contact_id_val = str(contact["_id"]) if contact else patient_contact_id or wa_id
        convo = await Conversations(tenant_id).find_one(
            {"contact_id": {"$in": mongo_id_candidates(contact_id_val)}}
        )
        assert convo is not None, f"No conversation found for contact {contact_id_val}"
        assert convo.get("state") == final_checks["conversation_state"], (
            f"Expected conversation state {final_checks['conversation_state']}, got {convo.get('state')}"
        )

    if "open_escalations" in final_checks:
        open_count = await Escalations(tenant_id).count_documents({"status": "open"})
        assert open_count == final_checks["open_escalations"], (
            f"Expected {final_checks['open_escalations']} open escalations, found {open_count}"
        )
