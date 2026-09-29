"""Component #0: Global Kill Switch.

This component is armed before any other thread or process starts.
When tripped, it immediately signals all background tasks to halt,
terminates registered child processes, and prevents any new executions.
Zero LLM calls. Pure deterministic Python.
"""

from __future__ import annotations

import logging
import os
import subprocess
import threading
from typing import Callable, Set

logger = logging.getLogger("max.infra.kill_switch")


class KillSwitchTrippedError(Exception):
    """Raised when an operation is attempted while the kill switch is tripped."""
    pass


class KillSwitch:
    _instance: KillSwitch | None = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._armed = True
        self._tripped = False
        self._trip_event = threading.Event()
        self._reason: str | None = None
        self._listeners: list[Callable[[str], None]] = []
        self._registered_pids: Set[int] = set()
        self._state_lock = threading.RLock()

    @classmethod
    def get_instance(cls) -> KillSwitch:
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def reset(self) -> None:
        """Reset the kill switch back to armed (non-tripped) state."""
        with self._state_lock:
            self._armed = True
            self._tripped = False
            self._trip_event.clear()
            self._reason = None
            self._registered_pids.clear()
            logger.info("KillSwitch armed and reset.")

    def is_armed(self) -> bool:
        with self._state_lock:
            return self._armed

    def is_tripped(self) -> bool:
        return self._trip_event.is_set()

    @property
    def registered_pids(self) -> Set[int]:
        with self._state_lock:
            return set(self._registered_pids)

    def guard(self) -> None:
        """Enforces that the switch is not tripped; raises if tripped."""
        if self.is_tripped():
            reason = self._reason or "Unspecified emergency shutdown"
            raise KillSwitchTrippedError(f"Operation aborted: KillSwitch is tripped ({reason})")

    def register_process(self, pid: int) -> None:
        """Register a child worker process PID for hard-kill on trip."""
        with self._state_lock:
            self._registered_pids.add(pid)

    def unregister_process(self, pid: int) -> None:
        with self._state_lock:
            self._registered_pids.discard(pid)

    def add_listener(self, callback: Callable[[str], None]) -> None:
        with self._state_lock:
            if callback not in self._listeners:
                self._listeners.append(callback)

    def trip(self, reason: str = "Emergency Kill Switch Activated") -> None:
        """Immediately trip the kill switch, terminate processes, notify listeners."""
        with self._state_lock:
            if self._tripped:
                return  # already tripped
            self._tripped = True
            self._reason = reason
            self._trip_event.set()
            logger.critical("🚨 KILL SWITCH TRIPPED: %s", reason)

            # Terminate registered child processes
            for pid in list(self._registered_pids):
                self._terminate_pid(pid)
            self._registered_pids.clear()

            # Execute callbacks
            for listener in list(self._listeners):
                try:
                    listener(reason)
                except Exception as exc:
                    logger.error("Error in KillSwitch listener: %s", exc)

    def _terminate_pid(self, pid: int) -> None:
        try:
            if os.name == "nt":
                # Windows tree kill
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(pid)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            else:
                import signal
                os.kill(pid, signal.SIGKILL)
            logger.warning("Terminated process PID %d via KillSwitch", pid)
        except Exception as exc:
            logger.error("Failed to terminate PID %d: %s", pid, exc)
