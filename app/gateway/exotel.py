"""Exotel voice webhook + media stream (TRD §5.1) — Phase 2.

POST /webhooks/exotel — handles incoming call routing by voice number.
WebSocket /webhooks/exotel/stream — bidirectional real-time audio stream.
"""

from __future__ import annotations

import logging
import re
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import quote, urlsplit
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from app.billing.meters import record_usage
from app.channels.voice.barge_in import detect_voice_activity, interrupt_playback
from app.channels.voice.exotel_protocol import (
    decode_media,
    media_messages,
    pcm_to_wav,
    validate_start,
)
from app.channels.voice.session import VoiceSession
from app.config import settings
from app.models.collections import Tenants, VoiceGrants
from app.privacy import is_suppressed

logger = logging.getLogger(__name__)
router = APIRouter(tags=["webhooks"])


async def verify_exotel_call(
    call_sid: str, *, expected_to: str, expected_from: str
) -> dict[str, object] | None:
    """Verify callback fields against Exotel's authenticated Call Details API."""
    if settings.use_mock_adapters:
        return None
    host = settings.exotel_subdomain.removeprefix("https://").removeprefix("http://").rstrip("/")
    url = f"https://{host}/v1/Accounts/{settings.exotel_sid}/Calls/{quote(call_sid)}.json"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                auth=(settings.exotel_api_key, settings.exotel_api_token),
                params={"details": "true"},
                timeout=10.0,
            )
    except httpx.HTTPError:
        logger.exception("Exotel call verification failed for %s", call_sid)
        return None
    if response.status_code != 200:
        logger.warning("Exotel call verification returned HTTP %s", response.status_code)
        return None
    body = response.json()
    call = body.get("Call", body)
    if not isinstance(call, dict):
        return None
    if str(call.get("Sid")) != call_sid:
        return None
    if str(call.get("To")) != expected_to or str(call.get("From")) != expected_from:
        return None
    return call


def _grant_signature(
    tenant_id: str, call_sid: str, caller_phone: str, expires_at: int, nonce: str
) -> str:
    import hashlib
    import hmac

    message = f"{tenant_id}:{call_sid}:{caller_phone}:{expires_at}:{nonce}".encode()
    return hmac.new(settings.jwt_secret.encode(), message, hashlib.sha256).hexdigest()


async def issue_stream_grant(
    tenant_id: str, call_sid: str, caller_phone: str, *, ttl_seconds: int = 60
) -> str | None:
    """Create or replay one short-lived, one-use grant for a verified call."""
    grants = VoiceGrants(tenant_id)
    existing = await grants.find_one({"call_sid": call_sid})
    now = datetime.now(UTC).replace(tzinfo=None)
    if existing:
        if existing.get("used_at") or existing.get("expires_at", now) <= now:
            return None
        if existing.get("caller_phone") != caller_phone:
            return None
        expires_at = int(existing["expires_at"].replace(tzinfo=UTC).timestamp())
        nonce = str(existing["nonce"])
    else:
        expires = now + timedelta(seconds=ttl_seconds)
        expires_at = int(expires.replace(tzinfo=UTC).timestamp())
        nonce = secrets.token_urlsafe(24)
        await grants.insert_one(
            {
                "call_sid": call_sid,
                "caller_phone": caller_phone,
                "nonce": nonce,
                "expires_at": expires,
                "created_at": now,
            }
        )
    signature = _grant_signature(tenant_id, call_sid, caller_phone, expires_at, nonce)
    return f"{expires_at}.{nonce}.{signature}"


async def consume_stream_grant(
    tenant_id: str, call_sid: str, caller_phone: str, token: str
) -> bool:
    """Atomically consume a grant bound to every verified call attribute."""
    import hmac

    try:
        expires_raw, nonce, signature = token.split(".", 2)
        expires_at = int(expires_raw)
    except (TypeError, ValueError):
        return False
    now_aware = datetime.now(UTC)
    if expires_at <= int(now_aware.timestamp()):
        return False
    expected = _grant_signature(tenant_id, call_sid, caller_phone, expires_at, nonce)
    if not hmac.compare_digest(signature, expected):
        return False
    consumed = await VoiceGrants(tenant_id).find_one_and_update(
        {
            "call_sid": call_sid,
            "caller_phone": caller_phone,
            "nonce": nonce,
            "expires_at": {"$gt": now_aware.replace(tzinfo=None)},
            "used_at": {"$exists": False},
        },
        {"$set": {"used_at": now_aware.replace(tzinfo=None)}},
    )
    return consumed is not None


