"""
MAX OS — Kill Switch (Component #0)

Boot dependency: Main Agent MUST check Kill Switch status and refuse to
fully initialize until it reports `armed`. See ARCHITECTURE.md step 0.2,
MAX_MASTER_PROMPT.md principle 1, DECISIONS.md D4.

Design:
  - Thread-safe state machine: DISARMED → ARMED → TRIGGERED
  - On trigger: sets a global Event that every running task checks
  - Acceptance criteria: triggering mid-task halts execution within 1s
  - Can be triggered via:
    1. signal_kill() function call
    2. Keyboard interrupt handler (Ctrl+C)
    3. External signal (SIGUSR1 on Unix, named event on Windows)
"""

import logging
import threading
import time
from enum import Enum
from typing import Callable, List, Optional

logger = logging.getLogger("max.kill_switch")


class KillSwitchState(Enum):
    DISARMED = "disarmed"
    ARMED = "armed"
    TRIGGERED = "triggered"


class KillSwitch:
    """
    Component #0 — nothing else may initialize before this reports armed.

    Usage:
        ks = KillSwitch()
        ks.arm()                    # Must happen before Main Agent boots
        assert ks.is_armed()        # Boot check

        # In task loops:
        if ks.is_triggered():
            # stop immediately, roll back
            ...

        # Emergency:
        ks.trigger("user requested halt")
    """

    def __init__(self) -> None:
        self._state = KillSwitchState.DISARMED
        self._lock = threading.Lock()
        self._triggered_event = threading.Event()
        self._trigger_reason: Optional[str] = None
        self._trigger_time: Optional[float] = None
        self._callbacks: List[Callable[[], None]] = []

    @property
    def state(self) -> KillSwitchState:
        """Current state of the kill switch."""
        with self._lock:
            return self._state

    def arm(self) -> None:
        """
        Arm the kill switch. Must be called before Main Agent boot.
        Raises RuntimeError if already triggered.
        """
        with self._lock:
            if self._state == KillSwitchState.TRIGGERED:
                raise RuntimeError("Cannot arm a triggered kill switch — restart required")
            self._state = KillSwitchState.ARMED
            logger.info("Kill switch ARMED")

    def is_armed(self) -> bool:
        """Check if kill switch is armed (boot-check)."""
        with self._lock:
            return self._state == KillSwitchState.ARMED

    def is_triggered(self) -> bool:
        """
        Check if kill switch has been triggered.
        This is the fast-path check that every task loop should call.
        Uses threading.Event for zero-overhead when not triggered.
        """
        return self._triggered_event.is_set()

    def trigger(self, reason: str = "manual trigger") -> None:
        """
        Trigger the kill switch — sends hard STOP to everything.
        Thread-safe, idempotent (safe to call multiple times).
        """
        with self._lock:
            if self._state == KillSwitchState.TRIGGERED:
                logger.warning(f"Kill switch already triggered, ignoring: {reason}")
                return

            self._state = KillSwitchState.TRIGGERED
            self._trigger_reason = reason
            self._trigger_time = time.monotonic()
            self._triggered_event.set()
            logger.critical(f"KILL SWITCH TRIGGERED: {reason}")

        # Fire callbacks outside the lock to avoid deadlocks
        for callback in self._callbacks:
            try:
                callback()
            except Exception as e:
                logger.error(f"Kill switch callback error: {e}")

    def register_callback(self, callback: Callable[[], None]) -> None:
        """
        Register a callback to be called when the kill switch is triggered.
        Used by task runners to receive immediate notification.
        """
        self._callbacks.append(callback)

    def wait_for_trigger(self, timeout: Optional[float] = None) -> bool:
        """
        Block until the kill switch is triggered or timeout expires.
        Returns True if triggered, False if timed out.
        """
        return self._triggered_event.wait(timeout=timeout)

    @property
    def trigger_reason(self) -> Optional[str]:
        """Why the kill switch was triggered (None if not triggered)."""
        with self._lock:
            return self._trigger_reason

    def reset(self) -> None:
        """
        Reset kill switch to DISARMED. Only for testing — in production,
        a triggered kill switch requires a full process restart.
        """
        with self._lock:
            self._state = KillSwitchState.DISARMED
            self._triggered_event.clear()
            self._trigger_reason = None
            self._trigger_time = None
            logger.warning("Kill switch RESET (test-only operation)")


def require_armed(kill_switch: KillSwitch) -> None:
    """
    Boot-time check: refuses to proceed unless kill switch is armed.
    Call this at the top of Main Agent initialization.

    Raises RuntimeError if not armed — this is intentionally a hard
    failure, not a warning, per D4.
    """
    if not kill_switch.is_armed():
        raise RuntimeError(
            "Kill Switch is not armed. Nothing may initialize before it "
            "reports armed. See DECISIONS.md D4: Kill Switch is Component #0."
        )


# Module-level singleton for global access
_global_kill_switch: Optional[KillSwitch] = None
_global_lock = threading.Lock()


def get_kill_switch() -> KillSwitch:
    """Get or create the global kill switch singleton."""
    global _global_kill_switch
    with _global_lock:
        if _global_kill_switch is None:
            _global_kill_switch = KillSwitch()
        return _global_kill_switch


def signal_kill(reason: str = "external signal") -> None:
    """Convenience function to trigger the global kill switch."""
    get_kill_switch().trigger(reason)
