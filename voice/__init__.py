"""
MAX OS — Dynamic Voice Input Layer Package.
Implements Section 3 (Voice Interface Node), Section 4 (Module Structure),
Section 5 (State Machine), and Section 7 (Voice-Mode Security Gate Confirmations).
"""

from voice.audio_capture import AudioCapture, AudioConfig
from voice.confirmation_mode import (
    ConfirmationDecision,
    ConfirmationResult,
    VoiceConfirmationHandler,
)
from voice.intent_bridge import IntentBridgeResult, VoiceIntentBridge
from voice.stt import STTConfig, STTResult, SpeechToTextEngine
from voice.tts import VoiceTTS
from voice.vad import VADConfig, VADEngine, VADFrameResult
from voice.voice_loop import VoiceLoop, VoiceLoopConfig, VoiceState
from voice.wakeword import WakeWordConfig, WakeWordDetector, WakeWordResult

__all__ = [
    "AudioCapture",
    "AudioConfig",
    "VADEngine",
    "VADConfig",
    "VADFrameResult",
    "WakeWordDetector",
    "WakeWordConfig",
    "WakeWordResult",
    "SpeechToTextEngine",
    "STTConfig",
    "STTResult",
    "VoiceIntentBridge",
    "IntentBridgeResult",
    "VoiceTTS",
    "VoiceConfirmationHandler",
    "ConfirmationDecision",
    "ConfirmationResult",
    "VoiceLoop",
    "VoiceLoopConfig",
    "VoiceState",
]
