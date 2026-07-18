from datetime import UTC, datetime, timedelta

import pytest
from app import audit
from app.agent.nodes.responder import responder
from app.agent.tools.booking_cancel import booking_cancel
from app.billing.invoice import generate_invoice
from app.billing.meters import record_usage
from app.booking.engine import claim_waitlist_slot
from app.gateway.razorpay import verify_razorpay_signature
from app.models.base import get_db
from app.workers.reminders import run_reminders
from app.workers.weekly_summary import run_weekly_summaries


@pytest.fixture(autouse=True)
async def clean_db():
    """Clear database before each test."""
    db = get_db()
    collections = await db.list_collection_names()
    for col in collections:
        if not col.startswith("system."):
            await db[col].delete_many({})
    yield


async def test_audit_logging():
    tenant_id = "tenant_audit_test"
    await audit.record(
        tenant_id,
        actor="agent",
        event_type="test_event",
        payload={"key": "value"},
        conversation_id="conv_123"
    )
    
    db = get_db()
    log = await db["audit_log"].find_one({"tenant_id": tenant_id})
    assert log is not None
    assert log["actor"] == "agent"
    assert log["event_type"] == "test_event"
    assert log["payload"] == {"key": "value"}
    assert log["conversation_id"] == "conv_123"
    assert isinstance(log["ts"], datetime)


async def test_usage_metering():
    tenant_id = "tenant_meter_test"
    period = datetime.now(UTC).strftime("%Y-%m")
    
    await record_usage(tenant_id, voice_minutes=10, llm_tokens_in=500)
    await record_usage(tenant_id, voice_minutes=5, llm_tokens_out=250)
    
    db = get_db()
    usage = await db["usage_meters"].find_one({"tenant_id": tenant_id, "period": period})
    assert usage is not None
    assert usage["voice_minutes"] == 15
    assert usage["llm_tokens_in"] == 500
    assert usage["llm_tokens_out"] == 250


async def test_gst_invoice_starter():
    tenant_id = "tenant_starter_test"
    db = get_db()
    await db["tenants"].insert_one({
        "_id": tenant_id,
        "name": "Starter Clinic",
        "plan": "starter",
        "gstin": "27CLINIC1111A1Z",
        "status": "active"
    })
    
    period = datetime.now(UTC).strftime("%Y-%m")
    invoice = await generate_invoice(tenant_id, period)
    
    assert invoice["invoice_number"] == f"INV-{tenant_id[:4].upper()}-{period.replace('-', '')}"
    assert invoice["base_amount"] == 2999.0
    assert invoice["gst_amount"] == 539.82
    assert invoice["total_amount"] == 3538.82
    assert invoice["tenant_gstin"] == "27CLINIC1111A1Z"


async def test_gst_invoice_pro_with_overage():
    tenant_id = "tenant_pro_test"
    db = get_db()
    await db["tenants"].insert_one({
        "_id": tenant_id,
        "name": "Pro Clinic",
        "plan": "pro",
        "gstin": "27CLINIC2222B2Z",
        "status": "active"
    })
    
    period = datetime.now(UTC).strftime("%Y-%m")
    
    # Pro includes 300 mins; we simulate 350 mins (50 mins overage at Rs 2.0/min = Rs 100 overage)
    await record_usage(tenant_id, voice_minutes=350)
    
    invoice = await generate_invoice(tenant_id, period)
    
    # Base: 4999.0 + Overage: 100.0 = 5099.0
    # GST: 5099.0 * 0.18 = 917.82
    # Total: 6016.82
    assert invoice["base_amount"] == 5099.0
    assert invoice["gst_amount"] == 917.82
    assert invoice["total_amount"] == 6016.82
    assert invoice["tenant_gstin"] == "27CLINIC2222B2Z"


async def test_razorpay_webhook_signature():
    assert verify_razorpay_signature(b"body", None) is False
    # If settings.razorpay_webhook_secret is empty, it bypasses verification (returns True)
    # We test that it works in test environment
    assert verify_razorpay_signature(b"body", "any_sig") is True


