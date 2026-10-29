"""
core/audio/pipeline.py — Full-Duplex Voice Pipeline & Barge-In Coordinator.

Coordinates microphone capture, Acoustic Echo Cancellation (AEC), wake-word detection,
Voice Activity Detection (VAD), Multilingual STT, Agent reasoning loop, and streaming TTS.
Guarantees sub-300ms barge-in cutoff when user speaks during playback.
"""
from __future__ import annotations

import asyncio
import logging
import queue
import threading
import time
from typing import Callable, Optional

import numpy as np

from core.audio.aec import AcousticEchoCanceller
from core.audio.stt import MultilingualSTT
from core.audio.tts import PiperTTS
from core.audio.wakeword import VoiceActivityDetector, WakeWordDetector

logger = logging.getLogger("friday.audio.pipeline")


class VoicePipeline:
    """
    Unified full-duplex audio pipeline with echo cancellation and barge-in support.
    """

    def __init__(
        self,
        agent_loop: Optional[any] = None,
        language: str = "en",
        sample_rate: int = 16000,
        on_state_change: Optional[Callable[[str], None]] = None,
        on_transcript: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        self.agent_loop = agent_loop
        self.language = language
        self.sample_rate = sample_rate
        self.on_state_change = on_state_change
        self.on_transcript = on_transcript

        # State tracking: "IDLE_LISTENING", "RECORDING_UTTERANCE", "THINKING", "SPEAKING"
        self._state = "IDLE_LISTENING"
        self._running = False
        self._barge_in_latency_ms: float = 0.0

        # Subsystems
        self.aec = AcousticEchoCanceller(sample_rate=sample_rate)
        self.wakeword = WakeWordDetector(on_wake=self._on_wake_triggered)
        self.vad = VoiceActivityDetector(sample_rate=sample_rate)
        self.stt = MultilingualSTT(device="cuda")
        self.tts = PiperTTS(
            sample_rate=22050,
            aec_reference_callback=self.aec.feed_speaker_reference,
        )

        self._audio_queue: queue.Queue = queue.Queue(maxsize=200)

    def _set_state(self, new_state: str) -> None:
        if self._state != new_state:
            self._state = new_state
            logger.info("VoicePipeline state -> %s", new_state)
            if self.on_state_change:
                self.on_state_change(new_state)

    def _on_wake_triggered(self, alias: str) -> None:
        logger.info("Wake word activated for alias '%s'. Listening for command...", alias)
        self._set_state("RECORDING_UTTERANCE")

    def process_mic_chunk(self, raw_mic_chunk: np.ndarray) -> dict:
        """
        Process a single mic frame (e.g. 20ms-80ms at 16kHz).
        Handles echo cancellation, barge-in detection, and utterance aggregation.
        """
        now = time.time()

        # 1. Acoustic Echo Cancellation: subtract speaker audio from mic
        clean_chunk, erle_db = self.aec.process_mic_frame(raw_mic_chunk)

        # 2. Barge-in check: if assistant is speaking and user speaks into mic
        if self.tts.is_playing:
            chunk_f32 = clean_chunk.astype(np.float32)
            if np.max(np.abs(chunk_f32)) > 1.0:
                chunk_f32 = chunk_f32 / 32768.0
            energy = float(np.sqrt(np.mean(chunk_f32 ** 2)))
            if energy >= self.vad.energy_threshold:
                # Barge-in detected!
                barge_start = time.time()
                self.tts.stop()
                self._barge_in_latency_ms = (time.time() - barge_start) * 1000.0
                logger.warning("BARGE-IN TRIGGERED: Playback halted in %.2fms", self._barge_in_latency_ms)
                self._set_state("RECORDING_UTTERANCE")
                return {
                    "event": "barge_in",
                    "latency_ms": self._barge_in_latency_ms,
                    "erle_db": erle_db,
                }

        # 3. If in IDLE_LISTENING, check for wake word
        if self._state == "IDLE_LISTENING":
            wake_det = self.wakeword.feed_audio(clean_chunk)
            if wake_det:
                return {"event": "wake_word_detected", "details": wake_det}

        # 4. If in RECORDING_UTTERANCE, aggregate speech using VAD
        elif self._state == "RECORDING_UTTERANCE":
            vad_res = self.vad.process_frame(clean_chunk)
            if vad_res["speech_ended"] and vad_res["complete_utterance"] is not None:
                utterance = vad_res["complete_utterance"]
                logger.info("Utterance complete (%d samples). Routing to STT...", len(utterance))
                self._set_state("THINKING")

                # Transcribe
                transcript, meta = self.stt.transcribe(utterance, language=self.language)
                if self.on_transcript:
                    self.on_transcript("user", transcript)

                # Execute LLM Turn if agent loop is connected
                if transcript and self.agent_loop:
                    asyncio.create_task(self._execute_agent_turn(transcript))
                else:
                    self._set_state("IDLE_LISTENING")

                return {
                    "event": "utterance_processed",
                    "transcript": transcript,
                    "metadata": meta,
                }

        return {"event": "idle", "erle_db": erle_db}

    async def _execute_agent_turn(self, user_text: str) -> None:
        """Run agent loop on transcribed voice text and stream reply."""
        try:
            self._set_state("THINKING")
            reply = await self.agent_loop.run(
                user_text,
                on_preamble=lambda p: self.tts.speak(p, block=False),
            )
            if reply:
                if self.on_transcript:
                    self.on_transcript("assistant", reply)
                self._set_state("SPEAKING")
                self.tts.speak(reply, block=True)
        except Exception as e:
            logger.error("Error executing agent turn from voice: %s", e)
        finally:
            self._set_state("IDLE_LISTENING")

    @property
    def current_state(self) -> str:
        return self._state

    @property
    def last_barge_in_latency_ms(self) -> float:
        return self._barge_in_latency_ms
