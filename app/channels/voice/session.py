"""Exotel call session <-> conversation mapping (TRD §1) — Phase 2.

Streams STT partials into the graph, sentence-chunked TTS out, barge-in on caller
speech. Latency budget instrumented per hop (ADR-05). Voice is a channel adapter,
not a new agent (06-engineering-plan §2).
"""

from __future__ import annotations


class VoiceSession:
    def __init__(self, tenant_id: str, call_sid: str) -> None:
        self.tenant_id = tenant_id
        self.call_sid = call_sid
        raise NotImplementedError("voice session — 06-engineering-plan Phase 2")
