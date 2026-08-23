"""
MAX OS — Circuit Breaker (Per-Agent Isolation)
Build Order: #14 (Layer 3D)
═══════════════════════════════════════════════════════

Isolates failing agents. 5 consecutive failures trips circuit breaker to OPEN.
Half-open test allows trial request after cooldown.
"""

from __future__ import annotations

import time
import logging
from enum import Enum
from typing import Optional

from src.infra import state_db

logger = logging.getLogger("max.core.circuit_breaker")

MAX_CONSECUTIVE_FAILURES = 5
COOLDOWN_SECONDS = 60.0


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpenError(RuntimeError):
    """Raised when an agent invocation is blocked because its circuit breaker is OPEN."""
    pass


class CircuitBreaker:
    """Manages circuit breaker state per agent."""

    def get_state(self, agent_name: str) -> CircuitState:
        row = state_db.fetchone("SELECT state, opened_at FROM circuit_breaker_state WHERE agent = ?", (agent_name,))
        if not row:
            return CircuitState.CLOSED

        current_state = CircuitState(row["state"])
        if current_state == CircuitState.OPEN and row["opened_at"]:
            # Check cooldown
            opened_ts = float(row["opened_at"])
            if (time.time() - opened_ts) > COOLDOWN_SECONDS:
                self._update_state(agent_name, CircuitState.HALF_OPEN)
                return CircuitState.HALF_OPEN

        return current_state

    def record_success(self, agent_name: str) -> None:
        state_db.execute(
            """
            INSERT INTO circuit_breaker_state (agent, state, consecutive_failures, opened_at)
            VALUES (?, 'closed', 0, NULL)
            ON CONFLICT(agent) DO UPDATE SET state = 'closed', consecutive_failures = 0, opened_at = NULL
            """,
            (agent_name,)
        )
        state_db.commit()

    def record_failure(self, agent_name: str) -> None:
        row = state_db.fetchone("SELECT consecutive_failures FROM circuit_breaker_state WHERE agent = ?", (agent_name,))
        fails = (row["consecutive_failures"] if row else 0) + 1

        if fails >= MAX_CONSECUTIVE_FAILURES:
            now_str = str(time.time())
            state_db.execute(
                """
                INSERT INTO circuit_breaker_state (agent, state, consecutive_failures, opened_at)
                VALUES (?, 'open', ?, ?)
                ON CONFLICT(agent) DO UPDATE SET state = 'open', consecutive_failures = ?, opened_at = ?
                """,
                (agent_name, fails, now_str, fails, now_str)
            )
            logger.error("Circuit breaker OPENED for agent '%s' after %d consecutive failures", agent_name, fails)
        else:
            state_db.execute(
                """
                INSERT INTO circuit_breaker_state (agent, state, consecutive_failures, opened_at)
                VALUES (?, 'closed', ?, NULL)
                ON CONFLICT(agent) DO UPDATE SET consecutive_failures = ?
                """,
                (agent_name, fails, fails)
            )
        state_db.commit()

    def check_allow(self, agent_name: str) -> None:
        st = self.get_state(agent_name)
        if st == CircuitState.OPEN:
            raise CircuitBreakerOpenError(
                f"Circuit breaker for agent '{agent_name}' is OPEN due to repeated failures. "
                f"Cooldown period is {COOLDOWN_SECONDS}s."
            )

    def _update_state(self, agent_name: str, state: CircuitState) -> None:
        state_db.execute(
            "UPDATE circuit_breaker_state SET state = ? WHERE agent = ?",
            (state.value, agent_name)
        )
        state_db.commit()


_global_cb: Optional[CircuitBreaker] = None


def get_circuit_breaker() -> CircuitBreaker:
    global _global_cb
    if _global_cb is None:
        _global_cb = CircuitBreaker()
    return _global_cb
