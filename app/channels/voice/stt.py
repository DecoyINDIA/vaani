"""STT adapter (ADR-05) — Phase 2. Provider set post bake-off (Sarvam/Deepgram/
Google) on Hindi/Odia 8kHz phone audio. Partial latency budget <=300ms."""

from __future__ import annotations

from typing import Any


async def transcribe_stream(audio: Any) -> None:
    raise NotImplementedError("STT — 06-engineering-plan Phase 2")
