"""
MAX OS — Task Lifecycle State Machine
Build Order: #7 (Layer 2B)
═══════════════════════════════════════════════════════

Manages task transitions and records event logs in SQLite.
Enforces strict transition matrix to prevent illegal state jumps.
"""

from __future__ import annotations

import logging
from enum import Enum
from datetime import datetime, timezone

from src.infra import state_db
from src.infra.errors import MaxError, ErrorClass

logger = logging.getLogger("max.core.task_lifecycle")


class TaskState(str, Enum):
    CREATED = "created"
    QUEUED = "queued"
    LOCK_WAIT = "lock_wait"
    RUNNING = "running"
    RECONCILING = "reconciling"
    DONE = "done"
    FAILED = "failed"
    KILLED = "killed"
    CANCELLED = "cancelled"


# Allowed transitions map: current_state -> set of valid next states
_VALID_TRANSITIONS: dict[TaskState, set[TaskState]] = {
    TaskState.CREATED: {TaskState.QUEUED, TaskState.CANCELLED, TaskState.FAILED},
    TaskState.QUEUED: {TaskState.LOCK_WAIT, TaskState.CANCELLED, TaskState.KILLED},
    TaskState.LOCK_WAIT: {TaskState.RUNNING, TaskState.CANCELLED, TaskState.KILLED, TaskState.FAILED},
    TaskState.RUNNING: {TaskState.RECONCILING, TaskState.FAILED, TaskState.KILLED, TaskState.CANCELLED},
    TaskState.RECONCILING: {TaskState.DONE, TaskState.FAILED, TaskState.KILLED},
    TaskState.DONE: set(),
    TaskState.FAILED: {TaskState.QUEUED},  # For retries
    TaskState.KILLED: set(),
    TaskState.CANCELLED: set(),
}


class InvalidStateTransitionError(ValueError):
    """Raised when an illegal state transition is attempted."""
    pass


def transition(
    task_id: str,
    target_state: TaskState | str,
    error: MaxError | None = None,
    result_summary: str | None = None,
) -> TaskState:
    """
    Transition a task from its current state to target_state.
    Validates state machine rules and records event trace in SQLite.
    """
    if isinstance(target_state, str):
        target_state = TaskState(target_state)

    conn = state_db.get_connection()
    row = state_db.fetchone("SELECT state FROM task_trace WHERE task_id = ?", (task_id,))
    if not row:
        raise ValueError(f"Task ID '{task_id}' not found in task_trace")

    current_state = TaskState(row["state"])

    # Validate transition
    if target_state not in _VALID_TRANSITIONS[current_state]:
        raise InvalidStateTransitionError(
            f"Cannot transition task '{task_id}' from '{current_state.value}' to '{target_state.value}'. "
            f"Allowed next states: {[s.value for s in _VALID_TRANSITIONS[current_state]]}"
        )

    now = datetime.now(timezone.utc).isoformat()
    err_class = error.error_class.value if error else None

    if target_state in (TaskState.DONE, TaskState.FAILED, TaskState.KILLED, TaskState.CANCELLED):
        conn.execute(
            """
            UPDATE task_trace
            SET state = ?, completed_at = ?, error_class = ?, result_summary = ?
            WHERE task_id = ?
            """,
            (target_state.value, now, err_class, result_summary, task_id)
        )
    else:
        conn.execute(
            "UPDATE task_trace SET state = ?, error_class = ? WHERE task_id = ?",
            (target_state.value, err_class, task_id)
        )

    conn.commit()
    logger.info("Task '%s' transitioned: %s ➔ %s", task_id, current_state.value, target_state.value)
    return target_state
