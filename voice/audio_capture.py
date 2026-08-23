"""
MAX OS — Voice Layer: Audio Capture Engine (Section 4).
Continuous microphone stream capture, circular ring buffer, and mic-gating/muting
for echo and self-triggering prevention.
"""

from __future__ import annotations

import collections
import logging
import threading
import time
from dataclasses import dataclass
from typing import Callable, Deque, List, Optional, Tuple

logger = logging.getLogger("max.voice.audio_capture")


@dataclass
class AudioConfig:
    sample_rate: int = 16000  # 16kHz standard for Whisper and openWakeWord
    channels: int = 1         # Mono
    sample_width: int = 2     # 16-bit PCM (2 bytes per sample)
    chunk_size: int = 512     # Frame size in samples (32ms at 16kHz)
    buffer_seconds: float = 10.0  # Ring buffer duration

    @property
    def bytes_per_sample(self) -> int:
        return self.channels * self.sample_width

    @property
    def chunk_bytes(self) -> int:
        return self.chunk_size * self.bytes_per_sample


class AudioCapture:
    """
    Continuous audio capture stream with circular ring buffer.
    Supports mic-gating (muting capture during TTS playback to prevent echo loops).
    """

    def __init__(self, config: Optional[AudioConfig] = None):
        self.config = config or AudioConfig()
        max_chunks = int((self.config.sample_rate * self.config.buffer_seconds) / self.config.chunk_size)
        self._ring_buffer: Deque[bytes] = collections.deque(maxlen=max_chunks)
        self._buffer_lock = threading.Lock()
        self._chunk_available = threading.Condition(self._buffer_lock)

        self._is_muted = False
        self._is_running = False
        self._capture_thread: Optional[threading.Thread] = None
        self._stream = None
        self._pyAudio = None
        self._subscribers: List[Callable[[bytes], None]] = []

    @property
    def is_muted(self) -> bool:
        with self._buffer_lock:
            return self._is_muted

    def mute(self) -> None:
        """
        Hard-mute audio capture. Audio received while muted is dropped
        or converted to silence, preventing TTS feedback and self-triggering.
        """
        with self._buffer_lock:
            self._is_muted = True
        logger.debug("AudioCapture mic-gated (MUTED)")

    def unmute(self) -> None:
        """Un-mutes audio capture after TTS playback completes."""
        with self._buffer_lock:
            self._is_muted = False
        logger.debug("AudioCapture mic-gated (UNMUTED)")

    def feed_chunk(self, pcm_data: bytes) -> None:
        """
        Feeds a chunk of PCM bytes into the ring buffer (used by live mic or test simulator).
        """
        with self._chunk_available:
            if self._is_muted:
                # Replace with silence chunk of identical byte length
                silent_chunk = b"\x00" * len(pcm_data)
                self._ring_buffer.append(silent_chunk)
                processed = silent_chunk
            else:
                self._ring_buffer.append(pcm_data)
                processed = pcm_data

            self._chunk_available.notify_all()

        # Notify subscribers
        for sub in list(self._subscribers):
            try:
                sub(processed)
            except Exception as e:
                logger.error(f"Error in audio subscriber: {e}")

    def read_chunk(self, timeout: Optional[float] = None) -> Optional[bytes]:
        """Reads the next available chunk from the ring buffer."""
        with self._chunk_available:
            if not self._ring_buffer:
                self._chunk_available.wait(timeout=timeout)
            if self._ring_buffer:
                return self._ring_buffer.popleft()
            return None

    def get_buffered_audio(self, duration_seconds: Optional[float] = None) -> bytes:
        """
        Retrieves recent audio from the ring buffer up to the requested duration.
        """
        with self._buffer_lock:
            if duration_seconds is None:
                return b"".join(self._ring_buffer)

            bytes_needed = int(duration_seconds * self.config.sample_rate * self.config.bytes_per_sample)
            chunks: List[bytes] = []
            accumulated = 0

            for chunk in reversed(self._ring_buffer):
                chunks.append(chunk)
                accumulated += len(chunk)
                if accumulated >= bytes_needed:
                    break

            chunks.reverse()
            return b"".join(chunks)

    def clear_buffer(self) -> None:
        """Clears all accumulated frames in the ring buffer."""
        with self._buffer_lock:
            self._ring_buffer.clear()

    def subscribe(self, callback: Callable[[bytes], None]) -> None:
        """Subscribes a listener to receive new audio chunks in real-time."""
        self._subscribers.append(callback)

    def start(self) -> bool:
        """
        Starts the background hardware capture thread if audio hardware is available.
        Returns True if hardware stream initialized, or False if in software/simulated mode.
        """
        if self._is_running:
            return True

        self._is_running = True

        try:
            import pyaudio
            self._pyAudio = pyaudio.PyAudio()
            self._stream = self._pyAudio.open(
                format=pyaudio.paInt16,
                channels=self.config.channels,
                rate=self.config.sample_rate,
                input=True,
                frames_per_buffer=self.config.chunk_size,
            )
            self._capture_thread = threading.Thread(target=self._hardware_read_loop, daemon=True)
            self._capture_thread.start()
            logger.info("Hardware audio stream started.")
            return True
        except Exception as e:
            logger.warning(f"Hardware audio device unavailable ({e}); running in software buffer mode.")
            return False

    def _hardware_read_loop(self) -> None:
        while self._is_running and self._stream:
            try:
                data = self._stream.read(self.config.chunk_size, exception_on_overflow=False)
                self.feed_chunk(data)
            except Exception as e:
                logger.error(f"Error reading hardware audio stream: {e}")
                time.sleep(0.01)

    def stop(self) -> None:
        """Stops the audio capture engine."""
        self._is_running = False
        if self._stream:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        if self._pyAudio:
            try:
                self._pyAudio.terminate()
            except Exception:
                pass
            self._pyAudio = None
        logger.info("AudioCapture stopped.")
