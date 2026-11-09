from __future__ import annotations

from datetime import UTC, datetime

import pytest
from app.billing.invoice import generate_invoice
from app.billing.meters import record_usage
from app.config import settings
from app.main import app
from app.models.base import get_db
from app.workers.billing import run_monthly_invoices
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
async def clean_db() -> None:
    db = get_db()
    for collection in await db.list_collection_names():
        if not collection.startswith("system."):
            await db[collection].delete_many({})


async def _tenant(tenant_id: str, *, plan: str = "starter", **extra: object) -> None:
    await get_db()["tenants"].insert_one(
        {
            "_id": tenant_id,
            "name": "Billing Clinic",
            "gstin": "27CLINIC1111A1Z",
            "timezone": "Asia/Kolkata",
            "plan": plan,
            "status": "active",
            **extra,
        }
    )


async def test_usage_period_uses_tenant_timezone_and_replay_is_free() -> None:
    tenant_id = "billing-period-boundary"
    await _tenant(tenant_id)
    assert await record_usage(
        tenant_id,
        event_id="before-midnight",
        metric="wa_conversations",
        quantity=1,
        occurred_at=datetime(2026, 1, 31, 18, 29, tzinfo=UTC),
    )
    assert await record_usage(
        tenant_id,
        event_id="after-midnight",
        metric="wa_conversations",
        quantity=1,
        occurred_at=datetime(2026, 1, 31, 18, 30, tzinfo=UTC),
    )
    assert not await record_usage(
        tenant_id,
        event_id="after-midnight",
        metric="wa_conversations",
        quantity=999,
        occurred_at=datetime(2026, 1, 31, 18, 30, tzinfo=UTC),
    )
    db = get_db()
    assert (await db["usage_meters"].find_one({"tenant_id": tenant_id, "period": "2026-01"}))[
        "wa_conversations"
    ] == 1
    assert (await db["usage_meters"].find_one({"tenant_id": tenant_id, "period": "2026-02"}))[
        "wa_conversations"
    ] == 1


async def test_starter_overages_use_integer_paise(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "xolver_gstin", "27XOLVER1111A1Z1")
    tenant_id = "billing-starter-overage"
    await _tenant(tenant_id)
    at = datetime(2026, 7, 15, tzinfo=UTC)
    await record_usage(
        tenant_id,
        event_id="conversations-july",
        metric="wa_conversations",
        quantity=1_001,
        occurred_at=at,
    )
    await record_usage(
        tenant_id,
        event_id="bookings-july",
        metric="confirmed_bookings",
        quantity=51,
        occurred_at=at,
    )
    invoice = await generate_invoice(tenant_id, "2026-07")
    assert invoice["overage_amount_paise"] == 5_100
    assert invoice["subtotal_paise"] == 305_000
    assert invoice["gst_paise"] == 54_900
    assert invoice["total_paise"] == 359_900


async def test_invoice_rejects_unknown_plan_and_missing_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "xolver_gstin", "27XOLVER1111A1Z1")
    await _tenant("billing-unknown-plan", plan="plan_mystery")
    with pytest.raises(ValueError, match="Unknown billing plan"):
        await generate_invoice("billing-unknown-plan", "2026-07")

    await get_db()["tenants"].insert_one(
        {"_id": "billing-no-gstin", "name": "No Identity", "plan": "starter"}
    )
    with pytest.raises(ValueError, match="billing name and GSTIN"):
        await generate_invoice("billing-no-gstin", "2026-07")


async def test_invoice_snapshot_survives_later_plan_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "xolver_gstin", "27XOLVER1111A1Z1")
    tenant_id = "billing-plan-snapshot"
    await _tenant(tenant_id)
    first = await generate_invoice(tenant_id, "2026-07")
    await get_db()["tenants"].update_one({"_id": tenant_id}, {"$set": {"plan": "pro"}})
    second = await generate_invoice(tenant_id, "2026-07")
    assert first["invoice_number"] == second["invoice_number"]
    assert second["plan"] == "starter"
    assert second["base_amount_paise"] == 299_900


