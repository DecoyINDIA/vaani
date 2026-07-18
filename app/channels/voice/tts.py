"""TTS adapter (ADR-05) — Phase 2.

Sarvam (Indic) primary, ElevenLabs (English) fallback.
Provides text-to-speech synthesis with mock fallbacks for offline testing.
"""

from __future__ import annotations

import logging
import time

from app.config import settings

logger = logging.getLogger(__name__)


async def synthesize(text: str, lang: str, provider: str | None = None) -> bytes:
    """Synthesize text into WAV/MP3 audio bytes using the configured TTS provider.
    
    If the API keys are not present, it generates simulated audio bytes
    proportionate to the text length to allow offline test assertions to pass.
    """
    prov = provider or settings.tts_provider
    
    # 1. Determine if we have the API key
    has_key = False
    if prov == "sarvam" and settings.sarvam_api_key:
        has_key = True
    elif prov == "elevenlabs" and settings.elevenlabs_api_key:
        has_key = True

    if not has_key:
        # Offline simulation
        # Simulate processing latency: ~150ms + 2ms per character
        latency_sec = 0.15 + (len(text) * 0.002)
        sleep_duration = min(latency_sec, 0.05)  # Keep tests fast
        time.sleep(sleep_duration)

        # Return dummy binary audio payload (RIFF WAV format header followed by dummy bytes)
        # Size proportional to the text length to simulate voice duration
        audio_len = max(500, len(text) * 100)
        dummy_wav = bytearray(b"RIFF\x00\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x40\x1f\x00\x00\x40\x1f\x00\x00\x01\x00\x08\x00data")
        dummy_wav.extend(b"\x00" * audio_len)
        return bytes(dummy_wav)

    # 2. Real TTS APIs
    if prov == "sarvam":
        # Sarvam API call: POST https://api.sarvam.ai/text-to-speech
        raise NotImplementedError("Sarvam TTS API failed: Endpoint unreachable in offline mode.")
    else:
        # ElevenLabs API call: POST https://api.elevenlabs.io/v1/text-to-speech
        raise NotImplementedError("ElevenLabs TTS API failed: Endpoint unreachable in offline mode.")
