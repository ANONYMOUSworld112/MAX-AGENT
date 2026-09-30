"""
User Activity Monitor & Desktop Input Conflict Guard
=====================================================

Monitors physical human user input (keyboard/mouse) via Win32 GetLastInputInfo().
Prevents automated agent actions from colliding with active human interaction.

Master Spec references:
  - Section 13 (Concurrency & Input Arbitration)
  - docs/audit/CONCURRENCY.md
"""

from __future__ import annotations

import ctypes
import logging
import platform
import time
from typing import Callable, Optional

from core.events import EventBus
from core.contracts import EventEnvelope, _new_id, _now_utc

logger = logging.getLogger("max.user_activity")


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint),
        ("dwTime", ctypes.c_uint),
    ]


class UserActivityConflictError(RuntimeError):
    """Raised when desktop automation attempts to execute while human user is actively typing/clicking."""
    pass


class UserActivityMonitor:
    """Detects human user keyboard and mouse activity to prevent input collisions."""

    def __init__(
        self,
        idle_threshold_ms: float = 1000.0,
        event_bus: Optional[EventBus] = None,
        get_last_input_time_fn: Optional[Callable[[], float]] = None,
        get_current_time_fn: Optional[Callable[[], float]] = None,
    ) -> None:
        self.idle_threshold_ms = idle_threshold_ms
        self.event_bus = event_bus
        self._custom_last_input_fn = get_last_input_time_fn
        self._custom_current_time_fn = get_current_time_fn
        self._is_windows = platform.system() == "Windows"
        self._user32 = ctypes.windll.user32 if self._is_windows else None
        self._kernel32 = ctypes.windll.kernel32 if self._is_windows else None
        self._last_state = "idle"

    def get_idle_duration_ms(self) -> float:
        """Calculate the duration in milliseconds since the last keyboard or mouse input."""
        if self._custom_last_input_fn and self._custom_current_time_fn:
            now_ms = self._custom_current_time_fn()
            last_ms = self._custom_last_input_fn()
            return max(0.0, now_ms - last_ms)

        if not self._is_windows or not self._user32 or not self._kernel32:
            return 999999.0  # Headless or non-Windows assumes idle

        try:
            lii = LASTINPUTINFO()
            lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
            if not self._user32.GetLastInputInfo(ctypes.byref(lii)):
                return 0.0

            current_tick = self._kernel32.GetTickCount()
            idle_ticks = (current_tick - lii.dwTime) & 0xFFFFFFFF
            return float(idle_ticks)
        except Exception as exc:
            logger.warning("Failed to query GetLastInputInfo: %s", exc)
            return 999999.0

    def is_user_active(self) -> bool:
        """Return True if human input occurred within the idle threshold window."""
        idle_ms = self.get_idle_duration_ms()
        return idle_ms < self.idle_threshold_ms

    def check_and_emit(self) -> str:
        """Check user state and emit transition events on the EventBus."""
        active = self.is_user_active()
        current_state = "active" if active else "idle"

        if current_state != self._last_state:
            self._last_state = current_state
            event_type = f"user.{current_state}"
            logger.info("User activity state changed to '%s'", current_state)
            if self.event_bus:
                self.event_bus.publish(
                    EventEnvelope(
                        id=_new_id(),
                        event_type=event_type,
                        actor="UserActivityMonitor",
                        payload={"state": current_state, "idle_duration_ms": self.get_idle_duration_ms()},
                        timestamp=_now_utc(),
                    )
                )

        return current_state

    def guard_automation(self, action_name: str = "desktop_action") -> None:
        """Ensure no human input is occurring; raises UserActivityConflictError if active."""
        if self.is_user_active():
            raise UserActivityConflictError(
                f"Desktop automation paused: human user is actively interacting with the system "
                f"(idle duration: {self.get_idle_duration_ms():.1f}ms < threshold {self.idle_threshold_ms:.1f}ms)."
            )

    def wait_until_idle(self, timeout_seconds: float = 5.0, poll_interval_seconds: float = 0.1) -> bool:
        """Block until the human user stops interacting, or until timeout."""
        start_t = time.time()
        while time.time() - start_t < timeout_seconds:
            if not self.is_user_active():
                return True
            time.sleep(poll_interval_seconds)
        return not self.is_user_active()
