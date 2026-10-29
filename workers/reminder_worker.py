"""
Reminder Worker (Task 10.3)
===========================

Provides persistent SQLite-backed reminders, due queries, snoozing,
and priority management integrated with the task scheduling pipeline.
"""

from __future__ import annotations

import contextlib
import logging
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger("max.workers.reminder")


@dataclass
class ReminderRecord:
    id: str
    text: str
    due_time: float
    priority: str = "NORMAL"
    status: str = "PENDING"
    created_at: float = field(default_factory=time.time)
    snooze_until: Optional[float] = None

    @property
    def effective_due_time(self) -> float:
        return self.snooze_until if self.snooze_until is not None else self.due_time


class ReminderWorker:
    """
    Manages reminders, due time tracking, and snoozing.
    """

    def __init__(self, db_path: Optional[Union[str, Path]] = None) -> None:
        self.db_path = str(db_path) if db_path else ":memory:"
        self._shared_conn: Optional[sqlite3.Connection] = None
        if self.db_path == ":memory:":
            self._shared_conn = sqlite3.connect(":memory:")
            self._shared_conn.row_factory = sqlite3.Row
        self._init_db()

    @contextlib.contextmanager
    def _get_connection(self):
        if self._shared_conn is not None:
            yield self._shared_conn
            return
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def close(self) -> None:
        if self._shared_conn is not None:
            self._shared_conn.close()
            self._shared_conn = None

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reminders (
                    id TEXT PRIMARY KEY,
                    text TEXT NOT NULL,
                    due_time REAL NOT NULL,
                    priority TEXT DEFAULT 'NORMAL',
                    status TEXT DEFAULT 'PENDING',
                    created_at REAL NOT NULL,
                    snooze_until REAL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_rem_due ON reminders (status, due_time, snooze_until)")

    def create_reminder(
        self,
        text: str,
        due_time: float,
        priority: str = "NORMAL",
    ) -> ReminderRecord:
        rem_id = str(uuid.uuid4())
        created_at = time.time()
        record = ReminderRecord(
            id=rem_id,
            text=text,
            due_time=due_time,
            priority=priority.upper(),
            status="PENDING",
            created_at=created_at,
        )

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO reminders (id, text, due_time, priority, status, created_at, snooze_until)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (record.id, record.text, record.due_time, record.priority, record.status, record.created_at, None),
            )

        logger.info("Created reminder '%s' due at %s", text, due_time)
        return record

    def get_due_reminders(self, now: Optional[float] = None) -> List[ReminderRecord]:
        t = now if now is not None else time.time()
        query = """
            SELECT id, text, due_time, priority, status, created_at, snooze_until
            FROM reminders
            WHERE status IN ('PENDING', 'SNOOZED')
              AND (
                  (status = 'PENDING' AND due_time <= ?)
                  OR (status = 'SNOOZED' AND snooze_until <= ?)
              )
            ORDER BY due_time ASC
        """
        results = []
        with self._get_connection() as conn:
            cur = conn.execute(query, (t, t))
            for row in cur.fetchall():
                results.append(ReminderRecord(**dict(row)))
        return results

    def snooze(self, reminder_id: str, minutes: float, now: Optional[float] = None) -> bool:
        t = now if now is not None else time.time()
        new_due = t + (minutes * 60.0)
        with self._get_connection() as conn:
            cur = conn.execute(
                """
                UPDATE reminders
                SET status = 'SNOOZED', snooze_until = ?
                WHERE id = ?
                """,
                (new_due, reminder_id),
            )
            return cur.rowcount > 0

    def complete(self, reminder_id: str) -> bool:
        with self._get_connection() as conn:
            cur = conn.execute("UPDATE reminders SET status = 'COMPLETED' WHERE id = ?", (reminder_id,))
            return cur.rowcount > 0

    def dismiss(self, reminder_id: str) -> bool:
        with self._get_connection() as conn:
            cur = conn.execute("UPDATE reminders SET status = 'DISMISSED' WHERE id = ?", (reminder_id,))
            return cur.rowcount > 0

    def list_reminders(self, status: Optional[str] = None) -> List[ReminderRecord]:
        query = "SELECT id, text, due_time, priority, status, created_at, snooze_until FROM reminders"
        params: list[Any] = []
        if status:
            query += " WHERE status = ?"
            params.append(status.upper())
        query += " ORDER BY due_time ASC"

        results = []
        with self._get_connection() as conn:
            cur = conn.execute(query, params)
            for row in cur.fetchall():
                results.append(ReminderRecord(**dict(row)))
        return results
