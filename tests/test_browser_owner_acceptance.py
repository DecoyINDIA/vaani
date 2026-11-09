from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from app.main import app
from app.models.base import get_db
from app.models.collections import (
    Bookings,
    Contacts,
    Conversations,
    Escalations,
    KbEntries,
    Messages,
    Slots,
    Tenants,
    Users,
)
from app.owner_api.auth import create_access_token, create_purpose_token, token_hash
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
async def clean_database() -> None:
    db = get_db()
    for col in await db.list_collection_names():
        if not col.startswith("system."):
            await db[col].delete_many({})

    # Seed test tenants and users
    for tenant_id in ("tenant-alpha", "tenant-beta"):
        await db["tenants"].insert_one({
            "_id": tenant_id,
            "name": f"Clinic {tenant_id}",
            "wa_number": f"91{tenant_id[:10].replace('-', '0')}",
            "landmark_line": f"Landmark for {tenant_id}",
            "location_pin": f"https://maps.example.com/{tenant_id}",
            "timezone": "Asia/Kolkata",
        })
        await db["users"].insert_many([
            {
                "_id": f"owner-{tenant_id}",
                "tenant_id": tenant_id,
                "role": "owner",
                "status": "active",
            },
            {
                "_id": f"staff-{tenant_id}",
                "tenant_id": tenant_id,
                "role": "staff",
                "status": "active",
            },
        ])


def test_dashboard_serves_spa_deep_links_and_responsive_assets() -> None:
    client = TestClient(app)

    # 1. Root loading
    resp_root = client.get("/")
    assert resp_root.status_code == 200
    assert "text/html" in resp_root.headers.get("content-type", "")
    assert '<div id="root"></div>' in resp_root.text
    assert '<meta name="viewport" content="width=device-width, initial-scale=1.0"' in resp_root.text

    # 2. Deep link with invitation token query parameter
    resp_deep = client.get("/?token=synthetic_invitation_token_123")
    assert resp_deep.status_code == 200
    assert "text/html" in resp_deep.headers.get("content-type", "")
    assert '<div id="root"></div>' in resp_deep.text

    # 3. Discover and fetch stylesheet and script bundles
    css_match = re.search(r'href="(/assets/[^"]+\.css)"', resp_root.text)
    js_match = re.search(r'src="(/assets/[^"]+\.js)"', resp_root.text)

    if css_match:
        css_path = css_match.group(1)
        resp_css = client.get(css_path)
        assert resp_css.status_code == 200
        assert "text/css" in resp_css.headers.get("content-type", "")
        # Verify responsive breakpoints for mobile/tablet layouts
        assert "@media" in resp_css.text and ("860px" in resp_css.text or "max-width" in resp_css.text)

    if js_match:
        js_path = js_match.group(1)
        resp_js = client.get(js_path)
        assert resp_js.status_code == 200
        # Verify script contains key API route bindings
        assert "/api/auth/magic/consume" in resp_js.text or "magic/consume" in resp_js.text


