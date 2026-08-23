"""
MAX OS — Lock Manager
Build Order: #11 (Layer 3A)
═══════════════════════════════════════════════════════

Sorted-order, all-or-nothing resource locking to prevent deadlocks.
"""

from __future__ import annotations

import time
import threading
import logging
from typing import Optional

logger = logging.getLogger("max.core.lock_manager")


class LockTimeoutError(TimeoutError):
    """Raised when resource lock acquisition times out."""
    pass


class LockManager:
    """Thread-safe resource lock manager using sorted locking order."""

    def __init__(self):
        self._locks: dict[str, threading.Lock] = {}
        self._global_lock = threading.Lock()
        self._held_locks: dict[str, set[str]] = {}  # task_id -> set of locked resource_ids

    def acquire_all(self, task_id: str, resource_ids: list[str], timeout: float = 5.0) -> bool:
        """
        Acquire locks for all resources in resource_ids in sorted lexicographical order.
        All-or-nothing: if any lock fails, releases all previously acquired locks.
        """
        if not resource_ids:
            return True

        sorted_resources = sorted(list(set(resource_ids)))
        acquired = []
        start = time.time()

        for res in sorted_resources:
            with self._global_lock:
                if res not in self._locks:
                    self._locks[res] = threading.Lock()
                lock = self._locks[res]

            remaining_time = timeout - (time.time() - start)
            if remaining_time <= 0:
                self._release_partial(acquired)
                raise LockTimeoutError(f"Task '{task_id}' timed out acquiring lock for '{res}'")

            got_it = lock.acquire(timeout=remaining_time)
            if not got_it:
                self._release_partial(acquired)
                raise LockTimeoutError(f"Task '{task_id}' failed to acquire lock for '{res}'")
            acquired.append(res)

        with self._global_lock:
            self._held_locks[task_id] = set(acquired)

        logger.debug("Task '%s' acquired locks for resources: %s", task_id, acquired)
        return True

    def release_all(self, task_id: str) -> None:
        """Release all locks held by task_id."""
        with self._global_lock:
            acquired = self._held_locks.pop(task_id, set())

        for res in acquired:
            lock = self._locks.get(res)
            if lock and lock.locked():
                try:
                    lock.release()
                except RuntimeError:
                    pass
        if acquired:
            logger.debug("Task '%s' released locks for resources: %s", task_id, list(acquired))

    def _release_partial(self, acquired: list[str]) -> None:
        for res in acquired:
            lock = self._locks.get(res)
            if lock and lock.locked():
                try:
                    lock.release()
                except RuntimeError:
                    pass


_global_lock_mgr: Optional[LockManager] = None


def get_lock_manager() -> LockManager:
    global _global_lock_mgr
    if _global_lock_mgr is None:
        _global_lock_mgr = LockManager()
    return _global_lock_mgr
