"""WhatsApp send wrapper + 24h-window tracker (TRD §5.3, Week 3 task 3.7).

Meta policy: free-form replies ONLY inside the 24h customer-service window;
outside it, pre-approved utility templates only. Tracks last-inbound ts per
contact; an out-of-window free-form send must RAISE and force the template path.
Template pack registry lives here (booking_confirm, *_reminder_*, payment_link,
escalation_alert_staff, weekly_summary_owner, consent_notice, missed_call_bridge).
All sends route through app.audit (choke point).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from app import audit
from app.config import settings
from app.models.collections import Contacts

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
        "consent_notice",
        "missed_call_bridge",
    }
)


class WindowClosedError(RuntimeError):
    """Raised when a free-form send is attempted outside the 24h window."""


def _offline() -> bool:
    """No BSP credentials -> mock the send (mirrors app.agent.llm offline path)."""
    return not (settings.bsp_access_token and settings.bsp_phone_number_id)


def _graph_url() -> str:
    return (
        f"https://graph.facebook.com/{_GRAPH_API_VERSION}"
        f"/{settings.bsp_phone_number_id}/messages"
    )


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.bsp_access_token}",
        "Content-Type": "application/json",
    }


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


async def _post(tenant_id: str, wa_id: str, body: dict[str, Any]) -> dict[str, Any]:
    """Single HTTP choke point for outbound sends. Offline -> deterministic mock."""
    if _offline():
        logger.debug("[WA Mock] to=%s body=%s", wa_id, body.get("type"))
        return {"messages": [{"id": f"mock_wamid_{wa_id}"}], "mock": True}

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            _graph_url(), headers=_headers(), json=body, timeout=30.0
        )
    if resp.status_code != 200:
        logger.error("WhatsApp send failed %s: %s", resp.status_code, resp.text)
        raise RuntimeError(f"WhatsApp API error {resp.status_code}: {resp.text}")
    data: dict[str, Any] = resp.json()
    return data


async def send_freeform(tenant_id: str, wa_id: str, text: str) -> dict[str, Any]:
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
    result = await _post(tenant_id, wa_id, body)

    await audit.record(
        tenant_id,
        actor="agent",
        event_type="outbound_freeform",
        payload={"wa_id": wa_id, "text": text, "wamid": _wamid(result)},
    )
    return result


async def send_template(
    tenant_id: str, wa_id: str, template: str, variables: dict[str, Any]
) -> dict[str, Any]:
    """Send a pre-approved utility template — always permitted (any window state)."""
    if template not in TEMPLATE_PACK:
        raise ValueError(f"Unknown template '{template}'; not in the approved pack.")

    # Positional body params in registry order — Meta templates are positional.
    components: list[dict[str, Any]] = []
    if variables:
        components.append(
            {
                "type": "body",
                "parameters": [
                    {"type": "text", "text": str(v)} for v in variables.values()
                ],
            }
        )

    body = {
        "messaging_product": "whatsapp",
        "to": wa_id,
        "type": "template",
        "template": {
            "name": template,
            "language": {"code": "en"},
            "components": components,
        },
    }
    result = await _post(tenant_id, wa_id, body)

    await audit.record(
        tenant_id,
        actor="agent",
        event_type="outbound_template",
        payload={
            "wa_id": wa_id,
            "template": template,
            "variables": variables,
            "wamid": _wamid(result),
        },
    )
    return result


def _wamid(result: dict[str, Any]) -> str | None:
    messages = result.get("messages")
    if isinstance(messages, list) and messages:
        wamid = messages[0].get("id")
        return str(wamid) if wamid is not None else None
    return None