async def test_owner_invitation_staff_magic_login_and_session_renewal() -> None:
    client = TestClient(app)
    owner_token = create_access_token("tenant-alpha", "owner-tenant-alpha")
    staff_token = create_access_token("tenant-alpha", "staff-tenant-alpha")

    # 1. Staff cannot issue invitations (403 Forbidden)
    denied = client.post(
        "/api/auth/invitations",
        json={"user_id": "new-staff-1", "role": "staff"},
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert denied.status_code == 403

    # 2. Owner issues invitation for new staff
    invitation = client.post(
        "/api/auth/invitations",
        json={"user_id": "new-staff-1", "role": "staff"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert invitation.status_code == 200
    magic_token = invitation.json()["magic_token"]
    assert magic_token

    # 3. Staff consumes magic link
    consumed = client.post("/api/auth/magic/consume", json={"token": magic_token})
    assert consumed.status_code == 200
    tokens = consumed.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens

    # 4. Magic link is single-use: replay returns 401
    replay = client.post("/api/auth/magic/consume", json={"token": magic_token})
    assert replay.status_code == 401

    # 5. Access token can reach staff routes
    active_client = client.get(
        "/api/conversations",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert active_client.status_code == 200

    # 6. Session renewal with refresh token
    rotated = client.post("/api/auth/refresh", json={"token": tokens["refresh_token"]})
    assert rotated.status_code == 200
    new_tokens = rotated.json()

    # Old refresh token is revoked
    replayed_refresh = client.post("/api/auth/refresh", json={"token": tokens["refresh_token"]})
    assert replayed_refresh.status_code == 401

    # 7. Removed membership immediately denies access
    await Users("tenant-alpha").update_one(
        {"_id": "new-staff-1"},
        {"$set": {"status": "removed"}},
    )
    assert client.get(
        "/api/conversations",
        headers={"Authorization": f"Bearer {new_tokens['access_token']}"},
    ).status_code == 401
    assert client.post(
        "/api/auth/refresh",
        json={"token": new_tokens["refresh_token"]},
    ).status_code == 401

    # 8. Re-activated member can logout session
    await Users("tenant-alpha").update_one(
        {"_id": "new-staff-1"},
        {"$set": {"status": "active"}},
    )
    logout = client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {new_tokens['access_token']}"},
    )
    assert logout.status_code == 200
    # Access token session is revoked
    assert client.get(
        "/api/conversations",
        headers={"Authorization": f"Bearer {new_tokens['access_token']}"},
    ).status_code == 401


async def test_expired_magic_link_rejected() -> None:
    expired_at = datetime.now(UTC) - timedelta(seconds=10)
    token, token_id = create_purpose_token(
        "tenant-alpha", "staff-expired", "magic", expired_at
    )
    await Users("tenant-alpha").insert_one({
        "_id": "staff-expired",
        "role": "staff",
        "status": "invited",
        "magic_hash": token_hash(token_id),
        "magic_expires_at": expired_at.replace(tzinfo=None),
    })
    client = TestClient(app)
    assert client.post("/api/auth/magic/consume", json={"token": token}).status_code == 401


async def test_inbox_browser_journey_takeover_reply_and_return() -> None:
    client = TestClient(app)
    staff_token = create_access_token("tenant-alpha", "staff-tenant-alpha")
    headers = {"Authorization": f"Bearer {staff_token}"}

    # Seed contact, conversation, and escalation
    await Contacts("tenant-alpha").insert_one({
        "_id": "contact-100",
        "tenant_id": "tenant-alpha",
        "wa_id": "919876543210",
        "phone": "919876543210",
    })
    await Conversations("tenant-alpha").insert_one({
        "_id": "conv-100",
        "tenant_id": "tenant-alpha",
        "contact_id": "contact-100",
        "state": "bot",
        "channel": "wa",
        "last_msg_at": datetime.now(UTC).replace(tzinfo=None),
    })
    await Messages("tenant-alpha").insert_one({
        "_id": "msg-inbound-1",
        "tenant_id": "tenant-alpha",
        "conversation_id": "conv-100",
        "direction": "inbound",
        "type": "text",
        "text": "I need help with my tooth ache",
        "ts": datetime.now(UTC).replace(tzinfo=None),
    })
    await Escalations("tenant-alpha").insert_one({
        "_id": "esc-100",
        "tenant_id": "tenant-alpha",
        "conversation_id": "conv-100",
        "status": "open",
        "reason": "Pain inquiry",
        "notification_status": "delivered",
        "ts": datetime.now(UTC).replace(tzinfo=None),
    })

    # 1. Staff lists conversations and messages
    convs = client.get("/api/conversations?limit=10&offset=0", headers=headers)
    assert convs.status_code == 200
    assert any(c["_id"] == "conv-100" for c in convs.json())

    msgs = client.get("/api/conversations/conv-100/messages?limit=20&offset=0", headers=headers)
    assert msgs.status_code == 200
    assert len(msgs.json()) == 1

    # 2. Staff cannot reply without taking over (409 Conflict)
    premature_reply = client.post(
        "/api/conversations/conv-100/reply",
        json={"text": "Hello, we can help", "request_id": "req-1"},
        headers=headers,
    )
    assert premature_reply.status_code == 409
    assert "Take over the conversation" in premature_reply.json()["detail"]

    # 3. Staff takes over
    takeover = client.post("/api/conversations/conv-100/takeover", headers=headers)
    assert takeover.status_code == 200
    assert takeover.json()["state"] == "human"

    conv = await Conversations("tenant-alpha").find_one({"_id": "conv-100"})
    assert conv is not None and conv["state"] == "human"

    # 4. Staff sends reply (with duplicate submit protection)
    with patch("app.owner_api.routes.send_freeform") as mock_send:
        mock_send.return_value = {"status": "sent", "messages": [{"id": "wamid.out-1"}]}
        reply_resp = client.post(
            "/api/conversations/conv-100/reply",
            json={"text": "Please visit tomorrow at 10 AM", "request_id": "req-reply-1"},
            headers=headers,
        )
        assert reply_resp.status_code == 200
        assert reply_resp.json()["status"] == "sent"

        # Duplicate submit with same request_id is deduplicated
        mock_send.return_value = {"status": "sent", "deduplicated": True, "messages": [{"id": "wamid.out-1"}]}
        dup_reply = client.post(
            "/api/conversations/conv-100/reply",
            json={"text": "Please visit tomorrow at 10 AM", "request_id": "req-reply-1"},
            headers=headers,
        )
        assert dup_reply.status_code == 200
        assert dup_reply.json()["deduplicated"] is True

    # 5. Return conversation requires resolution summary
    empty_return = client.post(
        "/api/conversations/conv-100/return",
        json={"summary": "   "},
        headers=headers,
    )
    assert empty_return.status_code == 422

    # Return with summary restores 'bot' state and marks escalation resolved
    valid_return = client.post(
        "/api/conversations/conv-100/return",
        json={"summary": "Advised in-person clinic visit tomorrow"},
        headers=headers,
    )
    assert valid_return.status_code == 200
    assert valid_return.json()["state"] == "bot"

    conv_restored = await Conversations("tenant-alpha").find_one({"_id": "conv-100"})
    assert conv_restored is not None and conv_restored["state"] == "bot"

    esc_resolved = await Escalations("tenant-alpha").find_one({"_id": "esc-100"})
    assert esc_resolved is not None
    assert esc_resolved["status"] == "resolved"
    assert esc_resolved["resolution_summary"] == "Advised in-person clinic visit tomorrow"


async def test_booking_calendar_cancellation_and_rescheduling() -> None:
    client = TestClient(app)
    staff_token = create_access_token("tenant-alpha", "staff-tenant-alpha")
    headers = {"Authorization": f"Bearer {staff_token}"}

    slot_time = datetime(2026, 11, 10, 10, 0, tzinfo=UTC).replace(tzinfo=None)
    slot_time_2 = datetime(2026, 11, 10, 11, 0, tzinfo=UTC).replace(tzinfo=None)

    for s in [
        {
            "_id": "slot-1",
            "tenant_id": "tenant-alpha",
            "practitioner_id": "dr-priya",
            "start": slot_time,
            "status": "booked",
            "booking_id": "booking-1",
        },
        {
            "_id": "slot-2",
            "tenant_id": "tenant-alpha",
            "practitioner_id": "dr-priya",
            "start": slot_time_2,
            "status": "open",
            "booking_id": None,
        },
    ]:
        await Slots("tenant-alpha").insert_one(s)
    await Bookings("tenant-alpha").insert_one({
        "_id": "booking-1",
        "tenant_id": "tenant-alpha",
        "slot_id": "slot-1",
        "contact_id": "contact-1",
        "service": "Consultation",
        "status": "confirmed",
        "ts": slot_time,
    })

    # 1. List bookings
    bookings = client.get("/api/bookings?limit=10&offset=0", headers=headers)
    assert bookings.status_code == 200
    assert any(b["_id"] == "booking-1" for b in bookings.json())

    # 2. Get booking detail
    detail = client.get("/api/bookings/booking-1", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["service"] == "Consultation"

    # 3. Reschedule booking
    reschedule = client.patch(
        "/api/bookings/booking-1",
        json={"status": "rescheduled", "new_slot_id": "slot-2", "request_id": "resched-req-1"},
        headers=headers,
    )
    assert reschedule.status_code == 200

    old_slot = await Slots("tenant-alpha").find_one({"_id": "slot-1"})
    new_slot = await Slots("tenant-alpha").find_one({"_id": "slot-2"})
    assert old_slot is not None and old_slot["status"] == "open"
    assert new_slot is not None and new_slot["status"] == "booked"

    # 4. Cancel booking
    cancel = client.patch(
        "/api/bookings/booking-1",
        json={"status": "cancelled"},
        headers=headers,
    )
    assert cancel.status_code == 200

    cancelled_slot = await Slots("tenant-alpha").find_one({"_id": "slot-2"})
    assert cancelled_slot is not None and cancelled_slot["status"] == "open"
    cancelled_booking = await Bookings("tenant-alpha").find_one({"_id": "booking-1"})
    assert cancelled_booking is not None and cancelled_booking["status"] == "cancelled"


async def test_delivery_and_processing_issue_views_strict_zero_pii() -> None:
    client = TestClient(app)
    staff_token = create_access_token("tenant-alpha", "staff-tenant-alpha")
    headers = {"Authorization": f"Bearer {staff_token}"}
    db = get_db()

    # 1. Outbound delivery issues view
    await db["outbound_intents"].insert_one({
        "_id": "intent-err-1",
        "tenant_id": "tenant-alpha",
        "operation_key": "private:919999999999",
        "to": "919999999999",
        "kind": "template",
        "state": "unknown",
        "attempted_at": datetime.now(UTC).replace(tzinfo=None),
        "last_error": "ProcessInterrupted",
        "payload": {"text": "Private reminder for patient"},
    })

    deliveries = client.get("/api/deliveries?limit=10&offset=0", headers=headers)
    assert deliveries.status_code == 200
    items = deliveries.json()
    assert len(items) == 1
    item = items[0]
    assert item["_id"] == "intent-err-1"
    assert item["state"] == "unknown"
    assert item["kind"] == "template"
    # Strict Zero-PII assertions
    assert "to" not in item
    assert "operation_key" not in item
    assert "payload" not in item
    assert "phone" not in item
    assert "recipient" not in item

    # 2. Inbound processing issues view
    await Messages("tenant-alpha").insert_one({
        "_id": "proc-err-1",
        "tenant_id": "tenant-alpha",
        "status": "failed",
        "attempts": 3,
        "failed_at": datetime.now(UTC).replace(tzinfo=None),
        "fail_reason": "RuntimeError",
        "payload": {"from": "918888888888", "text": "Confidential patient inquiry"},
        "text": "Confidential patient inquiry",
    })

    processing = client.get("/api/processing?limit=10&offset=0", headers=headers)
    assert processing.status_code == 200
    proc_items = processing.json()
    assert len(proc_items) == 1
    proc_item = proc_items[0]
    assert proc_item["_id"] == "proc-err-1"
    assert proc_item["status"] == "failed"
    assert proc_item["attempts"] == 3
    assert proc_item["fail_reason"] == "RuntimeError"
    # Strict Zero-PII assertions
    assert "payload" not in proc_item
    assert "text" not in proc_item
    assert "from" not in proc_item
    assert "wa_id" not in proc_item


async def test_knowledge_base_upsert_and_embedding_persistence() -> None:
    client = TestClient(app)
    staff_token = create_access_token("tenant-alpha", "staff-tenant-alpha")
    headers = {"Authorization": f"Bearer {staff_token}"}

    # 1. Upsert new KB entry
    upsert = client.put(
        "/api/kb",
        json={"question": "What are your hours?", "answer": "Mon-Sat 9am to 6pm", "kind": "faq"},
        headers=headers,
    )
    assert upsert.status_code == 200

    entry = await KbEntries("tenant-alpha").find_one({"question": "What are your hours?"})
    assert entry is not None
    assert entry["answer"] == "Mon-Sat 9am to 6pm"
    assert entry["version"] == 1
    assert "embedding" in entry
    assert entry["embedding_dimensions"] == len(entry["embedding"])

    # 2. Update existing KB entry
    update = client.put(
        "/api/kb",
        json={"question": "What are your hours?", "answer": "Mon-Sun 8am to 8pm", "kind": "faq"},
        headers=headers,
    )
    assert update.status_code == 200

    updated = await KbEntries("tenant-alpha").find_one({"question": "What are your hours?"})
    assert updated is not None
    assert updated["answer"] == "Mon-Sun 8am to 8pm"
    assert updated["version"] == 2

    # 3. Embedding service failure fails gracefully without corrupting entry
    with patch("app.owner_api.routes.embed_text", side_effect=RuntimeError("Embedding outage")):
        fail_resp = client.put(
            "/api/kb",
            json={"question": "What are your hours?", "answer": "Closed forever", "kind": "faq"},
            headers=headers,
        )
        assert fail_resp.status_code == 503
        assert "Knowledge embedding is unavailable" in fail_resp.json()["detail"]

    # Entry is preserved
    preserved = await KbEntries("tenant-alpha").find_one({"question": "What are your hours?"})
    assert preserved is not None
    assert preserved["answer"] == "Mon-Sun 8am to 8pm"


async def test_clinic_settings_role_protection() -> None:
    client = TestClient(app)
    staff_token = create_access_token("tenant-alpha", "staff-tenant-alpha")
    owner_token = create_access_token("tenant-alpha", "owner-tenant-alpha")

    # 1. Staff can read settings
    staff_read = client.get("/api/settings", headers={"Authorization": f"Bearer {staff_token}"})
    assert staff_read.status_code == 200
    assert staff_read.json()["name"] == "Clinic tenant-alpha"

    # 2. Staff cannot update settings (403 Forbidden)
    staff_write = client.put(
        "/api/settings",
        json={"name": "Hacked Clinic", "landmark_line": "None", "location_pin": "None"},
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert staff_write.status_code == 403

    # 3. Owner can update settings
    owner_write = client.put(
        "/api/settings",
        json={"name": "Updated Priya Dental", "landmark_line": "Opposite Metro Station", "location_pin": "https://maps.example.com/priya"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert owner_write.status_code == 200

    updated = await Tenants.find_by_id("tenant-alpha")
    assert updated is not None
    assert updated["name"] == "Updated Priya Dental"
    assert updated["landmark_line"] == "Opposite Metro Station"


async def test_cross_tenant_isolation_boundary_enforced() -> None:
    client = TestClient(app)
    staff_beta = create_access_token("tenant-beta", "staff-tenant-beta")
    headers_beta = {"Authorization": f"Bearer {staff_beta}"}

    # Seed confidential record in Tenant Alpha
    await Conversations("tenant-alpha").insert_one({
        "_id": "alpha-private-conv",
        "tenant_id": "tenant-alpha",
        "state": "bot",
        "channel": "wa",
    })
    await Bookings("tenant-alpha").insert_one({
        "_id": "alpha-private-booking",
        "tenant_id": "tenant-alpha",
        "slot_id": "slot-alpha",
        "contact_id": "contact-alpha",
        "service": "Root Canal",
        "status": "confirmed",
    })

    # Tenant Beta cannot access Tenant Alpha records
    assert client.get("/api/conversations", headers=headers_beta).json() == []
    assert client.get("/api/bookings", headers=headers_beta).json() == []
    assert client.get("/api/conversations/alpha-private-conv/messages", headers=headers_beta).json() == []
    assert client.post("/api/conversations/alpha-private-conv/takeover", headers=headers_beta).status_code == 404
    assert client.patch(
        "/api/bookings/alpha-private-booking",
        json={"status": "cancelled"},
        headers=headers_beta,
    ).status_code == 404
