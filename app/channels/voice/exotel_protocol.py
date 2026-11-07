"""Validation and audio framing for Exotel AgentStream Voicebot sessions."""

from __future__ import annotations

import base64
import binascii
from io import BytesIO
from typing import Any
from wave import open as wave_open

SUPPORTED_SAMPLE_RATES = {8000, 16000, 24000}


def validate_start(
    event: dict[str, Any],
    *,
    call_sid: str,
    account_sid: str,
    caller_phone: str,
    called_number: str,
) -> tuple[str, int]:
    if event.get("event") != "start" or not isinstance(event.get("start"), dict):
        raise ValueError("expected start event")
    start = event["start"]
    stream_sid = event.get("stream_sid")
    if not isinstance(stream_sid, str) or stream_sid != start.get("stream_sid"):
        raise ValueError("stream_sid mismatch")
    expected = {
        "call_sid": call_sid,
        "account_sid": account_sid,
        "from": caller_phone,
        "to": called_number,
    }
    if any(str(start.get(key)) != value for key, value in expected.items()):
        raise ValueError("verified call metadata mismatch")
    media_format = start.get("media_format")
    if not isinstance(media_format, dict):
        raise ValueError("missing media_format")
    if media_format.get("encoding") != "audio/x-raw" or str(media_format.get("bit_rate")) != "16":
        raise ValueError("unsupported audio encoding")
    sample_rate_raw = media_format.get("sample_rate")
    if isinstance(sample_rate_raw, bool) or not isinstance(sample_rate_raw, (int, str)):
        raise ValueError("invalid sample rate")
    try:
        sample_rate = int(sample_rate_raw)
    except ValueError:
        raise ValueError("invalid sample rate") from None
    if sample_rate not in SUPPORTED_SAMPLE_RATES:
        raise ValueError("unsupported sample rate")
    return stream_sid, sample_rate


def decode_media(event: dict[str, Any], stream_sid: str) -> bytes:
    if event.get("event") != "media" or event.get("stream_sid") != stream_sid:
        raise ValueError("invalid media event")
    media = event.get("media")
    if not isinstance(media, dict) or not isinstance(media.get("payload"), str):
        raise ValueError("missing media payload")
    try:
        audio = base64.b64decode(media["payload"], validate=True)
    except (ValueError, binascii.Error):
        raise ValueError("invalid media base64") from None
    if not audio or len(audio) % 2:
        raise ValueError("media must be nonempty 16-bit PCM")
    return audio


def pcm_to_wav(audio: bytes, sample_rate: int) -> bytes:
    output = BytesIO()
    with wave_open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(audio)
    return output.getvalue()


def wav_to_pcm(audio: bytes, expected_sample_rate: int) -> bytes:
    try:
        with wave_open(BytesIO(audio), "rb") as wav:
            if (
                wav.getnchannels() != 1
                or wav.getsampwidth() != 2
                or wav.getframerate() != expected_sample_rate
            ):
                raise ValueError("TTS WAV format does not match negotiated Exotel format")
            frames = wav.readframes(wav.getnframes())
    except EOFError:
        raise ValueError("invalid TTS WAV") from None
    if not frames:
        raise ValueError("empty TTS WAV")
    return frames


def media_messages(stream_sid: str, wav_audio: bytes, sample_rate: int) -> list[dict[str, Any]]:
    pcm = wav_to_pcm(wav_audio, sample_rate)
    if len(pcm) % 320:
        pcm += b"\x00" * (320 - (len(pcm) % 320))
    messages = []
    for offset in range(0, len(pcm), 3200):
        messages.append(
            {
                "event": "media",
                "stream_sid": stream_sid,
                "media": {"payload": base64.b64encode(pcm[offset : offset + 3200]).decode()},
            }
        )
    return messages
