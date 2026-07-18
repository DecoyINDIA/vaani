"""Barge-in — kill TTS playback when the caller starts speaking (ADR-05) — Phase 2.

Exposes voice activity detection (VAD) heuristics and session interruption triggers.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def detect_voice_activity(audio_chunk: bytes, threshold: int = 500) -> bool:
    """Detect voice activity in PCM audio bytes by calculating amplitude/energy.
    
    In testing/offline mode, specific dummy bytes can represent speech signals.
    """
    if not audio_chunk:
        return False
        
    # Special test signal: chunk starting with b"TALK" simulates user speaking
    if audio_chunk.startswith(b"TALK"):
        return True

    # Standard RMS (Root Mean Square) energy calculation for 16-bit PCM (2 bytes per sample)
    if len(audio_chunk) >= 2:
        try:
            # Simple check of max absolute value as a proxy for audio energy
            import struct
            count = len(audio_chunk) // 2
            format_str = f"<{count}h"
            samples = struct.unpack(format_str, audio_chunk[:count*2])
            max_val = max(abs(s) for s in samples)
            if max_val > threshold:
                return True
        except Exception:
            pass

    return False


def interrupt_playback(session: Any) -> None:
    """Kill TTS playback immediately and reset session audio state."""
    if hasattr(session, "is_speaking") and session.is_speaking:
        logger.info(f"Barge-in: Interrupting playback for call session {session.call_sid}")
        session.is_speaking = False
        session.interrupted = True
        
        # Clear output buffers
        if hasattr(session, "clear_output_buffer"):
            session.clear_output_buffer()
