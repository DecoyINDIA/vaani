"""TTS adapter (ADR-05) — Phase 2.

Sarvam (Indic) primary, ElevenLabs (English) fallback.
Provides text-to-speech synthesis with mock fallbacks for offline testing.
"""

from __future__ import annotations

import logging
import time
from io import BytesIO
from wave import open as wave_open

from app.config import settings

logger = logging.getLogger(__name__)


async def synthesize(text: str, lang: str, provider: str | None = None) -> bytes:
    """Synthesize text into WAV/MP3 audio bytes using the configured TTS provider.
    
    If the API keys are not present, it generates simulated audio bytes
    proportionate to the text length to allow offline test assertions to pass.
    """
    prov = provider or settings.tts_provider
    
    if settings.use_mock_adapters:
        # Offline simulation
        # Simulate processing latency: ~150ms + 2ms per character
        latency_sec = 0.15 + (len(text) * 0.002)
        sleep_duration = min(latency_sec, 0.05)  # Keep tests fast
        time.sleep(sleep_duration)

        audio_len = max(800, len(text) * 160)
        output = BytesIO()
        with wave_open(output, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(8000)
            wav.writeframes(b"\x00\x00" * audio_len)
        return output.getvalue()

    if prov == "sarvam" and not settings.sarvam_api_key:
        raise RuntimeError("SARVAM_API_KEY is required for Sarvam TTS")
    if prov == "elevenlabs" and not settings.elevenlabs_api_key:
        raise RuntimeError("ELEVENLABS_API_KEY is required for ElevenLabs TTS")

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
        
        payload: dict[str, object] = {
            "text": text,
            "language_code": target_lang,
            "speaker": "priya",
            "model": "bulbul:v3",
            "output_audio_codec": "wav",
            "speech_sample_rate": 8000,
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
        audios = res_json.get("audios")
        if not isinstance(audios, list) or not audios or not isinstance(audios[0], str):
            raise RuntimeError("Sarvam TTS returned no audio")
        try:
            audio = base64.b64decode(audios[0], validate=True)
        except ValueError as e:
            raise RuntimeError("Sarvam TTS returned invalid base64 audio") from e
        if not audio.startswith(b"RIFF") or len(audio) <= 44:
            raise RuntimeError("Sarvam TTS returned invalid or empty WAV audio")
        return audio
        
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