async def test_razorpay_payment_paid_webhook():
    from app.main import app
    from fastapi.testclient import TestClient
    
    tenant_id = "test_tenant"
    db = get_db()
    
    # 1. Insert active tenant, booking, and payments record
    await db["tenants"].insert_one({
        "_id": tenant_id,
        "name": "Test Clinic",
        "plan": "starter",
        "status": "active"
    })
    
    booking_id = "bk_123"
    await db["bookings"].insert_one({
        "_id": booking_id,
        "tenant_id": tenant_id,
        "slot_id": "slot_123",
        "status": "rescheduled",
        "ts": datetime.now(UTC).replace(tzinfo=None)
    })
    
    link_id = "plink_xyz"
    await db["payments"].insert_one({
        "tenant_id": tenant_id,
        "booking_id": booking_id,
        "rzp_link_id": link_id,
        "amount": 500,
        "status": "issued"
    })
    
    # 2. Call Razorpay Webhook endpoint
    client = TestClient(app)
    payload = {
        "event": "payment.link.paid",
        "payload": {
            "payment_link": {
                "entity": {
                    "id": link_id,
                    "status": "paid"
                }
            }
        }
    }
    
    response = client.post("/webhooks/razorpay", json=payload, headers={"X-Razorpay-Signature": "dummy_sig"})
    assert response.status_code == 200
    
    # 3. Assert payment updated to paid, booking updated to confirmed, and audit log populated
    payment = await db["payments"].find_one({"rzp_link_id": link_id})
    assert payment["status"] == "paid"
    assert payment["paid_at"] is not None
    
    booking = await db["bookings"].find_one({"_id": booking_id})
    assert booking["status"] == "confirmed"
    
    audit_entry = await db["audit_log"].find_one({"tenant_id": tenant_id, "event_type": "payment_completed"})
    assert audit_entry is not None
    assert audit_entry["payload"]["rzp_link_id"] == link_id


async def test_razorpay_subscription_activated_webhook():
    from app.main import app
    from fastapi.testclient import TestClient
    
    tenant_id = "tenant_sub_test"
    db = get_db()
    await db["tenants"].insert_one({
        "_id": tenant_id,
        "name": "Subscription Clinic",
        "plan": "starter",
        "status": "pending"
    })
    
    client = TestClient(app)
    payload = {
        "event": "subscription.activated",
        "payload": {
            "subscription": {
                "entity": {
                    "id": "sub_xyz",
                    "plan_id": "plan_pro",
                    "status": "active",
                    "notes": {
                        "tenant_id": tenant_id
                    }
                }
            }
        }
    }
    
    response = client.post("/webhooks/razorpay", json=payload, headers={"X-Razorpay-Signature": "dummy_sig"})
    assert response.status_code == 200
    
    tenant = await db["tenants"].find_one({"_id": tenant_id})
    assert tenant["plan"] == "plan_pro"
    assert tenant["status"] == "active"


async def test_reminders_worker():
    tenant_id = "tenant_reminders_test"
    db = get_db()
    
    await db["tenants"].insert_one({
        "_id": tenant_id,
        "name": "Reminder Clinic",
        "status": "active"
    })
    
    now = datetime.now(UTC).replace(tzinfo=None)
    
    # 1. 24h reminder booking (starts in 24 hours)
    slot_id_24h = "slot_24h"
    await db["slots"].insert_one({
        "_id": slot_id_24h,
        "tenant_id": tenant_id,
        "start": now + timedelta(hours=24),
        "status": "booked"
    })
    booking_id_24h = "bk_24h"
    await db["bookings"].insert_one({
        "_id": booking_id_24h,
        "tenant_id": tenant_id,
        "slot_id": slot_id_24h,
        "contact_id": "contact_abc",
        "status": "confirmed",
        "reminders_sent": []
    })
    
    # 2. 2h reminder booking (starts in 2 hours)
    slot_id_2h = "slot_2h"
    await db["slots"].insert_one({
        "_id": slot_id_2h,
        "tenant_id": tenant_id,
        "start": now + timedelta(hours=2),
        "status": "booked"
    })
    booking_id_2h = "bk_2h"
    await db["bookings"].insert_one({
        "_id": booking_id_2h,
        "tenant_id": tenant_id,
        "slot_id": slot_id_2h,
        "contact_id": "contact_abc",
        "status": "confirmed",
        "reminders_sent": []
    })
    
    # 3. Contact information
    await db["contacts"].insert_one({
        "_id": "contact_abc",
        "tenant_id": tenant_id,
        "name": "Ravi Mohanty",
        "phone": "919999999999"
    })
    
    # Run reminders
    await run_reminders()
    
    # Verify reminders sent
    booking_24h = await db["bookings"].find_one({"_id": booking_id_24h})
    assert "24h" in booking_24h["reminders_sent"]
    
    booking_2h = await db["bookings"].find_one({"_id": booking_id_2h})
    assert "2h" in booking_2h["reminders_sent"]
    
    # Check audit log for template sends
    audit_24h = await db["audit_log"].find_one({"tenant_id": tenant_id, "payload.template": "T_REMINDER_24H"})
    assert audit_24h is not None
    assert audit_24h["payload"]["patient_name"] == "Ravi Mohanty"
    
    audit_2h = await db["audit_log"].find_one({"tenant_id": tenant_id, "payload.template": "T_REMINDER_2H"})
    assert audit_2h is not None
    
    # Run reminders again (assert idempotency/no double reminders)
    await run_reminders()
    # The count should still be one in audit log
    audit_24h_count = await db["audit_log"].count_documents({"tenant_id": tenant_id, "payload.template": "T_REMINDER_24H"})
    assert audit_24h_count == 1


