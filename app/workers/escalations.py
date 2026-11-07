"""Clinic-local handoff SLA calculation and owner-breach notification."""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.channels.whatsapp import AmbiguousDeliveryError, send_template
from app.models.base import mongo_id_candidates
from app.models.collections import (
    Contacts,
    Conversations,
    Escalations,
    Tenants,
    Users,
)


def _schedule(tenant: dict[str, Any]) -> list[dict[str, str]]:
    configured = tenant.get("business_hours")
    return configured if isinstance(configured, list) else []


def _hours_for(day: datetime, schedule: list[dict[str, str]]) -> tuple[time, time] | None:
    name = day.strftime("%A").lower()
    row = next((item for item in schedule if item.get("day") == name), None)
    if not row:
        return None
    try:
        return time.fromisoformat(row["start"]), time.fromisoformat(row["end"])
    except (KeyError, ValueError):
        return None


def escalation_sla(
    tenant: dict[str, Any], now: datetime
) -> tuple[str, datetime | None]:
    """Return SLA mode and due instant; empty schedules keep the legacy always-in-hours mode."""
    timezone = ZoneInfo(str(tenant.get("timezone", "Asia/Kolkata")))
    aware_now = now if now.tzinfo else now.replace(tzinfo=UTC)
    local_now = aware_now.astimezone(timezone)
    schedule = _schedule(tenant)
    if not schedule:
        return "in_hours", aware_now.astimezone(UTC) + timedelta(minutes=10)
    hours = _hours_for(local_now, schedule)
    if hours and hours[0] <= local_now.time() < hours[1]:
        return "in_hours", aware_now.astimezone(UTC) + timedelta(minutes=10)
    for offset in range(0, 8):
        candidate = local_now + timedelta(days=offset)
        candidate_hours = _hours_for(candidate, schedule)
        if not candidate_hours:
            continue
        opening = datetime.combine(candidate.date(), candidate_hours[0], tzinfo=timezone)
        if opening > local_now:
            return "out_of_hours", opening.astimezone(UTC)
    return "out_of_hours", None


def escalation_variables(
    tenant: dict[str, Any],
    conversation_id: str,
    reason: str,
    contact: dict[str, Any] | None,
) -> dict[str, str]:
    profile = contact.get("profile", {}) if contact else {}
    base_url = str(tenant.get("dashboard_url", "")).rstrip("/")
    return {
        "patient_name": str((contact or {}).get("name") or profile.get("name") or "Patient"),
        "patient_phone": str(
            (contact or {}).get("wa_id")
            or (contact or {}).get("phone")
            or "Unavailable"
        ),
        "reason": reason,
        "dashboard_url": (
            f"{base_url}/conversations/{conversation_id}" if base_url else conversation_id
        ),
    }


async def run_escalation_slas(*, now: datetime | None = None) -> None:
    """Notify an owner once for each overdue, in-hours, unresolved escalation."""
    instant = now or datetime.now(UTC)
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=UTC)
    naive_now = instant.astimezone(UTC).replace(tzinfo=None)
    for tenant in await Tenants.all():
        tenant_id = str(tenant["_id"])
        escalations = Escalations(tenant_id)
        overdue = escalations.find(
            {
                "status": "open",
                "sla_mode": "in_hours",
                "sla_due_at": {"$lte": naive_now},
                "owner_notification_status": {
                    "$nin": ["sending", "sent", "unknown"]
                },
            }
        )
        async for escalation in overdue:
            claimed = await escalations.find_one_and_update(
                {
                    "_id": escalation["_id"],
                    "status": "open",
                    "owner_notification_status": {
                        "$nin": ["sending", "sent", "unknown"]
                    },
                },
                {"$set": {"owner_notification_status": "sending"}},
            )
            if not claimed:
                continue
            owner = await Users(tenant_id).find_one({"role": "owner", "status": "active"})
            wa_id = (owner or {}).get("wa_id") or (owner or {}).get("phone")
            conversation_id = str(escalation["conversation_id"])
            conversation = await Conversations(tenant_id).find_one(
                {"_id": {"$in": mongo_id_candidates(conversation_id)}}
            )
            contact = None
            if conversation and conversation.get("contact_id") is not None:
                contact = await Contacts(tenant_id).find_one(
                    {
                        "_id": {
                            "$in": mongo_id_candidates(str(conversation["contact_id"]))
                        }
                    }
                )
            if not wa_id:
                await escalations.update_one(
                    {"_id": escalation["_id"]},
                    {"$set": {"owner_notification_status": "missing_recipient"}},
                )
                continue
            try:
                await send_template(
                    tenant_id,
                    str(wa_id),
                    "escalation_alert_staff",
                    escalation_variables(
                        tenant, conversation_id, f"SLA breach: {escalation['reason']}", contact
                    ),
                    operation_key=f"escalation-sla:{escalation['_id']}",
                )
                status = "sent"
            except AmbiguousDeliveryError:
                status = "unknown"
            except Exception:
                status = "failed"
            await escalations.update_one(
                {"_id": escalation["_id"]},
                {
                    "$set": {
                        "owner_notification_status": status,
                        "owner_notification_updated_at": naive_now,
                    }
                },
            )
