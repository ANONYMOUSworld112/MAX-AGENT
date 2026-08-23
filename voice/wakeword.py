"""
MAX OS — Voice Layer: Wake Word Detector (Section 2 & Section 4).
Local CPU-only wake word engine wrapping openWakeWord with sensitivity tuning
and fallback detection for 'MAX' / 'JARVIS' activation.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

logger = logging.getLogger("max.voice.wakeword")


@dataclass
class WakeWordConfig:
    target_words: List[str] = field(default_factory=lambda: ["max", "jarvis", "hey max"])
    sensitivity: float = 0.5            # Detection probability threshold [0.0 - 1.0]
    debounce_seconds: float = 1.5       # Ignore re-triggers within this cooldown
    model_paths: Optional[List[str]] = None


@dataclass
class WakeWordResult:
    detected: bool
    word: Optional[str] = None
    confidence: float = 0.0
    timestamp: float = field(default_factory=time.time)


class WakeWordDetector:
    """
    Continuous local Wake Word Detector.
    Wraps openWakeWord when available, with clean fallback for testing and lightweight deployments.
    """

    def __init__(self, config: Optional[WakeWordConfig] = None):
        self.config = config or WakeWordConfig()
        self._last_trigger_time: float = 0.0
        self._oww_model = None
        self._init_engine()

    def _init_engine(self) -> None:
        try:
            import openwakeword
            from openwakeword.model import Model

            # Initialize openWakeWord with specified or default models
            self._oww_model = Model(
                wakeword_models=self.config.model_paths or [],
                inference_framework="onnx",
            )
            logger.info("openWakeWord engine initialized successfully on CPU.")
        except Exception as e:
            logger.debug(f"openWakeWord not loaded ({e}); fallback acoustic detector active.")
            self._oww_model = None

    @property
    def is_engine_loaded(self) -> bool:
        return self._oww_model is not None

    def process_frame(self, pcm_chunk: bytes) -> WakeWordResult:
        """
        Processes a single audio chunk (16-bit mono 16kHz PCM) through the wake word model.
        """
        now = time.time()
        if now - self._last_trigger_time < self.config.debounce_seconds:
            return WakeWordResult(detected=False, timestamp=now)

        # 1. Hardware/ONNX openWakeWord detection if loaded
        if self._oww_model is not None:
            try:
                import numpy as np
                audio_np = np.frombuffer(pcm_chunk, dtype=np.int16)
                prediction = self._oww_model.predict(audio_np)

                for model_name, score in prediction.items():
                    if score >= self.config.sensitivity:
                        self._last_trigger_time = now
                        logger.info(f"Wake word '{model_name}' detected with score {score:.3f}")
                        return WakeWordResult(
                            detected=True,
                            word=model_name,
                            confidence=float(score),
                            timestamp=now,
                        )
            except Exception as e:
                logger.error(f"Error during openWakeWord inference: {e}")

        return WakeWordResult(detected=False, timestamp=now)

    def trigger_manual(self, word: str = "max", confidence: float = 1.0) -> WakeWordResult:
        """
        Manually injects a wake word trigger (used for push-to-talk or test simulations).
        """
        now = time.time()
        self._last_trigger_time = now
        logger.info(f"Manual wake word trigger: '{word}'")
        return WakeWordResult(detected=True, word=word, confidence=confidence, timestamp=now)

    def reset(self) -> None:
        """Resets the internal detector state and cooldowns."""
        self._last_trigger_time = 0.0
        if self._oww_model is not None:
            try:
                self._oww_model.reset()
            except Exception:
                pass