async def resolve_voice_tenant(voice_number: str) -> str:
    """Resolve tenant ID from voice business number."""
    tenant = await Tenants.find_by_voice_number(voice_number)
    if not tenant:
        raise ValueError(f"Unknown voice_number: {voice_number}")
    return str(tenant["_id"])


def _public_voice_urls(
    tenant_id: str, grant_id: str, caller_phone: str, token: str
) -> tuple[str, str]:
    base_url = settings.voice_public_base_url.rstrip("/")
    parsed = urlsplit(base_url)
    if parsed.scheme != "https" or not parsed.netloc or parsed.query or parsed.fragment:
        raise RuntimeError("VOICE_PUBLIC_BASE_URL must be a public HTTPS origin")
    stream_url = (
        f"wss://{parsed.netloc}/webhooks/stream/{quote(tenant_id)}/{quote(grant_id)}"
        f"?token={quote(token)}&caller_phone={quote(caller_phone)}"
    )
    return stream_url, f"{base_url}/webhooks/exotel/status"


async def start_outbound_call(tenant_id: str, caller_phone: str) -> dict[str, str]:
    """Dial one customer and connect the answered call to Vaani's voice stream."""
    if not re.fullmatch(r"\+[1-9]\d{7,14}", caller_phone):
        raise ValueError("Destination must be an E.164 phone number")
    if await is_suppressed(tenant_id, caller_phone):
        raise PermissionError("Destination is suppressed")

    tenant = await Tenants.find_by_id(tenant_id)
    voice_number = str((tenant or {}).get("voice_number", "")).strip()
    if not voice_number:
        raise RuntimeError("Tenant has no Exotel voice number")
    if not all(
        (
            settings.exotel_sid,
            settings.exotel_api_key,
            settings.exotel_api_token,
            settings.exotel_subdomain,
        )
    ):
        raise RuntimeError("Exotel credentials are not configured")

    grant_id = f"out_{secrets.token_urlsafe(18)}"
    token = await issue_stream_grant(
        tenant_id, grant_id, caller_phone, ttl_seconds=300
    )
    if not token:
        raise RuntimeError("Could not create outbound stream grant")

    try:
        stream_url, status_url = _public_voice_urls(
            tenant_id, grant_id, caller_phone, token
        )
        host = (
            settings.exotel_subdomain.removeprefix("https://")
            .removeprefix("http://")
            .rstrip("/")
        )
        endpoint = f"https://{host}/v1/Accounts/{settings.exotel_sid}/Calls/connect"
        async with httpx.AsyncClient() as client:
            response = await client.post(
                endpoint,
                auth=(settings.exotel_api_key, settings.exotel_api_token),
                data={
                    "From": caller_phone,
                    "CallerId": voice_number,
                    "StreamUrl": stream_url,
                    "StreamType": "bidirectional",
                    "Record": "false",
                    "TimeLimit": "900",
                    "StatusCallback": status_url,
                    "StatusCallbackEvents[]": "terminal",
                },
                timeout=15.0,
            )
        if response.status_code < 200 or response.status_code >= 300:
            raise RuntimeError(f"Exotel outbound call failed with HTTP {response.status_code}")
        body = response.json()
        call = body.get("Call") if isinstance(body, dict) else None
        if not isinstance(call, dict):
            raise RuntimeError("Exotel outbound call returned no call")
        call_sid = call.get("Sid")
        if not isinstance(call_sid, str) or not call_sid:
            raise RuntimeError("Exotel outbound call returned no call SID")
        status = call.get("Status", "queued")
        return {"call_sid": call_sid, "status": str(status)}
    except (httpx.HTTPError, ValueError, RuntimeError):
        await VoiceGrants(tenant_id).delete_many({"call_sid": grant_id})
        raise


def _verified_conversation_duration(call: dict[str, object]) -> int | None:
    details = call.get("Details")
    value = details.get("ConversationDuration") if isinstance(details, dict) else None
    try:
        duration = int(str(value))
    except (TypeError, ValueError):
        return None
    return duration if 0 <= duration <= 24 * 60 * 60 else None


