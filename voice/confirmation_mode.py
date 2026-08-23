"""
MAX OS — Voice Layer: Voice-Mode Security Gate Confirmations (Section 7).
Ties into Security Gate (§ 13.2 / 13.4).
Features:
  - Speaks exact target + consequence of Tier 1/2 actions with mic-gating.
  - Direct-listen window (~6–8s) without requiring wake word.
  - Bounded semantic resolution (affirmative, negative, ambiguous).
  - Strict non-confirmation default on silence, timeout, or ambiguity.
"""

from __future__ import annotations

import enum
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Tuple

from core.security.security_gate import RiskTier, SecurityGate
from voice.audio_capture import AudioCapture
from voice.stt import STTResult, SpeechToTextEngine
from voice.tts import VoiceTTS
from voice.vad import VADEngine

logger = logging.getLogger("max.voice.confirmation_mode")


class ConfirmationDecision(str, enum.Enum):
    AFFIRMATIVE = "AFFIRMATIVE"
    NEGATIVE = "NEGATIVE"
    AMBIGUOUS = "AMBIGUOUS"
    TIMEOUT = "TIMEOUT"


@dataclass
class ConfirmationResult:
    decision: ConfirmationDecision
    transcript: str
    is_confirmed: bool
    approval_token: Optional[str] = None
    re_prompted: bool = False
    details: str = ""


# Bounded semantic classification patterns (intent-level resolution)
AFFIRMATIVE_PATTERNS = [
    re.compile(r"\b(yes|yeah|yep|sure|proceed|confirm|go ahead|do it|go for it|approved|affirmative|okay|ok)\b", re.IGNORECASE),
]

NEGATIVE_PATTERNS = [
    re.compile(r"\b(no|nope|cancel|stop|wait|don't|dont|negative|abort|nevermind|never mind|halt)\b", re.IGNORECASE),
]