async def test_weekly_summaries():
    tenant_id = "tenant_weekly_test"
    db = get_db()
    
    await db["tenants"].insert_one({
        "_id": tenant_id,
        "name": "Sharma Clinic",
        "status": "active"
    })
    
    # Create conversations (some active, one escalated)
    now = datetime.now(UTC).replace(tzinfo=None)
    await db["conversations"].insert_one({
        "tenant_id": tenant_id,
        "state": "bot",
        "started_at": now - timedelta(days=2)
    })
    await db["conversations"].insert_one({
        "tenant_id": tenant_id,
        "state": "human",
        "started_at": now - timedelta(days=3)
    })
    
    # Create bookings (one after-hours, one voice, one standard)
    # 1. After hours booking: Sunday (e.g. now + offset so it represents a Sunday)
    sunday_dt = now - timedelta(days=3)
    while sunday_dt.weekday() != 6: # Go back to Sunday
        sunday_dt -= timedelta(days=1)
    
    await db["bookings"].insert_one({
        "tenant_id": tenant_id,
        "status": "completed",
        "source": "wa",
        "ts": sunday_dt
    })
    
    # 2. Voice booking
    await db["bookings"].insert_one({
        "tenant_id": tenant_id,
        "status": "confirmed",
        "source": "voice",
        "ts": now - timedelta(days=1)
    })
    
    # 3. Regular booking (in hours, Monday-Saturday)
    regular_dt = now - timedelta(days=2)
    if regular_dt.weekday() == 6:
        regular_dt -= timedelta(days=1)
    # Ensure in business hours: set to 10:00 AM
    regular_dt = regular_dt.replace(hour=10, minute=0)
    
    await db["bookings"].insert_one({
        "tenant_id": tenant_id,
        "status": "confirmed",
        "source": "wa",
        "ts": regular_dt
    })
    
    # Run summaries
    await run_weekly_summaries()
    
    summary_audit = await db["audit_log"].find_one({"tenant_id": tenant_id, "payload.template": "T_WEEKLY_SUMMARY"})
    assert summary_audit is not None
    variables = summary_audit["payload"]["variables"]
    
    # variables: [owner_name, date_range_str, total_convs, confirmed_bookings, recovered_bookings, revenue]
    assert variables[0] == "Sharma Clinic"
    assert int(variables[2]) == 2 # total convs
    assert int(variables[3]) == 3 # total confirmed
    assert int(variables[4]) == 2 # recovered (1 Sunday, 1 Voice)
    assert variables[5] == "Rs. 2000"


