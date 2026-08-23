"""
MAX OS - Task System
tasks/task_system.py
"""
from __future__ import annotations

import heapq
import itertools
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from core.platform.detector import RiskLevel


class AgentState(str, Enum):
    IDLE = "IDLE"
    THINKING = "THINKING"
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    WAITING = "WAITING"
    VERIFYING = "VERIFYING"
    ERROR = "ERROR"
    RECOVERING = "RECOVERING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


@dataclass
class Task:
    description: str
    agent: str
    risk: RiskLevel
    priority: int = 5  # lower = higher priority
    depends_on: List[str] = field(default_factory=list)
    timeout_seconds: Optional[float] = None
    max_retries: int = 2
    retries_used: int = 0
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    state: AgentState = AgentState.IDLE
    created_at: float = field(default_factory=time.time)
    result: Any = None
    error: Optional[str] = None


class TaskQueue:
    """
    Priority queue with dependency gating. A task only becomes eligible for
    execution once every task in depends_on has reached COMPLETED.
    """

    def __init__(self) -> None:
        self._heap: List[tuple] = []
        self._counter = itertools.count()
        self._tasks: Dict[str, Task] = {}

    def add(self, task: Task) -> str:
        self._tasks[task.id] = task
        heapq.heappush(self._heap, (task.priority, next(self._counter), task.id))
        return task.id

    def _is_eligible(self, task: Task) -> bool:
        return all(
            self._tasks.get(dep_id) is not None
            and self._tasks[dep_id].state == AgentState.COMPLETED
            for dep_id in task.depends_on
        )

    def pop_next_eligible(self) -> Optional[Task]:
        deferred = []
        result = None
        while self._heap:
            _, _, task_id = heapq.heappop(self._heap)
            task = self._tasks[task_id]
            if task.state != AgentState.IDLE:
                continue  # already handled/cancelled
            if self._is_eligible(task):
                result = task
                break
            deferred.append((task.priority, next(self._counter), task_id))
        for item in deferred:
            heapq.heappush(self._heap, item)
        return result

    def get(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)

    def cancel(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if task is None or task.state in (AgentState.COMPLETED, AgentState.CANCELLED):
            return False
        task.state = AgentState.CANCELLED
        return True

    def history(self) -> List[Task]:
        return list(self._tasks.values())


AgentExecutor = Callable[[Task], Any]
"""An agent's run function: takes a Task, returns a result or raises."""
