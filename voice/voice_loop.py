"""
MAX OS — Voice Layer: Voice Loop State Machine (Section 5 & Section 11).
Implements the full reactive voice state machine:
  IDLE ➔ CAPTURING ➔ TRANSCRIBING ➔ THINKING ➔ SPEAKING ➔ IDLE
Supports Push-To-Talk (Phase A) and Always-On Wake Word (Phase B).
"""

from __future__ import annotations

import enum
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from voice.audio_capture import AudioCapture
from voice.confirmation_mode import VoiceConfirmationHandler
from voice.intent_bridge import IntentBridgeResult, VoiceIntentBridge
from voice.stt import STTResult, SpeechToTextEngine
from voice.tts import VoiceTTS
from voice.vad import VADEngine
from voice.wakeword import WakeWordDetector, WakeWordResult

logger = logging.getLogger("max.voice.voice_loop")


class VoiceState(str, enum.Enum):
    IDLE = "IDLE"                    # Listening for wake word, VAD-gated, mic open, TTS silent
    CAPTURING = "CAPTURING"          # Active user speech recording, VAD tracking trailing silence
    TRANSCRIBING = "TRANSCRIBING"    # Running faster-whisper STT on captured utterance
    THINKING = "THINKING"            # Intent Engine / Planner / ComputerUseAgent executing
    SPEAKING = "SPEAKING"            # Playing vocal response; mic capture hard-muted
    CONFIRMATION = "CONFIRMATION"    # Voice-Mode Security Gate direct-listen confirmation


@dataclass
class VoiceLoopConfig:
    push_to_talk_mode: bool = False   # If True, skips automatic wake word listening
    thinking_feedback_delay_seconds: float = 3.5  # Time before speaking "still working on that"
    max_recording_seconds: float = 15.0


