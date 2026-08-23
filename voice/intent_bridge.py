"""
MAX OS — Voice Layer: Intent Bridge (Section 3).
The ONLY contract: forwards raw STT output unmodified and un-pattern-matched
to the Master Orchestrator, Planner, and ComputerUseAgent.

CRITICAL INVARIANT:
This module contains ZERO keyword checking ('if <keyword> in transcript' is strictly forbidden).
The transcript is processed as free text exactly as if typed into the Text Interface.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

from core.command_model import CommandModel, TaskPlan
from core.orchestrator import MasterOrchestrator, OrchestrationPlan

logger = logging.getLogger("max.voice.intent_bridge")


@dataclass
class IntentBridgeResult:
    source: str
    transcript: str
    context: Dict[str, Any]
    plan: Optional[Any] = None
    execution_result: Optional[Any] = None
    speech_feedback: str = ""
    success: bool = True
    error: Optional[str] = None


class VoiceIntentBridge:
    """
    Zero-logic Intent Bridge connecting the Voice Layer to the Master Orchestrator.
    Transcripts pass through untouched into the existing AI planning pipeline.
    """

    def __init__(
        self,
        orchestrator: Optional[MasterOrchestrator] = None,
        custom_submit_fn: Optional[Callable[[str, Dict[str, Any]], Any]] = None,
    ):
        self.orchestrator = orchestrator or MasterOrchestrator()
        self.custom_submit_fn = custom_submit_fn

    def on_transcript(
        self,
        transcript: str,
        session_context: Optional[Dict[str, Any]] = None,
        approval_tokens: Optional[Dict[str, str]] = None,
    ) -> IntentBridgeResult:
        """
        transcript: raw STT output, unmodified, un-pattern-matched.
        Forwarded exactly as if typed into the Text Interface.
        """
        raw_text = transcript.strip()
        context = session_context or {}

        logger.info(f"[VoiceIntentBridge] Submitting raw voice transcript: '{raw_text}'")

        if not raw_text:
            return IntentBridgeResult(
                source="voice",
                transcript="",
                context=context,
                speech_feedback="I didn't catch that. Could you please repeat?",
                success=False,
                error="Empty transcript",
            )

        # 1. Custom submit handler if provided
        if self.custom_submit_fn is not None:
            try:
                res = self.custom_submit_fn(raw_text, context)
                return IntentBridgeResult(
                    source="voice",
                    transcript=raw_text,
                    context=context,
                    execution_result=res,
                    speech_feedback=f"Completed request: {raw_text[:50]}",
                    success=True,
                )
            except Exception as e:
                logger.error(f"Error in custom submit function: {e}")
                return IntentBridgeResult(
                    source="voice",
                    transcript=raw_text,
                    context=context,
                    speech_feedback="I encountered an issue executing your request, Sir.",
                    success=False,
                    error=str(e),
                )

        # 2. Master Orchestrator Pipeline (Universal Command Model + ComputerUseAgent)
        try:
            plan = self.orchestrator.execute_compound_goal(
                goal=raw_text,
                approval_tokens=approval_tokens,
            )
            feedback = f"Finished working on: {raw_text[:50]}"
            if hasattr(plan, "is_completed") and plan.is_completed:
                feedback = "Task executed and verified successfully, Sir."

            return IntentBridgeResult(
                source="voice",
                transcript=raw_text,
                context=context,
                plan=plan,
                execution_result=plan,
                speech_feedback=feedback,
                success=True,
            )
        except Exception as e:
            logger.error(f"Error executing orchestrated voice goal: {e}")
            return IntentBridgeResult(
                source="voice",
                transcript=raw_text,
                context=context,
                speech_feedback=f"Could not complete task: {str(e)[:60]}",
                success=False,
                error=str(e),
            )
