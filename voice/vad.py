"""
MAX OS — Voice Layer: Voice Activity Detection (VAD) Engine (Section 4 & Section 6).
Detects speech vs. silence/noise before audio reaches Whisper STT.
Tracks trailing silence hangover (500–800ms) to detect end-of-utterance cleanly.
"""

from __future__ import annotations

import logging
import math
import struct
import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

logger = logging.getLogger("max.voice.vad")


@dataclass
class VADConfig:
    sample_rate: int = 16000
    energy_threshold: float = 0.015     # RMS amplitude normalized [0.0, 1.0]
    silence_hangover_seconds: float = 0.6  # 600ms trailing silence to conclude utterance
    min_speech_duration_seconds: float = 0.25 # Minimum speech duration to consider valid utterance
    max_utterance_seconds: float = 15.0       # Max continuous recording duration safety limit


@dataclass
class VADFrameResult:
    is_speech: bool
    energy: float
    timestamp: float = field(default_factory=time.time)


class VADEngine:
    """
    Voice Activity Detection engine.
    Filters non-speech audio and tracks utterance boundary states.
    """

    def __init__(self, config: Optional[VADConfig] = None):
        self.config = config or VADConfig()
        self._speech_in_progress = False
        self._speech_start_time: Optional[float] = None
        self._last_speech_time: Optional[float] = None
        self._accumulated_speech_chunks: List[bytes] = []

    def compute_rms_energy(self, pcm_data: bytes) -> float:
        """
        Calculates normalized RMS energy for 16-bit mono PCM bytes.
        """
        if not pcm_data:
            return 0.0

        count = len(pcm_data) // 2
        if count == 0:
            return 0.0

        # Unpack signed 16-bit integers
        fmt = f"<{count}h"
        try:
            samples = struct.unpack(fmt, pcm_data[:count * 2])
        except struct.error:
            return 0.0

        sum_squares = sum(s * s for s in samples)
        mean_square = sum_squares / count
        rms = math.sqrt(mean_square)

        # Normalize against max 16-bit value (32768)
        return min(1.0, rms / 32768.0)

    def process_frame(self, pcm_chunk: bytes) -> VADFrameResult:
        """
        Evaluates a single audio frame for voice activity.
        """
        energy = self.compute_rms_energy(pcm_chunk)
        is_speech = energy >= self.config.energy_threshold
        now = time.time()

        if is_speech:
            if not self._speech_in_progress:
                self._speech_in_progress = True
                self._speech_start_time = now
            self._last_speech_time = now
            self._accumulated_speech_chunks.append(pcm_chunk)
        elif self._speech_in_progress:
            # Include trailing silence frames up to the hangover window
            self._accumulated_speech_chunks.append(pcm_chunk)

        return VADFrameResult(is_speech=is_speech, energy=energy, timestamp=now)

    def is_utterance_complete(self) -> bool:
        """
        Checks if an active speech utterance has ended (trailing silence reached)
        or exceeded max duration.
        """
        if not self._speech_in_progress or self._last_speech_time is None:
            return False

        now = time.time()
        silence_duration = now - self._last_speech_time
        speech_duration = (self._last_speech_time - (self._speech_start_time or now))

        # Check if max recording limit hit
        if self._speech_start_time and (now - self._speech_start_time >= self.config.max_utterance_seconds):
            logger.info("Utterance concluded: max recording duration reached.")
            return True

        # Check if silence hangover threshold reached
        if silence_duration >= self.config.silence_hangover_seconds:
            # Validate minimum speech length requirement
            if speech_duration >= self.config.min_speech_duration_seconds:
                return True
            else:
                # Discard noise spike that was too short
                self.reset()
                return False

        return False

    def get_and_reset_utterance(self) -> bytes:
        """
        Retrieves the complete accumulated utterance audio bytes and resets state.
        """
        audio = b"".join(self._accumulated_speech_chunks)
        self.reset()
        return audio

    def reset(self) -> None:
        """Resets the VAD tracking state."""
        self._speech_in_progress = False
        self._speech_start_time = None
        self._last_speech_time = None
        self._accumulated_speech_chunks.clear()

    @property
    def is_speaking(self) -> bool:
        return self._speech_in_progress
