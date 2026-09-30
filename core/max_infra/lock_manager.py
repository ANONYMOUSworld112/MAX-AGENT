"""Deadlock-Free Sorted Resource Lock Manager.

Eliminates circular-wait deadlocks mathematically via Dijkstra's Resource Ordering Principle:
All resource IDs are normalized, sorted lexicographically, and acquired in that strict order.
Each lock has an automatic TTL to ensure orphaned tasks cannot hold locks indefinitely.

Supports:
- Canonical resource catalog (desktop-input, audio-out, gpu-vram, system-settings, project:<path>, file:<path>)
- Lock modes (EXCLUSIVE, SHARED)
- Lease renewals and heartbeats
- Injectable Clock for deterministic simulation
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from enum import Enum
import logging
import os
import threading
import time
from typing import Any, Dict, Iterator, List, Optional, Set, Tuple, Union

logger = logging.getLogger("max.infra.lock_manager")


class LockMode(str, Enum):
    """Access mode for resource locks."""
    EXCLUSIVE = "EXCLUSIVE"
    SHARED = "SHARED"


# Canonical Resource Catalog
RESOURCE_DESKTOP_INPUT = "desktop-input"       # EXCLUSIVE
RESOURCE_AUDIO_OUT = "audio-out"               # EXCLUSIVE
RESOURCE_SYSTEM_SETTINGS = "system-settings"   # EXCLUSIVE
RESOURCE_GPU_VRAM = "gpu-vram"                 # SHARED


def canonical_project_resource(path: str) -> str:
    """Canonical identifier for a project workspace resource."""
    clean_path = os.path.abspath(path).lower().replace("\\", "/")
    return f"project:{clean_path}"


def canonical_file_resource(path: str) -> str:
    """Canonical identifier for a specific file resource."""
    clean_path = os.path.abspath(path).lower().replace("\\", "/")
    return f"file:{clean_path}"


@dataclass(frozen=True)
class ResourceRequest:
    """Request for a specific resource with designated lock mode."""
    resource_id: str
    mode: LockMode = LockMode.EXCLUSIVE

    @classmethod
    def from_any(cls, item: Union[str, Tuple[str, LockMode], ResourceRequest]) -> ResourceRequest:
        if isinstance(item, ResourceRequest):
            return item
        if isinstance(item, tuple):
            return cls(resource_id=item[0].strip(), mode=item[1])
        return cls(resource_id=item.strip(), mode=LockMode.EXCLUSIVE)


class LockTimeoutError(Exception):
    """Raised when acquiring one or more resource locks times out."""
    pass


class _ResourceLockEntry:
    def __init__(self, mode: LockMode) -> None:
        self.mode = mode
        # task_id -> expires_at
        self.holders: Dict[str, float] = {}

    def is_empty(self) -> bool:
        return len(self.holders) == 0


class LockManager:
    def __init__(self, default_ttl: float = 60.0, clock: Optional[Any] = None) -> None:
        self.default_ttl = default_ttl
        self.clock = clock
        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)
        # resource_id -> _ResourceLockEntry
        self._held_entries: Dict[str, _ResourceLockEntry] = {}

    def _now(self) -> float:
        if self.clock is not None:
            if hasattr(self.clock, "now"):
                return self.clock.now().timestamp()
            if hasattr(self.clock, "monotonic"):
                return self.clock.monotonic()
        return time.time()

    def _cleanup_expired(self) -> None:
        now = self._now()
        released = False
        empty_resources = []

        for res, entry in self._held_entries.items():
            expired_tasks = [task_id for task_id, exp in entry.holders.items() if exp <= now]
            for task_id in expired_tasks:
                entry.holders.pop(task_id, None)
                logger.warning(
                    "Resource lock '%s' held by '%s' (mode=%s) expired and was reclaimed.",
                    res, task_id, entry.mode.value
                )
                released = True
            if entry.is_empty():
                empty_resources.append(res)

        for res in empty_resources:
            self._held_entries.pop(res, None)

        if released:
            self._condition.notify_all()

    def is_locked(self, resource_id: str) -> bool:
        with self._lock:
            self._cleanup_expired()
            canonical = resource_id.strip()
            return canonical in self._held_entries and not self._held_entries[canonical].is_empty()

    def get_holder(self, resource_id: str) -> Optional[str]:
        with self._lock:
            self._cleanup_expired()
            canonical = resource_id.strip()
            entry = self._held_entries.get(canonical)
            if entry and entry.holders:
                return next(iter(entry.holders.keys()))
            return None

    def get_holders(self, resource_id: str) -> List[str]:
        with self._lock:
            self._cleanup_expired()
            canonical = resource_id.strip()
            entry = self._held_entries.get(canonical)
            if entry:
                return list(entry.holders.keys())
            return []

    def get_lock_mode(self, resource_id: str) -> Optional[LockMode]:
        with self._lock:
            self._cleanup_expired()
            canonical = resource_id.strip()
            entry = self._held_entries.get(canonical)
            return entry.mode if entry and not entry.is_empty() else None

    def renew_lease(
        self,
        resource_id: str,
        task_id: str,
        additional_ttl: Optional[float] = None,
    ) -> bool:
        """Extends expiration time for a resource currently held by task_id."""
        with self._condition:
            self._cleanup_expired()
            canonical = resource_id.strip()
            entry = self._held_entries.get(canonical)
            if entry and task_id in entry.holders:
                ttl = additional_ttl if additional_ttl is not None else self.default_ttl
                entry.holders[task_id] = self._now() + ttl
                logger.debug("Renewed lock lease on '%s' for task '%s' (TTL: %ss)", canonical, task_id, ttl)
                return True
            return False

    def heartbeat(
        self,
        task_id: str,
        additional_ttl: Optional[float] = None,
    ) -> List[str]:
        """Extends expiration for all resource locks currently held by task_id."""
        with self._condition:
            self._cleanup_expired()
            renewed = []
            ttl = additional_ttl if additional_ttl is not None else self.default_ttl
            new_exp = self._now() + ttl
            for res, entry in self._held_entries.items():
                if task_id in entry.holders:
                    entry.holders[task_id] = new_exp
                    renewed.append(res)
            if renewed:
                logger.debug("Heartbeat extended locks for task '%s' on: %s", task_id, renewed)
            return renewed

    def release(self, resource_id: str, task_id: str) -> bool:
        """Explicitly release a resource lock held by task_id."""
        with self._condition:
            canonical = resource_id.strip()
            entry = self._held_entries.get(canonical)
            if entry and task_id in entry.holders:
                entry.holders.pop(task_id, None)
                if entry.is_empty():
                    self._held_entries.pop(canonical, None)
                self._condition.notify_all()
                logger.debug("Task '%s' explicitly released lock on '%s'", task_id, canonical)
                return True
            return False

    def release_all(self, task_id: str) -> List[str]:
        """Release all resource locks held by task_id."""
        with self._condition:
            released = []
            for res, entry in list(self._held_entries.items()):
                if task_id in entry.holders:
                    entry.holders.pop(task_id, None)
                    released.append(res)
                    if entry.is_empty():
                        self._held_entries.pop(res, None)
            if released:
                self._condition.notify_all()
                logger.debug("Task '%s' released all locks on: %s", task_id, released)
            return released

    @contextlib.contextmanager
    def acquire(
        self,
        resources: List[Union[str, Tuple[str, LockMode], ResourceRequest]],
        task_id: str,
        timeout: float = 5.0,
        ttl: Optional[float] = None,
    ) -> Iterator[List[str]]:
        """
        Acquires all requested resources in sorted order or raises LockTimeoutError.

        Guarantees:
        1. Dijkstra Canonical Sort: requests are sorted lexicographically by resource ID.
        2. Reader/Writer correctness: EXCLUSIVE locks require zero other holders.
           SHARED locks permit concurrent SHARED holders.
        3. Automatic rollback: if any acquisition fails or times out, all partially
           acquired locks for this task in this context are cleanly released.
        """
        if not resources:
            yield []
            return

        # Normalize and deduplicate requests
        req_map: Dict[str, LockMode] = {}
        for r in resources:
            parsed = ResourceRequest.from_any(r)
            rid = parsed.resource_id
            if rid not in req_map:
                req_map[rid] = parsed.mode
            else:
                # If requested multiple times, elevate to EXCLUSIVE if either requested it
                if parsed.mode == LockMode.EXCLUSIVE:
                    req_map[rid] = LockMode.EXCLUSIVE

        # Dijkstra resource ordering: sort strictly ascending
        sorted_requests = [ResourceRequest(rid, req_map[rid]) for rid in sorted(req_map.keys())]
        effective_ttl = ttl if ttl is not None else self.default_ttl
        start_time = self._now()
        deadline = start_time + timeout
        acquired: List[str] = []

        try:
            with self._condition:
                for req in sorted_requests:
                    res_id = req.resource_id
                    req_mode = req.mode

                    while True:
                        self._cleanup_expired()
                        now = self._now()
                        entry = self._held_entries.get(res_id)

                        can_acquire = False
                        if entry is None or entry.is_empty():
                            # Free resource
                            can_acquire = True
                        elif req_mode == LockMode.SHARED and entry.mode == LockMode.SHARED:
                            # Concurrent shared readers permitted
                            can_acquire = True
                        elif task_id in entry.holders and len(entry.holders) == 1:
                            # Re-entrant acquisition by the same task
                            can_acquire = True

                        if can_acquire:
                            if entry is None:
                                entry = _ResourceLockEntry(mode=req_mode)
                                self._held_entries[res_id] = entry
                            elif entry.is_empty():
                                entry.mode = req_mode

                            entry.holders[task_id] = now + effective_ttl
                            acquired.append(res_id)
                            logger.debug(
                                "Task '%s' acquired lock on '%s' (mode=%s, TTL=%ss)",
                                task_id, res_id, req_mode.value, effective_ttl
                            )
                            break

                        remaining = deadline - now
                        if remaining <= 0:
                            # Roll back all acquired locks in this context
                            for r in acquired:
                                ent = self._held_entries.get(r)
                                if ent:
                                    ent.holders.pop(task_id, None)
                                    if ent.is_empty():
                                        self._held_entries.pop(r, None)
                            self._condition.notify_all()
                            holder_names = list(entry.holders.keys()) if entry else ["unknown"]
                            raise LockTimeoutError(
                                f"Task '{task_id}' timed out waiting for lock '{res_id}' "
                                f"held by {holder_names} (requested {req_mode.value}, held {entry.mode.value if entry else 'NONE'})"
                            )

                        # Wait for lock release or expiration notification
                        self._condition.wait(timeout=max(0.01, min(0.05, remaining)))

            yield acquired

        finally:
            with self._condition:
                for res_id in reversed(acquired):
                    entry = self._held_entries.get(res_id)
                    if entry and task_id in entry.holders:
                        entry.holders.pop(task_id, None)
                        if entry.is_empty():
                            self._held_entries.pop(res_id, None)
                        logger.debug("Task '%s' released lock on '%s'", task_id, res_id)
                self._condition.notify_all()
