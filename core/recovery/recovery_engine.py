"""
MAX OS — Recovery Engine (Section 12).
Implements the 13-class failure taxonomy and ordered 8-step recovery strategy pipeline.
Enforces strict retry caps (default 3) and wall-clock budgets to prevent unbounded loops.
"""

from __future__ import annotations

import enum
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple


class FailureClass(str, enum.Enum):
    TARGET_NOT_FOUND = "target_not_found"
    APPLICATION_CLOSED = "application_closed"
    TIMEOUT = "timeout"
    NAVIGATION_FAILURE = "navigation_failure"
    WRONG_WINDOW_TAB = "wrong_window_tab"
    POPUP_BLOCKING = "popup_blocking"
    PERMISSION_DENIED = "permission_denied"
    STALE_ELEMENT = "stale_element"
    UNEXPECTED_DIALOG = "unexpected_dialog"
    NETWORK_FAILURE = "network_failure"
    APPLICATION_CRASH = "application_crash"
    MODEL_UNCERTAINTY = "model_uncertainty"
    ACTION_MISMATCH = "action_mismatch"


class RecoveryStrategy(str, enum.Enum):
    REOBSERVE = "reobserve"
    REFRESH_STATE = "refresh_state"
    SEARCH_AGAIN = "search_again"
    ALT_INTERACTION_METHOD = "alt_interaction_method"
    RETRY = "retry"
    CHANGE_STRATEGY = "change_strategy"
    REPLAN = "replan"
    ESCALATE_USER = "escalate_user"


# Ordered recovery strategy progression per failure class
STRATEGY_PIPELINE: Dict[FailureClass, List[RecoveryStrategy]] = {
    FailureClass.TARGET_NOT_FOUND: [
        RecoveryStrategy.REOBSERVE,
        RecoveryStrategy.SEARCH_AGAIN,
        RecoveryStrategy.ALT_INTERACTION_METHOD,
        RecoveryStrategy.REPLAN,
        RecoveryStrategy.ESCALATE_USER,
    ],
    FailureClass.STALE_ELEMENT: [
        RecoveryStrategy.REFRESH_STATE,
        RecoveryStrategy.SEARCH_AGAIN,
        RecoveryStrategy.RETRY,
        RecoveryStrategy.ESCALATE_USER,
    ],
    FailureClass.APPLICATION_CLOSED: [
        RecoveryStrategy.CHANGE_STRATEGY,
        RecoveryStrategy.REPLAN,
        RecoveryStrategy.ESCALATE_USER,
    ],
    FailureClass.UNEXPECTED_DIALOG: [
        RecoveryStrategy.ALT_INTERACTION_METHOD,
        RecoveryStrategy.REPLAN,
        RecoveryStrategy.ESCALATE_USER,
    ],
    FailureClass.POPUP_BLOCKING: [
        RecoveryStrategy.ALT_INTERACTION_METHOD,
        RecoveryStrategy.REOBSERVE,
        RecoveryStrategy.RETRY,
        RecoveryStrategy.ESCALATE_USER,
    ],
    FailureClass.TIMEOUT: [
        RecoveryStrategy.REOBSERVE,
        RecoveryStrategy.RETRY,
        RecoveryStrategy.REPLAN,
        RecoveryStrategy.ESCALATE_USER,
    ],
    FailureClass.NAVIGATION_FAILURE: [
        RecoveryStrategy.REFRESH_STATE,
        RecoveryStrategy.ALT_INTERACTION_METHOD,
        RecoveryStrategy.REPLAN,
        RecoveryStrategy.ESCALATE_USER,
    ],
    FailureClass.WRONG_WINDOW_TAB: [
        RecoveryStrategy.ALT_INTERACTION_METHOD,
        RecoveryStrategy.REFRESH_STATE,
        RecoveryStrategy.RETRY,
        RecoveryStrategy.ESCALATE_USER,
    ],
    FailureClass.PERMISSION_DENIED: [
        RecoveryStrategy.ESCALATE_USER,  # Permission denied escalates directly
    ],
    FailureClass.NETWORK_FAILURE: [
        RecoveryStrategy.RETRY,
        RecoveryStrategy.CHANGE_STRATEGY,
        RecoveryStrategy.ESCALATE_USER,
    ],
    FailureClass.APPLICATION_CRASH: [
        RecoveryStrategy.CHANGE_STRATEGY,
        RecoveryStrategy.REPLAN,
        RecoveryStrategy.ESCALATE_USER,
    ],
    FailureClass.MODEL_UNCERTAINTY: [
        RecoveryStrategy.REOBSERVE,
        RecoveryStrategy.REPLAN,
        RecoveryStrategy.ESCALATE_USER,
    ],
    FailureClass.ACTION_MISMATCH: [
        RecoveryStrategy.REFRESH_STATE,
        RecoveryStrategy.REPLAN,
        RecoveryStrategy.ESCALATE_USER,
    ],
}


@dataclass
class RecoveryAttempt:
    attempt_index: int
    failure_class: FailureClass
    strategy_used: RecoveryStrategy
    timestamp: float
    success: bool
    details: str = ""


