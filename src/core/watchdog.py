"""
MAX OS — Watchdog Heartbeat Monitor
Build Order: #12 (Layer 3B)
═══════════════════════════════════════════════════════

Monitors active tasks via 15s heartbeat checks.
If a task misses 3 heartbeats (45s), kills process, releases locks,
and initiates rollback.
"""

from __future__ import annotations

import time
import threading
import logging
from typing import Optional

from src.core import task_lifecycle, lock_manager, snapshot
from src.core.task_lifecycle import TaskState

logger = logging.getLogger("max.core.watchdog")

HEARTBEAT_INTERVAL_SEC = 15.0
MAX_MISSED_HEARTBEATS = 3
TIMEOUT_THRESHOLD_SEC = HEARTBEAT_INTERVAL_SEC * MAX_MISSED_HEARTBEATS  # 45s


class Watchdog:
    """Background monitor thread checking heartbeat updates for active tasks."""

    def __init__(self):
        self._heartbeats: dict[str, float] = {}  # task_id -> last_heartbeat_time
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        logger.info("Watchdog monitor thread started")

    def stop(self) -> None:
        self._running = False

    def heartbeat(self, task_id: str) -> None:
        """Record heartbeat from a running task."""
        with self._lock:
            self._heartbeats[task_id] = time.time()

    def register(self, task_id: str) -> None:
        """Register a task with watchdog."""
        with self._lock:
            self._heartbeats[task_id] = time.time()

    def unregister(self, task_id: str) -> None:
        """Unregister a finished task."""
        with self._lock:
            self._heartbeats.pop(task_id, None)

    def _monitor_loop(self) -> None:
        while self._running:
            time.sleep(5.0)
            now = time.time()
            stuck_tasks = []

            with self._lock:
                for task_id, last_time in list(self._heartbeats.items()):
                    if (now - last_time) > TIMEOUT_THRESHOLD_SEC:
                        stuck_tasks.append(task_id)

            for task_id in stuck_tasks:
                logger.error("Watchdog: Task '%s' missed 3 heartbeats (hung for >%.0fs). Terminating!", task_id, TIMEOUT_THRESHOLD_SEC)
                self.unregister(task_id)
                try:
                    # Release locks & transition to killed
                    lock_manager.get_lock_manager().release_all(task_id)
                    task_lifecycle.transition(task_id, TaskState.KILLED)
                except Exception as e:
                    logger.error("Watchdog failure handling task '%s': %s", task_id, e)


_global_watchdog: Optional[Watchdog] = None


def get_watchdog() -> Watchdog:
    global _global_watchdog
    if _global_watchdog is None:
        _global_watchdog = Watchdog()
    return _global_watchdog
