"""Voice test suite (L15 TDD loop).

Tests call events, WebSocket media streaming, consent playing, user query handling,
barge-in interruption, latency budgets, and cross-model overrides.
"""

from __future__ import annotations

import pytest
from app.config import settings
from app.main import app
from fastapi.testclient import TestClient
from ops.seed_tenant import seed_async


@pytest.fixture(autouse=True)
async def setup_test_db():
    """Seed the database with test_tenant configuration before each test."""
    await seed_async("default.yaml")


def test_exotel_webhook_tenant_resolution() -> None:
    client = TestClient(app)
    
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


def test_exotel_websocket_stream_e2e() -> None:
    client = TestClient(app)
    
    # Connect to websocket stream
    # Pass caller_phone in stream connection as parameter (simulating Exotel headers/channel context)
    with client.websocket_connect("/webhooks/stream/test_tenant/call_websocket?caller_phone=919876543210") as ws:
        # 1. First event must play the voice consent audio bytes
        consent_audio = ws.receive_bytes()
        assert len(consent_audio) > 100
        assert consent_audio.startswith(b"RIFF")  # WAV header signature

        # 2. Send DTMF_1 to accept consent
        ws.send_bytes(b"DTMF_1")
        welcome_audio = ws.receive_bytes()
        assert welcome_audio.startswith(b"RIFF")

        response_json = ws.receive_json()
        assert response_json["event"] == "response"
        assert response_json["consent_accepted"] is True

        # 3. Send User query via simulated speech trigger
        # We target a specific line in our metadata.csv lookup:
        # VC_HI_032: "क्लीनिक कब से कब तक खुला रहता है?" -> faq_hours
        query_payload = b"QUERY:hi:evals/voice_corpus/audio/vc_hi_032.wav"
        ws.send_bytes(query_payload)
        
        response_audio = ws.receive_bytes()
        assert response_audio.startswith(b"RIFF")
        
        meta_json = ws.receive_json()
        assert meta_json["event"] == "response"
        assert meta_json["transcript"] == "क्लीनिक कब से कब तक खुला रहता है?"
        assert "open" in meta_json["response"].lower() or "timings" in meta_json["response"].lower() or "sharma" in meta_json["response"].lower()
        
        # Verify latency tracking was captured
        latencies = meta_json["latencies"]
        assert "stt_ms" in latencies
        assert "llm_ms" in latencies
        assert "tts_ms" in latencies
        assert "total_ms" in latencies


def test_voice_barge_in() -> None:
    client = TestClient(app)
    
    with client.websocket_connect("/webhooks/stream/test_tenant/call_bargein") as ws:
        # Consume consent audio
        ws.receive_bytes()
        
        # Send user talking trigger (test b"TALK" prefix)
        ws.send_bytes(b"TALK_sound_energy_bytes_inbound")
        
        event_json = ws.receive_json()
        assert event_json["event"] == "barge_in"
        assert event_json["status"] == "playback_interrupted"


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
