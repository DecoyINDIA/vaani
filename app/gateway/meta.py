"""Meta WhatsApp Cloud API webhook (TRD §5.1, ADR-04).

GET  /webhooks/meta  — verification handshake (hub.challenge).
POST /webhooks/meta  — signature-verified, idempotent on message_id, must ack
                        <5s then process async via Redis Streams (Week 3, 3.2/3.3).
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

router = APIRouter(tags=["webhooks"])


@router.get("/meta")
async def verify(request: Request) -> Response:
    """Meta verification handshake — echo hub.challenge when the token matches."""
    raise NotImplementedError("webhook verify — 06-engineering-plan task 3.2")


@router.post("/meta")
async def receive(request: Request) -> Response:
    """Ack fast (200), then enqueue for the inbound worker. No processing inline."""
    raise NotImplementedError("webhook receive + enqueue — 06-engineering-plan task 3.2")
