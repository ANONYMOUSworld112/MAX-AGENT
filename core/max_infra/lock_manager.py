"""Deadlock-Free Sorted Resource Lock Manager.

Eliminates circular-wait deadlocks mathematically via Dijkstra's Resource Ordering Principle:
All resource IDs are normalized, sorted lexicographically, and acquired in that strict order.
Each lock has an automatic TTL to ensure orphaned tasks cannot hold locks indefinitely.
"""

from __future__ import annotations

import contextlib
import logging
import threading
import time
from typing import Dict, Iterator, List, Optional, Set

logger = logging.getLogger("max.infra.lock_manager")


class LockTimeoutError(Exception):
    """Raised when acquiring one or more resource locks times out."""
    pass


class LockManager:
    def __init__(self, default_ttl: float = 60.0) -> None:
        self.default_ttl = default_ttl
        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)
        # resource_id -> (task_id, expires_at)
        self._held_locks: Dict[str, tuple[str, float]] = {}

    def _cleanup_expired(self) -> None:
        now = time.time()
        expired = [res for res, (_, exp) in self._held_locks.items() if exp <= now]
        for res in expired:
            owner, _ = self._held_locks.pop(res)
            logger.warning("Resource lock '%s' held by '%s' expired and was reclaimed.", res, owner)
        if expired:
            self._condition.notify_all()

    def is_locked(self, resource_id: str) -> bool:
        with self._lock:
            self._cleanup_expired()
            canonical = resource_id.strip()
            return canonical in self._held_locks

    def get_holder(self, resource_id: str) -> Optional[str]:
        with self._lock:
            self._cleanup_expired()
            canonical = resource_id.strip()
            entry = self._held_locks.get(canonical)
            return entry[0] if entry else None

    @contextlib.contextmanager
    def acquire(
        self,
        resources: List[str],
        task_id: str,
        timeout: float = 5.0,
        ttl: Optional[float] = None,
    ) -> Iterator[List[str]]:
        """Acquires all requested resources in sorted order or raises LockTimeoutError."""
        if not resources:
            yield []
            return

        # Canonical sort order eliminates deadlock
        sorted_res = sorted(list(set(r.strip() for r in resources)))
        effective_ttl = ttl if ttl is not None else self.default_ttl
        deadline = time.time() + timeout
        acquired: List[str] = []

        try:
            with self._condition:
                for res in sorted_res:
                    while True:
                        self._cleanup_expired()
                        now = time.time()
                        if res not in self._held_locks:
                            self._held_locks[res] = (task_id, now + effective_ttl)
                            acquired.append(res)
                            logger.debug("Task '%s' acquired lock on '%s'", task_id, res)
                            break

                        remaining = deadline - now
                        if remaining <= 0:
                            # Roll back any partially acquired locks for this task
                            for r in acquired:
                                self._held_locks.pop(r, None)
                            self._condition.notify_all()
                            raise LockTimeoutError(
                                f"Task '{task_id}' timed out waiting for lock '{res}' held by '{self._held_locks[res][0]}'"
                            )
                        self._condition.wait(timeout=max(0.01, min(0.05, remaining)))

            yield acquired

        finally:
            with self._condition:
                for res in reversed(acquired):
                    if self._held_locks.get(res, (None,))[0] == task_id:
                        self._held_locks.pop(res, None)
                        logger.debug("Task '%s' released lock on '%s'", task_id, res)
                self._condition.notify_all()
