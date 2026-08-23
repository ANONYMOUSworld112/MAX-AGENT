"""
MAX OS — Voice Layer: Speech-to-Text (STT) Engine (Section 2 & Section 4).
Runs faster-whisper on CPU with int8 quantization (tiny.en / base.en).
Configured with no_speech_threshold to eliminate silence hallucinations.
"""

from __future__ import annotations

import io
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

logger = logging.getLogger("max.voice.stt")


@dataclass
class STTConfig:
    model_size: str = "base.en"          # tiny.en, base.en, or small.en
    device: str = "cpu"                  # strictly CPU to preserve VRAM for Ollama LLM
    compute_type: str = "int8"           # int8 quantization
    beam_size: int = 5
    no_speech_threshold: float = 0.6     # Suppress Whisper silence hallucinations
    language: str = "en"
    condition_on_previous_text: bool = False
    min_confidence: float = 0.45


@dataclass
class STTResult:
    transcript: str
    confidence: float
    duration_seconds: float
    language: str = "en"
    is_empty: bool = False
    error: Optional[str] = None


class SpeechToTextEngine:
    """
    Local Speech-to-Text engine powered by faster-whisper.
    Enforces int8 CPU inference with no-speech gating.
    """

    def __init__(
        self,
        config: Optional[STTConfig] = None,
        mock_backend_fn: Optional[Callable[[bytes], str]] = None,
    ):
        self.config = config or STTConfig()
        self.mock_backend_fn = mock_backend_fn
        self._model = None
        self._init_model()

    def _init_model(self) -> None:
        if self.mock_backend_fn is not None:
            return

        try:
            from faster_whisper import WhisperModel
            logger.info(f"Loading faster-whisper model '{self.config.model_size}' ({self.config.compute_type} on {self.config.device})...")
            self._model = WhisperModel(
                self.config.model_size,
                device=self.config.device,
                compute_type=self.config.compute_type,
            )
            logger.info("faster-whisper STT model loaded successfully.")
        except Exception as e:
            logger.debug(f"faster-whisper not initialized ({e}); mock/fallback STT available.")
            self._model = None

    @property
    def is_model_loaded(self) -> bool:
        return self._model is not None or self.mock_backend_fn is not None

    def transcribe(self, audio_bytes: bytes) -> STTResult:
        """
        Transcribes 16-bit 16kHz mono PCM audio bytes to free text.
        """
        start_t = time.monotonic()

        if not audio_bytes or len(audio_bytes) < 1000:
            return STTResult(
                transcript="",
                confidence=0.0,
                duration_seconds=0.0,
                is_empty=True,
            )

        # 1. Custom mock / test hook
        if self.mock_backend_fn is not None:
            text = self.mock_backend_fn(audio_bytes).strip()
            duration = time.monotonic() - start_t
            return STTResult(
                transcript=text,
                confidence=0.95 if text else 0.0,
                duration_seconds=duration,
                is_empty=(not bool(text)),
            )

        # 2. faster-whisper inference
        if self._model is not None:
            try:
                import numpy as np
                # Convert 16-bit PCM bytes to normalized float32 array [-1.0, 1.0]
                audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0

                segments, info = self._model.transcribe(
                    audio_np,
                    beam_size=self.config.beam_size,
                    language=self.config.language,
                    no_speech_threshold=self.config.no_speech_threshold,
                    condition_on_previous_text=self.config.condition_on_previous_text,
                )

                collected_text = []
                avg_confidence = 1.0

                segment_list = list(segments)
                if not segment_list:
                    return STTResult(
                        transcript="",
                        confidence=0.0,
                        duration_seconds=time.monotonic() - start_t,
                        is_empty=True,
                    )

                for seg in segment_list:
                    # Filter out segments flagged as no_speech
                    if getattr(seg, "no_speech_prob", 0.0) < self.config.no_speech_threshold:
                        collected_text.append(seg.text.strip())

                raw_transcript = " ".join(collected_text).strip()
                duration = time.monotonic() - start_t

                # Guard against near-empty or garbage hallucinations
                if not raw_transcript or len(raw_transcript) < 2:
                    return STTResult(
                        transcript="",
                        confidence=0.0,
                        duration_seconds=duration,
                        is_empty=True,
                    )

                return STTResult(
                    transcript=raw_transcript,
                    confidence=info.language_probability if hasattr(info, "language_probability") else 0.9,
                    duration_seconds=duration,
                    language=info.language if hasattr(info, "language") else "en",
                    is_empty=False,
                )

            except Exception as e:
                logger.error(f"faster-whisper transcription error: {e}")
                return STTResult(
                    transcript="",
                    confidence=0.0,
                    duration_seconds=time.monotonic() - start_t,
                    is_empty=True,
                    error=str(e),
                )

        # 3. Fallback when model is not installed/loaded
        return STTResult(
            transcript="",
            confidence=0.0,
            duration_seconds=time.monotonic() - start_t,
            is_empty=True,
            error="No STT model loaded",
        )
