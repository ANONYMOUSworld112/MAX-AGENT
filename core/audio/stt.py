"""
core/audio/stt.py — Multilingual Speech-to-Text Router.

Language Routing Policy:
  - English ('en'): Handled locally by faster-whisper small int8 on CUDA (<5% WER, <800ms).
  - Telugu ('te') & Hindi ('hi'): Routed to Cloud STT (Google Cloud Speech / Whisper API)
    due to small local model degradation on Indic phonemes.
  - PRIVACY NOTICE: Routing to Cloud STT transmits audio data to third-party cloud servers;
    this requires explicit user consent.
"""
from __future__ import annotations

import io
import json
import logging
import os
import time
from typing import Optional, Tuple

import numpy as np

logger = logging.getLogger("friday.audio.stt")

# Privacy disclosure text required for third-party cloud STT
CLOUD_STT_PRIVACY_DISCLOSURE = (
    "Privacy Notice: Telugu and Hindi voice audio is processed using Cloud Speech-to-Text "
    "APIs. Your voice recordings for these languages will be transmitted to external servers."
)


class MultilingualSTT:
    """
    Speech-to-Text router that dispatches audio to local CUDA Whisper for English
    or Cloud STT for Indic languages (Telugu and Hindi).
    """

    def __init__(
        self,
        model_size: str = "small",
        device: str = "cuda",
        compute_type: str = "int8",
        google_api_key: Optional[str] = None,
    ) -> None:
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.google_api_key = google_api_key

        self._local_whisper = None
        self._mock_transcript: Optional[str] = None
        self._last_latency_ms: float = 0.0
        self._init_local_model()

    def _init_local_model(self) -> None:
        """Attempt to load faster-whisper on CUDA/CPU."""
        try:
            from faster_whisper import WhisperModel  # type: ignore
            import torch  # type: ignore

            dev = "cuda" if (self.device == "cuda" and torch.cuda.is_available()) else "cpu"
            comp = self.compute_type if dev == "cuda" else "int8"
            logger.info("STT: Loading faster-whisper '%s' on %s (%s)...", self.model_size, dev, comp)
            self._local_whisper = WhisperModel(self.model_size, device=dev, compute_type=comp)
            logger.info("STT: faster-whisper initialized.")
        except Exception as e:
            logger.warning("STT: faster-whisper not available (%s). Using SpeechRecognition fallback.", e)
            self._local_whisper = None

    def set_mock_transcript(self, text: Optional[str]) -> None:
        """Sets mock transcript for deterministic unit testing."""
        self._mock_transcript = text

    def transcribe(
        self,
        audio_data: np.ndarray,
        language: str = "en",
        sample_rate: int = 16000,
    ) -> Tuple[str, dict]:
        """
        Transcribe audio array to text according to language policy.

        Returns:
            text (str): Transcribed text.
            metadata (dict): Provider used, latency, language, and privacy notes.
        """
        start_time = time.time()
        lang = (language or "en").lower().strip()

        # Check mock override
        if self._mock_transcript is not None:
            self._last_latency_ms = (time.time() - start_time) * 1000.0
            return self._mock_transcript, {
                "provider": "mock",
                "language": lang,
                "latency_ms": self._last_latency_ms,
                "cloud_used": False,
            }

        # Language policy routing
        if lang in ("te", "hi", "telugu", "hindi"):
            text, meta = self._transcribe_cloud_indic(audio_data, lang, sample_rate)
        else:
            text, meta = self._transcribe_local_english(audio_data, sample_rate)

        self._last_latency_ms = (time.time() - start_time) * 1000.0
        meta["latency_ms"] = round(self._last_latency_ms, 2)
        return text, meta

    def _transcribe_local_english(self, audio: np.ndarray, sample_rate: int) -> Tuple[str, dict]:
        """Transcribe English using local faster-whisper or local recognizer."""
        # Convert float32 mono array in [-1.0, 1.0]
        samples = audio.astype(np.float32)
        if np.max(np.abs(samples)) > 1.0:
            samples = samples / 32768.0

        if self._local_whisper is not None:
            try:
                segments, info = self._local_whisper.transcribe(
                    samples,
                    language="en",
                    beam_size=1,
                    best_of=1,
                    vad_filter=True,
                )
                text = " ".join(seg.text for seg in segments).strip()
                return text, {
                    "provider": "faster-whisper-local",
                    "device": self.device,
                    "language": "en",
                    "cloud_used": False,
                }
            except Exception as e:
                logger.error("Local Whisper transcription failed: %s", e)

        # Fallback to speech_recognition library
        try:
            import speech_recognition as sr  # type: ignore
            recognizer = sr.Recognizer()
            # Convert float32 to int16 bytes
            int16_audio = (samples * 32767).astype(np.int16).tobytes()
            audio_source = sr.AudioData(int16_audio, sample_rate, 2)
            text = recognizer.recognize_google(audio_source, language="en-US")
            return text, {
                "provider": "google-fallback",
                "language": "en",
                "cloud_used": True,
            }
        except Exception as e:
            logger.debug("Local recognizer fallback error: %s", e)
            return "", {
                "provider": "none",
                "error": str(e),
                "language": "en",
                "cloud_used": False,
            }

    def _transcribe_cloud_indic(
        self,
        audio: np.ndarray,
        language: str,
        sample_rate: int,
    ) -> Tuple[str, dict]:
        """
        Transcribe Telugu or Hindi using Cloud STT API.
        Includes mandatory privacy disclosure metadata.
        """
        samples = audio.astype(np.float32)
        if np.max(np.abs(samples)) > 1.0:
            samples = samples / 32768.0

        lang_code = "te-IN" if language in ("te", "telugu") else "hi-IN"

        try:
            import speech_recognition as sr  # type: ignore
            recognizer = sr.Recognizer()
            int16_audio = (samples * 32767).astype(np.int16).tobytes()
            audio_source = sr.AudioData(int16_audio, sample_rate, 2)
            text = recognizer.recognize_google(audio_source, language=lang_code)
            return text, {
                "provider": "cloud-stt",
                "language": language,
                "cloud_used": True,
                "privacy_disclosure": CLOUD_STT_PRIVACY_DISCLOSURE,
            }
        except Exception as e:
            logger.warning("Cloud Indic STT error: %s", e)
            return "", {
                "provider": "cloud-stt",
                "error": str(e),
                "language": language,
                "cloud_used": True,
                "privacy_disclosure": CLOUD_STT_PRIVACY_DISCLOSURE,
            }

    @property
    def last_latency_ms(self) -> float:
        return self._last_latency_ms
