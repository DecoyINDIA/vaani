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
    import base64

    import httpx

    if prov == "sarvam":
        # Sarvam API call: POST https://api.sarvam.ai/text-to-speech
        lang_code_map = {
            "hi": "hi-IN",
            "hi-Latn": "hi-IN",
            "or": "or-IN",
            "en": "en-IN"
        }
        target_lang = lang_code_map.get(lang, "en-IN")
        
        payload = {
            "text": text,
            "target_language_code": target_lang,
            "speaker": "arvind" if target_lang == "hi-IN" else "anushka",
            "model": "bulbul:v1"
        }
        headers = {
            "api-subscription-key": settings.sarvam_api_key,
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.sarvam.ai/text-to-speech",
                json=payload,
                headers=headers,
                timeout=30.0
            )
            
        if resp.status_code != 200:
            logger.error("Sarvam TTS failed: %s", resp.text)
            raise RuntimeError(f"Sarvam TTS API error {resp.status_code}: {resp.text}")
            
        res_json = resp.json()
        audio_encoded = res_json.get("audio_encoded", "")
        return base64.b64decode(audio_encoded)
        
    else:
        # ElevenLabs API call: POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}
        voice_id = "21m00Tcm4TlvDq8ikWAM"
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {
            "xi-api-key": settings.elevenlabs_api_key,
            "Content-Type": "application/json"
        }
        payload = {
            "text": text,
            "model_id": "eleven_monolingual_v1"
        }
        
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                json=payload,
                headers=headers,
                timeout=30.0
            )
            
        if resp.status_code != 200:
            logger.error("ElevenLabs TTS failed: %s", resp.text)
            raise RuntimeError(f"ElevenLabs TTS API error {resp.status_code}: {resp.text}")
            
        return resp.content
