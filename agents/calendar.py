"""
MAX OS — Calendar Agent (Tier 1 Core).
Permission: auto. Execution mode: on_demand.
Manages events, meetings, and reminders without requiring locks.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.kill_switch import get_kill_switch, require_armed

DEFAULT_CALENDAR_DB = Path(__file__).parent.parent / "max_state.db"


@dataclass
class CalendarEvent:
    event_id: str
    title: str
    start_time: str
    end_time: Optional[str] = None
    description: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class CalendarAgent:
    """
    Tier 1 Calendar Agent.
    Handles scheduling, listing, and querying events and reminders.
    """

    def __init__(self, db_path: Optional[Path | str] = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_CALENDAR_DB
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
                CREATE TABLE IF NOT EXISTS calendar_events (
                    event_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    description TEXT,
                    created_at TEXT NOT NULL
                );
                """
            )
            conn.commit()
        finally:
            conn.close()

    def add_event(
        self,
        title: str,
        start_time: str,
        end_time: Optional[str] = None,
        description: Optional[str] = None,
        event_id: Optional[str] = None,
    ) -> CalendarEvent:
        """Adds a new calendar event. Permission tier: auto."""
        require_armed(get_kill_switch())

        import uuid
        eid = event_id or str(uuid.uuid4())
        event = CalendarEvent(
            event_id=eid,
            title=title,
            start_time=start_time,
            end_time=end_time,
            description=description,
        )

        conn = self._get_conn()
        try:
            conn.execute(
                """
                INSERT INTO calendar_events (event_id, title, start_time, end_time, description, created_at)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (event.event_id, event.title, event.start_time, event.end_time, event.description, event.created_at),
            )
            conn.commit()
            return event
        finally:
            conn.close()

    # Alias for API compatibility
    create_event = add_event

    def list_events(self) -> List[CalendarEvent]:
        """Lists all calendar events ordered by start_time."""
        require_armed(get_kill_switch())
        conn = self._get_conn()
        try:
            rows = conn.execute("SELECT * FROM calendar_events ORDER BY start_time ASC;").fetchall()
            return [
                CalendarEvent(
                    event_id=r["event_id"],
                    title=r["title"],
                    start_time=r["start_time"],
                    end_time=r["end_time"],
                    description=r["description"],
                    created_at=r["created_at"],
                )
                for r in rows
            ]
        finally:
            conn.close()
