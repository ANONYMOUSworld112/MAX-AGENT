"""
MAX OS — Task State Machine & Idempotency Key Engine.
Implements the task lifecycle: CREATED -> QUEUED -> RUNNING -> RECONCILING -> DONE (or FAILED / ROLLED_BACK).
Every state transition is persisted in SQLite `task_trace` table.
"""

from __future__ import annotations

import enum
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional

DEFAULT_DB_PATH = Path(__file__).parent.parent / "max_state.db"


class TaskState(str, enum.Enum):
    CREATED = "CREATED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    RECONCILING = "RECONCILING"
    DONE = "DONE"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"


# Allowed state transitions
VALID_TRANSITIONS = {
    TaskState.CREATED: {TaskState.QUEUED, TaskState.RUNNING, TaskState.FAILED},
    TaskState.QUEUED: {TaskState.RUNNING, TaskState.FAILED, TaskState.ROLLED_BACK},
    TaskState.RUNNING: {TaskState.RECONCILING, TaskState.FAILED, TaskState.ROLLED_BACK, TaskState.DONE},
    TaskState.RECONCILING: {TaskState.DONE, TaskState.FAILED, TaskState.ROLLED_BACK},
    TaskState.FAILED: {TaskState.ROLLED_BACK, TaskState.QUEUED},  # can retry by re-queuing
    TaskState.ROLLED_BACK: {TaskState.QUEUED},  # can retry by re-queuing
    TaskState.DONE: set(),  # terminal
}


class InvalidStateTransitionError(Exception):
    """Raised when an illegal task state transition is attempted."""
    pass


class DuplicateIdempotencyKeyError(Exception):
    """Raised when attempting to execute a task with an already completed or running idempotency key."""
    pass


@dataclass
class Task:
    task_id: str
    idempotency_key: str
    agent: str
    intent: str
    input_summary: str
    priority_band: int = 1
    state: TaskState = TaskState.CREATED
    error_class: Optional[str] = None
    attempt_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None
    duration_ms: Optional[int] = None
    result_summary: Optional[str] = None
    _start_monotonic: Optional[float] = field(default=None, repr=False)
    _db_path: Path = field(default_factory=lambda: DEFAULT_DB_PATH, repr=False)

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.row_factory = sqlite3.Row
        return conn

    def _persist(self, conn: Optional[sqlite3.Connection] = None) -> None:
        close_conn = False
        if conn is None:
            conn = self._get_conn()
            close_conn = True

        try:
            conn.execute(
                """
                INSERT INTO task_trace (
                    task_id, idempotency_key, agent, intent, input_summary,
                    priority_band, state, error_class, attempt_count,
                    created_at, completed_at, duration_ms, result_summary
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(task_id) DO UPDATE SET
                    state = excluded.state,
                    error_class = excluded.error_class,
                    attempt_count = excluded.attempt_count,
                    completed_at = excluded.completed_at,
                    duration_ms = excluded.duration_ms,
                    result_summary = excluded.result_summary;
                """,
                (
                    self.task_id,
                    self.idempotency_key,
                    self.agent,
                    self.intent,
                    self.input_summary,
                    self.priority_band,
                    self.state.value if isinstance(self.state, TaskState) else self.state,
                    self.error_class,
                    self.attempt_count,
                    self.created_at,
                    self.completed_at,
                    self.duration_ms,
                    self.result_summary,
                ),
            )
            conn.commit()
        finally:
            if close_conn:
                conn.close()

    def transition_to(
        self,
        new_state: TaskState,
        error_class: Optional[str] = None,
        result_summary: Optional[str] = None,
    ) -> None:
        """Transitions the task to a new state if valid, recording timestamps and updating task_trace."""
        if isinstance(new_state, str):
            new_state = TaskState(new_state)

        if new_state not in VALID_TRANSITIONS.get(self.state, set()):
            raise InvalidStateTransitionError(
                f"Cannot transition task {self.task_id} from {self.state} to {new_state}"
            )

        if new_state == TaskState.RUNNING:
            self.attempt_count += 1
            if self._start_monotonic is None:
                self._start_monotonic = time.monotonic()

        self.state = new_state
        if error_class is not None:
            self.error_class = error_class
        if result_summary is not None:
            self.result_summary = result_summary

        # If terminal state reached, record completed_at and duration_ms
        if new_state in {TaskState.DONE, TaskState.FAILED, TaskState.ROLLED_BACK}:
            self.completed_at = datetime.now(timezone.utc).isoformat()
            if self._start_monotonic is not None:
                self.duration_ms = int((time.monotonic() - self._start_monotonic) * 1000)

        self._persist()


