"""Private, searchable SQLite episodic memory with export and wipe operations."""
from __future__ import annotations

import json
import re
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_LOCK = threading.RLock()
_SENSITIVE = re.compile(
    r"(?i)\b(password|passcode|api key|secret token|private key|social security number|"
    r"passport number|aadhaar|bank account|credit card|medical diagnosis|prescription)\b"
)


class EpisodeStore:
    """SQLite journal of user-approved summaries, never raw audio/transcripts."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS episodes (id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, summary TEXT NOT NULL, tags TEXT NOT NULL DEFAULT '[]')")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_episodes_created_at ON episodes(created_at)")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def add(self, summary: str, tags: list[str] | None = None) -> int:
        text = " ".join(str(summary).split()).strip()
        if not text:
            raise ValueError("episode summary cannot be empty")
        if _SENSITIVE.search(text):
            raise ValueError("episode matches a sensitive-data exclusion")
        with _LOCK, self._connect() as conn:
            cur = conn.execute("INSERT INTO episodes(created_at,summary,tags) VALUES(?,?,?)",
                               (datetime.now(timezone.utc).isoformat(), text[:2000],
                                json.dumps([str(t)[:64] for t in (tags or [])[:20]])))
            return int(cur.lastrowid)

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        words = [w for w in re.findall(r"[\w'-]+", query.lower()) if len(w) > 1][:12]
        if not words:
            sql, args = "SELECT * FROM episodes ORDER BY id DESC LIMIT ?", (max(1, min(limit, 100)),)
        else:
            where = " OR ".join("lower(summary) LIKE ?" for _ in words)
            sql, args = f"SELECT * FROM episodes WHERE {where} ORDER BY id DESC LIMIT ?", tuple(f"%{w}%" for w in words) + (max(1, min(limit, 100)),)
        with _LOCK, self._connect() as conn:
            rows = conn.execute(sql, args).fetchall()
        return [{"id": r["id"], "created_at": r["created_at"], "summary": r["summary"],
                 "tags": json.loads(r["tags"] or "[]")} for r in rows]

    def export(self) -> list[dict[str, Any]]:
        return self.search("", limit=10000)

    def wipe(self) -> None:
        with _LOCK, self._connect() as conn:
            conn.execute("DELETE FROM episodes")

    def delete(self, episode_id: int) -> bool:
        with _LOCK, self._connect() as conn:
            cur = conn.execute("DELETE FROM episodes WHERE id=?", (int(episode_id),))
            return cur.rowcount > 0
