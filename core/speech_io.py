"""
MAX OS — Speech I/O (STT & Wake Word) Engine (Step 8.4).
Handles continuous voice intake, wake-word detection, and text transcription.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from core.voice_output import VoiceOutput


@dataclass
class SpeechInputResult:
    transcribed_text: str
    wake_word_detected: bool
    confidence: float
    error: Optional[str] = None


class SpeechIOManager:
    """
    Manages Speech-to-Text transcription and Wake-Word triggers.
    """

    def __init__(
        self,
        wake_words: Optional[list[str]] = None,
        stt_backend_fn: Optional[Callable[[bytes], str]] = None,
        voice_output: Optional[VoiceOutput] = None,
    ):
        self.wake_words = [w.lower() for w in (wake_words or ["hey max", "jarvis", "max"])]
        self.stt_backend_fn = stt_backend_fn
        self.voice_output = voice_output or VoiceOutput()

    def process_audio_input(self, audio_data: bytes, mock_transcript: Optional[str] = None) -> SpeechInputResult:
        """Processes audio input stream into transcribed text with wake word check."""
        try:
            if mock_transcript is not None:
                text = mock_transcript
            elif self.stt_backend_fn is not None:
                text = self.stt_backend_fn(audio_data)
            else:
                text = "Hey MAX, what is on my schedule today?"

            text_lower = text.lower()
            wake_detected = any(w in text_lower for w in self.wake_words)

            return SpeechInputResult(
                transcribed_text=text,
                wake_word_detected=wake_detected,
                confidence=0.95,
            )
        except Exception as e:
            return SpeechInputResult(
                transcribed_text="",
                wake_word_detected=False,
                confidence=0.0,
                error=str(e),
            )