class TaskManager:
    """Manages creation, idempotency tracking, and lookup of tasks."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.row_factory = sqlite3.Row
        return conn

    def get_task_by_idempotency_key(self, idempotency_key: str) -> Optional[Task]:
        """Looks up existing task by idempotency key."""
        conn = self._get_conn()
        try:
            cur = conn.execute(
                "SELECT * FROM task_trace WHERE idempotency_key = ? ORDER BY created_at DESC LIMIT 1",
                (idempotency_key,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return self._row_to_task(row)
        finally:
            conn.close()

    def get_task(self, task_id: str) -> Optional[Task]:
        """Looks up task by task_id."""
        conn = self._get_conn()
        try:
            cur = conn.execute("SELECT * FROM task_trace WHERE task_id = ?", (task_id,))
            row = cur.fetchone()
            if not row:
                return None
            return self._row_to_task(row)
        finally:
            conn.close()

    def create_task(
        self,
        agent: str,
        intent: str,
        input_summary: str,
        priority_band: int = 1,
        idempotency_key: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> Task:
        """
        Creates a new task in CREATED state and persists it to task_trace.
        If an idempotency_key is provided and already exists with DONE state,
        it can either be retrieved or flagged depending on caller needs.
        """
        final_id = task_id or str(uuid.uuid4())
        final_idem = idempotency_key or str(uuid.uuid4())

        task = Task(
            task_id=final_id,
            idempotency_key=final_idem,
            agent=agent,
            intent=intent,
            input_summary=input_summary,
            priority_band=priority_band,
            state=TaskState.CREATED,
            _db_path=self.db_path,
        )
        task._persist()
        return task

    def execute_idempotent(
        self,
        idempotency_key: str,
        agent: str,
        intent: str,
        input_summary: str,
        side_effect_fn: Callable[[Task], Any],
        priority_band: int = 1,
    ) -> tuple[Task, Any, bool]:
        """
        Executes an action with an idempotency key guarantee.
        Returns (task, result, was_executed):
        - If task with this idempotency_key is already DONE, returns (existing_task, existing_task.result_summary, False).
        - Otherwise runs side_effect_fn inside standard lifecycle:
          CREATED -> QUEUED -> RUNNING -> RECONCILING -> DONE (or FAILED / ROLLED_BACK on error).
        """
        existing = self.get_task_by_idempotency_key(idempotency_key)
        if existing and existing.state == TaskState.DONE:
            return existing, existing.result_summary, False

        if existing and existing.state in {TaskState.RUNNING, TaskState.RECONCILING}:
            raise DuplicateIdempotencyKeyError(
                f"Task with idempotency key {idempotency_key} is currently {existing.state.value}"
            )

        task = self.create_task(
            agent=agent,
            intent=intent,
            input_summary=input_summary,
            priority_band=priority_band,
            idempotency_key=idempotency_key,
        )

        task.transition_to(TaskState.QUEUED)
        task.transition_to(TaskState.RUNNING)

        try:
            res = side_effect_fn(task)
            task.transition_to(TaskState.RECONCILING)
            result_str = str(res) if res is not None else "Success"
            task.transition_to(TaskState.DONE, result_summary=result_str)
            return task, res, True
        except Exception as e:
            task.transition_to(
                TaskState.FAILED,
                error_class=getattr(e, "error_class", "systemic"),
                result_summary=str(e),
            )
            raise

    def _row_to_task(self, row: sqlite3.Row) -> Task:
        t = Task(
            task_id=row["task_id"],
            idempotency_key=row["idempotency_key"],
            agent=row["agent"],
            intent=row["intent"],
            input_summary=row["input_summary"],
            priority_band=row["priority_band"],
            state=TaskState(row["state"]),
            error_class=row["error_class"],
            attempt_count=row["attempt_count"],
            created_at=row["created_at"],
            completed_at=row["completed_at"],
            duration_ms=row["duration_ms"],
            result_summary=row["result_summary"],
            _db_path=self.db_path,
        )
        return t
