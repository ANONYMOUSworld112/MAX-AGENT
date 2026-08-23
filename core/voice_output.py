"""
MAX OS — Voice Output Engine (Step 5.2).
Infra-tier component for Text-to-Speech (TTS).
Architectural rule: Infra-tier, not a task — NEVER enters task_trace.
Gracefully degrades to text-only if audio device or TTS engine fails.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Optional

logger = logging.getLogger("max.voice_output")


@dataclass
class VoiceResult:
    text: str
    spoken: bool
    fallback_to_text: bool
    error: Optional[str] = None


class VoiceOutput:
    """
    Infra-tier TTS output engine.
    Never creates rows in task_trace.
    """

    def __init__(self, tts_engine_fn: Optional[Callable[[str], None]] = None, enabled: bool = True):
        self.tts_engine_fn = tts_engine_fn
        self.enabled = enabled

    def speak(self, text: str) -> VoiceResult:
        """
        Attempts to speak text. If TTS is disabled or fails, falls back gracefully to text.
        """
        if not self.enabled or not text.strip():
            return VoiceResult(text=text, spoken=False, fallback_to_text=True)

        try:
            if self.tts_engine_fn is not None:
                self.tts_engine_fn(text)
            return VoiceResult(text=text, spoken=True, fallback_to_text=False)
        except Exception as e:
            logger.warning(f"TTS audio playback failed ({e}), falling back to text-only.")
            return VoiceResult(text=text, spoken=False, fallback_to_text=True, error=str(e))