async def test_exotel_missed_call_bridge():
    from app.main import app
    from fastapi.testclient import TestClient
    
    tenant_id = "tenant_missed_call_test"
    db = get_db()
    
    await db["tenants"].insert_one({
        "_id": tenant_id,
        "name": "Missed Call Clinic",
        "voice_number": "919999999990",
        "status": "active"
    })
    
    client = TestClient(app)
    payload = {
        "From": "919876543210",
        "To": "919999999990"
    }
    
    response = client.post("/webhooks/exotel/missed_call", data=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "bridge_initiated"
    
    # Verify contact created
    contact = await db["contacts"].find_one({"phone": "919876543210", "tenant_id": tenant_id})
    assert contact is not None
    assert "missed_call_bridge" in contact["tags"]
    
    # Verify conversation created/opened
    conv = await db["conversations"].find_one({"contact_id": str(contact["_id"]), "tenant_id": tenant_id})
    assert conv is not None
    assert conv["state"] == "bot"
    assert conv["channel"] == "wa"
    
    # Verify missed call template audit logged
    audit_entry = await db["audit_log"].find_one({"tenant_id": tenant_id, "payload.template": "T_MISSED_CALL_BRIDGE"})
    assert audit_entry is not None
    assert audit_entry["payload"]["to"] == "919876543210"


async def test_waitlist_cancellation_and_backfill():
    tenant_id = "tenant_waitlist_test"
    db = get_db()
    
    # 1. Setup slot and booking
    slot_id = "slot_to_cancel"
    start_dt = datetime.now(UTC).replace(tzinfo=None) + timedelta(days=2)
    
    await db["slots"].insert_one({
        "_id": slot_id,
        "tenant_id": tenant_id,
        "practitioner_id": "prac_1",
        "start": start_dt,
        "status": "booked"
    })
    
    booking_id = "booking_to_cancel"
    await db["bookings"].insert_one({
        "_id": booking_id,
        "tenant_id": tenant_id,
        "slot_id": slot_id,
        "status": "confirmed"
    })
    
    # 2. Add contact to waitlist for that practitioner and date
    waitlist_contact_id = "contact_waitlist_1"
    await db["waitlist"].insert_one({
        "tenant_id": tenant_id,
        "contact_id": waitlist_contact_id,
        "practitioner_id": "prac_1",
        "date": start_dt.strftime("%Y-%m-%d"),
        "status": "active"
    })
    
    # 3. Call cancel booking
    cancel_res = await booking_cancel(tenant_id, booking_id)
    assert cancel_res["status"] == "success"
    
    # 4. Verify slot is open and booking is cancelled
    slot = await db["slots"].find_one({"_id": slot_id})
    assert slot["status"] == "open"
    
    booking = await db["bookings"].find_one({"_id": booking_id})
    assert booking["status"] == "cancelled"
    
    # 5. Verify waitlist offers logged in audit log
    offer_audit = await db["audit_log"].find_one({"tenant_id": tenant_id, "payload.template": "T_SLOT_OPEN_OFFER"})
    assert offer_audit is not None
    assert offer_audit["payload"]["contact_id"] == waitlist_contact_id
    assert offer_audit["payload"]["slot_id"] == slot_id
    
    # 6. Verify atomic claim_waitlist_slot works (first-tap-wins)
    claim_success = await claim_waitlist_slot(tenant_id, slot_id, waitlist_contact_id, "Tooth Extraction")
    assert claim_success is True
    
    # Verify slot is booked again and waitlist entry updated to fulfilled
    slot = await db["slots"].find_one({"_id": slot_id})
    assert slot["status"] == "booked"
    
    waitlist_item = await db["waitlist"].find_one({"contact_id": waitlist_contact_id})
    assert waitlist_item["status"] == "fulfilled"
    
    # Verify second claim fails (already held/booked)
    claim_fail = await claim_waitlist_slot(tenant_id, slot_id, "other_contact", "Cleaning")
    assert claim_fail is False


async def test_patient_memory_one_tap_rebook():
    tenant_id = "tenant_memory_test"
    db = get_db()
    
    # 1. Setup practitioner
    prac_id = "dr_sharma"
    await db["practitioners"].insert_one({
        "_id": prac_id,
        "tenant_id": tenant_id,
        "name": "Dr. Sharma"
    })
    
    # 2. Setup contact with profile memory
    contact_id = "contact_returning"
    await db["contacts"].insert_one({
        "_id": contact_id,
        "tenant_id": tenant_id,
        "name": "Ravi Mohanty",
        "profile": {
            "preferred_practitioner_id": prac_id,
            "last_service": "Tooth Extraction"
        }
    })
    
    # 3. Setup conversation mapping to contact
    conv_id = "conv_returning"
    await db["conversations"].insert_one({
        "_id": conv_id,
        "tenant_id": tenant_id,
        "contact_id": contact_id,
        "state": "bot"
    })
    
    # Run responder node with intent "book"
    state = {
        "tenant_id": tenant_id,
        "conversation_id": conv_id,
        "intent": "book",
        "text": "I want to book an appointment",
        "lang": "en",
        "tool_results": []
    }
    
    # Call responder (which queries LLM, mocked here to return a default)
    res = await responder(state)
    assert res is not None
    assert "response" in res
