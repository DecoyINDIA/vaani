"""Node 1 — language detection (TRD §4.3).

lingua + script heuristics. Hinglish (Latin-script Hindi) is its own register:
hi-Latn. Voice notes transcribed by the same STT (Phase 2); STT confidence <0.75
-> ask to type or escalate.
"""

from __future__ import annotations

from typing import Any


async def lang_detect(state: dict[str, Any]) -> dict[str, Any]:
    raise NotImplementedError("lang detect — 06-engineering-plan task 3.5")
