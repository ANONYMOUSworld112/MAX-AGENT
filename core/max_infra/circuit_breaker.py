"""Circuit Breaker for Fault Tolerance and Cascading Failure Prevention.

Enforces a 3-strike trip policy:
- CLOSED: Normal operation
- OPEN: Tripped after 3 consecutive failures. Rejects requests immediately without invoking workers
- HALF_OPEN: Entered after cooldown expires. A single success restores CLOSED state.
"""

from __future__ import annotations

import logging
import threading
import time
from enum import Enum
from typing import Dict, Optional

logger = logging.getLogger("max.infra.circuit_breaker")


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 3,
        cooldown_seconds: float = 60.0,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self._lock = threading.RLock()
        self._failures = 0
        self._trip_time: Optional[float] = None
        self._state = CircuitState.CLOSED

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN:
                if self._trip_time and (time.time() - self._trip_time >= self.cooldown_seconds):
                    self._state = CircuitState.HALF_OPEN
                    logger.info("CircuitBreaker transitioned to HALF_OPEN after cooldown")
            return self._state

    def is_allowed(self, target: str = "") -> bool:
        with self._lock:
            st = self.state
            return st in (CircuitState.CLOSED, CircuitState.HALF_OPEN)

    def record_failure(self, target: str = "") -> None:
        with self._lock:
            self._failures += 1
            logger.warning("Circuit failure recorded for '%s' (%d/%d)", target, self._failures, self.failure_threshold)
            if self._failures >= self.failure_threshold:
                self._state = CircuitState.OPEN
                self._trip_time = time.time()
                logger.critical("🚨 CircuitBreaker tripped to OPEN for '%s'", target)

    def record_success(self, target: str = "") -> None:
        with self._lock:
            self._failures = 0
            self._trip_time = None
            self._state = CircuitState.CLOSED
            logger.info("CircuitBreaker reset to CLOSED for '%s'", target)
