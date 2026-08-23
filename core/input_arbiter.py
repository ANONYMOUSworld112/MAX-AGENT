"""
MAX OS — Input Arbitration Engine (Section 7.3).
Enforces exclusive physical input ownership (mouse, keyboard, active window focus).
Guarantees strictly ONE agent stream controls input at a time, with unconditional
instant revocation by the Security Gate kill switch.
"""

from __future__ import annotations

import contextlib
import threading
import time
from dataclasses import dataclass, field
from typing import Generator, Optional, Set

from core.kill_switch import get_kill_switch, require_armed


class InputArbiterPreemptedError(Exception):
    """Raised when an active input holder is preempted by the emergency kill switch."""
    pass


class InputOwnershipTimeoutError(Exception):
    """Raised when an agent fails to acquire exclusive input ownership within timeout."""
    pass


@dataclass
class OwnershipLease:
    agent_id: str
    acquired_at: float
    lease_id: str
    is_active: bool = True


class InputArbiter:
    """
    Physical Input Arbiter for Mouse, Keyboard, and Window Focus.
    Prevents race conditions between concurrent agents and guarantees instant
    unconditional kill-switch preemption.
    """

    _instance: Optional[InputArbiter] = None
    _singleton_lock = threading.Lock()

    def __init__(self, default_timeout: float = 10.0):
        self.default_timeout = default_timeout
        self._mutex = threading.Lock()
        self._owner_cond = threading.Condition(self._mutex)
        self._current_lease: Optional[OwnershipLease] = None
        self._preempted = False

    @property
    def _kill_switch(_self):
        ks = get_kill_switch()
        # Ensure revocation callback registered
        if _self.revoke_all_unconditional not in ks._callbacks:
            ks.register_callback(_self.revoke_all_unconditional)
        return ks

    @classmethod
    def get_instance(cls) -> InputArbiter:
        with cls._singleton_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @property
    def current_holder(self) -> Optional[str]:
        with self._mutex:
            if self._current_lease and self._current_lease.is_active:
                return self._current_lease.agent_id
            return None

    def request_ownership(self, agent_id: str, timeout: Optional[float] = None) -> OwnershipLease:
        """
        Requests exclusive ownership of physical input. Blocks until granted or timed out.
        """
        if self._kill_switch.is_triggered():
            raise InputArbiterPreemptedError("Cannot acquire input ownership: Kill switch is triggered.")
        require_armed(self._kill_switch)
        effective_timeout = timeout if timeout is not None else self.default_timeout
        deadline = time.monotonic() + effective_timeout

        with self._owner_cond:
            while self._current_lease is not None and self._current_lease.is_active:
                # If the same agent already holds the lease, allow re-entrant access
                if self._current_lease.agent_id == agent_id:
                    return self._current_lease

                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise InputOwnershipTimeoutError(
                        f"Agent '{agent_id}' timed out waiting for InputArbiter ownership (currently held by '{self._current_lease.agent_id}')."
                    )

                if self._kill_switch.is_triggered():
                    raise InputArbiterPreemptedError("Cannot acquire input ownership: Kill switch is triggered.")

                self._owner_cond.wait(timeout=min(0.2, remaining))

            if self._kill_switch.is_triggered():
                raise InputArbiterPreemptedError("Cannot acquire input ownership: Kill switch is triggered.")

            # Issue new lease
            import uuid
            lease = OwnershipLease(
                agent_id=agent_id,
                acquired_at=time.time(),
                lease_id=str(uuid.uuid4()),
                is_active=True,
            )
            self._current_lease = lease
            return lease

    def release_ownership(self, lease: OwnershipLease) -> bool:
        """Releases input ownership held by the given lease."""
        with self._owner_cond:
            if self._current_lease and self._current_lease.lease_id == lease.lease_id:
                self._current_lease.is_active = False
                self._current_lease = None
                self._owner_cond.notify_all()
                return True
            return False

    def revoke_all_unconditional(self) -> None:
        """
        Unconditionally revokes ownership immediately without requiring cooperation
        from the active holder (triggered on emergency kill switch halt).
        """
        with self._owner_cond:
            if self._current_lease:
                self._current_lease.is_active = False
                self._current_lease = None
            self._preempted = True
            self._owner_cond.notify_all()

    def check_lease(self, lease: OwnershipLease) -> None:
        """Verifies that the lease is still valid and has not been preempted or invalidated."""
        if self._kill_switch.is_triggered():
            raise InputArbiterPreemptedError("Kill switch triggered: Input ownership revoked.")
        with self._mutex:
            if not lease.is_active or self._current_lease is None or self._current_lease.lease_id != lease.lease_id:
                raise InputArbiterPreemptedError(f"Lease {lease.lease_id} for agent '{lease.agent_id}' is no longer active.")

    @contextlib.contextmanager
    def acquire(self, agent_id: str, timeout: Optional[float] = None) -> Generator[OwnershipLease, None, None]:
        """
        Context manager for scoped input ownership.
        """
        lease = self.request_ownership(agent_id, timeout=timeout)
        try:
            yield lease
        finally:
            self.release_ownership(lease)
