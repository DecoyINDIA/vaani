"""Exotel voice webhook + media stream (TRD §5.1) — Phase 2.

POST /webhooks/exotel — call events; a media-stream WebSocket carries audio.
Voice is a channel adapter, not a new agent (06-engineering-plan §2): it emits
the same normalized inbound events as the Meta gateway. Router is not mounted
until Phase 2.
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

router = APIRouter(tags=["webhooks"])


@router.post("/exotel")
async def receive(request: Request) -> Response:
    raise NotImplementedError("exotel webhook — 06-engineering-plan Phase 2")
