"""
Calendar Worker (Task 10.3)
===========================

Provides persistent, SQLite-backed RFC 5545 calendar event scheduling,
querying, and rigorous half-open interval [start, end) conflict detection.
"""

from __future__ import annotations

import logging
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger("max.workers.calendar")


@dataclass
class CalendarEvent:
    id: str
    summary: str
    start_time: float
    end_time: float
    location: str = ""
    description: str = ""
    recurrence: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "summary": self.summary,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "location": self.location,
            "description": self.description,
            "recurrence": self.recurrence,
        }


class CalendarWorker:
    """
    Manages calendar events with deterministic half-open interval conflict detection.
    """

    def __init__(self, db_path: Optional[Union[str, Path]] = None) -> None:
        self.db_path = str(db_path) if db_path else ":memory:"
        self._shared_conn: Optional[sqlite3.Connection] = None
        if self.db_path == ":memory:":
            self._shared_conn = sqlite3.connect(":memory:")
            self._shared_conn.row_factory = sqlite3.Row
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if self._shared_conn is not None:
            return self._shared_conn
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS calendar_events (
                    id TEXT PRIMARY KEY,
                    summary TEXT NOT NULL,
                    start_time REAL NOT NULL,
                    end_time REAL NOT NULL,
                    location TEXT DEFAULT '',
                    description TEXT DEFAULT '',
                    recurrence TEXT DEFAULT ''
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cal_time ON calendar_events (start_time, end_time)")

    def check_conflicts(
        self,
        start_time: float,
        end_time: float,
        exclude_id: Optional[str] = None,
    ) -> List[CalendarEvent]:
        """
        Detects conflicts using half-open intervals [start, end).
        Two intervals [s1, e1) and [s2, e2) overlap iff (s1 < e2 AND e1 > s2).
        """
        if end_time <= start_time:
            raise ValueError("end_time must be strictly greater than start_time.")

        query = """
            SELECT id, summary, start_time, end_time, location, description, recurrence
            FROM calendar_events
            WHERE start_time < ? AND end_time > ?
        """
        params: list[Any] = [end_time, start_time]
        if exclude_id:
            query += " AND id != ?"
            params.append(exclude_id)

        conflicts = []
        with self._get_connection() as conn:
            cur = conn.execute(query, params)
            for row in cur.fetchall():
                conflicts.append(CalendarEvent(**dict(row)))
        return conflicts

    def create_event(
        self,
        summary: str,
        start_time: float,
        end_time: float,
        location: str = "",
        description: str = "",
        recurrence: str = "",
        allow_conflicts: bool = False,
    ) -> CalendarEvent:
        if end_time <= start_time:
            raise ValueError(f"Invalid interval: end_time ({end_time}) <= start_time ({start_time})")

        if not allow_conflicts:
            conflicts = self.check_conflicts(start_time, end_time)
            if conflicts:
                conflict_names = ", ".join(f"'{c.summary}'" for c in conflicts)
                raise ValueError(f"Conflicting event(s) found during specified interval: {conflict_names}")

        event_id = str(uuid.uuid4())
        event = CalendarEvent(
            id=event_id,
            summary=summary,
            start_time=start_time,
            end_time=end_time,
            location=location,
            description=description,
            recurrence=recurrence,
        )

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO calendar_events (id, summary, start_time, end_time, location, description, recurrence)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (event.id, event.summary, event.start_time, event.end_time, event.location, event.description, event.recurrence),
            )

        logger.info("Created calendar event '%s' [%s - %s]", summary, start_time, end_time)
        return event

    def list_events(
        self,
        start_range: Optional[float] = None,
        end_range: Optional[float] = None,
    ) -> List[CalendarEvent]:
        query = "SELECT id, summary, start_time, end_time, location, description, recurrence FROM calendar_events"
        params: list[Any] = []
        conditions = []

        if start_range is not None:
            conditions.append("end_time > ?")
            params.append(start_range)
        if end_range is not None:
            conditions.append("start_time < ?")
            params.append(end_range)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY start_time ASC"

        events = []
        with self._get_connection() as conn:
            cur = conn.execute(query, params)
            for row in cur.fetchall():
                events.append(CalendarEvent(**dict(row)))
        return events

    def update_event(
        self,
        event_id: str,
        start_time: float,
        end_time: float,
        summary: Optional[str] = None,
        allow_conflicts: bool = False,
    ) -> Optional[CalendarEvent]:
        if end_time <= start_time:
            raise ValueError(f"Invalid interval: end_time ({end_time}) <= start_time ({start_time})")

        if not allow_conflicts:
            conflicts = self.check_conflicts(start_time, end_time, exclude_id=event_id)
            if conflicts:
                conflict_names = ", ".join(f"'{c.summary}'" for c in conflicts)
                raise ValueError(f"Conflicting event(s) found during specified interval: {conflict_names}")

        with self._get_connection() as conn:
            if summary is not None:
                cur = conn.execute(
                    "UPDATE calendar_events SET start_time = ?, end_time = ?, summary = ? WHERE id = ?",
                    (start_time, end_time, summary, event_id),
                )
            else:
                cur = conn.execute(
                    "UPDATE calendar_events SET start_time = ?, end_time = ? WHERE id = ?",
                    (start_time, end_time, event_id),
                )
            if cur.rowcount == 0:
                return None

            cur = conn.execute("SELECT * FROM calendar_events WHERE id = ?", (event_id,))
            row = cur.fetchone()
            return CalendarEvent(**dict(row)) if row else None

    # Alias for natural language intent callers
    move_event = update_event

    def find_free_time(
        self,
        start_range: float,
        end_range: float,
        slot_duration_seconds: float = 1800.0,
    ) -> List[Tuple[float, float]]:
        """Finds unoccupied intervals in [start_range, end_range) of at least slot_duration_seconds."""
        if end_range <= start_range:
            return []
        events = self.list_events(start_range=start_range, end_range=end_range)
        events.sort(key=lambda e: e.start_time)
        free_slots: List[Tuple[float, float]] = []
        current = start_range

        for ev in events:
            ev_start = max(ev.start_time, start_range)
            ev_end = min(ev.end_time, end_range)
            if ev_start > current:
                if (ev_start - current) >= slot_duration_seconds:
                    free_slots.append((current, ev_start))
            current = max(current, ev_end)

        if current < end_range:
            if (end_range - current) >= slot_duration_seconds:
                free_slots.append((current, end_range))

        return free_slots

    def delete_event(self, event_id: str) -> bool:
        with self._get_connection() as conn:
            cur = conn.execute("DELETE FROM calendar_events WHERE id = ?", (event_id,))
            return cur.rowcount > 0

