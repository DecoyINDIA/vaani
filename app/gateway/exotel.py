"""Exotel voice webhook + media stream (TRD §5.1) — Phase 2.

POST /webhooks/exotel — handles incoming call routing by voice number.
WebSocket /webhooks/exotel/stream — bidirectional real-time audio stream.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Request, Response, WebSocket, WebSocketDisconnect

from app.channels.voice.barge_in import detect_voice_activity, interrupt_playback
from app.channels.voice.session import VoiceSession
from app.models.collections import Tenants

logger = logging.getLogger(__name__)
router = APIRouter(tags=["webhooks"])


async def resolve_voice_tenant(voice_number: str) -> str:
    """Resolve tenant ID from voice business number."""
    tenant = await Tenants.find_by_voice_number(voice_number)
    if not tenant:
        raise ValueError(f"Unknown voice_number: {voice_number}")
    return str(tenant["_id"])


@router.post("/exotel")
async def receive(request: Request) -> Response:
    """Accept call event from Exotel, resolve tenant, and return XML to connect WebSocket stream."""
    try:
        # Exotel sends form URL-encoded parameters on webhook
        form_data = await request.form()
        to_number = form_data.get("To")
        from_number = form_data.get("From")
        call_sid = form_data.get("CallSid")
    except Exception:
        # Fallback for JSON testing/script payloads
        try:
            body = await request.json()
            to_number = body.get("To")
            from_number = body.get("From")
            call_sid = body.get("CallSid")
        except Exception:
            to_number = None
            from_number = None
            call_sid = None

    if not to_number or not call_sid:
        logger.warning("Exotel webhook missing To or CallSid parameter")
        return Response(content="<Response><Hangup/></Response>", media_type="application/xml", status_code=400)

    try:
        tenant_id = await resolve_voice_tenant(to_number)
    except ValueError as e:
        logger.warning(f"Tenant resolution failed: {e}")
        # Return static refusal XML
        refusal_xml = (
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
            "<Response>\n"
            "    <Say>This number is not registered on the Vaani platform.</Say>\n"
            "    <Hangup/>\n"
            "</Response>"
        )
        return Response(content=refusal_xml, media_type="application/xml")

    # Connect to the media stream WebSocket
    host = request.url.netloc
    scheme = "wss" if request.url.scheme == "https" else "ws"
    websocket_url = f"{scheme}://{host}/webhooks/stream/{tenant_id}/{call_sid}"
    
    xml_response = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<Response>\n"
        "    <Connect>\n"
        f"        <Stream url=\"{websocket_url}\"/>\n"
        "    </Connect>\n"
        "</Response>"
    )
    
    return Response(content=xml_response, media_type="application/xml")


@router.websocket("/stream/{tenant_id}/{call_sid}")
async def websocket_stream(
    websocket: WebSocket,
    tenant_id: str,
    call_sid: str,
    caller_phone: str | None = None
) -> None:
    """FastAPI WebSocket stream for bidirectional voice communication."""
    await websocket.accept()
    
    # Initialize voice session
    session = VoiceSession(tenant_id, call_sid, caller_phone=caller_phone)
    await session.initialize()
    
    logger.info(f"Accepted Exotel WebSocket stream for tenant {tenant_id}, call {call_sid}")

    # Immediately play DPDP consent script at start of call
    # Default language is Hinglish (hi-Latn) for clinics unless query triggers else
    consent_result = await session.handle_user_input(b"INIT", lang="hi-Latn")
    await websocket.send_bytes(consent_result["audio"])

    try:
        while True:
            # Receive binary audio chunk from Exotel stream
            data = await websocket.receive_bytes()

            # 1. Check for barge-in (caller starts speaking while TTS is speaking)
            is_control = data.startswith(b"DTMF_") or data.startswith(b"QUERY:") or data == b"INIT"
            if not is_control and detect_voice_activity(data):
                interrupt_playback(session)
                await websocket.send_json({
                    "event": "barge_in",
                    "status": "playback_interrupted"
                })

            # 2. Process query payload triggers
            # For testing/harness, we allow sending query commands prefixed with b"QUERY:" or b"DTMF_"
            if data.startswith(b"QUERY:") or data.startswith(b"DTMF_"):
                if data.startswith(b"QUERY:"):
                    payload_str = data[6:].decode("utf-8", errors="ignore")
                    # Format: "language:query_file_path_or_text"
                    parts = payload_str.split(":", 1)
                    lang = parts[0] if len(parts) > 1 else "hi-Latn"
                    query = parts[1] if len(parts) > 1 else parts[0]
                    query_bytes = query.encode("utf-8")
                else:
                    lang = "hi-Latn"
                    query_bytes = data
                
                # Run query through the session turn
                result = await session.handle_user_input(query_bytes, lang=lang)
                
                # Send synthesized TTS audio reply
                await websocket.send_bytes(result["audio"])
                
                # Send metadata response JSON
                response_payload = {
                    "event": "response",
                    "transcript": result.get("transcript", ""),
                    "response": result.get("response", ""),
                    "latencies": result.get("latencies", {}),
                    "filler_injected": result.get("filler_injected", False),
                    "interrupted": result.get("interrupted", False)
                }
                if result.get("consent_accepted"):
                    response_payload["consent_accepted"] = True
                await websocket.send_json(response_payload)
    except WebSocketDisconnect:
        logger.info(f"WebSocket stream disconnected for call {call_sid}")
    except Exception as e:
        logger.error(f"Error in WebSocket stream loop: {e}")
        try:
            await websocket.close()
        except Exception:
            pass
