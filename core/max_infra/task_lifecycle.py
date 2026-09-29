"""Task Lifecycle Finite State Machine (FSM).

Enforces strict deterministic progression:
CREATED -> QUEUED -> LOCK_WAIT -> RUNNING -> RECONCILING -> DONE | FAILED | ROLLED_BACK
Supports cancellation from any non-terminal state when Kill Switch is tripped.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Dict, Set

logger = logging.getLogger("max.infra.task_lifecycle")


class TaskState(str, Enum):
    CREATED = "CREATED"
    QUEUED = "QUEUED"
    LOCK_WAIT = "LOCK_WAIT"
    RUNNING = "RUNNING"
    RECONCILING = "RECONCILING"
    DONE = "DONE"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    ROLLED_BACK = "ROLLED_BACK"


class InvalidStateTransitionError(Exception):
    """Raised when an illegal lifecycle state transition is attempted."""
    pass


class TaskLifecycleFSM:
    def __init__(self, task_id: Optional[str] = None, initial_state: TaskState = TaskState.CREATED) -> None:
        self.task_id = task_id
        self.current_state = initial_state

    def transition_to(self, target: TaskState) -> TaskState:
        self.current_state = self.transition(self.current_state, target)
        return self.current_state

    def step(self, target: TaskState) -> TaskState:
        return self.transition_to(target)

    # Explicit allowed transitions map
    ALLOWED_TRANSITIONS: Dict[TaskState, Set[TaskState]] = {
        TaskState.CREATED: {TaskState.QUEUED, TaskState.CANCELLED, TaskState.FAILED},
        TaskState.QUEUED: {TaskState.LOCK_WAIT, TaskState.CANCELLED, TaskState.FAILED},
        TaskState.LOCK_WAIT: {TaskState.RUNNING, TaskState.CANCELLED, TaskState.FAILED},
        TaskState.RUNNING: {TaskState.RECONCILING, TaskState.FAILED, TaskState.CANCELLED},
        TaskState.RECONCILING: {TaskState.DONE, TaskState.ROLLED_BACK, TaskState.FAILED, TaskState.CANCELLED},
        # Terminal states have no further transitions
        TaskState.DONE: set(),
        TaskState.FAILED: set(),
        TaskState.CANCELLED: set(),
        TaskState.ROLLED_BACK: set(),
    }

    @classmethod
    def can_transition(cls, current: TaskState, target: TaskState) -> bool:
        if target == TaskState.CANCELLED:
            # Any active state can transition to CANCELLED on emergency kill
            return current not in {TaskState.DONE, TaskState.CANCELLED, TaskState.ROLLED_BACK}
        return target in cls.ALLOWED_TRANSITIONS.get(current, set())

    @classmethod
    def transition(cls, current: TaskState, target: TaskState) -> TaskState:
        if not cls.can_transition(current, target):
            raise InvalidStateTransitionError(
                f"Cannot transition task from '{current.value}' to '{target.value}'."
            )
        logger.debug("Task state transitioned: %s -> %s", current.value, target.value)
        return target
