"""
MAX OS — Dead Letter Queue (DLQ)
Build Order: #15 (Layer 3E)
═══════════════════════════════════════════════════════

Captures tasks that exhaust all retries.
Allows querying dead tasks and requeuing them.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from src.infra import state_db

logger = logging.getLogger("max.core.dlq")


class DeadLetterQueue:
    """Manages dead letter task persistence and requeuing."""

    def push(self, task_id: str, agent: str, original_input: str, attempts_history: list[dict]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        attempts_json = json.dumps(attempts_history)

        state_db.execute(
            """
            INSERT INTO dead_letter_queue (task_id, agent, original_input, attempts_json, died_at, requeued)
            VALUES (?, ?, ?, ?, ?, 0)
            ON CONFLICT(task_id) DO UPDATE SET attempts_json = ?, died_at = ?
            """,
            (task_id, agent, original_input, attempts_json, now, attempts_json, now)
        )
        state_db.commit()
        logger.info("Pushed task '%s' to Dead Letter Queue", task_id)

    def list_dead_tasks(self) -> list[dict]:
        rows = state_db.fetchall("SELECT * FROM dead_letter_queue WHERE requeued = 0 ORDER BY died_at DESC")
        return [dict(r) for r in rows]

    def requeue(self, task_id: str) -> bool:
        row = state_db.fetchone("SELECT * FROM dead_letter_queue WHERE task_id = ?", (task_id,))
        if not row:
            return False

        from src.core.task_queue import get_queue
        q = get_queue()
        q.push(
            agent=row["agent"],
            intent="requeued_from_dlq",
            input_summary=row["original_input"],
            priority_band=1,
        )

        state_db.execute("UPDATE dead_letter_queue SET requeued = 1 WHERE task_id = ?", (task_id,))
        state_db.commit()
        logger.info("Requeued task '%s' from Dead Letter Queue", task_id)
        return True


_global_dlq: Optional[DeadLetterQueue] = None


def get_dlq() -> DeadLetterQueue:
    global _global_dlq
    if _global_dlq is None:
        _global_dlq = DeadLetterQueue()
    return _global_dlq
