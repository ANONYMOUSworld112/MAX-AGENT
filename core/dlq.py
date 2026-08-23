"""
MAX OS — Dead Letter Queue Engine (Step 4.4).
Stores tasks that have exhausted all retries or failed unrecoverably, retaining complete attempt history.
Allows operator inspection and requeueing.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_DB_PATH = Path(__file__).parent.parent / "max_state.db"


@dataclass
class DLQRecord:
    task_id: str
    agent: str
    original_input: str
    attempts_json: str
    died_at: str
    requeued: int

    @property
    def attempts(self) -> List[Dict[str, Any]]:
        try:
            return json.loads(self.attempts_json)
        except Exception:
            return []


class DeadLetterQueue:
    """
    Dead Letter Queue service backed by SQLite dead_letter_queue table.
    """

    def __init__(self, db_path: Optional[Path | str] = None):
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
                CREATE TABLE IF NOT EXISTS dead_letter_queue (
                    task_id TEXT PRIMARY KEY,
                    agent TEXT NOT NULL,
                    original_input TEXT NOT NULL,
                    attempts_json TEXT NOT NULL,
                    died_at TEXT NOT NULL,
                    requeued INTEGER NOT NULL DEFAULT 0
                );
                """
            )
            conn.commit()
        finally:
            conn.close()

    def push(
        self,
        task_id: str,
        agent: str,
        original_input: str,
        attempts: List[Dict[str, Any]],
        died_at: Optional[str] = None,
    ) -> DLQRecord:
        """Pushes an exhausted task into the Dead Letter Queue."""
        now = died_at or datetime.now(timezone.utc).isoformat()
        attempts_str = json.dumps(attempts, default=str)

        conn = self._get_conn()
        try:
            conn.execute(
                """
                INSERT INTO dead_letter_queue (task_id, agent, original_input, attempts_json, died_at, requeued)
                VALUES (?, ?, ?, ?, ?, 0)
                ON CONFLICT(task_id) DO UPDATE SET
                    attempts_json = excluded.attempts_json,
                    died_at = excluded.died_at,
                    requeued = 0;
                """,
                (task_id, agent, original_input, attempts_str, now),
            )
            conn.commit()
            return DLQRecord(task_id, agent, original_input, attempts_str, now, 0)
        finally:
            conn.close()

    def list_records(self, include_requeued: bool = False) -> List[DLQRecord]:
        """Lists DLQ records, optionally filtering out requeued tasks."""
        conn = self._get_conn()
        try:
            query = "SELECT * FROM dead_letter_queue"
            if not include_requeued:
                query += " WHERE requeued = 0"
            query += " ORDER BY died_at DESC;"

            rows = conn.execute(query).fetchall()
            return [
                DLQRecord(
                    task_id=r["task_id"],
                    agent=r["agent"],
                    original_input=r["original_input"],
                    attempts_json=r["attempts_json"],
                    died_at=r["died_at"],
                    requeued=r["requeued"],
                )
                for r in rows
            ]
        finally:
            conn.close()

    def get_record(self, task_id: str) -> Optional[DLQRecord]:
        """Retrieves a single DLQ record by task_id."""
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM dead_letter_queue WHERE task_id = ?", (task_id,)).fetchone()
            if not row:
                return None
            return DLQRecord(
                task_id=row["task_id"],
                agent=row["agent"],
                original_input=row["original_input"],
                attempts_json=row["attempts_json"],
                died_at=row["died_at"],
                requeued=row["requeued"],
            )
        finally:
            conn.close()

    def mark_requeued(self, task_id: str) -> bool:
        """Marks a DLQ task as requeued."""
        conn = self._get_conn()
        try:
            cur = conn.execute("UPDATE dead_letter_queue SET requeued = 1 WHERE task_id = ?", (task_id,))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()
