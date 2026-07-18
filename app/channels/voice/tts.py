"""TTS adapter (ADR-05) — Phase 2. Sarvam (Indic) primary, ElevenLabs (English)
fallback. First-audio budget <=400ms; filler ack injected when budget slips."""

from __future__ import annotations


async def synthesize(text: str, lang: str) -> bytes:
    raise NotImplementedError("TTS — 06-engineering-plan Phase 2")
