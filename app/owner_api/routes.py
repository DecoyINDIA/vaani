"""Owner dashboard REST (TRD §5.2). All routes JWT-authed and tenant-scoped.

Endpoints (stubs — Week 5 task 5.3):
  GET  /conversations           GET  /conversations/{id}/messages
  POST /conversations/{id}/takeover   POST /conversations/{id}/return
  GET  /bookings   POST /bookings   PATCH /bookings/{id}
  GET  /escalations
  GET/PUT /kb      GET/PUT /settings
  GET  /metrics/summary          GET  /audit/export
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["owner"])


@router.get("/conversations")
async def list_conversations() -> dict:
    raise NotImplementedError("owner API — 06-engineering-plan task 5.3")