class VoiceConfirmationHandler:
    """
    Voice-Mode Security Gate Confirmation Coordinator.
    Enforces per-instance verification for sensitive/destructive operations without compromising safety.
    """

    def __init__(
        self,
        security_gate: Optional[SecurityGate] = None,
        tts: Optional[VoiceTTS] = None,
        stt: Optional[SpeechToTextEngine] = None,
        audio_capture: Optional[AudioCapture] = None,
        vad: Optional[VADEngine] = None,
        direct_listen_seconds: float = 7.0,
    ):
        self.security_gate = security_gate or SecurityGate()
        self.tts = tts or VoiceTTS()
        self.stt = stt or SpeechToTextEngine()
        self.audio_capture = audio_capture
        self.vad = vad or VADEngine()
        self.direct_listen_seconds = direct_listen_seconds

    def evaluate_response_semantics(self, text: str) -> ConfirmationDecision:
        """
        Performs bounded semantic classification on the confirmation response:
        AFFIRMATIVE, NEGATIVE, or AMBIGUOUS.
        Handles conversational hesitations (e.g. 'hold on... okay, do it' vs 'yes... wait, cancel that')
        and compound negations (e.g. 'don't do it', 'do not proceed').
        """
        clean = text.strip().lower()
        if not clean:
            return ConfirmationDecision.AMBIGUOUS

        # 0. Explicit uncertainty expressions -> AMBIGUOUS
        if re.search(r"\b(not sure|unsure|dont know|don't know|uncertain|undecided)\b", clean):
            return ConfirmationDecision.AMBIGUOUS

        # 1. Normalize negated affirmative phrases (e.g. "don't do it" -> "cancel")
        normalized = re.sub(r"\b(don't|dont|do not|never)\s+(do it|proceed|confirm|go ahead|do that)\b", "cancel", clean)

        # 2. Strip conversational non-decision hesitations
        cleaned_clause = re.sub(r"\b(hold on|wait a second|wait a sec|let me think|hang on)\b", "", normalized).strip()

        neg_matches = [m.start() for p in NEGATIVE_PATTERNS for m in p.finditer(cleaned_clause)]
        aff_matches = [m.start() for p in AFFIRMATIVE_PATTERNS for m in p.finditer(cleaned_clause)]

        # If only affirmative tokens found
        if aff_matches and not neg_matches:
            return ConfirmationDecision.AFFIRMATIVE

        # If only negative tokens found
        if neg_matches and not aff_matches:
            return ConfirmationDecision.NEGATIVE

        # If both are present, inspect the final clause / trailing decision
        if aff_matches and neg_matches:
            # Check for direct conflicting juxtaposition (e.g. "yes no", "no yes", "yes but no")
            if re.search(r"\b(yes|yeah|yep)\s+(no|nope|cancel)\b", clean) or re.search(r"\b(no|nope)\s+(yes|yeah|yep)\b", clean) or "yes but no" in clean or "no but yes" in clean:
                return ConfirmationDecision.AMBIGUOUS

            last_aff = max(aff_matches)
            last_neg = max(neg_matches)

            # E.g. "wait... okay do it" -> affirmative is trailing
            if last_aff > last_neg + 4:
                return ConfirmationDecision.AFFIRMATIVE
            # E.g. "yes... wait, actually cancel" -> negative is trailing
            elif last_neg > last_aff + 4:
                return ConfirmationDecision.NEGATIVE
            else:
                # Contradictory close juxtaposition
                return ConfirmationDecision.AMBIGUOUS

        return ConfirmationDecision.AMBIGUOUS

    def request_confirmation_voice(
        self,
        action_type: str,
        target: str,
        action_id: str,
        task_id: str,
        risk_tier: RiskTier = RiskTier.TIER_2,
        consequence_description: str = "",
        mock_response_text: Optional[str] = None,
    ) -> ConfirmationResult:
        """
        Full voice confirmation workflow:
        1. Speaks question aloud (e.g. "This action will delete build logs on disk. Would you like to proceed?")
        2. Direct-listen window without wake word.
        3. Classifies response semantics.
        4. Issues single-use SecurityGate token if affirmed, or aborts/escalates.
        """
        consequence = consequence_description or f"execute {action_type} on {target}"
        prompt_text = (
            f"Caution, Sir. This action will {consequence}. "
            "Would you like me to proceed?"
        )

        logger.info(f"[VoiceConfirmation] Prompting user for Tier {risk_tier.value} action '{action_id}': {prompt_text}")
        self.tts.speak_sync(prompt_text, timeout=8.0)

        # Direct-listen attempt 1
        decision, transcript = self._listen_direct_window(mock_response_text=mock_response_text)

        # If ambiguous or timeout, re-prompt ONCE
        re_prompted = False
        if decision in (ConfirmationDecision.AMBIGUOUS, ConfirmationDecision.TIMEOUT) and mock_response_text is None:
            re_prompted = True
            reask_text = "I did not receive a clear confirmation. Please say yes to proceed, or no to cancel."
            self.tts.speak_sync(reask_text, timeout=6.0)
            decision, transcript = self._listen_direct_window()

        # Evaluate final decision
        if decision == ConfirmationDecision.AFFIRMATIVE:
            # Issue single-use approval token from SecurityGate
            token = self.security_gate.issue_tier2_approval_token(action_id)
            self.tts.speak("Proceeding with authorized action, Sir.")
            return ConfirmationResult(
                decision=decision,
                transcript=transcript,
                is_confirmed=True,
                approval_token=token,
                re_prompted=re_prompted,
                details=f"Authorized by voice response: '{transcript}'",
            )
        elif decision == ConfirmationDecision.NEGATIVE:
            self.tts.speak("Action cancelled, Sir.")
            return ConfirmationResult(
                decision=decision,
                transcript=transcript,
                is_confirmed=False,
                approval_token=None,
                re_prompted=re_prompted,
                details="Action explicitly cancelled by user.",
            )
        else:
            # Ambiguous / Timeout strictly defaults to non-confirmation
            self.tts.speak("Confirmation unresolved. Cancelling action for safety, Sir.")
            return ConfirmationResult(
                decision=decision,
                transcript=transcript,
                is_confirmed=False,
                approval_token=None,
                re_prompted=re_prompted,
                details="Unresolved or timed out confirmation; safety gate preserved.",
            )

    def _listen_direct_window(
        self, mock_response_text: Optional[str] = None
    ) -> Tuple[ConfirmationDecision, str]:
        """
        Listens directly during the window without requiring wake-word re-trigger.
        """
        if mock_response_text is not None:
            dec = self.evaluate_response_semantics(mock_response_text)
            return dec, mock_response_text

        if not self.audio_capture:
            return ConfirmationDecision.TIMEOUT, ""

        start_time = time.time()
        self.vad.reset()
        captured_chunks = []

        while time.time() - start_time < self.direct_listen_seconds:
            chunk = self.audio_capture.read_chunk(timeout=0.1)
            if chunk:
                frame_res = self.vad.process_frame(chunk)
                if self.vad.is_utterance_complete():
                    audio_bytes = self.vad.get_and_reset_utterance()
                    stt_res: STTResult = self.stt.transcribe(audio_bytes)
                    if not stt_res.is_empty:
                        dec = self.evaluate_response_semantics(stt_res.transcript)
                        return dec, stt_res.transcript
                    break

        return ConfirmationDecision.TIMEOUT, ""
