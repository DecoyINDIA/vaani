"""Voice test suite (L15 TDD loop).

Tests call events, WebSocket media streaming, consent playing, user query handling,
barge-in interruption, latency budgets, and cross-model overrides.
"""

from __future__ import annotations

import base64
import html
import re
import struct
from unittest.mock import AsyncMock
from urllib.parse import urlsplit

import pytest
from app.channels.voice.session import VoiceSession
from app.config import settings
from app.main import app
from fastapi.testclient import TestClient
from ops.seed_tenant import seed_demo_async


@pytest.fixture(autouse=True)
async def setup_test_db():
    """Seed the database with test_tenant configuration before each test."""
    from app.models.base import get_db
    db = get_db()
    for col in ["contacts", "conversations", "bookings", "slots", "messages", "audit_log"]:
        await db[col].delete_many({})
    await seed_demo_async()


def _verify_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.gateway.exotel.verify_exotel_call",
        AsyncMock(return_value={"Sid": "verified"}),
    )


def _stream_path(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    call_sid: str,
    caller: str = "919876543210",
) -> str:
    _verify_provider(monkeypatch)
    response = client.post(
        "/webhooks/exotel",
        data={"To": "919999999998", "From": caller, "CallSid": call_sid},
    )
    assert response.status_code == 200
    match = re.search(r'<Stream url="([^"]+)"', response.text)
    assert match
    url = urlsplit(html.unescape(match.group(1)))
    return f"{url.path}?{url.query}"


def _start_event(call_sid: str, sequence: int = 1) -> dict[str, object]:
    return {
        "event": "start",
        "sequence_number": str(sequence),
        "stream_sid": f"stream-{call_sid}",
        "start": {
            "stream_sid": f"stream-{call_sid}",
            "call_sid": call_sid,
            "account_sid": settings.exotel_sid,
            "from": "919876543210",
            "to": "919999999998",
            "custom_parameters": {},
            "media_format": {
                "encoding": "audio/x-raw",
                "sample_rate": "8000",
                "bit_rate": "16",
            },
        },
    }


def _receive_playback(ws: object) -> str:
    saw_audio = False
    while True:
        message = ws.receive_json()  # type: ignore[attr-defined]
        if message["event"] == "media":
            assert base64.b64decode(message["media"]["payload"], validate=True)
            saw_audio = True
        elif message["event"] == "mark":
            assert saw_audio
            return str(message["mark"]["name"])


def test_exotel_webhook_tenant_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    client = TestClient(app)
    _verify_provider(monkeypatch)
    
    # 1. Resolve successfully registered tenant voice number
    payload = {"To": "919999999998", "From": "919876543210", "CallSid": "call_12345"}
    resp = client.post("/webhooks/exotel", data=payload)
    
    assert resp.status_code == 200
    assert "application/xml" in resp.headers["content-type"]
    assert "stream/test_tenant/call_12345" in resp.text
    assert "<Connect>" in resp.text

    # 2. Reject unregistered tenant voice number
    payload_bad = {"To": "910000000000", "From": "919876543210", "CallSid": "call_12345"}
    resp_bad = client.post("/webhooks/exotel", data=payload_bad)
    
    assert resp_bad.status_code == 200
    assert "not registered on the Vaani platform" in resp_bad.text
    assert "<Hangup/>" in resp_bad.text

    # 3. Handle missing parameters gracefully
    payload_missing = {"From": "919876543210"}
    resp_missing = client.post("/webhooks/exotel", data=payload_missing)
    assert resp_missing.status_code == 400