def _provider_end_time(value: object, timezone: ZoneInfo) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone).astimezone(UTC)


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

    if not to_number or not from_number or not call_sid:
        logger.warning("Exotel webhook missing To, From, or CallSid parameter")
        return Response(
            content="<Response><Hangup/></Response>",
            media_type="application/xml",
            status_code=400,
        )

    verified = await verify_exotel_call(
        str(call_sid), expected_to=str(to_number), expected_from=str(from_number)
    )
    if not verified:
        logger.warning("Rejected unverified Exotel call %s", call_sid)
        return Response(content="Unauthorized call", status_code=401)

    try:
        tenant_id = await resolve_voice_tenant(str(to_number))
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

    if await is_suppressed(tenant_id, str(from_number)):
        logger.info("Refusing call from suppressed caller %s", from_number)
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
    
    token = await issue_stream_grant(tenant_id, str(call_sid), str(from_number))
    if not token:
        return Response(content="Call grant already consumed or expired", status_code=409)
    websocket_url = (
        f"{scheme}://{host}/webhooks/stream/{tenant_id}/{quote(str(call_sid))}"
        f"?token={quote(token)}&amp;caller_phone={quote(str(from_number))}"
    )
    
    xml_response = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<Response>\n"
        "    <Connect>\n"
        f"        <Stream url=\"{websocket_url}\"/>\n"
        "    </Connect>\n"
        "</Response>"
    )
    
    return Response(content=xml_response, media_type="application/xml")


@router.post("/exotel/missed_call")
async def missed_call(request: Request) -> Response:
    """Handle missed call event from Exotel, trigger WhatsApp contact bridge."""
    try:
        form_data = await request.form()
        from_number = form_data.get("From")
        to_number = form_data.get("To")
        call_sid = form_data.get("CallSid")
    except Exception:
        try:
            body = await request.json()
            from_number = body.get("From")
            to_number = body.get("To")
            call_sid = body.get("CallSid")
        except Exception:
            from_number = None
            to_number = None
            call_sid = None

    if not from_number or not to_number or not call_sid:
        logger.warning("Missed call webhook missing From, To, or CallSid parameter")
        return Response(content="Missing parameter", status_code=400)

    verified = await verify_exotel_call(
        str(call_sid), expected_to=str(to_number), expected_from=str(from_number)
    )
    if not verified:
        logger.warning("Rejected unverified Exotel missed call %s", call_sid)
        return Response(content="Unauthorized call", status_code=401)

    try:
        tenant_id = await resolve_voice_tenant(str(to_number))
    except ValueError as e:
        logger.warning(f"Tenant resolution failed for missed call: {e}")
        return Response(content="Tenant not found", status_code=404)
    tenant = await Tenants.find_by_id(tenant_id)

    if await is_suppressed(tenant_id, str(from_number)):
        logger.info("Ignoring missed call from suppressed caller %s", from_number)
        return Response(content="Suppressed caller", status_code=200)

    # 1. Resolve or create contact
    from app.models.collections import Contacts, Conversations
    contacts_accessor = Contacts(tenant_id)
    contact = await contacts_accessor.find_one({"phone": from_number})
    if not contact:
        await contacts_accessor.insert_one({
            "phone": from_number,
            "wa_id": from_number,
            "tags": ["missed_call_bridge"],
            "created_at": 0
        })
        contact = await contacts_accessor.find_one({"phone": from_number})

    contact_id = str(contact["_id"]) if contact else "unknown"

    # 2. Check or open conversation
    convs_accessor = Conversations(tenant_id)
    existing_conv = await convs_accessor.find_one(
        {"contact_id": contact_id, "state": {"$ne": "closed"}}
    )
    if not existing_conv:
        from datetime import datetime
        await convs_accessor.insert_one({
            "contact_id": contact_id,
            "channel": "wa",
            "state": "bot",
            "started_at": datetime.now(UTC).replace(tzinfo=None),
            "last_msg_at": datetime.now(UTC).replace(tzinfo=None)
        })

    # 3. Dispatch template bridge
    from app import audit
    from app.channels.whatsapp import send_template
    operation_key = f"missed-call:{tenant_id}:{from_number}:{call_sid or 'unknown'}"
    try:
        await send_template(
            tenant_id=tenant_id,
            wa_id=str(from_number),
            template="missed_call_bridge",
            variables={"clinic_name": str((tenant or {}).get("name", "our business"))},
            operation_key=operation_key,
        )
        await audit.record(
            tenant_id,
            actor="system",
            event_type="outbound_template",
            operation_key=f"missed-call-record:{operation_key}",
            payload={
                "template": "T_MISSED_CALL_BRIDGE",
                "to": from_number,
                "reason": "missed_call",
            },
        )
    except Exception as e:
        logger.error("Failed to send missed call bridge template: %s", type(e).__name__)

    return Response(content='{"status":"bridge_initiated"}', status_code=200)


