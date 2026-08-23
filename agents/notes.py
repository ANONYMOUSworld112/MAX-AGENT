"""
MAX OS — Notes Agent (Tier 1 Core).
Permission: auto. Execution mode: on_demand.
Manages notes creation, search, tagging, and retrieval.
"""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.kill_switch import get_kill_switch, require_armed

DEFAULT_NOTES_DB = Path(__file__).parent.parent / "max_state.db"


@dataclass
class Note:
    note_id: str
    title: str
    content: str
    tags: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class NotesAgent:
    """
    Tier 1 Notes Agent.
    Creates, searches, retrieves, and lists notes.
    """

    def __init__(self, db_path: Optional[Path | str] = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_NOTES_DB
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
                CREATE TABLE IF NOT EXISTS notes_store (
                    note_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tags TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            conn.commit()
        finally:
            conn.close()

    def create_note(
        self,
        title: str,
        content: str,
        tags: str = "",
        note_id: Optional[str] = None,
    ) -> Note:
        """Creates a new note. Permission tier: auto."""
        require_armed(get_kill_switch())

        nid = note_id or str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        tags_str = ",".join(tags) if isinstance(tags, (list, tuple, set)) else str(tags or "")
        note = Note(
            note_id=nid,
            title=title,
            content=content,
            tags=tags_str,
            created_at=now,
            updated_at=now,
        )

        conn = self._get_conn()
        try:
            conn.execute(
                """
                INSERT INTO notes_store (note_id, title, content, tags, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (note.note_id, note.title, note.content, note.tags, note.created_at, note.updated_at),
            )
            conn.commit()
            return note
        finally:
            conn.close()

    def get_note(self, title_or_id: str) -> Optional[Note]:
        """Retrieves a note by ID or exact title."""
        require_armed(get_kill_switch())
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM notes_store WHERE note_id = ? OR title = ? LIMIT 1;",
                (title_or_id, title_or_id),
            ).fetchone()
            if not row:
                return None
            return Note(
                note_id=row["note_id"],
                title=row["title"],
                content=row["content"],
                tags=row["tags"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
        finally:
            conn.close()

    def search_notes(self, query: str) -> List[Note]:
        """Searches notes by matching query against title, content, or tags."""
        require_armed(get_kill_switch())
        conn = self._get_conn()
        try:
            q = f"%{query}%"
            rows = conn.execute(
                """
                SELECT * FROM notes_store 
                WHERE title LIKE ? OR content LIKE ? OR tags LIKE ?
                ORDER BY updated_at DESC;
                """,
                (q, q, q),
            ).fetchall()
            return [
                Note(
                    note_id=r["note_id"],
                    title=r["title"],
                    content=r["content"],
                    tags=r["tags"],
                    created_at=r["created_at"],
                    updated_at=r["updated_at"],
                )
                for r in rows
            ]
        finally:
            conn.close()

    def list_notes(self) -> List[Note]:
        """Lists all notes ordered by updated_at."""
        require_armed(get_kill_switch())
        conn = self._get_conn()
        try:
            rows = conn.execute("SELECT * FROM notes_store ORDER BY updated_at DESC;").fetchall()
            return [
                Note(
                    note_id=r["note_id"],
                    title=r["title"],
                    content=r["content"],
                    tags=r["tags"],
                    created_at=r["created_at"],
                    updated_at=r["updated_at"],
                )
                for r in rows
            ]
        finally:
            conn.close()