def test_exotel_websocket_stream_e2e(monkeypatch: pytest.MonkeyPatch) -> None:
    client = TestClient(app)
    stream_path = _stream_path(client, monkeypatch, "call_websocket")
    
    # Connect to websocket stream
    # Pass caller_phone in stream connection as parameter (simulating Exotel headers/channel context)
    with client.websocket_connect(stream_path) as ws:
        ws.send_json({"event": "connected"})
        ws.send_json(_start_event("call_websocket"))
        consent_mark = _receive_playback(ws)
        ws.send_json(
            {
                "event": "mark",
                "sequence_number": "2",
                "stream_sid": "stream-call_websocket",
                "mark": {"name": consent_mark},
            }
        )

        ws.send_json(
            {
                "event": "dtmf",
                "sequence_number": "3",
                "stream_sid": "stream-call_websocket",
                "dtmf": {"digit": "1", "duration": "100"},
            }
        )
        dtmf_mark = _receive_playback(ws)
        ws.send_json(
            {
                "event": "mark",
                "sequence_number": "4",
                "stream_sid": "stream-call_websocket",
                "mark": {"name": dtmf_mark},
            }
        )

        voiced = struct.pack("<800h", *([1000] * 800))
        silence = b"\x00\x00" * 800
        for sequence, audio in enumerate([voiced, *([silence] * 6)], start=5):
            ws.send_json(
                {
                    "event": "media",
                    "sequence_number": str(sequence),
                    "stream_sid": "stream-call_websocket",
                    "media": {
                        "chunk": str(sequence),
                        "timestamp": str(sequence * 100),
                        "payload": base64.b64encode(audio).decode(),
                    },
                }
            )
        _receive_playback(ws)
        ws.send_json(
            {
                "event": "stop",
                "sequence_number": "12",
                "stream_sid": "stream-call_websocket",
                "stop": {
                    "call_sid": "call_websocket",
                    "account_sid": settings.exotel_sid,
                    "reason": "callended",
                },
            }
        )


def test_voice_barge_in(monkeypatch: pytest.MonkeyPatch) -> None:
    client = TestClient(app)
    stream_path = _stream_path(client, monkeypatch, "call_bargein")

    with client.websocket_connect(stream_path) as ws:
        ws.send_json({"event": "connected"})
        ws.send_json(_start_event("call_bargein"))
        _receive_playback(ws)
        voiced = struct.pack("<800h", *([1000] * 800))
        ws.send_json(
            {
                "event": "media",
                "sequence_number": "2",
                "stream_sid": "stream-call_bargein",
                "media": {"chunk": "1", "timestamp": "100", "payload": base64.b64encode(voiced).decode()},
            }
        )
        event_json = ws.receive_json()
        assert event_json == {"event": "clear", "stream_sid": "stream-call_bargein"}


@pytest.mark.asyncio
async def test_cross_model_compatibility() -> None:
    """Verifies that the agent graph runs cleanly with classifier and responder overrides."""
    from app.channels.voice.session import VoiceSession
    
    # Temporarily set overrides in configurations
    old_classifier = settings.llm_model_classifier
    old_responder = settings.llm_model_responder
    
    # Test with alternative model overrides (cross-model verification)
    settings.llm_model_classifier = "google/gemini-2.5-pro"
    settings.llm_model_responder = "google/gemini-2.5-flash"
    
    try:
        session = VoiceSession("test_tenant", "call_cross_model", caller_phone="919876543210")
        await session.initialize()
        
        # Play consent
        consent_res = await session.handle_user_input(b"INIT", lang="hi")
        assert consent_res["consent_pending"] is True
        
        # Accept consent
        accept_res = await session.handle_user_input(b"DTMF_1", lang="hi")
        assert accept_res["consent_accepted"] is True
        
        # Send query
        # Using a valid file from our voice corpus metadata to test offline lookup
        query_bytes = b"evals/voice_corpus/audio/vc_hi_032.wav"
        res = await session.handle_user_input(query_bytes, lang="hi")
        
        assert "timings" in res["response"].lower() or "sharma" in res["response"].lower() or "open" in res["response"].lower()
        assert res["latencies"]["total_ms"] > 0
    finally:
        # Revert settings
        settings.llm_model_classifier = old_classifier
        settings.llm_model_responder = old_responder


