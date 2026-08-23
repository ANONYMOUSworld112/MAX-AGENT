"""
MAX OS — Heartbeat Watchdog (Step 2.4).
Monitors task liveness via periodic heartbeats.
If a task produces no heartbeat within timeout (default 45s), the watchdog halts it
and triggers rollback to that task's snapshot boundary.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional

logger = logging.getLogger("max.watchdog")


@dataclass
class WatchedTask:
    task_id: str
    timeout_seconds: float
    last_heartbeat: float = field(default_factory=time.monotonic)
    on_timeout: Optional[Callable[[str], None]] = None
    is_active: bool = True


class HeartbeatWatchdog:
    """
    Heartbeat Watchdog Service.
    Monitors running tasks. Kills and triggers rollback for tasks that stop heartbeating.
    """

    def __init__(self, default_timeout_seconds: float = 45.0, check_interval: float = 0.05):
        self.default_timeout_seconds = default_timeout_seconds
        self.check_interval = check_interval
        self._tasks: Dict[str, WatchedTask] = {}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._monitor_thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Starts the background watchdog monitor thread."""
        with self._lock:
            if self._monitor_thread is not None and self._monitor_thread.is_alive():
                return
            self._stop_event.clear()
            self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self._monitor_thread.start()

    def stop(self) -> None:
        """Stops the background watchdog monitor thread."""
        self._stop_event.set()
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=1.0)

    def register_task(
        self,
        task_id: str,
        timeout_seconds: Optional[float] = None,
        on_timeout: Optional[Callable[[str], None]] = None,
    ) -> None:
        """Registers a task for heartbeat monitoring."""
        timeout = timeout_seconds if timeout_seconds is not None else self.default_timeout_seconds
        with self._lock:
            self._tasks[task_id] = WatchedTask(
                task_id=task_id,
                timeout_seconds=timeout,
                last_heartbeat=time.monotonic(),
                on_timeout=on_timeout,
                is_active=True,
            )

    def heartbeat(self, task_id: str) -> None:
        """Records a heartbeat for a registered task."""
        with self._lock:
            if task_id in self._tasks:
                self._tasks[task_id].last_heartbeat = time.monotonic()

    def unregister_task(self, task_id: str) -> None:
        """Unregisters a completed or stopped task."""
        with self._lock:
            if task_id in self._tasks:
                self._tasks[task_id].is_active = False
                del self._tasks[task_id]

    def _monitor_loop(self) -> None:
        while not self._stop_event.is_set():
            now = time.monotonic()
            timed_out_tasks = []

            with self._lock:
                for task_id, watched in list(self._tasks.items()):
                    if not watched.is_active:
                        continue
                    if (now - watched.last_heartbeat) > watched.timeout_seconds:
                        watched.is_active = False
                        timed_out_tasks.append((task_id, watched.on_timeout))
                        del self._tasks[task_id]

            # Fire timeout callbacks outside the lock
            for task_id, callback in timed_out_tasks:
                logger.warning(f"Task {task_id} timed out (no heartbeat). Triggering kill & rollback.")
                if callback:
                    try:
                        callback(task_id)
                    except Exception as e:
                        logger.error(f"Error in timeout callback for {task_id}: {e}")

            time.sleep(self.check_interval)