async def test_monthly_worker_issues_previous_period_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "xolver_gstin", "27XOLVER1111A1Z1")
    tenant_id = "billing-monthly-worker"
    await _tenant(tenant_id, timezone="UTC")
    now = datetime(2026, 8, 1, 0, 5, tzinfo=UTC)
    await run_monthly_invoices(now=now)
    await run_monthly_invoices(now=now)
    db = get_db()
    assert await db["invoices"].count_documents(
        {"tenant_id": tenant_id, "period": "2026-07"}
    ) == 1


async def test_monthly_worker_records_failure_and_continues_other_tenants(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "xolver_gstin", "27XOLVER1111A1Z1")
    await _tenant("billing-invalid", timezone="UTC", gstin="")
    await _tenant("billing-continues", timezone="UTC")
    now = datetime(2026, 8, 1, 0, 5, tzinfo=UTC)

    await run_monthly_invoices(now=now)
    await run_monthly_invoices(now=now)

    db = get_db()
    assert await db["invoices"].count_documents(
        {"tenant_id": "billing-continues", "period": "2026-07"}
    ) == 1
    alerts = await db["audit_log"].find(
        {"tenant_id": "billing-invalid", "event_type": "operational_alert"}
    ).to_list(length=10)
    assert len(alerts) == 1
    assert alerts[0]["payload"] == {
        "kind": "invoice_issuance_failed",
        "period": "2026-07",
        "error_type": "ValueError",
    }


async def test_subscription_unknown_plan_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "razorpay_plan_pro_id", "plan_pro")
    tenant_id = "billing-unknown-provider-plan"
    await _tenant(tenant_id)
    response = TestClient(app).post(
        "/webhooks/razorpay",
        json={
            "event": "subscription.activated",
            "payload": {
                "subscription": {
                    "entity": {
                        "id": "sub_unknown",
                        "plan_id": "plan_not_configured",
                        "status": "active",
                        "notes": {"tenant_id": tenant_id},
                    }
                }
            },
        },
        headers={"X-Razorpay-Signature": "mock"},
    )
    assert response.status_code == 202
    tenant = await get_db()["tenants"].find_one({"_id": tenant_id})
    assert tenant["plan"] == "starter"


async def test_subscription_cancellation_updates_billing_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "razorpay_plan_pro_id", "plan_pro")
    tenant_id = "billing-subscription-cancelled"
    await _tenant(tenant_id, plan="pro")
    payload = {
        "event": "subscription.cancelled",
        "payload": {
            "subscription": {
                "entity": {
                    "id": "sub_cancelled",
                    "plan_id": "plan_pro",
                    "status": "cancelled",
                    "notes": {"tenant_id": tenant_id},
                }
            }
        },
    }
    client = TestClient(app)
    assert client.post(
        "/webhooks/razorpay",
        json=payload,
        headers={"X-Razorpay-Signature": "mock"},
    ).status_code == 200
    duplicate = client.post(
        "/webhooks/razorpay",
        json=payload,
        headers={"X-Razorpay-Signature": "mock"},
    )
    assert duplicate.json()["status"] == "duplicate"
    tenant = await get_db()["tenants"].find_one({"_id": tenant_id})
    assert tenant["billing_status"] == "cancelled"
    assert await get_db()["audit_log"].count_documents(
        {"tenant_id": tenant_id, "event_type": "subscription_updated"}
    ) == 1


async def test_meta_billable_delivery_records_one_provider_usage_event() -> None:
    tenant_id = "billing-meta-delivery"
    await _tenant(tenant_id, wa_number="919999999999")
    client = TestClient(app)

    def payload(state: str) -> dict[str, object]:
        return {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "metadata": {"display_phone_number": "919999999999"},
                                "statuses": [
                                    {
                                        "id": "wamid.billable-1",
                                        "status": state,
                                        "pricing": {"billable": True, "category": "utility"},
                                    }
                                ],
                            }
                        }
                    ]
                }
            ]
        }

    assert client.post("/webhooks/meta", json=payload("delivered")).status_code == 200
    assert client.post("/webhooks/meta", json=payload("read")).status_code == 200
    events = get_db()["usage_events"]
    assert await events.count_documents(
        {"tenant_id": tenant_id, "event_id": "meta:wamid.billable-1:billable"}
    ) == 1
