"""SQLite WAL State Database Manager for MAX OS.

Zero LLM calls. Deterministic transactional storage for:
- Task lifecycle and microsecond step traces
- Resource locks
- Circuit breaker state
- 5-layer memory context
- File snapshot records
- Cryptographically chained audit logs
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("max.infra.state_db")

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


class StateDB:
    def __init__(self, db_path: str | Path = "max_state.db", auto_init: bool = True) -> None:
        self.db_path = str(db_path)
        self._lock = threading.RLock()
        self._conn: Optional[sqlite3.Connection] = None
        if auto_init:
            self.initialize()

    def _get_connection(self) -> sqlite3.Connection:
        if self._conn is None:
            parent = os.path.dirname(self.db_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=30.0)
            self._conn.row_factory = sqlite3.Row
            # Enable WAL mode and synchronous normal for high throughput
            with self._conn:
                self._conn.execute("PRAGMA journal_mode = WAL;")
                self._conn.execute("PRAGMA synchronous = NORMAL;")
                self._conn.execute("PRAGMA foreign_keys = ON;")
        return self._conn

    def initialize(self) -> None:
        """Executes the DDL schema to set up all tables and indices."""
        with self._lock:
            conn = self._get_connection()
            if SCHEMA_PATH.exists():
                schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
            else:
                raise FileNotFoundError(f"Schema file not found at {SCHEMA_PATH}")
            with conn:
                conn.executescript(schema_sql)
            logger.info("StateDB initialized at %s with WAL mode.", self.db_path)

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    def get_journal_mode(self) -> str:
        with self._lock:
            conn = self._get_connection()
            cursor = conn.execute("PRAGMA journal_mode;")
            row = cursor.fetchone()
            return str(row[0]) if row else ""

    def get_tables(self) -> List[str]:
        with self._lock:
            conn = self._get_connection()
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
            return [row[0] for row in cursor.fetchall()]

    # -------------------------------------------------------------
    # Task Operations
    # -------------------------------------------------------------
    def create_task(
        self,
        task_id: str,
        agent_name: str,
        priority_band: int = 2,
        payload: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
    ) -> None:
        with self._lock:
            conn = self._get_connection()
            payload_str = json.dumps(payload or {})
            with conn:
                conn.execute(
                    """
                    INSERT INTO tasks (task_id, agent_name, status, priority_band, payload_json, idempotency_key, updated_at)
                    VALUES (?, ?, 'CREATED', ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (task_id, agent_name, priority_band, payload_str, idempotency_key),
                )

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            conn = self._get_connection()
            cursor = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
            row = cursor.fetchone()
            if not row:
                return None
            res = dict(row)
            res["payload"] = json.loads(res.get("payload_json") or "{}")
            res["metadata"] = json.loads(res.get("metadata_json") or "{}")
            return res

    def update_task_status(
        self,
        task_id: str,
        status: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        with self._lock:
            conn = self._get_connection()
            meta_str = json.dumps(metadata or {})
            with conn:
                conn.execute(
                    """
                    UPDATE tasks
                    SET status = ?, metadata_json = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE task_id = ?
                    """,
                    (status, meta_str, task_id),
                )

    # -------------------------------------------------------------
    # Trace Operations
    # -------------------------------------------------------------
    def log_trace(self, task_id: str, step: str, details: str = "") -> None:
        with self._lock:
            conn = self._get_connection()
            with conn:
                conn.execute(
                    """
                    INSERT INTO task_traces (task_id, step, details, timestamp)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (task_id, step, details),
                )

    def get_traces(self, task_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            conn = self._get_connection()
            cursor = conn.execute(
                "SELECT * FROM task_traces WHERE task_id = ? ORDER BY id ASC",
                (task_id,),
            )
            return [dict(row) for row in cursor.fetchall()]
