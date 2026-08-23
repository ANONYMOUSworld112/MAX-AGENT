"""
MAX OS — Resource Manager (Section 21)
core/resource_manager.py

Coordinates exclusive and shared access across system resources:
- Physical Hardware: keyboard, mouse, microphone, camera, GPU
- Automation Subsystems: browser sessions, terminal sessions, filesystem paths, model instances
Integrates with InputArbiter, ResourceLockManager, Watchdog, and Emergency Kill Switch.
"""

from __future__ import annotations

import contextlib
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Generator, List, Optional, Set

from core.input_arbiter import InputArbiter, OwnershipLease
from core.kill_switch import get_kill_switch, require_armed
from core.lock_manager import ResourceLockManager


@dataclass
class ResourceLease:
    lease_id: str
    resource_id: str
    owner_task_id: str
    is_exclusive: bool
    acquired_at: float
    is_active: bool = True


class ResourceManager:
    """
    Centralized Resource Manager for MAX OS.
    Manages physical devices, interactive sessions, and compute resources.
    """

    _instance: Optional[ResourceManager] = None
    _singleton_lock = threading.Lock()

    def __init__(self):
        self.lock_manager = ResourceLockManager()
        self.input_arbiter = InputArbiter.get_instance()
        self.kill_switch = get_kill_switch()
        self._active_leases: Dict[str, ResourceLease] = {}
        self._lease_lock = threading.Lock()

        # Register Kill Switch revocation callback
        self.kill_switch.register_callback(self.revoke_all_leases)

    @classmethod
    def get_instance(cls) -> ResourceManager:
        with cls._singleton_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def acquire_resource(
        self,
        task_id: str,
        resource_id: str,
        is_exclusive: bool = True,
        timeout: Optional[float] = 10.0,
    ) -> ResourceLease:
        """
        Acquires lease on specified resource.
        For physical input (keyboard/mouse), delegates through InputArbiter.
        """
        require_armed(self.kill_switch)

        # Handle physical input arbitration
        if resource_id in ("keyboard", "mouse", "physical_input"):
            input_lease = self.input_arbiter.request_ownership(agent_id=task_id, timeout=timeout)
            lease = ResourceLease(
                lease_id=input_lease.lease_id,
                resource_id=resource_id,
                owner_task_id=task_id,
                is_exclusive=True,
                acquired_at=input_lease.acquired_at,
                is_active=True,
            )
        else:
            # Handle general sorted resource locking
            self.lock_manager.acquire_locks(task_id, [resource_id], timeout=timeout)
            import uuid
            lease = ResourceLease(
                lease_id=f"lease_{uuid.uuid4().hex[:8]}",
                resource_id=resource_id,
                owner_task_id=task_id,
                is_exclusive=is_exclusive,
                acquired_at=time.time(),
                is_active=True,
            )

        with self._lease_lock:
            self._active_leases[lease.lease_id] = lease

        return lease

    def release_resource(self, lease: ResourceLease) -> None:
        """Releases acquired resource lease."""
        with self._lease_lock:
            if lease.lease_id in self._active_leases:
                lease.is_active = False
                del self._active_leases[lease.lease_id]

        if lease.resource_id in ("keyboard", "mouse", "physical_input"):
            # Construct dummy OwnershipLease to match arbiter release signature
            dummy = OwnershipLease(
                agent_id=lease.owner_task_id,
                acquired_at=lease.acquired_at,
                lease_id=lease.lease_id,
                is_active=True,
            )
            self.input_arbiter.release_ownership(dummy)
        else:
            self.lock_manager.release_locks(lease.owner_task_id, [lease.resource_id])

    @contextlib.contextmanager
    def acquire(
        self,
        task_id: str,
        resource_id: str,
        is_exclusive: bool = True,
        timeout: Optional[float] = 10.0,
    ) -> Generator[ResourceLease, None, None]:
        """Scoped context manager for acquiring and releasing resources."""
        lease = self.acquire_resource(task_id, resource_id, is_exclusive=is_exclusive, timeout=timeout)
        try:
            yield lease
        finally:
            self.release_resource(lease)

    def revoke_all_leases(self) -> None:
        """Unconditionally revokes all active resource leases (called on Kill Switch trigger)."""
        with self._lease_lock:
            for lease in self._active_leases.values():
                lease.is_active = False
            self._active_leases.clear()
        self.input_arbiter.revoke_all_unconditional()
