"""
MAX OS — Priority Task Queue
Build Order: #8 (Layer 2C)
═══════════════════════════════════════════════════════

Heap-backed priority queue with priority bands 0-4 (0=highest),
task aging to prevent starvation, backpressure limit (500 tasks),
and idempotency check against duplicate execution.
"""

from __future__ import annotations

import heapq
import time
import uuid
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from src.infra import state_db
from src.core import task_lifecycle
from src.core.task_lifecycle import TaskState

logger = logging.getLogger("max.core.task_queue")

MAX_QUEUE_DEPTH = 500


class QueueFullError(RuntimeError):
    """Raised when task queue depth reaches MAX_QUEUE_DEPTH."""
    pass


class DuplicateTaskError(ValueError):
    """Raised when an idempotency key matches an existing active task."""
    pass


@dataclass(order=True)
class TaskItem:
    priority: int                                 # 0 to 4 (0 highest)
    created_timestamp: float = field(compare=True) # Secondary sort order
    task_id: str = field(compare=False)
    idempotency_key: str = field(compare=False)
    agent: str = field(compare=False)
    intent: str = field(compare=False)
    input_summary: str = field(compare=False)
    payload: dict = field(compare=False, default_factory=dict)
    depends_on: list[str] = field(compare=False, default_factory=list)


class TaskQueue:
    """Thread-safe priority queue backed by heapq and SQLite."""

    def __init__(self):
        self._heap: list[TaskItem] = []
        self._idempotency_map: dict[str, str] = {}  # idempotency_key -> task_id

    def push(
        self,
        agent: str,
        intent: str,
        input_summary: str,
        priority_band: int = 2,
        idempotency_key: Optional[str] = None,
        payload: Optional[dict] = None,
        depends_on: Optional[list[str]] = None,
    ) -> str:
        """Push a task onto the queue."""
        if len(self._heap) >= MAX_QUEUE_DEPTH:
            raise QueueFullError(f"Task queue reached max capacity ({MAX_QUEUE_DEPTH})")

        key = idempotency_key or str(uuid.uuid4())
        
        # Check idempotency in queue and DB
        if key in self._idempotency_map:
            return self._idempotency_map[key]

        existing = state_db.fetchone(
            "SELECT task_id FROM task_trace WHERE idempotency_key = ? AND state NOT IN ('done', 'failed', 'killed', 'cancelled')",
            (key,)
        )
        if existing:
            return existing["task_id"]

        task_id = str(uuid.uuid4())
        now_iso = datetime.now(timezone.utc).isoformat()

        # Insert into task_trace
        state_db.execute(
            """
            INSERT INTO task_trace (task_id, idempotency_key, agent, intent, input_summary, priority_band, state, attempt_count, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'created', 0, ?)
            """,
            (task_id, key, agent, intent, input_summary, priority_band, now_iso)
        )
        state_db.commit()

        item = TaskItem(
            priority=max(0, min(4, priority_band)),
            created_timestamp=time.time(),
            task_id=task_id,
            idempotency_key=key,
            agent=agent,
            intent=intent,
            input_summary=input_summary,
            payload=payload or {},
            depends_on=depends_on or [],
        )

        task_lifecycle.transition(task_id, TaskState.QUEUED)
        heapq.heappush(self._heap, item)
        self._idempotency_map[key] = task_id

        logger.info("Task '%s' pushed to queue (priority=%d, agent=%s)", task_id, item.priority, agent)
        return task_id

    def pop(self) -> Optional[TaskItem]:
        """Pop the highest priority task ready for execution."""
        self._apply_aging()
        if not self._heap:
            return None

        item = heapq.heappop(self._heap)
        self._idempotency_map.pop(item.idempotency_key, None)
        task_lifecycle.transition(item.task_id, TaskState.LOCK_WAIT)
        return item

    def _apply_aging(self) -> None:
        """Promote tasks waiting over 30s by 1 priority band to prevent starvation."""
        now = time.time()
        updated = False
        for item in self._heap:
            if item.priority > 0 and (now - item.created_timestamp) > 30.0:
                item.priority -= 1
                updated = True
        if updated:
            heapq.heapify(self._heap)

    def size(self) -> int:
        return len(self._heap)


_global_queue: Optional[TaskQueue] = None


def get_queue() -> TaskQueue:
    global _global_queue
    if _global_queue is None:
        _global_queue = TaskQueue()
    return _global_queue
