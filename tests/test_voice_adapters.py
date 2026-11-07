from __future__ import annotations

import base64
from io import BytesIO
from typing import Any
from wave import open as wave_open

import pytest
from app.channels.voice.stt import transcribe_audio
from app.channels.voice.tts import synthesize
from app.config import settings


def _wav() -> bytes:
    output = BytesIO()
    with wave_open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes(b"\x00\x00" * 800)
    return output.getvalue()


async def test_sarvam_tts_current_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class Response:
        status_code = 200
        text = ""

        def json(self) -> dict[str, object]:
            return {"request_id": "req-1", "audios": [base64.b64encode(_wav()).decode()]}

    class Client:
        async def __aenter__(self) -> Client:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(self, url: str, **kwargs: Any) -> Response:
            captured.update({"url": url, **kwargs})
            return Response()

    monkeypatch.setattr(settings, "use_mock_adapters", False)
    monkeypatch.setattr(settings, "sarvam_api_key", "sarvam-key")
    monkeypatch.setattr("httpx.AsyncClient", Client)
    audio = await synthesize("Namaste", "hi", provider="sarvam")
    assert audio.startswith(b"RIFF")
    assert captured["json"] == {
        "text": "Namaste",
        "language_code": "hi-IN",
        "speaker": "priya",
        "model": "bulbul:v3",
        "output_audio_codec": "wav",
        "speech_sample_rate": 8000,
    }


async def test_sarvam_stt_current_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class Response:
        status_code = 200
        text = ""

        def json(self) -> dict[str, object]:
            return {
                "request_id": "req-2",
                "transcript": "ନମସ୍କାର",
                "language_code": "od-IN",
                "language_probability": 0.98,
            }

    class Client:
        async def __aenter__(self) -> Client:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(self, url: str, **kwargs: Any) -> Response:
            captured.update({"url": url, **kwargs})
            return Response()

    monkeypatch.setattr(settings, "use_mock_adapters", False)
    monkeypatch.setattr(settings, "sarvam_api_key", "sarvam-key")
    monkeypatch.setattr("httpx.AsyncClient", Client)
    result = await transcribe_audio(_wav(), "or", provider="sarvam")
    assert result["text"] == "ନମସ୍କାର"
    assert result["confidence"] == 0.98
    assert captured["data"] == {
        "model": "saaras:v4",
        "mode": "transcribe",
        "language_code": "od-IN",
    }


async def test_voice_adapters_do_not_mock_missing_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "use_mock_adapters", False)
    monkeypatch.setattr(settings, "sarvam_api_key", "")
    with pytest.raises(RuntimeError, match="SARVAM_API_KEY"):
        await synthesize("hello", "en", provider="sarvam")
    with pytest.raises(RuntimeError, match="SARVAM_API_KEY"):
        await transcribe_audio(_wav(), "en", provider="sarvam")
