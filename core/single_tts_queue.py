"""
MAX OS — Single TTS Queue & Serial Audio Arbiter.
Guarantees strictly ONE Text-to-Speech (TTS) audio stream plays at any given time.
Eliminates audio overlaps, stuttering, and engine lockups across all multi-agent subsystems.
Uses lock-free low-level OS writes and clean atexit teardown to prevent interpreter shutdown errors.
"""

from __future__ import annotations

import atexit
import logging
import os
import sys
import queue
import subprocess
import threading
import time
from typing import Callable, Optional

import pyttsx3

logger = logging.getLogger("max.single_tts")


def _safe_os_print(msg: str) -> None:
    """Low-level lock-free direct OS write that never deadlocks Python's BufferedWriter."""
    try:
        if getattr(sys, "is_finalizing", lambda: False)():
            return
        os.write(1, (msg + "\r\n").encode("utf-8", errors="ignore"))
    except Exception:
        pass


class SingleTTSQueue:
    """
    Thread-safe, FIFO-synchronized serial Text-to-Speech engine.
    Ensures zero overlapping speech across all concurrent agents.
    """

    _instance: Optional[SingleTTSQueue] = None
    _lock = threading.Lock()

    def __init__(self, rate: int = 175, enabled: bool = True):
        self.rate = rate
        self.enabled = enabled
        self._speech_queue: queue.Queue[Optional[str]] = queue.Queue()
        self._is_speaking = threading.Event()
        self._stop_event = threading.Event()
        self._audio_mutex = threading.Lock()
        self._worker_thread = threading.Thread(target=self._process_queue_worker, daemon=True)
        self._worker_thread.start()

    @classmethod
    def get_instance(cls) -> SingleTTSQueue:
        """Singleton accessor for global audio queue."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def _process_queue_worker(self) -> None:
        """Background daemon processing speech items one by one sequentially."""
        while not self._stop_event.is_set():
            try:
                text = self._speech_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            except Exception:
                break

            if text is None or getattr(sys, "is_finalizing", lambda: False)():
                try:
                    self._speech_queue.task_done()
                except Exception:
                    pass
                break

            if not text or not text.strip() or not self.enabled:
                try:
                    self._speech_queue.task_done()
                except Exception:
                    pass
                continue

            with self._audio_mutex:
                if self._stop_event.is_set() or getattr(sys, "is_finalizing", lambda: False)():
                    try:
                        self._speech_queue.task_done()
                    except Exception:
                        pass
                    break

                self._is_speaking.set()
                _safe_os_print(f"🔊 [J.A.R.V.I.S. Voice]: \"{text}\"")

                try:
                    # Windows pyttsx3 SAPI5 audio playback
                    engine = pyttsx3.init()
                    engine.setProperty("rate", self.rate)
                    engine.say(text)
                    engine.runAndWait()
                except Exception as e:
                    logger.debug(f"pyttsx3 playback fallback: {e}")
                    # Fallback to PowerShell System.Speech
                    try:
                        sanitized = text.replace('"', "'")
                        ps_cmd = f'Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak("{sanitized}")'
                        subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True, timeout=5)
                    except Exception:
                        pass
                finally:
                    self._is_speaking.clear()
                    try:
                        self._speech_queue.task_done()
                    except Exception:
                        pass

    def speak(self, text: str) -> None:
        """
        Enqueues text for sequential speech (non-blocking).
        Guaranteed to never overlap with previous or future speech.
        """
        if text and text.strip() and self.enabled and not self._stop_event.is_set():
            self._speech_queue.put(text.strip())

    def speak_sync(self, text: str, timeout: float = 10.0) -> None:
        """
        Enqueues text and blocks until this specific speech item finishes playing.
        """
        if not text or not text.strip() or not self.enabled or self._stop_event.is_set():
            return

        self._speech_queue.put(text.strip())
        self.wait_until_idle(timeout=timeout)

    def wait_until_idle(self, timeout: float = 15.0) -> None:
        """Blocks until all queued speech items have finished playing."""
        start_t = time.time()
        while (not self._speech_queue.empty() or self._is_speaking.is_set()) and (time.time() - start_t < timeout):
            time.sleep(0.05)

    def stop(self) -> None:
        """Stops the worker thread cleanly."""
        self._stop_event.set()
        try:
            self._speech_queue.put(None)
        except Exception:
            pass

    @property
    def is_busy(self) -> bool:
        return self._is_speaking.is_set() or not self._speech_queue.empty()


def _cleanup_tts_at_exit():
    if SingleTTSQueue._instance is not None:
        SingleTTSQueue._instance.stop()


atexit.register(_cleanup_tts_at_exit)


# Global helper functions
def speak(text: str) -> None:
    SingleTTSQueue.get_instance().speak(text)


def speak_sync(text: str, timeout: float = 10.0) -> None:
    SingleTTSQueue.get_instance().speak_sync(text, timeout=timeout)
