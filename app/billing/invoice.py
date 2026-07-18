"""GST tax invoice generation (F-17, 06-engineering-plan Phase 3 item 2).

Xolver GSTIN + SAC (998314) + 18% + clinic GSTIN, auto-delivered monthly. Live
before the first paid invoice.
"""

from __future__ import annotations


async def generate_invoice(tenant_id: str, period: str) -> dict:
    raise NotImplementedError("GST invoice — 06-engineering-plan Phase 3")
