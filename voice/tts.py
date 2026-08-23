"""
MAX OS — Voice Layer: Text-to-Speech (TTS) Engine & Mic Gating (Section 4 & Section 6).
Wraps Piper TTS and SingleTTSQueue with automatic mic-gating hooks
to prevent acoustic feedback, echo, and self-triggering loops.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from core.single_tts_queue import SingleTTSQueue, speak, speak_sync
from voice.audio_capture import AudioCapture

logger = logging.getLogger("max.voice.tts")


class VoiceTTS:
    """
    Text-to-Speech engine with automatic mic-gating coordination.
    Mutes AudioCapture for the duration of spoken output to prevent feedback.
    """

    def __init__(
        self,
        audio_capture: Optional[AudioCapture] = None,
        tts_queue: Optional[SingleTTSQueue] = None,
    ):
        self.audio_capture = audio_capture
        self.tts_queue = tts_queue or SingleTTSQueue.get_instance()

    def speak(self, text: str) -> None:
        """
        Enqueues text for asynchronous speech with mic-gating.
        """
        clean_text = text.strip() if text else ""
        if not clean_text:
            return

        if self.audio_capture:
            self.audio_capture.mute()

        self.tts_queue.speak(clean_text)

        # Unmute asynchronously once speech queue becomes idle
        if self.audio_capture:
            import threading
            def _unmute_watcher():
                self.tts_queue.wait_until_idle(timeout=10.0)
                if self.audio_capture:
                    self.audio_capture.unmute()

            threading.Thread(target=_unmute_watcher, daemon=True).start()

    def speak_sync(self, text: str, timeout: float = 10.0) -> None:
        """
        Blocks until speech finishes playing, ensuring mic remains gated throughout.
        """
        clean_text = text.strip() if text else ""
        if not clean_text:
            return

        if self.audio_capture:
            self.audio_capture.mute()

        try:
            self.tts_queue.speak_sync(clean_text, timeout=timeout)
        finally:
            if self.audio_capture:
                self.audio_capture.unmute()

    def wait_until_idle(self, timeout: float = 10.0) -> None:
        """Blocks until any active speech has concluded."""
        self.tts_queue.wait_until_idle(timeout=timeout)
        if self.audio_capture:
            self.audio_capture.unmute()

    @property
    def is_speaking(self) -> bool:
        return self.tts_queue.is_busy
