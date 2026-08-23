"""
MAX OS — Unified Cancellation Subsystem (Section 19)
core/cancellation.py

Provides CancellationToken propagation across tasks, agents, tools, subprocesses, and browser sessions.
"""

from __future__ import annotations

import threading
import time
from typing import Callable, List, Optional

from core.kill_switch import get_kill_switch


class TaskCancelledError(Exception):
    """Raised when an operation is cancelled via CancellationToken or Kill Switch."""
    pass


class CancellationToken:
    """
    Thread-safe CancellationToken used by tasks and tool backends to monitor stop signals.
    """

    def __init__(self, parent_token: Optional[CancellationToken] = None):
        self._is_cancelled = False
        self._cancel_reason = ""
        self._lock = threading.Lock()
        self._callbacks: List[Callable[[], None]] = []
        self.parent_token = parent_token
        self.kill_switch = get_kill_switch()

    def is_cancelled(self) -> bool:
        if self.kill_switch.is_triggered():
            return True
        if self.parent_token and self.parent_token.is_cancelled():
            return True
        with self._lock:
            return self._is_cancelled

    def cancel(self, reason: str = "User cancelled task execution") -> None:
        with self._lock:
            if self._is_cancelled:
                return
            self._is_cancelled = True
            self._cancel_reason = reason

        for cb in self._callbacks:
            try:
                cb()
            except Exception:
                pass

    def check(self) -> None:
        """Raises TaskCancelledError if cancelled or Kill Switch triggered."""
        if self.is_cancelled():
            reason = self._cancel_reason or self.kill_switch.trigger_reason or "Cancelled"
            raise TaskCancelledError(f"Task execution cancelled: {reason}")

    def register_callback(self, callback: Callable[[], None]) -> None:
        with self._lock:
            self._callbacks.append(callback)
