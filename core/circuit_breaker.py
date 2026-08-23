"""
MAX OS — Per-Agent Circuit Breaker (Step 4.3).
Prevents cascading failures and quota drain when an external service or agent fails repeatedly.
States: CLOSED (normal) -> OPEN (tripped on 5 consecutive failures) -> HALF_OPEN (trial after cooldown).
Isolates failures so other agents remain completely unaffected.
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, Optional, TypeVar

DEFAULT_DB_PATH = Path(__file__).parent.parent / "max_state.db"

T = TypeVar("T")


class BreakerState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpenError(Exception):
    """Raised when an action is attempted on an agent whose circuit breaker is OPEN."""
    def __init__(self, agent: str, consecutive_failures: int, opened_at: Optional[str] = None):
        super().__init__(
            f"Circuit breaker for agent '{agent}' is OPEN ({consecutive_failures} consecutive failures). "
            f"Calls rejected instantly to prevent cascading failures."
        )
        self.agent = agent
        self.consecutive_failures = consecutive_failures
        self.opened_at = opened_at


class CircuitBreaker:
    """
    Per-agent circuit breaker with SQLite persistence in circuit_breaker_state table.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        cooldown_seconds: float = 30.0,
        db_path: Optional[Path | str] = None,
    ):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        conn = self._get_conn()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS circuit_breaker_state (
                    agent TEXT PRIMARY KEY,
                    state TEXT NOT NULL DEFAULT 'closed' CHECK (state IN ('closed','open','half_open')),
                    consecutive_failures INTEGER NOT NULL DEFAULT 0,
                    opened_at TEXT
                );
                """
            )
            conn.commit()
        finally:
            conn.close()

    def get_state(self, agent: str) -> tuple[BreakerState, int, Optional[str]]:
        """Returns (state, consecutive_failures, opened_at) for agent."""
        conn = self._get_conn()
        try:
            cur = conn.execute("SELECT state, consecutive_failures, opened_at FROM circuit_breaker_state WHERE agent = ?", (agent,))
            row = cur.fetchone()
            if not row:
                return BreakerState.CLOSED, 0, None

            state = BreakerState(row["state"])
            failures = row["consecutive_failures"]
            opened_at = row["opened_at"]

            # Check if cooldown has elapsed on OPEN breaker -> transition to HALF_OPEN
            if state == BreakerState.OPEN and opened_at:
                try:
                    opened_dt = datetime.fromisoformat(opened_at)
                    elapsed = (datetime.now(timezone.utc) - opened_dt).total_seconds()
                    if elapsed >= self.cooldown_seconds:
                        self.set_state(agent, BreakerState.HALF_OPEN, failures, opened_at)
                        return BreakerState.HALF_OPEN, failures, opened_at
                except Exception:
                    pass

            return state, failures, opened_at
        finally:
            conn.close()

    def set_state(self, agent: str, state: BreakerState, failures: int, opened_at: Optional[str] = None) -> None:
        conn = self._get_conn()
        try:
            conn.execute(
                """
                INSERT INTO circuit_breaker_state (agent, state, consecutive_failures, opened_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(agent) DO UPDATE SET
                    state = excluded.state,
                    consecutive_failures = excluded.consecutive_failures,
                    opened_at = excluded.opened_at;
                """,
                (agent, state.value, failures, opened_at),
            )
            conn.commit()
        finally:
            conn.close()

    def record_success(self, agent: str) -> None:
        """Records a successful operation, resetting circuit breaker to CLOSED."""
        self.set_state(agent, BreakerState.CLOSED, 0, None)

    def record_failure(self, agent: str) -> None:
        """Records a failed operation. If consecutive failures reaches threshold, trips breaker to OPEN."""
        state, failures, opened_at = self.get_state(agent)
        failures += 1

        if failures >= self.failure_threshold:
            now = datetime.now(timezone.utc).isoformat()
            self.set_state(agent, BreakerState.OPEN, failures, now)
        else:
            self.set_state(agent, state, failures, opened_at)

    def execute(self, agent: str, fn: Callable[[], T]) -> T:
        """
        Executes fn under circuit breaker protection.
        Raises CircuitBreakerOpenError immediately if breaker is OPEN.
        """
        state, failures, opened_at = self.get_state(agent)

        if state == BreakerState.OPEN:
            raise CircuitBreakerOpenError(agent, failures, opened_at)

        try:
            res = fn()
            self.record_success(agent)
            return res
        except Exception:
            self.record_failure(agent)
            raise
