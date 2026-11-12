"""Tests for structured understanding node and single-turn booking execution (W2-03)."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from app.agent.graph import build_graph
from app.agent.nodes.intent import (
    build_intent_prompts,
    parse_understanding,
)
from app.agent.nodes.tool_router import tool_router
from app.agent.profile import BusinessProfile
from app.booking.relative_date import resolve_or_none
from app.models.base import get_db
from app.models.collections import Messages, Slots
from app.workers.inbound import process_event


def test_parse_understanding_full_partial_and_intent_only() -> None:
    today = date(2026, 11, 12)

    # 1. Full JSON response
    full_json = json.dumps({
        "intent": "book",
        "confidence": 0.95,
        "date": "2026-11-15",
        "time": "14:30",
        "practitioner_hint": "Dr. Sharma",
        "service_hint": "Cleaning",
    })
    parsed_full = parse_understanding(full_json, today=today)
    assert parsed_full["intent"] == "book"
    assert parsed_full["confidence"] == 0.95
    assert parsed_full["req_date"] == "2026-11-15"
    assert parsed_full["req_time"] == "14:30"
    assert parsed_full["practitioner_hint"] == "Dr. Sharma"
    assert parsed_full["service_hint"] == "Cleaning"

    # 2. Partial JSON (date only, null time/hints)
    partial_json = json.dumps({
        "intent": "reschedule",
        "confidence": 0.88,
        "date": "2026-11-20",
        "time": None,
        "practitioner_hint": None,
        "service_hint": None,
    })
    parsed_partial = parse_understanding(partial_json, today=today)
    assert parsed_partial["intent"] == "reschedule"
    assert parsed_partial["req_date"] == "2026-11-20"
    assert "req_time" not in parsed_partial
    assert "practitioner_hint" not in parsed_partial
    assert "service_hint" not in parsed_partial

    # 3. Intent-only JSON (mock LLM compatibility)
    intent_only = json.dumps({
        "intent": "greet",
        "confidence": 0.99,
    })
    parsed_intent = parse_understanding(intent_only, today=today)
    assert parsed_intent["intent"] == "greet"
    assert parsed_intent["confidence"] == 0.99
    assert "req_date" not in parsed_intent


def test_parse_understanding_drops_invalid_fields() -> None:
    today = date(2026, 11, 12)

    # Past date dropped
    past_json = json.dumps({
        "intent": "book",
        "confidence": 0.9,
        "date": "2026-11-10",  # past
        "time": "25:99",       # invalid time
    })
    parsed_past = parse_understanding(past_json, today=today)
    assert "req_date" not in parsed_past
    assert "req_time" not in parsed_past

    # Far future (> 90 days) dropped
    far_future = today + timedelta(days=95)
    future_json = json.dumps({
        "intent": "book",
        "confidence": 0.9,
        "date": far_future.isoformat(),
        "time": "12:00",
    })
    parsed_future = parse_understanding(future_json, today=today)
    assert "req_date" not in parsed_future
    assert parsed_future["req_time"] == "12:00"

    # Malformed date string dropped
    bad_date_json = json.dumps({
        "intent": "book",
        "confidence": 0.9,
        "date": "tomorrow",
    })
    parsed_bad_date = parse_understanding(bad_date_json, today=today)
    assert "req_date" not in parsed_bad_date


def test_prompt_builder_structure_and_mock_coupling() -> None:
    profile = BusinessProfile(name="City Care Clinic", business_type="clinic")
    sys_prompt, user_prompt = build_intent_prompts(
        "kal subah 10 baje",
        "hi-Latn",
        profile=profile,
        today_iso="2026-11-12",
        weekday="Thursday",
        history="Patient: hello\nClinic: Namaste! How can I help?",
    )

    # System prompt mentions today
    assert "Today is Thursday, 2026-11-12" in sys_prompt
    assert "date" in sys_prompt
    assert "time" in sys_prompt

    # User prompt ends exactly with the User message line (required for mock regex)
    lines = user_prompt.strip().splitlines()
    assert lines[-1] == "User message: 'kal subah 10 baje'"
    assert "Language detected: hi-Latn" in user_prompt
    assert "Patient: hello" in user_prompt


def test_history_apostrophes_neutralized() -> None:
    """Apostrophes in history must be replaced with right single quote ’ to avoid breaking mock regex."""
    raw_history = "Patient: it's hurting\nClinic: don't worry"
    # Even if history has quotes, when passed into prompt it replaces ' with ’
    sys_prompt, user_prompt = build_intent_prompts(
        "help me",
        "en",
        today_iso="2026-11-12",
        weekday="Thursday",
        history=raw_history.replace("'", "’"),
    )
    assert "it’s hurting" in user_prompt
    assert "don’t worry" in user_prompt
    assert user_prompt.endswith("User message: 'help me'")


def test_relative_date_resolve_or_none() -> None:
    today = date(2026, 11, 12)
    # Explicit match returns date
    assert resolve_or_none("kal", today=today, lang="hi-Latn") == today + timedelta(days=1)
    assert resolve_or_none("parso", today=today, lang="hi-Latn") == today + timedelta(days=2)
    assert resolve_or_none("aaj", today=today, lang="hi-Latn") == today
    # No match returns None
    assert resolve_or_none("hello can you help", today=today, lang="en") is None


@pytest.mark.asyncio
async def test_tool_router_date_priority_and_disagreement_logging() -> None:
    tenant_id = "t_router_test"
    db = get_db()
    await db["tenants"].delete_many({})
    await db["tenants"].insert_one({
        "_id": tenant_id,
        "name": "Router Clinic",
        "timezone": "Asia/Kolkata",
    })
    await db["practitioners"].delete_many({})
    await db["practitioners"].insert_one({
        "tenant_id": tenant_id,
        "name": "Dr. Rao",
        "status": "active",
    })

    # Case 1: parser explicit keyword ("parso") matches today + 2,
    # but model erroneously returned today + 1. Parser wins!
    today = date(2026, 11, 12)
    state: dict[str, Any] = {
        "tenant_id": tenant_id,
        "intent": "book",
        "text": "parso appointment chahiye",
        "lang": "hi-Latn",
        "req_date": (today + timedelta(days=1)).isoformat(),
    }
    res = await tool_router(state)
    assert len(res["tool_results"]) == 1
    # Should prefer parser date: today + 2
    assert res["tool_results"][0]["date"] == (today + timedelta(days=2)).isoformat()

    # Case 2: text has no relative date keyword, model provided req_date. Model req_date wins!
    state_2: dict[str, Any] = {
        "tenant_id": tenant_id,
        "intent": "book",
        "text": "appointment please",
        "lang": "en",
        "req_date": (today + timedelta(days=5)).isoformat(),
    }
    res_2 = await tool_router(state_2)
    assert res_2["tool_results"][0]["date"] == (today + timedelta(days=5)).isoformat()


@pytest.mark.asyncio
async def test_tool_router_slots_ordered_by_req_time() -> None:
    tenant_id = "t_slot_sort"
    db = get_db()
    for col in await db.list_collection_names():
        if not col.startswith("system."):
            await db[col].delete_many({})

    await db["tenants"].insert_one({
        "_id": tenant_id,
        "name": "Sort Clinic",
        "timezone": "Asia/Kolkata",
    })
    prac_res = await db["practitioners"].insert_one({
        "tenant_id": tenant_id,
        "name": "Dr. Verma",
        "status": "active",
    })
    practitioner_id = str(prac_res.inserted_id)

    # Seed 3 slots on 2026-11-13 at 09:00, 14:00, 18:00 IST
    # Asia/Kolkata is UTC+5:30 -> 09:00 IST is 03:30 UTC, 14:00 IST is 08:30 UTC, 18:00 IST is 12:30 UTC
    target_d = date(2026, 11, 13)
    s1 = datetime(2026, 11, 13, 3, 30, tzinfo=UTC).replace(tzinfo=None)
    s2 = datetime(2026, 11, 13, 8, 30, tzinfo=UTC).replace(tzinfo=None)
    s3 = datetime(2026, 11, 13, 12, 30, tzinfo=UTC).replace(tzinfo=None)

    for st in [s1, s2, s3]:
        await Slots(tenant_id).insert_one({
            "practitioner_id": practitioner_id,
            "start": st,
            "end": st + timedelta(minutes=30),
            "status": "open",
        })

    # Request time at 15:00 (closest to s2: 14:00, then s3: 18:00, then s1: 09:00)
    state: dict[str, Any] = {
        "tenant_id": tenant_id,
        "intent": "book",
        "text": "3 pm appointment",
        "lang": "en",
        "req_date": target_d.isoformat(),
        "req_time": "15:00",
    }
    router_res = await tool_router(state)
    slots = router_res["tool_results"][0]["result"]
    assert len(slots) == 3
    # First slot should be 14:00 IST (diff 60 mins from 15:00)
    first_start = datetime.fromisoformat(slots[0]["start"]).astimezone(ZoneInfo("Asia/Kolkata"))
    assert first_start.hour == 14
    assert router_res["tool_results"][0]["requested_time"] == "15:00"


@pytest.mark.asyncio
async def test_single_llm_call_on_whatsapp_booking(monkeypatch: pytest.MonkeyPatch) -> None:
    """WhatsApp booking intents must make exactly ONE LLM call (intent/understand) and skip responder."""
    import app.agent.nodes.intent as intent_module
    import app.agent.nodes.responder as responder_module

    call_counts = {"intent": 0, "responder": 0}

    orig_query = intent_module.query_llm

    async def counted_query(prompt: str, model: str, **kwargs: Any) -> str:
        node = kwargs.get("node")
        if node == "intent":
            call_counts["intent"] += 1
        elif node == "responder":
            call_counts["responder"] += 1
        return await orig_query(prompt, model, **kwargs)

    monkeypatch.setattr(intent_module, "query_llm", counted_query)
    monkeypatch.setattr(responder_module, "query_llm", counted_query)

    graph = build_graph()

    # 1. WhatsApp channel -> skips responder after tool_router
    wa_state: dict[str, Any] = {
        "tenant_id": "t_test_calls",
        "channel": "wa",
        "text": "book an appointment",
        "lang": "en",
    }
    await graph.ainvoke(wa_state)
    assert call_counts["intent"] == 1
    assert call_counts["responder"] == 0

    # 2. Voice channel -> does NOT skip responder (voice has no tappable menus)
    voice_state: dict[str, Any] = {
        "tenant_id": "t_test_calls",
        "channel": "voice",
        "text": "book an appointment",
        "lang": "en",
    }
    await graph.ainvoke(voice_state)
    assert call_counts["intent"] == 2
    assert call_counts["responder"] == 1


@pytest.mark.asyncio
async def test_no_slots_day_yields_booking_no_slots_message() -> None:
    """When tool_router finds no available slots for book/reschedule, reply with booking.no_slots."""
    tenant_id = "t_no_slots"
    wa_id = "919876543299"
    db = get_db()
    for col in await db.list_collection_names():
        if not col.startswith("system."):
            await db[col].delete_many({})

    await db["tenants"].insert_one({
        "_id": tenant_id,
        "name": "No Slots Clinic",
        "timezone": "Asia/Kolkata",
        "status": "active",
    })
    await db["contacts"].insert_one({
        "tenant_id": tenant_id,
        "wa_id": wa_id,
        "phone": wa_id,
        "name": "No Slots Patient",
        "last_inbound_ts": datetime.now(UTC).replace(tzinfo=None),
    })
    # Practitioner exists, but 0 open slots
    await db["practitioners"].insert_one({
        "tenant_id": tenant_id,
        "name": "Dr. Busy",
        "status": "active",
    })

    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "contacts": [{"wa_id": wa_id, "profile": {"name": "No Slots Patient"}}],
                            "messages": [{"from": wa_id, "id": "msg-no-slots-1", "type": "text", "text": {"body": "book appointment for tomorrow"}}],
                        }
                    }
                ]
            }
        ]
    }
    await process_event({"tenant_id": tenant_id, "message_id": "msg-no-slots-1", "payload": json.dumps(payload)})

    # Outbound text message should contain the booking.no_slots text
    last_msg = await Messages(tenant_id).find_one({"direction": "outbound", "type": "text"}, sort=[("ts", -1)])
    assert last_msg is not None
    assert "No appointments are available on" in last_msg["text"]
    assert "Please send another day" in last_msg["text"]
