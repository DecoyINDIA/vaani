"""Tests for the interactive capability menu (W2-09)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from app.agent.templates import TEMPLATES
from app.channels.whatsapp import WindowClosedError, send_menu
from app.i18n.strings import STRINGS
from app.models.base import get_db, mongo_id_candidates
from app.models.collections import (
    Bookings,
    Contacts,
    Conversations,
    Escalations,
    KbEntries,
    Messages,
    Practitioners,
    Slots,
    Tenants,
    Users,
)
from app.workers.inbound import process_event

from tests.golden_support import (
    WhatsAppRecorder,
    make_list_reply_payload,
    make_text_payload,
    wa_recorder,
)

_ = wa_recorder


@pytest.fixture(autouse=True)
async def clean_db() -> None:
    """Clean all non-system collections before each test."""
    db = get_db()
    for name in await db.list_collection_names():
        if not name.startswith("system."):
            await db[name].delete_many({})


async def _seed_test_tenant(
    tenant_id: str = "t_menu_test",
    locale_default: str = "en",
    clinic_name: str = "Apex Clinic",
) -> tuple[str, str, str]:
    """Helper to seed isolated tenant, practitioner, slots, and staff."""
    wa_id = "919876543210"
    staff_wa_id = "919999999999"
    practitioner_id = f"doc_{tenant_id}"

    await Tenants(tenant_id).insert_one(
        {
            "_id": tenant_id,
            "name": clinic_name,
            "locale_default": locale_default,
            "timezone": "Asia/Kolkata",
            "booking_lead_minutes": 0,
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

    await Practitioners(tenant_id).insert_one(
        {
            "_id": practitioner_id,
            "tenant_id": tenant_id,
            "name": "Dr. Roy",
            "is_active": True,
        }
    )

    # Seed today and tomorrow slots
    tz = ZoneInfo("Asia/Kolkata")
    now_local = datetime.now(tz)
    s_today = now_local + timedelta(minutes=5)
    e_today = s_today + timedelta(minutes=30)
    await Slots(tenant_id).insert_one(
        {
            "tenant_id": tenant_id,
            "practitioner_id": practitioner_id,
            "service_id": "consultation",
            "service_name": "Consultation",
            "start": s_today.astimezone(UTC).replace(tzinfo=None),
            "end": e_today.astimezone(UTC).replace(tzinfo=None),
            "status": "open",
        }
    )

    tomorrow = (now_local + timedelta(days=1)).date()
    for hour in [10, 11, 14]:
        s = datetime(tomorrow.year, tomorrow.month, tomorrow.day, hour, 0, tzinfo=tz)
        e = s + timedelta(minutes=30)
        await Slots(tenant_id).insert_one(
            {
                "tenant_id": tenant_id,
                "practitioner_id": practitioner_id,
                "service_id": "consultation",
                "service_name": "Consultation",
                "start": s.astimezone(UTC).replace(tzinfo=None),
                "end": e.astimezone(UTC).replace(tzinfo=None),
                "status": "open",
            }
        )

    # Seed FAQ KB entries
    await KbEntries(tenant_id).insert_one(
        {
            "tenant_id": tenant_id,
            "key": "faq_hours",
            "question": "What are your hours?",
            "answer": "We are open from 9:00 AM to 6:00 PM Monday through Saturday.",
        }
    )
    await KbEntries(tenant_id).insert_one(
        {
            "tenant_id": tenant_id,
            "key": "faq_location",
            "question": "Where are you located?",
            "answer": "We are located near Main Market, Bhubaneswar, opposite HDFC Bank.",
        }
    )

    return tenant_id, wa_id, staff_wa_id


async def test_unrecognised_message_sends_apology_and_menu(
    wa_recorder: WhatsAppRecorder,
) -> None:
    """Out-of-scope message produces short apology text followed by 5-item interactive menu."""
    tenant_id, wa_id, _ = await _seed_test_tenant()

    payload = make_text_payload(wa_id, "what is the weather today in mumbai", "wamid.oos.1")
    await process_event(
        {
            "tenant_id": tenant_id,
            "message_id": "wamid.oos.1",
            "payload": json.dumps(payload),
        }
    )

    assert len(wa_recorder.messages) == 2
    # 1. Apology text
    msg_apology = wa_recorder.messages[0]
    assert msg_apology["body"]["type"] == "text"
    apology_text = msg_apology["body"]["text"]["body"]
    assert apology_text == TEMPLATES["out_of_scope"]["en"]
    assert "1. " not in apology_text
    assert "Here is what I can do" not in apology_text

    # 2. Interactive capability menu
    msg_menu = wa_recorder.messages[1]
    assert msg_menu["body"]["type"] == "interactive"
    interactive = msg_menu["body"]["interactive"]
    assert interactive["type"] == "list"
    assert interactive["body"]["text"] == STRINGS["menu.prompt"]["en"]
    assert interactive["action"]["button"] == STRINGS["menu.button"]["en"]
    assert len(interactive["action"]["button"]) <= 20

    rows = interactive["action"]["sections"][0]["rows"]
    assert len(rows) == 5
    row_ids = [r["id"] for r in rows]
    assert row_ids == [
        "menu:book",
        "menu:hours",
        "menu:location",
        "menu:status",
        "menu:human",
    ]
    for r in rows:
        assert len(r["title"]) <= 24

    # Verify interactive flow was logged
    recorded_menu = await Messages(tenant_id).find_one({"flow": "menu"})
    assert recorded_menu is not None


async def test_unrecognised_message_in_hindi(
    wa_recorder: WhatsAppRecorder,
) -> None:
    """Out-of-scope message in Hindi produces Hindi apology and Hindi capability menu."""
    tenant_id, wa_id, _ = await _seed_test_tenant(locale_default="hi")

    payload = make_text_payload(wa_id, "आज का मौसम कैसा रहेगा", "wamid.oos.hi")
    await process_event(
        {
            "tenant_id": tenant_id,
            "message_id": "wamid.oos.hi",
            "payload": json.dumps(payload),
        }
    )

    assert len(wa_recorder.messages) == 2
    # Apology in Hindi
    apology_text = wa_recorder.messages[0]["body"]["text"]["body"]
    assert apology_text == TEMPLATES["out_of_scope"]["hi"]
    assert "1. " not in apology_text

    # Menu in Hindi
    menu_body = wa_recorder.messages[1]["body"]["interactive"]
    assert menu_body["body"]["text"] == STRINGS["menu.prompt"]["hi"]
    assert menu_body["action"]["button"] == STRINGS["menu.button"]["hi"]
    rows = menu_body["action"]["sections"][0]["rows"]
    assert rows[0]["title"] == STRINGS["menu.book"]["hi"]
    assert rows[1]["title"] == STRINGS["menu.hours"]["hi"]
    assert rows[2]["title"] == STRINGS["menu.location"]["hi"]
    assert rows[3]["title"] == STRINGS["menu.status"]["hi"]
    assert rows[4]["title"] == STRINGS["menu.human"]["hi"]


async def test_menu_tap_book(
    wa_recorder: WhatsAppRecorder,
) -> None:
    """Tapping menu:book routes deterministically to booking slot picker."""
    tenant_id, wa_id, _ = await _seed_test_tenant()

    # Pre-seed contact
    await Contacts(tenant_id).insert_one(
        {
            "tenant_id": tenant_id,
            "wa_id": wa_id,
            "name": "Patient",
            "lang_pref": "en",
            "last_inbound_ts": datetime.now(UTC).replace(tzinfo=None),
        }
    )

    payload = make_list_reply_payload(
        wa_id=wa_id,
        slot_id="menu:book",
        title="Book appointment",
        msg_id="wamid.tap.book",
    )
    await process_event(
        {
            "tenant_id": tenant_id,
            "message_id": "wamid.tap.book",
            "payload": json.dumps(payload),
        }
    )

    assert len(wa_recorder.messages) == 1
    outbound = wa_recorder.messages[0]
    assert outbound["body"]["type"] == "interactive"
    assert outbound["body"]["interactive"]["type"] == "list"
    rows = outbound["body"]["interactive"]["action"]["sections"][0]["rows"]
    assert len(rows) > 0
    assert rows[0]["id"].startswith("slot:")

    # Verify inbound was stored exactly once with action_id="menu:book"
    inbound_msgs = await Messages(tenant_id).find({"direction": "inbound"}).to_list(10)
    assert len(inbound_msgs) == 1
    assert inbound_msgs[0].get("action_id") == "menu:book"


async def test_menu_tap_hours_and_location(
    wa_recorder: WhatsAppRecorder,
) -> None:
    """Tapping menu:hours and menu:location routes to FAQ answers."""
    tenant_id, wa_id, _ = await _seed_test_tenant()

    # 1. Hours tap
    payload_hours = make_list_reply_payload(
        wa_id=wa_id,
        slot_id="menu:hours",
        title="Clinic timings",
        msg_id="wamid.tap.hours",
    )
    await process_event(
        {
            "tenant_id": tenant_id,
            "message_id": "wamid.tap.hours",
            "payload": json.dumps(payload_hours),
        }
    )

    assert len(wa_recorder.messages) == 1
    assert "9:00 AM to 6:00 PM" in wa_recorder.messages[0]["body"]["text"]["body"]

    # 2. Location tap
    payload_loc = make_list_reply_payload(
        wa_id=wa_id,
        slot_id="menu:location",
        title="Location",
        msg_id="wamid.tap.loc",
    )
    await process_event(
        {
            "tenant_id": tenant_id,
            "message_id": "wamid.tap.loc",
            "payload": json.dumps(payload_loc),
        }
    )

    assert len(wa_recorder.messages) == 2
    assert "Main Market, Bhubaneswar" in wa_recorder.messages[1]["body"]["text"]["body"]


async def test_menu_tap_status(
    wa_recorder: WhatsAppRecorder,
) -> None:
    """Tapping menu:status routes to appointment status."""
    tenant_id, wa_id, _ = await _seed_test_tenant()

    # Seed contact and booking
    contact_res = await Contacts(tenant_id).insert_one(
        {
            "tenant_id": tenant_id,
            "wa_id": wa_id,
            "name": "Patient",
            "lang_pref": "en",
            "last_inbound_ts": datetime.now(UTC).replace(tzinfo=None),
        }
    )
    slot = await Slots(tenant_id).find_one({"status": "open"})
    assert slot is not None
    await Slots(tenant_id).update_one({"_id": slot["_id"]}, {"$set": {"status": "booked"}})
    await Bookings(tenant_id).insert_one(
        {
            "tenant_id": tenant_id,
            "contact_id": str(contact_res.inserted_id),
            "slot_id": str(slot["_id"]),
            "status": "confirmed",
            "created_at": datetime.now(UTC).replace(tzinfo=None),
        }
    )

    payload = make_list_reply_payload(
        wa_id=wa_id,
        slot_id="menu:status",
        title="My appointment",
        msg_id="wamid.tap.status",
    )
    await process_event(
        {
            "tenant_id": tenant_id,
            "message_id": "wamid.tap.status",
            "payload": json.dumps(payload),
        }
    )

    assert len(wa_recorder.messages) == 1
    reply = wa_recorder.messages[0]["body"]["text"]["body"]
    assert "confirmed" in reply.lower()


async def test_menu_tap_human(
    wa_recorder: WhatsAppRecorder,
) -> None:
    """Tapping menu:human triggers escalation and hands off conversation."""
    tenant_id, wa_id, _ = await _seed_test_tenant()

    payload = make_list_reply_payload(
        wa_id=wa_id,
        slot_id="menu:human",
        title="Talk to staff",
        msg_id="wamid.tap.human",
    )
    await process_event(
        {
            "tenant_id": tenant_id,
            "message_id": "wamid.tap.human",
            "payload": json.dumps(payload),
        }
    )

    # 1. Staff alert template
    # 2. Patient handoff ack
    assert len(wa_recorder.messages) == 2
    assert wa_recorder.messages[0]["body"]["type"] == "template"
    assert wa_recorder.messages[0]["body"]["template"]["name"] == "escalation_alert_staff"

    patient_msg = wa_recorder.messages[1]["body"]["text"]["body"]
    assert patient_msg == TEMPLATES["handoff_ack"]["en"]

    # Verify conversation state is human
    contact = await Contacts(tenant_id).find_one({"wa_id": wa_id})
    assert contact is not None
    convo = await Conversations(tenant_id).find_one(
        {"contact_id": {"$in": mongo_id_candidates(str(contact["_id"]))}}
    )
    assert convo is not None
    assert convo.get("state") == "human"

    # Verify escalation was logged
    open_esc = await Escalations(tenant_id).count_documents({"status": "open"})
    assert open_esc == 1


async def test_hindi_conversation_stays_hindi_after_menu_tap(
    wa_recorder: WhatsAppRecorder,
) -> None:
    """Hindi conversation retains Hindi language context and replies after tapping English synthetic menu action."""
    tenant_id, wa_id, _ = await _seed_test_tenant(locale_default="hi")

    # 1. Start with Hindi out of scope query
    payload_oos = make_text_payload(wa_id, "मौसम कैसा है आज", "wamid.hi.1")
    await process_event(
        {
            "tenant_id": tenant_id,
            "message_id": "wamid.hi.1",
            "payload": json.dumps(payload_oos),
        }
    )
    wa_recorder.clear()

    # 2. Tap menu:book
    payload_book = make_list_reply_payload(
        wa_id=wa_id,
        slot_id="menu:book",
        title="अपॉइंटमेंट बुक करें",
        msg_id="wamid.hi.tap",
    )
    await process_event(
        {
            "tenant_id": tenant_id,
            "message_id": "wamid.hi.tap",
            "payload": json.dumps(payload_book),
        }
    )

    assert len(wa_recorder.messages) == 1
    interactive = wa_recorder.messages[0]["body"]["interactive"]
    # Verify button label and prompt are in Hindi
    assert interactive["action"]["button"] == STRINGS["ui.choose_time"]["hi"]
    assert "समय चुनें" in interactive["body"]["text"]

    # Verify conversation language in DB is still 'hi'
    contact = await Contacts(tenant_id).find_one({"wa_id": wa_id})
    assert contact is not None
    convo = await Conversations(tenant_id).find_one(
        {"contact_id": {"$in": mongo_id_candidates(str(contact["_id"]))}}
    )
    assert convo is not None
    assert convo.get("lang") == "hi"


async def test_no_menu_sent_when_reply_escalated(
    wa_recorder: WhatsAppRecorder,
) -> None:
    """When a bot reply is an escalation, no capability menu list is sent."""
    tenant_id, wa_id, _ = await _seed_test_tenant()

    # Send restricted advice (escalates immediately)
    payload = make_text_payload(wa_id, "my tooth hurts what medicine to take", "wamid.med")
    await process_event(
        {
            "tenant_id": tenant_id,
            "message_id": "wamid.med",
            "payload": json.dumps(payload),
        }
    )

    # 1 staff template + 1 refusal text to patient. No menu list!
    assert len(wa_recorder.messages) == 2
    types = [m["body"]["type"] for m in wa_recorder.messages]
    assert "template" in types
    assert "text" in types
    assert "interactive" not in types


async def test_unknown_menu_id_falls_through_safely(
    wa_recorder: WhatsAppRecorder,
) -> None:
    """An unknown menu ID does not crash and is handled safely as out_of_scope."""
    tenant_id, wa_id, _ = await _seed_test_tenant()

    payload = make_list_reply_payload(
        wa_id=wa_id,
        slot_id="menu:xyz_unknown",
        title="Unknown action",
        msg_id="wamid.unknown",
    )
    await process_event(
        {
            "tenant_id": tenant_id,
            "message_id": "wamid.unknown",
            "payload": json.dumps(payload),
        }
    )

    # Unknown action was parsed as text "Unknown action", which is out_of_scope -> apology + menu
    assert len(wa_recorder.messages) == 2
    assert wa_recorder.messages[0]["body"]["type"] == "text"
    assert wa_recorder.messages[1]["body"]["type"] == "interactive"


async def test_send_menu_window_closed() -> None:
    """send_menu raises WindowClosedError outside 24h CS window."""
    tenant_id = "t_win_closed"
    wa_id = "919876543210"
    await Tenants(tenant_id).insert_one(
        {
            "_id": tenant_id,
            "name": "Clinic",
            "whatsapp": {"phone_number_id": "123", "access_token_env": "TOKEN"},
        }
    )
    # Contact with expired last_inbound_ts (25 hours ago)
    past = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=25)
    await Contacts(tenant_id).insert_one(
        {"tenant_id": tenant_id, "wa_id": wa_id, "last_inbound_ts": past}
    )

    with pytest.raises(WindowClosedError):
        await send_menu(
            tenant_id,
            wa_id,
            prompt="Options",
            button_label="Options",
            rows=[{"id": "menu:book", "title": "Book"}],
            operation_key="op_test",
        )
