"""
MAX OS — Resource Lock Manager (Deadlock Prevention by Construction).
Principle #6: Locks acquire in sorted resource-ID order, always, all-or-nothing.
Guarantees zero deadlocks even under concurrent, reversed-order lock acquisition requests.
"""

from __future__ import annotations

import contextlib
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, Generator, List, Optional, Set


class LockAcquisitionTimeoutError(Exception):
    """Raised when sorted-order all-or-nothing lock acquisition times out."""
    pass


class ResourceLockManager:
    """
    Deterministic Resource Lock Manager.
    - Locks are sorted by resource identifier before acquisition.
    - All-or-nothing semantics: if any resource cannot be acquired, all acquired locks are released.
    - No LLM call inside this component (Principle #3).
    """

    def __init__(self, default_timeout: float = 5.0):
        self.default_timeout = default_timeout
        self._global_lock = threading.Lock()
        self._resource_locks: Dict[str, threading.Lock] = {}
        self._lock_holders: Dict[str, str] = {}  # resource_id -> task_id

    def _get_or_create_lock(self, resource_id: str) -> threading.Lock:
        with self._global_lock:
            if resource_id not in self._resource_locks:
                self._resource_locks[resource_id] = threading.Lock()
            return self._resource_locks[resource_id]

    def acquire_locks(
        self,
        task_id: str,
        resource_ids: List[str],
        timeout: Optional[float] = None,
    ) -> List[str]:
        """
        Acquires locks for all resource_ids in strict sorted order.
        If acquisition of any lock fails within timeout, releases all acquired locks
        in reverse order and raises LockAcquisitionTimeoutError.
        """
        if not resource_ids:
            return []

        # 1. Deduplicate and sort resource IDs (Deadlock Prevention Algorithm)
        sorted_resources = sorted(set(resource_ids))
        effective_timeout = timeout if timeout is not None else self.default_timeout
        deadline = time.monotonic() + effective_timeout

        acquired_locks: List[tuple[str, threading.Lock]] = []

        for res_id in sorted_resources:
            lock = self._get_or_create_lock(res_id)
            remaining_time = max(0.001, deadline - time.monotonic())

            # Attempt to acquire single lock before deadline
            acquired = lock.acquire(timeout=remaining_time)
            if not acquired:
                # All-or-nothing failure: rollback all acquired locks in reverse order
                self._rollback_acquired(task_id, acquired_locks)
                raise LockAcquisitionTimeoutError(
                    f"Task {task_id} timed out waiting for resource lock: {res_id}. "
                    f"Released all partially acquired locks."
                )

            with self._global_lock:
                self._lock_holders[res_id] = task_id
            acquired_locks.append((res_id, lock))

        return sorted_resources

    def _rollback_acquired(
        self, task_id: str, acquired_locks: List[tuple[str, threading.Lock]]
    ) -> None:
        """Releases acquired locks in reverse order."""
        for res_id, lock in reversed(acquired_locks):
            with self._global_lock:
                if self._lock_holders.get(res_id) == task_id:
                    del self._lock_holders[res_id]
            try:
                lock.release()
            except RuntimeError:
                pass

    def release_locks(self, task_id: str, resource_ids: List[str]) -> None:
        """Releases all locks held by task_id for specified resource_ids."""
        sorted_resources = sorted(set(resource_ids), reverse=True)
        for res_id in sorted_resources:
            with self._global_lock:
                holder = self._lock_holders.get(res_id)
                if holder != task_id:
                    continue
                del self._lock_holders[res_id]
                lock = self._resource_locks.get(res_id)

            if lock is not None:
                try:
                    lock.release()
                except RuntimeError:
                    pass

    @contextlib.contextmanager
    def locked(
        self,
        task_id: str,
        resource_ids: List[str],
        timeout: Optional[float] = None,
    ) -> Generator[List[str], None, None]:
        """Context manager for acquiring and safely releasing sorted-order locks."""
        acquired = self.acquire_locks(task_id, resource_ids, timeout=timeout)
        try:
            yield acquired
        finally:
            self.release_locks(task_id, acquired)

    def is_locked(self, resource_id: str) -> bool:
        """Checks if a resource is currently locked."""
        with self._global_lock:
            return resource_id in self._lock_holders

    def get_holder(self, resource_id: str) -> Optional[str]:
        """Returns the task_id holding the lock on resource_id, if any."""
        with self._global_lock:
            return self._lock_holders.get(resource_id)
