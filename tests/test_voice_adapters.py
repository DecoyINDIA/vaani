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


@pytest.mark.parametrize(
    ("lang", "expected_code"),
    [
        ("hi", "hi-IN"),
        ("hi-Latn", "hi-IN"),
        ("or", "od-IN"),
        ("en", "en-IN"),
    ],
)
async def test_sarvam_tts_language_codes(
    monkeypatch: pytest.MonkeyPatch, lang: str, expected_code: str
) -> None:
    captured: dict[str, Any] = {}

    class Response:
        status_code = 200
        text = ""

        def json(self) -> dict[str, object]:
            return {"request_id": "req-lang", "audios": [base64.b64encode(_wav()).decode()]}

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

    audio = await synthesize("Test speech", lang, provider="sarvam", sample_rate=16000)
    assert audio.startswith(b"RIFF")
    payload = captured["json"]
    assert payload["language_code"] == expected_code
    assert payload["speech_sample_rate"] == 16000
    assert payload["model"] == "bulbul:v3"


@pytest.mark.parametrize(
    ("lang", "expected_code"),
    [
        ("hi", "hi-IN"),
        ("hi-Latn", "hi-IN"),
        ("or", "od-IN"),
        ("en", "en-IN"),
    ],
)
async def test_sarvam_stt_language_codes(
    monkeypatch: pytest.MonkeyPatch, lang: str, expected_code: str
) -> None:
    captured: dict[str, Any] = {}

    class Response:
        status_code = 200
        text = ""

        def json(self) -> dict[str, object]:
            return {
                "request_id": "req-lang-stt",
                "transcript": "Test transcript",
                "language_code": expected_code,
                "language_probability": 0.95,
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

    result = await transcribe_audio(_wav(), lang, provider="sarvam")
    assert result["text"] == "Test transcript"
    assert captured["data"]["language_code"] == expected_code
    assert captured["data"]["model"] == "saaras:v4"


async def test_sarvam_bad_provider_responses_fail_visibly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "use_mock_adapters", False)
    monkeypatch.setattr(settings, "sarvam_api_key", "sarvam-key")

    # 1. STT HTTP 500 error
    class Error500Response:
        status_code = 500
        text = "Internal Server Error"

    class Client500:
        async def __aenter__(self) -> Client500:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(self, url: str, **kwargs: Any) -> Error500Response:
            return Error500Response()

    monkeypatch.setattr("httpx.AsyncClient", Client500)
    with pytest.raises(RuntimeError, match="Sarvam STT API error 500"):
        await transcribe_audio(_wav(), "hi", provider="sarvam")

    with pytest.raises(RuntimeError, match="Sarvam TTS API error 500"):
        await synthesize("Hello", "hi", provider="sarvam")

    # 2. STT empty transcript
    class EmptySTTResponse:
        status_code = 200
        text = ""

        def json(self) -> dict[str, object]:
            return {"transcript": "   "}

    class ClientEmptySTT:
        async def __aenter__(self) -> ClientEmptySTT:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(self, url: str, **kwargs: Any) -> EmptySTTResponse:
            return EmptySTTResponse()

    monkeypatch.setattr("httpx.AsyncClient", ClientEmptySTT)
    with pytest.raises(RuntimeError, match="empty transcript"):
        await transcribe_audio(_wav(), "hi", provider="sarvam")

    # 3. TTS empty audios list
    class EmptyTTSResponse:
        status_code = 200
        text = ""

        def json(self) -> dict[str, object]:
            return {"audios": []}

    class ClientEmptyTTS:
        async def __aenter__(self) -> ClientEmptyTTS:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(self, url: str, **kwargs: Any) -> EmptyTTSResponse:
            return EmptyTTSResponse()

    monkeypatch.setattr("httpx.AsyncClient", ClientEmptyTTS)
    with pytest.raises(RuntimeError, match="Sarvam TTS returned no audio"):
        await synthesize("Hello", "hi", provider="sarvam")

    # 4. TTS invalid base64
    class BadBase64TTSResponse:
        status_code = 200
        text = ""

        def json(self) -> dict[str, object]:
            return {"audios": ["!!!not-base64!!!"]}

    class ClientBadBase64TTS:
        async def __aenter__(self) -> ClientBadBase64TTS:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(self, url: str, **kwargs: Any) -> BadBase64TTSResponse:
            return BadBase64TTSResponse()

    monkeypatch.setattr("httpx.AsyncClient", ClientBadBase64TTS)
    with pytest.raises(RuntimeError, match="invalid base64"):
        await synthesize("Hello", "hi", provider="sarvam")

    # 5. TTS invalid WAV (not RIFF or truncated)
    class BadWavTTSResponse:
        status_code = 200
        text = ""

        def json(self) -> dict[str, object]:
            return {"audios": [base64.b64encode(b"NOT_A_WAV_FILE_HEADER").decode()]}

    class ClientBadWavTTS:
        async def __aenter__(self) -> ClientBadWavTTS:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(self, url: str, **kwargs: Any) -> BadWavTTSResponse:
            return BadWavTTSResponse()

    monkeypatch.setattr("httpx.AsyncClient", ClientBadWavTTS)
    with pytest.raises(RuntimeError, match="invalid or empty WAV"):
        await synthesize("Hello", "hi", provider="sarvam")
