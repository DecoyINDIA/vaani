"""WhatsApp send wrapper + 24h-window tracker (TRD §5.3, Week 3 task 3.7).

Meta policy: free-form replies ONLY inside the 24h customer-service window;
outside it, pre-approved utility templates only. Tracks last-inbound ts per
contact; an out-of-window free-form send must RAISE and force the template path.
Template pack registry lives here (booking_confirm, *_reminder_*, payment_link,
escalation_alert_staff, weekly_summary_owner, daily_brief_owner, consent_notice,
missed_call_bridge).
All sends route through app.audit (choke point).
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from pymongo.errors import DuplicateKeyError

from app import audit
from app.config import settings
from app.models.collections import Contacts, OutboundIntents, Tenants
from app.privacy import is_suppressed

logger = logging.getLogger(__name__)

# Meta Graph API version pinned per ADR-04. Bump deliberately, not incidentally.
_GRAPH_API_VERSION = "v20.0"

# Pre-approved utility templates (TRD §5.3). Free-form is blocked outside the
# 24h window; these are the only sends permitted there.
TEMPLATE_PACK: frozenset[str] = frozenset(
    {
        "booking_confirm",
        "reminder_24h",
        "reminder_2h",
        "payment_link",
        "escalation_alert_staff",
        "weekly_summary_owner",
        "daily_brief_owner",
        "consent_notice",
        "missed_call_bridge",
    }
)

# Must match the positional approval artifact in ops/whatsapp_templates.md.
TEMPLATE_CONTRACTS: dict[str, tuple[str, ...]] = {
    "reminder_24h": ("patient_name", "doctor_name", "date", "time"),
    "reminder_2h": ("patient_name", "time", "landmark"),
    "escalation_alert_staff": (
        "patient_name",
        "patient_phone",
        "reason",
        "dashboard_url",
    ),
    "weekly_summary_owner": (
        "owner_name",
        "date_range_str",
        "convs_count",
        "confirmed_count",
        "recovered_count",
        "revenue_str",
    ),
    "daily_brief_owner": (
        "owner_name",
        "date_str",
        "convs_count",
        "confirmed_count",
        "recovered_count",
        "revenue_str",
        "open_escalations",
    ),
    "missed_call_bridge": ("clinic_name",),
}
TEMPLATE_LANGUAGES: frozenset[str] = frozenset({"en", "hi", "hi-Latn", "or"})


class WindowClosedError(RuntimeError):
    """Raised when a free-form send is attempted outside the 24h window."""


class AmbiguousDeliveryError(RuntimeError):
    """Raised when retrying could duplicate an external side effect."""


class SuppressedRecipientError(RuntimeError):
    """Raised when an erasure record blocks future delivery."""


def _offline() -> bool:
    """Mocks are selected explicitly; missing credentials never imply success."""
    return settings.use_mock_adapters


def _graph_url(phone_number_id: str) -> str:
    return (
        f"https://graph.facebook.com/{_GRAPH_API_VERSION}"
        f"/{phone_number_id}/messages"
    )


def _headers(access_token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }


async def _tenant_credentials(tenant_id: str) -> tuple[str, str]:
    tenant = await Tenants.find_by_id(tenant_id)
    channel = tenant.get("whatsapp") if tenant else None
    if not isinstance(channel, dict):
        raise RuntimeError("tenant WhatsApp configuration is missing")
    phone_number_id = channel.get("phone_number_id")
    access_token_env = channel.get("access_token_env")
    if not isinstance(phone_number_id, str) or not phone_number_id:
        raise RuntimeError("tenant WhatsApp sender ID is missing")
    if not isinstance(access_token_env, str) or not access_token_env:
        raise RuntimeError("tenant WhatsApp credential reference is missing")
    access_token = os.environ.get(access_token_env)
    if not access_token:
        raise RuntimeError(
            f"tenant WhatsApp credential reference {access_token_env!r} is not configured"
        )
    return phone_number_id, access_token


async def _window_open(tenant_id: str, wa_id: str) -> bool:
    """True if the contact messaged us within the last 24h (Meta CS window)."""
    contact = await Contacts(tenant_id).find_one({"wa_id": wa_id})
    if not contact:
        return False
    last_inbound = contact.get("last_inbound_ts")
    if not isinstance(last_inbound, datetime):
        return False
    now = datetime.now(UTC).replace(tzinfo=None)
    return (now - last_inbound) <= timedelta(hours=24)


async def _post(
    tenant_id: str, wa_id: str, body: dict[str, Any], operation_key: str
) -> dict[str, Any]:
    """Persist intent before send and never retry an ambiguous external result."""
    if not operation_key:
        raise ValueError("operation_key is required for outbound delivery")
    if await is_suppressed(tenant_id, wa_id):
        raise SuppressedRecipientError("recipient is suppressed by erasure")
    credentials = None if _offline() else await _tenant_credentials(tenant_id)
    intents = OutboundIntents(tenant_id)
    existing = await intents.find_one({"operation_key": operation_key})
    if existing:
        if existing.get("state") in {"sent", "delivered"}:
            return {
                "messages": [{"id": existing.get("provider_message_id")}],
                "deduplicated": True,
            }
        if existing.get("state") in {"sending", "unknown"}:
            raise AmbiguousDeliveryError(f"delivery state is {existing['state']}")
    else:
        try:
            await intents.insert_one(
                {
                    "operation_key": operation_key,
                    "channel": "whatsapp",
                    "to": wa_id,
                    "kind": body.get("type"),
                    "state": "pending",
                    "created_at": datetime.now(UTC).replace(tzinfo=None),
                }
            )
        except DuplicateKeyError:
            raise AmbiguousDeliveryError("concurrent delivery owns this operation") from None

    acquired = await intents.find_one_and_update(
        {"operation_key": operation_key, "state": {"$in": ["pending", "failed"]}},
        {"$set": {"state": "sending", "attempted_at": datetime.now(UTC).replace(tzinfo=None)}},
    )
    if not acquired:
        raise AmbiguousDeliveryError("delivery could not be acquired")

    if _offline():
        data: dict[str, Any] = {
            "messages": [{"id": f"mock_wamid_{operation_key}"}],
            "mock": True,
        }
    else:
        assert credentials is not None
        phone_number_id, access_token = credentials
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    _graph_url(phone_number_id),
                    headers=_headers(access_token),
                    json=body,
                    timeout=30.0,
                )
        except httpx.HTTPError as e:
            await intents.update_one(
                {"operation_key": operation_key, "state": "sending"},
                {"$set": {"state": "unknown", "last_error": type(e).__name__}},
            )
            await audit.record(
                tenant_id,
                actor="system",
                event_type="operational_alert",
                payload={
                    "kind": "unknown_delivery",
                    "operation_key": operation_key,
                    "error_type": type(e).__name__,
                },
                operation_key=f"unknown-delivery-alert:{operation_key}",
            )
            raise AmbiguousDeliveryError("provider result is unknown") from e
        if resp.status_code != 200:
            await intents.update_one(
                {"operation_key": operation_key, "state": "sending"},
                {"$set": {"state": "failed", "last_error": f"HTTP {resp.status_code}"}},
            )
            await audit.record(
                tenant_id,
                actor="system",
                event_type="operational_alert",
                payload={
                    "kind": "provider_failure",
                    "provider": "meta_whatsapp",
                    "status_code": resp.status_code,
                },
                operation_key=f"provider-failure-alert:{operation_key}",
            )
            raise RuntimeError(f"WhatsApp API error {resp.status_code}")
        data = resp.json()

    provider_id = _wamid(data)
    await intents.update_one(
        {"operation_key": operation_key, "state": "sending"},
        {
            "$set": {
                "state": "sent",
                "provider_message_id": provider_id,
                "sent_at": datetime.now(UTC).replace(tzinfo=None),
            }
        },
    )
    return data


async def send_freeform(
    tenant_id: str, wa_id: str, text: str, *, operation_key: str
) -> dict[str, Any]:
    """Raises if the 24h window is closed — caller must use a template."""
    if not await _window_open(tenant_id, wa_id):
        raise WindowClosedError(
            f"24h window closed for {wa_id}; a utility template is required."
        )

    body = {
        "messaging_product": "whatsapp",
        "to": wa_id,
        "type": "text",
        "text": {"body": text},
    }
    result = await _post(tenant_id, wa_id, body, operation_key)

    await audit.record(
        tenant_id,
        actor="agent",
        event_type="outbound_freeform",
        operation_key=operation_key,
        payload={"wa_id": wa_id, "text": text, "wamid": _wamid(result)},
    )
    return result


async def send_template(
    tenant_id: str,
    wa_id: str,
    template: str,
    variables: dict[str, Any],
    *,
    operation_key: str,
    language_code: str = "en",
) -> dict[str, Any]:
    """Send a pre-approved utility template — always permitted (any window state)."""
    if template not in TEMPLATE_PACK:
        raise ValueError(f"Unknown template '{template}'; not in the approved pack.")
    if language_code not in TEMPLATE_LANGUAGES:
        raise ValueError(f"Unsupported template language '{language_code}'")

    parameter_order = TEMPLATE_CONTRACTS.get(template)
    if parameter_order is not None and set(variables) != set(parameter_order):
        raise ValueError(
            f"Template '{template}' requires variables {parameter_order}; "
            f"received {tuple(variables)}"
        )

    # Positional body params in registry order — Meta templates are positional.
    components: list[dict[str, Any]] = []
    if variables:
        ordered_values = (
            [variables[name] for name in parameter_order]
            if parameter_order is not None
            else list(variables.values())
        )
        components.append(
            {
                "type": "body",
                "parameters": [
                    {"type": "text", "text": str(value)} for value in ordered_values
                ],
            }
        )

    body = {
        "messaging_product": "whatsapp",
        "to": wa_id,
        "type": "template",
        "template": {
            "name": template,
            "language": {"code": language_code},
            "components": components,
        },
    }
    result = await _post(tenant_id, wa_id, body, operation_key)

    await audit.record(
        tenant_id,
        actor="agent",
        event_type="outbound_template",
        operation_key=operation_key,
        payload={
            "wa_id": wa_id,
            "template": template,
            "variables": variables,
            "wamid": _wamid(result),
        },
    )
    return result


async def send_slot_picker(
    tenant_id: str,
    wa_id: str,
    *,
    prompt: str,
    slots: list[dict[str, str]],
    operation_key: str,
) -> dict[str, Any]:
    """Send an in-window WhatsApp list whose row IDs carry slot identity."""
    if not await _window_open(tenant_id, wa_id):
        raise WindowClosedError("24h window closed; interactive picker is not permitted")
    rows = [
        {"id": f"slot:{slot['slot_id']}", "title": slot["label"][:24]}
        for slot in slots[:10]
    ]
    if not rows:
        raise ValueError("slot picker requires at least one slot")
    body = {
        "messaging_product": "whatsapp",
        "to": wa_id,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": prompt},
            "action": {
                "button": "Choose a time",
                "sections": [{"title": "Available appointments", "rows": rows}],
            },
        },
    }
    result = await _post(tenant_id, wa_id, body, operation_key)
    await audit.record(
        tenant_id,
        actor="agent",
        event_type="outbound_interactive",
        operation_key=operation_key,
        payload={"wa_id": wa_id, "kind": "slot_picker", "wamid": _wamid(result)},
    )
    return result


async def send_booking_confirmation(
    tenant_id: str,
    wa_id: str,
    *,
    prompt: str,
    operation_key: str,
) -> dict[str, Any]:
    """Send explicit confirm/cancel buttons after echoing the selected date."""
    if not await _window_open(tenant_id, wa_id):
        raise WindowClosedError("24h window closed; confirmation buttons are not permitted")
    body = {
        "messaging_product": "whatsapp",
        "to": wa_id,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": prompt},
            "action": {
                "buttons": [
                    {
                        "type": "reply",
                        "reply": {"id": "booking:confirm", "title": "Confirm"},
                    },
                    {
                        "type": "reply",
                        "reply": {"id": "booking:cancel", "title": "Choose again"},
                    },
                ]
            },
        },
    }
    result = await _post(tenant_id, wa_id, body, operation_key)
    await audit.record(
        tenant_id,
        actor="agent",
        event_type="outbound_interactive",
        operation_key=operation_key,
        payload={"wa_id": wa_id, "kind": "booking_confirmation", "wamid": _wamid(result)},
    )
    return result


def _wamid(result: dict[str, Any]) -> str | None:
    messages = result.get("messages")
    if isinstance(messages, list) and messages:
        wamid = messages[0].get("id")
        return str(wamid) if wamid is not None else None
    return None