class VoiceLoop:
    """
    Continuous Voice Loop State Machine.
    Coordinates AudioCapture, VAD, WakeWord, STT, IntentBridge, TTS, and ConfirmationMode.
    """

    def __init__(
        self,
        audio_capture: Optional[AudioCapture] = None,
        vad: Optional[VADEngine] = None,
        wakeword: Optional[WakeWordDetector] = None,
        stt: Optional[SpeechToTextEngine] = None,
        intent_bridge: Optional[VoiceIntentBridge] = None,
        tts: Optional[VoiceTTS] = None,
        confirmation_handler: Optional[VoiceConfirmationHandler] = None,
        config: Optional[VoiceLoopConfig] = None,
    ):
        self.audio_capture = audio_capture or AudioCapture()
        self.vad = vad or VADEngine()
        self.wakeword = wakeword or WakeWordDetector()
        self.stt = stt or SpeechToTextEngine()
        self.intent_bridge = intent_bridge or VoiceIntentBridge()
        self.tts = tts or VoiceTTS(audio_capture=self.audio_capture)
        self.confirmation_handler = confirmation_handler or VoiceConfirmationHandler(
            tts=self.tts, stt=self.stt, audio_capture=self.audio_capture, vad=self.vad
        )
        self.config = config or VoiceLoopConfig()

        self._state = VoiceState.IDLE
        self._state_lock = threading.Lock()
        self._is_running = False
        self._loop_thread: Optional[threading.Thread] = None
        self._state_callbacks: List[Callable[[VoiceState], None]] = []

    @property
    def state(self) -> VoiceState:
        with self._state_lock:
            return self._state

    def _set_state(self, new_state: VoiceState) -> None:
        with self._state_lock:
            if self._state == new_state:
                return
            self._state = new_state
            logger.info(f"[VoiceLoop State] ➔ {new_state.value}")

        for cb in list(self._state_callbacks):
            try:
                cb(new_state)
            except Exception as e:
                logger.error(f"Error in VoiceLoop state callback: {e}")

    def on_state_change(self, callback: Callable[[VoiceState], None]) -> None:
        self._state_callbacks.append(callback)

    def start(self) -> None:
        """Starts the voice processing loop."""
        if self._is_running:
            return
        self._is_running = True
        self.audio_capture.start()
        self._loop_thread = threading.Thread(target=self._run_loop, name="VoiceLoopThread", daemon=True)
        self._loop_thread.start()
        logger.info("VoiceLoop started.")

    def stop(self) -> None:
        """Stops the voice processing loop."""
        self._is_running = False
        self.audio_capture.stop()
        self._set_state(VoiceState.IDLE)
        logger.info("VoiceLoop stopped.")

    def trigger_push_to_talk(self) -> None:
        """Manually transitions to CAPTURING state for Push-To-Talk invocation."""
        logger.info("Push-to-talk triggered.")
        self.vad.reset()
        self._set_state(VoiceState.CAPTURING)

    def _run_loop(self) -> None:
        """Main processing loop driving state transitions."""
        while self._is_running:
            curr_state = self.state

            if curr_state == VoiceState.IDLE:
                chunk = self.audio_capture.read_chunk(timeout=0.1)
                if not chunk:
                    continue

                if not self.config.push_to_talk_mode:
                    # 1. VAD Check
                    vad_res = self.vad.process_frame(chunk)
                    # 2. Wake Word Check if speech detected or checking continuously
                    ww_res = self.wakeword.process_frame(chunk)
                    if ww_res.detected:
                        logger.info(f"Wake word '{ww_res.word}' triggered.")
                        self.vad.reset()
                        self._set_state(VoiceState.CAPTURING)

            elif curr_state == VoiceState.CAPTURING:
                chunk = self.audio_capture.read_chunk(timeout=0.1)
                if chunk:
                    self.vad.process_frame(chunk)

                if self.vad.is_utterance_complete():
                    self._set_state(VoiceState.TRANSCRIBING)

            elif curr_state == VoiceState.TRANSCRIBING:
                audio_bytes = self.vad.get_and_reset_utterance()
                if not audio_bytes or len(audio_bytes) < 1000:
                    self._set_state(VoiceState.IDLE)
                    continue

                stt_res: STTResult = self.stt.transcribe(audio_bytes)
                if stt_res.is_empty or not stt_res.transcript:
                    logger.info("No speech detected or empty transcription.")
                    self._set_state(VoiceState.IDLE)
                    continue

                # Valid transcript received ➔ Transition to THINKING
                logger.info(f"STT Transcript: '{stt_res.transcript}'")
                self._execute_thinking_and_speaking(stt_res.transcript)

            time.sleep(0.01)

    def _execute_thinking_and_speaking(self, transcript: str) -> None:
        """Handles the THINKING and SPEAKING phases with timeout feedback."""
        self._set_state(VoiceState.THINKING)

        # Background timer for "Still working on that" if planning takes long
        stop_thinking_notify = threading.Event()

        def _thinking_feedback_timer():
            if not stop_thinking_notify.wait(timeout=self.config.thinking_feedback_delay_seconds):
                if self.state == VoiceState.THINKING:
                    self.tts.speak("Still working on that, Sir...")

        timer_thread = threading.Thread(target=_thinking_feedback_timer, daemon=True)
        timer_thread.start()

        # Execute through Intent Bridge
        bridge_res: IntentBridgeResult = self.intent_bridge.on_transcript(transcript)
        stop_thinking_notify.set()

        # Transition to SPEAKING
        self._set_state(VoiceState.SPEAKING)
        feedback_text = bridge_res.speech_feedback or "Done, Sir."
        self.tts.speak_sync(feedback_text, timeout=10.0)

        # Return to IDLE
        self._set_state(VoiceState.IDLE)

    def process_utterance_sync(self, audio_bytes: bytes) -> IntentBridgeResult:
        """
        Synchronously processes a raw audio utterance through STT, IntentBridge, and TTS.
        Convenience method for tests and direct injection.
        """
        self._set_state(VoiceState.TRANSCRIBING)
        stt_res = self.stt.transcribe(audio_bytes)
        if stt_res.is_empty:
            self._set_state(VoiceState.IDLE)
            return IntentBridgeResult(
                source="voice",
                transcript="",
                context={},
                speech_feedback="I didn't catch that.",
                success=False,
                error="Empty transcript",
            )

        self._set_state(VoiceState.THINKING)
        bridge_res = self.intent_bridge.on_transcript(stt_res.transcript)

        self._set_state(VoiceState.SPEAKING)
        if bridge_res.speech_feedback:
            self.tts.speak_sync(bridge_res.speech_feedback, timeout=6.0)

        self._set_state(VoiceState.IDLE)
        return bridge_res