@router.post("/exotel/status")
async def call_status(request: Request) -> Response:
    """Meter only API-verified terminal conversation seconds, replay safely."""
    try:
        fields = dict(await request.form())
    except Exception:
        try:
            fields = dict(await request.json())
        except Exception:
            fields = {}
    call_sid = str(fields.get("CallSid", ""))
    to_number = str(fields.get("To", ""))
    from_number = str(fields.get("From", ""))
    if not call_sid or not to_number or not from_number:
        return JSONResponse({"detail": "Missing call identity"}, status_code=400)
    verified = await verify_exotel_call(
        call_sid, expected_to=to_number, expected_from=from_number
    )
    if not verified:
        return JSONResponse({"detail": "Unauthorized call"}, status_code=401)
    if str(verified.get("Status", "")).lower() != "completed":
        return JSONResponse({"status": "ignored", "reason": "non_billable_status"})

    duration = _verified_conversation_duration(verified)
    if duration is None:
        return JSONResponse(
            {"detail": "Verified call duration is not finalized"}, status_code=503
        )
    callback_duration = fields.get("ConversationDuration")
    if callback_duration is not None:
        try:
            if int(str(callback_duration)) != duration:
                return JSONResponse(
                    {"detail": "Callback duration does not match verified call"},
                    status_code=409,
                )
        except ValueError:
            return JSONResponse({"detail": "Invalid callback duration"}, status_code=400)

    direction = str(verified.get("Direction", "")).lower()
    candidate_numbers = [to_number]
    if direction == "outbound-api":
        candidate_numbers = [
            str(verified.get("PhoneNumberSid", "")),
            str(fields.get("PhoneNumberSid", "")),
            from_number,
            to_number,
        ]
    tenant_ids: set[str] = set()
    for number in candidate_numbers:
        if not number:
            continue
        try:
            tenant_ids.add(await resolve_voice_tenant(number))
        except ValueError:
            continue
    if len(tenant_ids) != 1:
        return JSONResponse({"detail": "Tenant not found"}, status_code=404)
    tenant_id = tenant_ids.pop()
    tenant = await Tenants.find_by_id(tenant_id)
    timezone = ZoneInfo(str((tenant or {}).get("timezone", "Asia/Kolkata")))
    occurred_at = _provider_end_time(verified.get("EndTime"), timezone)
    if occurred_at is None:
        return JSONResponse(
            {"detail": "Verified call end time is not finalized"}, status_code=503
        )
    created = await record_usage(
        tenant_id,
        event_id=f"exotel:{call_sid}:conversation-duration",
        metric="voice_audio_seconds",
        quantity=duration,
        occurred_at=occurred_at,
    )
    return JSONResponse(
        {
            "status": "recorded" if created else "duplicate",
            "duration_seconds": duration,
        }
    )


