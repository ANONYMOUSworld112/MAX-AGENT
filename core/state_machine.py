"""
MAX-AGENT Task State Machine
==============================

14-state lifecycle state machine for task execution.

States: CREATED → PLANNED → QUEUED → BLOCKED → RUNNING →
        VERIFYING → RETRYING → PAUSED → CANCELLING →
        INTERRUPTED → COMPLETED → FAILED → CANCELLED → EXPIRED

Terminal states: COMPLETED, FAILED, CANCELLED, EXPIRED

Design decisions:
  - Explicit transition table: every legal transition is enumerated.
    Unlisted transitions raise InvalidStateTransitionError.
  - BLOCKED state requires a BlockedReason.
  - Terminal states reject all further transitions.
  - Thread-safe via threading.Lock for concurrent task updates.
  - Records transition history for audit/debugging.

Master Spec references:
  - Section 8 (task state machine)
  - Section 14 (verification outcome gating)
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Optional

from core.contracts import TaskStatus, BlockedReason, _now_utc


class InvalidStateTransitionError(Exception):
    """Raised when a task attempts an illegal state transition."""

    def __init__(self, current: TaskStatus, requested: TaskStatus, reason: str = ""):
        self.current = current
        self.requested = requested
        msg = f"Invalid transition: {current.value} → {requested.value}"
        if reason:
            msg += f" ({reason})"
        super().__init__(msg)


@dataclass
class TransitionRecord:
    """Audit record of a single state transition."""
    from_state: TaskStatus
    to_state: TaskStatus
    timestamp: str = field(default_factory=_now_utc)
    reason: str = ""
    actor: str = ""  # "system", "user", agent name

    def to_dict(self) -> dict:
        return {
            "from_state": self.from_state.value,
            "to_state": self.to_state.value,
            "timestamp": self.timestamp,
            "reason": self.reason,
            "actor": self.actor,
        }


# ---------------------------------------------------------------------------
# Transition Table
# ---------------------------------------------------------------------------

# Maps (current_state) → set of valid target states.
# If a transition is not in this table, it is illegal.
_TRANSITION_TABLE: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.CREATED: {
        TaskStatus.PLANNED,       # Decomposition produced a plan
        TaskStatus.QUEUED,        # Fast-path: single-action, no planning needed
        TaskStatus.CANCELLED,     # User cancels before execution
        TaskStatus.FAILED,        # Intent validation failure
    },
    TaskStatus.PLANNED: {
        TaskStatus.QUEUED,        # Plan validated, ready for scheduling
        TaskStatus.CANCELLED,     # User cancels after plan review
        TaskStatus.FAILED,        # Plan validation failure
    },
    TaskStatus.QUEUED: {
        TaskStatus.BLOCKED,       # Waiting on resource, dependency, or user
        TaskStatus.RUNNING,       # Scheduler dispatched, resources acquired
        TaskStatus.CANCELLED,     # User cancels while queued
        TaskStatus.EXPIRED,       # Deadline passed while waiting
    },
    TaskStatus.BLOCKED: {
        TaskStatus.QUEUED,        # Block resolved, re-queued for dispatch
        TaskStatus.CANCELLED,     # User cancels while blocked
        TaskStatus.EXPIRED,       # Deadline passed while blocked
        TaskStatus.FAILED,        # Block cannot be resolved
    },
    TaskStatus.RUNNING: {
        TaskStatus.VERIFYING,     # Execution completed, awaiting verification
        TaskStatus.PAUSED,        # User pauses or user-activity detected
        TaskStatus.CANCELLING,    # Cancel requested during execution
        TaskStatus.FAILED,        # Unrecoverable execution error
        TaskStatus.INTERRUPTED,   # Kill switch or emergency stop
    },
    TaskStatus.VERIFYING: {
        TaskStatus.COMPLETED,     # Verification passed (SUCCESS)
        TaskStatus.RETRYING,      # Verification failed, retry allowed
        TaskStatus.FAILED,        # Verification FAILURE, no retries left
    },
    TaskStatus.RETRYING: {
        TaskStatus.RUNNING,       # Retry attempt started
        TaskStatus.FAILED,        # Max retries exceeded
        TaskStatus.CANCELLED,     # User cancels retry loop
    },
    TaskStatus.PAUSED: {
        TaskStatus.RUNNING,       # User resumes
        TaskStatus.CANCELLING,    # User cancels while paused
    },
    TaskStatus.CANCELLING: {
        TaskStatus.CANCELLED,     # Graceful cleanup completed
        TaskStatus.INTERRUPTED,   # Forced kill after cancel timeout
    },
    TaskStatus.INTERRUPTED: {
        TaskStatus.FAILED,        # Post-interrupt cleanup confirms failure
        TaskStatus.CANCELLED,     # Emergency stop treated as cancel
    },
    # Terminal states: no outgoing transitions
    TaskStatus.COMPLETED: set(),
    TaskStatus.FAILED: set(),
    TaskStatus.CANCELLED: set(),
    TaskStatus.EXPIRED: set(),
}


class TaskStateMachine:
    """
    Thread-safe state machine enforcing the 14-state task lifecycle.

    Usage:
        fsm = TaskStateMachine(task_id="abc-123")
        fsm.transition(TaskStatus.QUEUED, reason="Fast-path intent")
        fsm.transition(TaskStatus.RUNNING, actor="scheduler")
        fsm.transition(TaskStatus.VERIFYING)
        fsm.transition(TaskStatus.COMPLETED)
    """

    def __init__(
        self,
        task_id: str = "",
        initial_state: TaskStatus = TaskStatus.CREATED,
    ):
        self._task_id = task_id
        self._state = initial_state
        self._blocked_reason: Optional[BlockedReason] = None
        self._history: list[TransitionRecord] = []
        self._lock = threading.Lock()

    @property
    def state(self) -> TaskStatus:
        return self._state

    @property
    def task_id(self) -> str:
        return self._task_id

    @property
    def blocked_reason(self) -> Optional[BlockedReason]:
        return self._blocked_reason

    @property
    def history(self) -> list[TransitionRecord]:
        """Return a copy of the transition history."""
        with self._lock:
            return list(self._history)

    @property
    def is_terminal(self) -> bool:
        return self._state.is_terminal

    def can_transition(self, target: TaskStatus) -> bool:
        """Check if a transition to target is legal from current state."""
        return target in _TRANSITION_TABLE.get(self._state, set())

    def transition(
        self,
        target: TaskStatus,
        *,
        reason: str = "",
        actor: str = "system",
        blocked_reason: Optional[BlockedReason] = None,
    ) -> TransitionRecord:
        """
        Attempt a state transition.

        Args:
            target: The desired new state.
            reason: Human-readable reason for the transition.
            actor: Who triggered the transition.
            blocked_reason: Required when transitioning to BLOCKED.

        Returns:
            TransitionRecord documenting the transition.

        Raises:
            InvalidStateTransitionError: If the transition is illegal.
        """
        with self._lock:
            return self._transition_locked(target, reason, actor, blocked_reason)

    def _transition_locked(
        self,
        target: TaskStatus,
        reason: str,
        actor: str,
        blocked_reason: Optional[BlockedReason],
    ) -> TransitionRecord:
        current = self._state

        # Terminal states reject all transitions
        if current.is_terminal:
            raise InvalidStateTransitionError(
                current, target,
                f"Task is in terminal state {current.value}; no further transitions allowed"
            )

        # Check transition table
        allowed = _TRANSITION_TABLE.get(current, set())
        if target not in allowed:
            raise InvalidStateTransitionError(current, target)

        # BLOCKED requires a reason
        if target == TaskStatus.BLOCKED:
            if blocked_reason is None:
                raise InvalidStateTransitionError(
                    current, target,
                    "blocked_reason is required when transitioning to BLOCKED"
                )
            self._blocked_reason = blocked_reason
        else:
            # Clear blocked reason when leaving BLOCKED
            if current == TaskStatus.BLOCKED:
                self._blocked_reason = None

        # Record and apply
        record = TransitionRecord(
            from_state=current,
            to_state=target,
            reason=reason,
            actor=actor,
        )
        self._history.append(record)
        self._state = target
        return record

    def get_allowed_transitions(self) -> set[TaskStatus]:
        """Return the set of states reachable from the current state."""
        return set(_TRANSITION_TABLE.get(self._state, set()))

    def to_dict(self) -> dict:
        return {
            "task_id": self._task_id,
            "current_state": self._state.value,
            "blocked_reason": self._blocked_reason.value if self._blocked_reason else None,
            "is_terminal": self.is_terminal,
            "history": [r.to_dict() for r in self._history],
        }
