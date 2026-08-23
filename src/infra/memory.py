"""
MAX OS — 5-Layer Persistent Memory Context Heap
═══════════════════════════════════════════════════════

Manages identity, preferences, behavioral patterns, project context,
and short-term conversational working memory with promotion.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from src.infra import state_db

logger = logging.getLogger("max.infra.memory")


class MemoryHeap:
    """Interface for 5-layer persistent memory store."""

    # ── Layer 1: Identity ─────────────────────────────────────
    def get_identity(self, key: str) -> Optional[str]:
        row = state_db.fetchone("SELECT value FROM memory_identity WHERE key = ?", (key,))
        return row["value"] if row else None

    def set_identity(self, key: str, value: str, source: str = "explicit", confidence: float = 1.0) -> None:
        now = datetime.now(timezone.utc).isoformat()
        state_db.execute(
            """
            INSERT INTO memory_identity (key, value, source, confidence, set_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = ?, source = ?, confidence = ?, updated_at = ?
            """,
            (key, value, source, confidence, now, now, value, source, confidence, now)
        )
        state_db.commit()

    # ── Layer 2: Preferences ──────────────────────────────────
    def get_preference(self, category: str, key: str) -> Optional[str]:
        row = state_db.fetchone(
            "SELECT value FROM memory_preferences WHERE category = ? AND key = ?",
            (category, key)
        )
        return row["value"] if row else None

    def set_preference(self, category: str, key: str, value: str, source: str = "explicit", confidence: float = 1.0) -> None:
        now = datetime.now(timezone.utc).isoformat()
        state_db.execute(
            """
            INSERT INTO memory_preferences (category, key, value, source, confidence, set_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(category, key) DO UPDATE SET value = ?, source = ?, confidence = ?, updated_at = ?
            """,
            (category, key, value, source, confidence, now, now, value, source, confidence, now)
        )
        state_db.commit()

    # ── Layer 3: Behavioral Patterns ─────────────────────────
    def record_behavioral_pattern(self, pattern_type: str, description: str, evidence_item: dict) -> None:
        now = datetime.now(timezone.utc).isoformat()
        row = state_db.fetchone(
            "SELECT pattern_id, evidence, observation_count, confidence FROM memory_behavioral WHERE pattern_type = ? AND description = ?",
            (pattern_type, description)
        )
        if row:
            ev_list = json.loads(row["evidence"])
            ev_list.append(evidence_item)
            new_count = row["observation_count"] + 1
            new_conf = min(1.0, row["confidence"] + 0.1)
            state_db.execute(
                """
                UPDATE memory_behavioral
                SET evidence = ?, observation_count = ?, confidence = ?, last_seen = ?
                WHERE pattern_id = ?
                """,
                (json.dumps(ev_list), new_count, new_conf, now, row["pattern_id"])
            )
        else:
            ev_json = json.dumps([evidence_item])
            state_db.execute(
                """
                INSERT INTO memory_behavioral (pattern_type, description, evidence, observation_count, confidence, first_seen, last_seen, active)
                VALUES (?, ?, ?, 1, 0.3, ?, ?, 1)
                """,
                (pattern_type, description, ev_json, now, now)
            )
        state_db.commit()

    # ── Layer 4: Project Memory ──────────────────────────────
    def get_project_context(self, project_id: str, key: str) -> Optional[str]:
        row = state_db.fetchone("SELECT value FROM memory_project WHERE project_id = ? AND key = ?", (project_id, key))
        return row["value"] if row else None

    def set_project_context(self, project_id: str, key: str, value: str, source: str = "observed") -> None:
        now = datetime.now(timezone.utc).isoformat()
        state_db.execute(
            """
            INSERT INTO memory_project (project_id, key, value, source, confidence, set_at, updated_at)
            VALUES (?, ?, ?, ?, 0.8, ?, ?)
            ON CONFLICT(project_id, key) DO UPDATE SET value = ?, source = ?, updated_at = ?
            """,
            (project_id, key, value, source, now, now, value, source, now)
        )
        state_db.commit()

    # ── Layer 5: Conversational Working Memory ───────────────
    def push_conversational(self, session_id: str, content: str, content_type: str = "context", importance: float = 0.5) -> int:
        now = datetime.now(timezone.utc).isoformat()
        cur = state_db.execute(
            """
            INSERT INTO memory_conversational (session_id, content, content_type, importance, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (session_id, content, content_type, importance, now)
        )
        state_db.commit()
        return cur.lastrowid

    def list_session_memory(self, session_id: str) -> list[dict]:
        rows = state_db.fetchall(
            "SELECT * FROM memory_conversational WHERE session_id = ? ORDER BY created_at ASC",
            (session_id,)
        )
        return [dict(r) for r in rows]


_global_memory: Optional[MemoryHeap] = None


def get_memory() -> MemoryHeap:
    global _global_memory
    if _global_memory is None:
        _global_memory = MemoryHeap()
    return _global_memory
