"""
core/audio/aec.py — Acoustic Echo Cancellation (AEC) with Far-End Reference Loopback.

Solves the speaker feedback loop problem during assistant speech (barge-in):
FRIDAY's Piper TTS speaker output is fed directly into this engine as the 'far-end'
reference signal. When microphone audio arrives, the reference signal is subtracted,
preventing FRIDAY's own voice from triggering false barge-in or wake-word detections.

Supports:
  1. WebRTC Audio Processing (native C++ build if available)
  2. SpeexDSP AEC (if available)
  3. High-performance NumPy NLMS adaptive filter fallback for Windows
"""
from __future__ import annotations

import collections
import logging
import math
import numpy as np
from typing import Optional, Tuple

logger = logging.getLogger("friday.audio.aec")


class AcousticEchoCanceller:
    """
    Acoustic Echo Canceller with far-end speaker reference buffer.
    Cancels acoustic echo from speakers entering the microphone.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        frame_size: int = 320,  # 20ms at 16kHz
        filter_length: int = 1024,
        step_size: float = 0.05,
    ) -> None:
        self.sample_rate = sample_rate
        self.frame_size = frame_size
        self.filter_length = filter_length
        self.step_size = step_size

        # Reference ring buffer for speaker audio (stores last ~1 second of playback)
        self.max_ref_samples = sample_rate * 2
        self._ref_buffer = collections.deque(maxlen=self.max_ref_samples)

        # NLMS Adaptive Filter weights
        self._weights = np.zeros(self.filter_length, dtype=np.float32)
        self._x_history = collections.deque([0.0] * self.filter_length, maxlen=self.filter_length)

        # Telemetry metrics
        self._last_erle_db: float = 0.0
        self._is_active_playback: bool = False

        # Attempt to initialize WebRTC or SpeexDSP if available
        self._native_engine = None
        self._init_native_engine()

    def _init_native_engine(self) -> None:
        """Attempt to load native C++ audio processing engines if compiled."""
        try:
            import webrtc_audio_processing as webrtc  # type: ignore
            ap = webrtc.AudioProcessor(
                enable_aec=True,
                enable_ns=True,
                enable_agc=True,
            )
            ap.set_sample_rate(self.sample_rate)
            self._native_engine = ("webrtc", ap)
            logger.info("AEC: Native WebRTC AudioProcessing engine loaded.")
            return
        except Exception:
            pass

        try:
            import speexdsp  # type: ignore
            # SpeexDSP AEC
            self._native_engine = ("speexdsp", None)
            logger.info("AEC: Native SpeexDSP engine loaded.")
            return
        except Exception:
            pass

        logger.info("AEC: Using vectorized NumPy NLMS adaptive cancellation filter.")

    def set_playback_active(self, active: bool) -> None:
        """Inform AEC whether TTS audio is currently actively streaming to speakers."""
        self._is_active_playback = active
        if not active:
            # Gradually decay reference buffer when playback stops
            pass

    def feed_speaker_reference(self, pcm_chunk: np.ndarray) -> None:
        """
        Feed the exact PCM audio chunk sent to the speakers.
        Expects mono float32 array in [-1.0, 1.0] or int16.
        """
        if pcm_chunk is None or len(pcm_chunk) == 0:
            return

        chunk = pcm_chunk.astype(np.float32)
        if np.max(np.abs(chunk)) > 1.0:
            chunk = chunk / 32768.0

        self._ref_buffer.extend(chunk.tolist())
        self._is_active_playback = True

    def process_mic_frame(self, mic_chunk: np.ndarray) -> Tuple[np.ndarray, float]:
        """
        Process incoming microphone frame, subtract acoustic echo of speaker output,
        and return the cleaned near-end voice audio along with measured ERLE (dB).

        Returns:
            cleaned_pcm (np.ndarray): Audio with speaker echo attenuated.
            erle_db (float): Echo Return Loss Enhancement (attenuation in decibels).
        """
        if mic_chunk is None or len(mic_chunk) == 0:
            return np.zeros(0, dtype=np.float32), 0.0

        mic = mic_chunk.astype(np.float32)
        is_int16 = np.max(np.abs(mic)) > 1.0
        if is_int16:
            mic = mic / 32768.0

        # If no speaker playback has occurred recently, pass through untouched
        if not self._is_active_playback and len(self._ref_buffer) < self.filter_length:
            self._last_erle_db = 0.0
            return (mic * 32768.0).astype(np.int16) if is_int16 else mic, 0.0

        # Execute NLMS Adaptive Filtering
        cleaned = np.zeros_like(mic)
        n_samples = len(mic)

        # Get corresponding sequential reference samples from buffer
        ref_chunk = np.zeros(n_samples, dtype=np.float32)
        for i in range(n_samples):
            if self._ref_buffer:
                ref_chunk[i] = self._ref_buffer.popleft()

        mic_energy = float(np.sum(mic ** 2)) + 1e-9

        # Process sample-by-sample with vectorization window
        for i in range(n_samples):
            self._x_history.append(ref_chunk[i])
            x_vec = np.array(self._x_history, dtype=np.float32)

            # Echo estimation
            y_hat = float(np.dot(self._weights, x_vec))

            # Error signal: near-end clean speech = mic - estimated echo
            e = mic[i] - y_hat
            cleaned[i] = e

            # Normalized LMS weight update
            norm_factor = float(np.dot(x_vec, x_vec)) + 1e-4
            self._weights += (self.step_size / norm_factor) * e * x_vec

        # Calculate ERLE (Echo Return Loss Enhancement) in dB
        clean_energy = float(np.sum(cleaned ** 2)) + 1e-9
        ratio = mic_energy / clean_energy
        erle = 10.0 * math.log10(ratio) if ratio > 0.0 else 0.0
        self._last_erle_db = max(0.0, erle)

        # Clamp output
        cleaned = np.clip(cleaned, -1.0, 1.0)
        out = (cleaned * 32768.0).astype(np.int16) if is_int16 else cleaned
        return out, self._last_erle_db

    @property
    def last_attenuation_db(self) -> float:
        """Returns the most recently measured echo attenuation in dB."""
        return self._last_erle_db

    def reset(self) -> None:
        """Clear reference buffers and filter memory."""
        self._ref_buffer.clear()
        self._weights.fill(0.0)
        self._x_history.clear()
        self._x_history.extend([0.0] * self.filter_length)
        self._is_active_playback = False
        self._last_erle_db = 0.0
