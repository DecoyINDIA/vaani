"""WhatsApp send wrapper + 24h-window tracker (TRD §5.3, Week 3 task 3.7).

Meta policy: free-form replies ONLY inside the 24h customer-service window;
outside it, pre-approved utility templates only. Tracks last-inbound ts per
contact; an out-of-window free-form send must RAISE and force the template path.
Template pack registry lives here (booking_confirm, *_reminder_*, payment_link,
escalation_alert_staff, weekly_summary_owner, consent_notice, missed_call_bridge).
All sends route through app.audit (choke point).
"""

from __future__ import annotations

from typing import Any


async def send_freeform(tenant_id: str, wa_id: str, text: str) -> dict[str, Any]:
    """Raises if the 24h window is closed — caller must use a template."""
    raise NotImplementedError("whatsapp free-form send — 06-engineering-plan task 3.7")


async def send_template(
    tenant_id: str, wa_id: str, template: str, variables: dict[str, Any]
) -> dict[str, Any]:
    raise NotImplementedError("whatsapp template send — 06-engineering-plan task 3.7")
