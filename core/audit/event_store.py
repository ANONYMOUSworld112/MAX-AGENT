"""
MAX OS — Audit Event Store (Section 23)
core/audit/event_store.py

SQLite-backed persistent event store for querying and auditing execution traces.
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.audit.audit_logger import AuditEvent, redact_secrets

DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "max_state.db"


class EventStore:
    """
    SQLite event store for structured audit querying.
    """

    def __init__(self, db_path: Optional[Path | str] = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.row_factory = sqlite3.Row
        return conn

    def store_event(self, event: AuditEvent) -> None:
        conn = self._get_conn()
        event_dict = event.to_dict()
        try:
            conn.execute(
                """
                INSERT INTO audit_events (event_id, task_id, action_id, agent_id, event_type, risk_level, status, payload_json, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    event.event_id,
                    event.task_id,
                    event.action_id,
                    event.agent_id,
                    event.event_type,
                    event.risk_level,
                    event.status,
                    json.dumps(event_dict["payload"]),
                    event.timestamp,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def get_events_for_task(self, task_id: str) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM audit_events WHERE task_id = ? ORDER BY timestamp ASC",
                (task_id,),
            ).fetchall()
            return [
                {
                    "event_id": r["event_id"],
                    "task_id": r["task_id"],
                    "action_id": r["action_id"],
                    "agent_id": r["agent_id"],
                    "event_type": r["event_type"],
                    "risk_level": r["risk_level"],
                    "status": r["status"],
                    "payload": json.loads(r["payload_json"]) if r["payload_json"] else {},
                    "timestamp": r["timestamp"],
                }
                for r in rows
            ]
        finally:
            conn.close()