def test_exotel_malformed_stream_events_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi import WebSocketDisconnect

    client = TestClient(app)

    # 1. Event before start -> code 4002
    stream_path = _stream_path(client, monkeypatch, "call_malformed_1")
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(stream_path) as ws:
            ws.send_json(
                {
                    "event": "media",
                    "sequence_number": "1",
                    "stream_sid": "stream-early",
                    "media": {"payload": "AAAA"},
                }
            )
            ws.receive_json()
    assert exc.value.code == 4002

    # 2. Duplicate start -> code 4002
    stream_path = _stream_path(client, monkeypatch, "call_malformed_2")
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(stream_path) as ws:
            ws.send_json({"event": "connected"})
            ws.send_json(_start_event("call_malformed_2", sequence=1))
            _receive_playback(ws)
            ws.send_json(_start_event("call_malformed_2", sequence=2))
            ws.receive_json()
    assert exc.value.code == 4002

    # 3. Changed stream_sid -> code 4002
    stream_path = _stream_path(client, monkeypatch, "call_malformed_3")
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(stream_path) as ws:
            ws.send_json({"event": "connected"})
            ws.send_json(_start_event("call_malformed_3", sequence=1))
            _receive_playback(ws)
            ws.send_json(
                {
                    "event": "mark",
                    "sequence_number": "2",
                    "stream_sid": "changed_sid",
                    "mark": {"name": "test"},
                }
            )
            ws.receive_json()
    assert exc.value.code == 4002

    # 4. Out of order sequence number -> code 4002
    stream_path = _stream_path(client, monkeypatch, "call_malformed_4")
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(stream_path) as ws:
            ws.send_json({"event": "connected"})
            ws.send_json(_start_event("call_malformed_4", sequence=5))
            _receive_playback(ws)
            ws.send_json(
                {
                    "event": "mark",
                    "sequence_number": "4",
                    "stream_sid": "stream-call_malformed_4",
                    "mark": {"name": "test"},
                }
            )
            ws.receive_json()
    assert exc.value.code == 4002

    # 5. Invalid DTMF digit -> code 4002
    stream_path = _stream_path(client, monkeypatch, "call_malformed_5")
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(stream_path) as ws:
            ws.send_json({"event": "connected"})
            ws.send_json(_start_event("call_malformed_5", sequence=1))
            _receive_playback(ws)
            ws.send_json(
                {
                    "event": "dtmf",
                    "sequence_number": "2",
                    "stream_sid": "stream-call_malformed_5",
                    "dtmf": {"digit": "Z"},
                }
            )
            ws.receive_json()
    assert exc.value.code == 4002

    # 6. Unsupported event name -> code 4002
    stream_path = _stream_path(client, monkeypatch, "call_malformed_6")
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(stream_path) as ws:
            ws.send_json({"event": "connected"})
            ws.send_json(_start_event("call_malformed_6", sequence=1))
            _receive_playback(ws)
            ws.send_json(
                {
                    "event": "unsupported_event",
                    "sequence_number": "2",
                    "stream_sid": "stream-call_malformed_6",
                }
            )
            ws.receive_json()
    assert exc.value.code == 4002


@pytest.mark.asyncio
@pytest.mark.parametrize("lang", ["hi", "hi-Latn", "or", "en"])
async def test_voice_multi_language_and_latency_budgets(lang: str) -> None:
    session = VoiceSession("test_tenant", f"call_lang_{lang}", caller_phone="919876543210")
    await session.initialize()

    # Step 1: Consent
    consent = await session.handle_user_input(b"INIT", lang=lang)
    assert consent["consent_pending"] is True
    assert "Sharma Dental Clinic" in consent["response"]
    assert len(consent["audio"]) > 44

    # Step 2: DTMF_1 acceptance
    accept = await session.handle_user_input(b"DTMF_1", lang=lang)
    assert accept["consent_accepted"] is True
    assert len(accept["audio"]) > 44

    # Step 3: Query
    query_bytes = b"evals/voice_corpus/audio/vc_hi_032.wav"
    res = await session.handle_user_input(query_bytes, lang=lang)
    assert res["response"]
    assert len(res["audio"]) > 44

    # Latencies
    latencies = res["latencies"]
    assert "stt_ms" in latencies
    assert "llm_ms" in latencies
    assert "tts_ms" in latencies
    assert "total_ms" in latencies
    assert latencies["total_ms"] > 0
    assert latencies["total_ms"] <= 2000
    assert latencies["stt_ms"] <= 300
    assert latencies["llm_ms"] <= 700
    assert latencies["tts_ms"] <= 400


@pytest.mark.asyncio
async def test_voice_low_confidence_and_empty_utterance_recovery() -> None:
    from unittest.mock import AsyncMock

    import app.channels.voice.session as session_module

    session = VoiceSession("test_tenant", "call_recovery", caller_phone="919876543210")
    await session.initialize()
    await session.handle_user_input(b"INIT", lang="hi")
    await session.handle_user_input(b"DTMF_1", lang="hi")

    # STT returning empty transcript
    empty_stt = AsyncMock(
        return_value={"text": "   ", "confidence": 0.1, "latency_ms": 50, "provider": "sarvam"}
    )
    old_transcribe = session_module.transcribe_audio
    session_module.transcribe_audio = empty_stt
    try:
        res = await session.handle_user_input(b"dummy_silence", lang="hi")
        assert res.get("low_confidence_recovery") is True
        assert "माफ़ कीजिये" in res["response"]
        assert len(res["audio"]) > 44
    finally:
        session_module.transcribe_audio = old_transcribe
