"""
MAX OS — Outcome Tracker (Step 3.3).
Tracks task outcomes, average duration, success rates, and sample counts in SQLite outcome_tracker table.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

DEFAULT_DB_PATH = Path(__file__).parent.parent / "max_state.db"


@dataclass
class TaskOutcomeStats:
    task_type: str
    avg_duration_ms: int
    success_rate: float
    sample_count: int
    last_updated: str


class OutcomeTracker:
    """
    Records and tracks execution outcomes per task type.
    Informs planning heuristics and post-deploy performance metrics.
    """

    def __init__(self, db_path: Optional[Path | str] = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.row_factory = sqlite3.Row
        return conn

    def record_outcome(self, task_type: str, duration_ms: int, success: bool) -> TaskOutcomeStats:
        """Updates outcome_tracker table with a new task run result."""
        conn = self._get_conn()
        now = datetime.now(timezone.utc).isoformat()
        try:
            cur = conn.execute("SELECT * FROM outcome_tracker WHERE task_type = ?", (task_type,))
            row = cur.fetchone()

            if not row:
                sample_count = 1
                avg_dur = duration_ms
                success_rate = 1.0 if success else 0.0
                conn.execute(
                    """
                    INSERT INTO outcome_tracker (task_type, avg_duration_ms, success_rate, sample_count, last_updated)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (task_type, avg_dur, success_rate, sample_count, now),
                )
            else:
                sample_count = row["sample_count"] + 1
                prev_avg = row["avg_duration_ms"] or 0
                prev_success_count = (row["success_rate"] or 0.0) * row["sample_count"]

                new_avg = int((prev_avg * row["sample_count"] + duration_ms) / sample_count)
                new_success_count = prev_success_count + (1 if success else 0)
                new_success_rate = round(new_success_count / sample_count, 4)

                conn.execute(
                    """
                    UPDATE outcome_tracker
                    SET avg_duration_ms = ?, success_rate = ?, sample_count = ?, last_updated = ?
                    WHERE task_type = ?
                    """,
                    (new_avg, new_success_rate, sample_count, now, task_type),
                )

            conn.commit()
            return TaskOutcomeStats(
                task_type=task_type,
                avg_duration_ms=avg_dur if not row else new_avg,
                success_rate=success_rate if not row else new_success_rate,
                sample_count=sample_count,
                last_updated=now,
            )
        finally:
            conn.close()

    def get_stats(self, task_type: str) -> Optional[TaskOutcomeStats]:
        """Retrieves stats for a task type."""
        conn = self._get_conn()
        try:
            cur = conn.execute("SELECT * FROM outcome_tracker WHERE task_type = ?", (task_type,))
            row = cur.fetchone()
            if not row:
                return None
            return TaskOutcomeStats(
                task_type=row["task_type"],
                avg_duration_ms=row["avg_duration_ms"],
                success_rate=row["success_rate"],
                sample_count=row["sample_count"],
                last_updated=row["last_updated"],
            )
        finally:
            conn.close()