@router.websocket("/stream/{tenant_id}/{call_sid}")
async def websocket_stream(
    websocket: WebSocket,
    tenant_id: str,
    call_sid: str,
    token: str | None = None,
    caller_phone: str | None = None
) -> None:
    """FastAPI WebSocket stream for bidirectional voice communication."""
    token_val = token or websocket.query_params.get("token")
    verified_caller = caller_phone or websocket.query_params.get("caller_phone")
    if (
        not token_val
        or not verified_caller
        or not await consume_stream_grant(tenant_id, call_sid, verified_caller, token_val)
    ):
        logger.warning(
            "Unauthenticated WebSocket stream connection attempt: tenant_id=%s, call_sid=%s",
            tenant_id, call_sid,
        )
        await websocket.accept()
        await websocket.close(code=4003)
        return

    await websocket.accept()
    active_call_sid = call_sid
    session = VoiceSession(tenant_id, active_call_sid, caller_phone=verified_caller)
    await session.initialize()
    tenant = await Tenants.find_by_id(tenant_id)
    if not tenant or not tenant.get("voice_number"):
        await websocket.close(code=4004)
        return

    tenant_lang = str(tenant.get("locale_default", "hi-Latn"))
    logger.info("Accepted Exotel WebSocket for tenant %s, call %s", tenant_id, call_sid)
    stream_sid: str | None = None
    sample_rate = 0
    last_sequence = 0
    speech = bytearray()
    silence_ms = 0
    playback_pending = False
    turn = 0

    async def send_audio(result: dict[str, object]) -> None:
        nonlocal playback_pending, turn
        if stream_sid is None:
            raise ValueError("audio cannot be sent before start")
        audio = result.get("audio")
        if not isinstance(audio, bytes):
            raise ValueError("voice result contains no audio")
        for message in media_messages(stream_sid, audio, sample_rate):
            await websocket.send_json(message)
        turn += 1
        await websocket.send_json(
            {
                "event": "mark",
                "stream_sid": stream_sid,
                "mark": {"name": f"turn-{turn}-end"},
            }
        )
        playback_pending = True

    try:
        while True:
            event = await websocket.receive_json()
            if not isinstance(event, dict) or not isinstance(event.get("event"), str):
                raise ValueError("malformed Exotel event")
            sequence = event.get("sequence_number")
            if sequence is not None:
                try:
                    sequence_number = int(sequence)
                except (TypeError, ValueError):
                    raise ValueError("invalid sequence number") from None
                if sequence_number <= last_sequence:
                    raise ValueError("replayed or out-of-order event")
                last_sequence = sequence_number

            event_name = event["event"]
            if event_name == "connected":
                continue
            if event_name == "start":
                if stream_sid is not None:
                    raise ValueError("duplicate start")
                if call_sid.startswith("out_"):
                    start = event.get("start")
                    if not isinstance(start, dict) or not isinstance(start.get("call_sid"), str):
                        raise ValueError("missing outbound call SID")
                    provider_call_sid = start["call_sid"]
                    verified = await verify_exotel_call(
                        provider_call_sid,
                        expected_to=str(start.get("to", "")),
                        expected_from=str(start.get("from", "")),
                    )
                    if not verified or str(verified.get("Direction", "")).lower() != "outbound-api":
                        raise ValueError("unverified outbound call")
                    active_call_sid = provider_call_sid
                    session.call_sid = provider_call_sid
                stream_sid, sample_rate = validate_start(
                    event,
                    call_sid=active_call_sid,
                    account_sid=settings.exotel_sid,
                    caller_phone=verified_caller,
                    called_number=str(tenant["voice_number"]),
                )
                session.sample_rate = sample_rate
                consent = await session.handle_user_input(b"INIT", lang=tenant_lang)
                await send_audio(consent)
                continue
            if stream_sid is None:
                raise ValueError("event received before start")
            if event.get("stream_sid") != stream_sid:
                raise ValueError("stream_sid changed")

            if event_name == "media":
                audio = decode_media(event, stream_sid)
                has_voice = detect_voice_activity(audio)
                if has_voice and playback_pending:
                    session.is_speaking = True
                    interrupt_playback(session)
                    await websocket.send_json({"event": "clear", "stream_sid": stream_sid})
                    playback_pending = False
                if has_voice:
                    speech.extend(audio)
                    silence_ms = 0
                elif speech:
                    speech.extend(audio)
                    silence_ms += int(len(audio) * 1000 / (sample_rate * 2))
                    if silence_ms >= 600:
                        utterance = pcm_to_wav(bytes(speech), sample_rate)
                        speech.clear()
                        silence_ms = 0
                        result = await session.handle_user_input(utterance, lang=tenant_lang)
                        await send_audio(result)
            elif event_name == "dtmf":
                dtmf = event.get("dtmf")
                if not isinstance(dtmf, dict) or str(dtmf.get("digit")) not in set("0123456789#*"):
                    raise ValueError("invalid DTMF event")
                result = await session.handle_user_input(
                    f"DTMF_{dtmf['digit']}".encode(), lang=tenant_lang
                )
                await send_audio(result)
            elif event_name == "mark":
                playback_pending = False
            elif event_name == "stop":
                stop = event.get("stop")
                if (
                    not isinstance(stop, dict)
                    or stop.get("call_sid") != active_call_sid
                    or stop.get("account_sid") != settings.exotel_sid
                ):
                    raise ValueError("invalid stop event")
                break
            else:
                raise ValueError(f"unsupported Exotel event: {event_name}")
    except WebSocketDisconnect:
        logger.info("WebSocket stream disconnected for call %s", active_call_sid)
    except ValueError as e:
        logger.warning(
            "Rejected malformed Exotel stream event for %s: %s", active_call_sid, e
        )
        await websocket.close(code=4002)
    except Exception as e:
        logger.error("Error in WebSocket stream loop: %s", e, exc_info=True)
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
    finally:
        if session.conversation_id:
            from app.models.collections import Conversations

            convs = Conversations(tenant_id)
            target_id = (
                await convs.resolve_id(str(session.conversation_id))
                or session.conversation_id
            )
            await convs.update_one(
                {"_id": target_id},
                {"$set": {"state": "closed", "ended_at": datetime.now(UTC).replace(tzinfo=None)}},
            )
