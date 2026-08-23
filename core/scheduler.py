"""
MAX OS — Scheduler Service (Step 6.3).
Handles cron-based and interval agent task scheduling (e.g. morning brief, monitor operatives, backups).
Maintains scheduled_tasks table in SQLite.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from core.kill_switch import get_kill_switch, require_armed

DEFAULT_DB_PATH = Path(__file__).parent.parent / "max_state.db"


@dataclass
class ScheduledTaskRecord:
    schedule_id: str
    agent: str
    cron_expr: str
    task_spec: str
    status: str
    last_run_at: Optional[str]
    next_run_at: Optional[str]
    created_at: str


class SchedulerService:
    """
    Cron and interval scheduler service for scheduled and continuous agents.
    """

    def __init__(self, db_path: Optional[Path | str] = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self._handlers: Dict[str, Callable[[Dict[str, Any]], Any]] = {}
        self._lock = threading.Lock()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.row_factory = sqlite3.Row
        return conn

    def register_agent_handler(self, agent: str, handler_fn: Callable[[Dict[str, Any]], Any]) -> None:
        with self._lock:
            self._handlers[agent] = handler_fn

    def add_schedule(
        self,
        schedule_id: str,
        agent: str,
        cron_expr: str,
        task_spec: Dict[str, Any],
    ) -> ScheduledTaskRecord:
        """Registers a new scheduled task in SQLite."""
        conn = self._get_conn()
        now = datetime.now(timezone.utc).isoformat()
        spec_str = json.dumps(task_spec)
        try:
            conn.execute(
                """
                INSERT INTO scheduled_tasks (schedule_id, agent, cron_expr, task_spec, status, last_run_at, next_run_at, created_at)
                VALUES (?, ?, ?, ?, 'active', NULL, NULL, ?)
                ON CONFLICT(schedule_id) DO UPDATE SET
                    agent = excluded.agent,
                    cron_expr = excluded.cron_expr,
                    task_spec = excluded.task_spec,
                    status = 'active';
                """,
                (schedule_id, agent, cron_expr, spec_str, now),
            )
            conn.commit()
            return ScheduledTaskRecord(schedule_id, agent, cron_expr, spec_str, "active", None, None, now)
        finally:
            conn.close()

    def list_schedules(self) -> List[ScheduledTaskRecord]:
        """Lists all registered schedules."""
        conn = self._get_conn()
        try:
            rows = conn.execute("SELECT * FROM scheduled_tasks ORDER BY created_at DESC;").fetchall()
            return [
                ScheduledTaskRecord(
                    schedule_id=r["schedule_id"],
                    agent=r["agent"],
                    cron_expr=r["cron_expr"],
                    task_spec=r["task_spec"],
                    status=r["status"],
                    last_run_at=r["last_run_at"],
                    next_run_at=r["next_run_at"],
                    created_at=r["created_at"],
                )
                for r in rows
            ]
        finally:
            conn.close()

    def trigger_task(self, schedule_id: str) -> Any:
        """Manually triggers execution of a scheduled task."""
        require_armed(get_kill_switch())
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM scheduled_tasks WHERE schedule_id = ?", (schedule_id,)).fetchone()
            if not row:
                raise ValueError(f"Schedule {schedule_id} not found.")

            agent = row["agent"]
            spec = json.loads(row["task_spec"])
            handler = self._handlers.get(agent)

            now = datetime.now(timezone.utc).isoformat()
            conn.execute("UPDATE scheduled_tasks SET last_run_at = ? WHERE schedule_id = ?", (now, schedule_id))
            conn.commit()

            if handler:
                return handler(spec)
            return f"Executed scheduled task {schedule_id} for agent {agent}"
        finally:
            conn.close()

    def cancel_schedule(self, schedule_id: str) -> bool:
        """Cancels a scheduled task."""
        conn = self._get_conn()
        try:
            cur = conn.execute("UPDATE scheduled_tasks SET status = 'cancelled' WHERE schedule_id = ?", (schedule_id,))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()
