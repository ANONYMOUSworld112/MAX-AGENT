"""Watchdog Daemon for Heartbeat Monitoring and Orphan Task Reclamation.

Runs a lightweight background thread every `check_interval` seconds.
Monitors task heartbeats and invokes callback or aborts tasks if their deadline passes.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Dict, Optional

logger = logging.getLogger("max.infra.watchdog")


class Watchdog:
    def __init__(
        self,
        check_interval: float = 0.5,
        timeout_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.check_interval = check_interval
        self.timeout_callback = timeout_callback
        self._lock = threading.RLock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        # task_id -> (last_ping, timeout_seconds)
        self._tasks: Dict[str, tuple[float, float]] = {}

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(target=self._loop, daemon=True, name="MaxWatchdog")
            self._thread.start()
            logger.info("Watchdog started with check interval %.2fs", self.check_interval)

    def stop(self) -> None:
        with self._lock:
            self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        logger.info("Watchdog stopped.")

    def register_heartbeat(self, task_id: str, timeout_seconds: float = 30.0) -> None:
        with self._lock:
            self._tasks[task_id] = (time.time(), timeout_seconds)
            logger.debug("Registered heartbeat for task '%s' (timeout: %.1fs)", task_id, timeout_seconds)

    def ping(self, task_id: str) -> None:
        with self._lock:
            if task_id in self._tasks:
                _, timeout = self._tasks[task_id]
                self._tasks[task_id] = (time.time(), timeout)

    def unregister(self, task_id: str) -> None:
        with self._lock:
            self._tasks.pop(task_id, None)

    def _loop(self) -> None:
        while self._running:
            now = time.time()
            timed_out = []

            with self._lock:
                for task_id, (last_ping, timeout) in list(self._tasks.items()):
                    if now - last_ping > timeout:
                        timed_out.append(task_id)

            for task_id in timed_out:
                self.unregister(task_id)
                logger.error("🚨 Watchdog detected TIMEOUT for task '%s'", task_id)
                if self.timeout_callback:
                    try:
                        self.timeout_callback(task_id)
                    except Exception as exc:
                        logger.error("Error in watchdog timeout callback: %s", exc)

            time.sleep(self.check_interval)
