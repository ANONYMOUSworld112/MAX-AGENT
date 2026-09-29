"""Priority Task Queue with Starvation Aging and Backpressure.

Deterministic scheduling across Priority Bands 0–4:
- Band 0 (Critical)
- Band 1 (Interactive)
- Band 2 (Workflow)
- Band 3 (Background)
- Band 4 (Maintenance)

Prevents low-priority starvation by calculating dynamic effective priority based on wait time.
"""

from __future__ import annotations

import heapq
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("max.infra.task_queue")


class QueueBackpressureError(Exception):
    """Raised when the task queue is at maximum capacity."""
    pass


@dataclass
class TaskItem:
    task_id: str
    priority_band: int = 2
    created_at: float = field(default_factory=time.time)
    payload: Dict[str, Any] = field(default_factory=dict)
    agent_name: str = ""

    def effective_priority(self, aging_threshold_seconds: float = 30.0) -> int:
        now = time.time()
        age = max(0.0, now - self.created_at)
        promotions = int(age // aging_threshold_seconds)
        return max(0, self.priority_band - promotions)

    def __lt__(self, other: TaskItem) -> bool:
        # Default fallback comparison by base priority and created_at
        if self.priority_band == other.priority_band:
            return self.created_at < other.created_at
        return self.priority_band < other.priority_band


class TaskQueue:
    def __init__(
        self,
        max_capacity: int = 500,
        aging_threshold_seconds: float = 30.0,
    ) -> None:
        self.max_capacity = max_capacity
        self.aging_threshold_seconds = aging_threshold_seconds
        self._items: List[TaskItem] = []
        self._lock = threading.RLock()
        self._not_empty = threading.Condition(self._lock)

    def size(self) -> int:
        with self._lock:
            return len(self._items)

    def peek(self) -> Optional[TaskItem]:
        with self._lock:
            return self._items[0] if self._items else None

    def enqueue(self, task: TaskItem) -> None:
        with self._lock:
            if len(self._items) >= self.max_capacity:
                raise QueueBackpressureError(
                    f"Queue backpressure reached max capacity ({self.max_capacity} tasks)"
                )
            self._items.append(task)
            self._not_empty.notify()
            logger.debug("Task %s enqueued (Band %d)", task.task_id, task.priority_band)

    def dequeue(self, timeout: Optional[float] = 1.0) -> Optional[TaskItem]:
        with self._not_empty:
            start_time = time.time()
            while not self._items:
                if timeout is not None:
                    elapsed = time.time() - start_time
                    remaining = timeout - elapsed
                    if remaining <= 0:
                        return None
                    self._not_empty.wait(timeout=remaining)
                else:
                    self._not_empty.wait()

            # Find the task with the lowest effective priority score (0 is highest priority)
            best_idx = 0
            best_effective = self._items[0].effective_priority(self.aging_threshold_seconds)
            best_created = self._items[0].created_at

            for i in range(1, len(self._items)):
                item = self._items[i]
                eff = item.effective_priority(self.aging_threshold_seconds)
                if eff < best_effective or (eff == best_effective and item.created_at < best_created):
                    best_idx = i
                    best_effective = eff
                    best_created = item.created_at

            chosen = self._items.pop(best_idx)
            logger.debug(
                "Task %s dequeued (Base Band: %d, Effective: %d)",
                chosen.task_id,
                chosen.priority_band,
                best_effective,
            )
            return chosen