@dataclass
class RecoverySession:
    task_id: str
    action_id: str
    max_retries: int = 3
    timeout_seconds: float = 30.0
    start_time: float = field(default_factory=time.time)
    attempts: List[RecoveryAttempt] = field(default_factory=list)
    current_failure: Optional[FailureClass] = None
    is_escalated: bool = False

    @property
    def retry_count(self) -> int:
        return len(self.attempts)

    @property
    def is_exhausted(self) -> bool:
        elapsed = time.time() - self.start_time
        return self.retry_count >= self.max_retries or elapsed >= self.timeout_seconds


class RecoveryEngine:
    """
    Failure Classification and Progressive Recovery Engine.
    Limits retries, executes ordered recovery strategies, and escalates cleanly.
    """

    def __init__(self, default_max_retries: int = 3, default_timeout: float = 30.0):
        self.default_max_retries = default_max_retries
        self.default_timeout = default_timeout
        self._active_sessions: Dict[str, RecoverySession] = {}

    def classify_failure(self, error: Exception | str, evidence: str = "") -> FailureClass:
        """
        Classifies an observed error or verification failure into the 13 FailureClasses.
        """
        msg = (f"{str(error)} {evidence}").lower()

        if any(w in msg for w in ("not found", "missing element", "element not found", "cannot locate")):
            return FailureClass.TARGET_NOT_FOUND
        elif any(w in msg for w in ("stale", "element moved", "element detached", "stale element")):
            return FailureClass.STALE_ELEMENT
        elif any(w in msg for w in ("closed", "not running", "window destroyed", "process exited")):
            return FailureClass.APPLICATION_CLOSED
        elif any(w in msg for w in ("popup", "modal blocking", "overlay", "interception")):
            return FailureClass.POPUP_BLOCKING
        elif any(w in msg for w in ("dialog", "alert", "unexpected prompt", "uac")):
            return FailureClass.UNEXPECTED_DIALOG
        elif any(w in msg for w in ("nav", "url mismatch", "failed to load", "dns", "http 404")):
            return FailureClass.NAVIGATION_FAILURE
        elif any(w in msg for w in ("wrong window", "wrong tab", "background window")):
            return FailureClass.WRONG_WINDOW_TAB
        elif any(w in msg for w in ("permission", "denied", "gate required", "unauthorized")):
            return FailureClass.PERMISSION_DENIED
        elif any(w in msg for w in ("crash", "segmentation", "aborted", "crashed")):
            return FailureClass.APPLICATION_CRASH
        elif any(w in msg for w in ("timeout", "timed out", "no response")):
            return FailureClass.TIMEOUT
        elif any(w in msg for w in ("network", "econnreset", "socket", "disconnected")):
            return FailureClass.NETWORK_FAILURE
        elif any(w in msg for w in ("uncertain", "low confidence", "ambiguous")):
            return FailureClass.MODEL_UNCERTAINTY

        return FailureClass.ACTION_MISMATCH

    def start_recovery_session(
        self,
        task_id: str,
        action_id: str,
        failure_class: FailureClass,
        max_retries: Optional[int] = None,
    ) -> RecoverySession:
        """Starts a tracking session for a failing action."""
        session_key = f"{task_id}:{action_id}"
        session = RecoverySession(
            task_id=task_id,
            action_id=action_id,
            max_retries=max_retries or self.default_max_retries,
            timeout_seconds=self.default_timeout,
            current_failure=failure_class,
        )
        self._active_sessions[session_key] = session
        return session

    def get_next_strategy(self, task_id: str, action_id: str, failure_class: FailureClass) -> RecoveryStrategy:
        """
        Determines the next ordered recovery strategy.
        If retry budget is exhausted, immediately returns ESCALATE_USER.
        """
        session_key = f"{task_id}:{action_id}"
        session = self._active_sessions.get(session_key)
        if not session:
            session = self.start_recovery_session(task_id, action_id, failure_class)

        # Check if exhausted
        if session.is_exhausted:
            session.is_escalated = True
            return RecoveryStrategy.ESCALATE_USER

        # Pipeline lookup
        pipeline = STRATEGY_PIPELINE.get(failure_class, [RecoveryStrategy.RETRY, RecoveryStrategy.ESCALATE_USER])
        attempt_idx = session.retry_count

        if attempt_idx < len(pipeline):
            strategy = pipeline[attempt_idx]
        else:
            strategy = RecoveryStrategy.ESCALATE_USER

        return strategy

    def record_attempt(
        self,
        task_id: str,
        action_id: str,
        failure_class: FailureClass,
        strategy: RecoveryStrategy,
        success: bool,
        details: str = "",
    ) -> None:
        """Records an attempted recovery strategy result."""
        session_key = f"{task_id}:{action_id}"
        session = self._active_sessions.get(session_key)
        if session:
            attempt = RecoveryAttempt(
                attempt_index=session.retry_count + 1,
                failure_class=failure_class,
                strategy_used=strategy,
                timestamp=time.time(),
                success=success,
                details=details,
            )
            session.attempts.append(attempt)
            if success:
                # Clean up session on recovery success
                del self._active_sessions[session_key]
