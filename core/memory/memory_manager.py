"""
MAX OS — 5-Layer Memory Context Heap (Step 6.4).
On-device persistent memory:
  Layer 1: Identity Memory (who the user is)
  Layer 2: Preference Memory (explicit & inferred preferences)
  Layer 3: Behavioral Memory (learned patterns with Bayesian confidence)
  Layer 4: Project Memory (per-project context)
  Layer 5: Conversational Memory (working memory with promotion)
Audit log: memory_access_log.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "max_state.db"


@dataclass
class IdentityMemory:
    key: str
    value: str
    source: str = "explicit"
    confidence: float = 1.0


@dataclass
class PreferenceMemory:
    category: str
    key: str
    value: str
    source: str = "explicit"
    confidence: float = 1.0
    context: Optional[str] = None


@dataclass
class BehavioralPattern:
    pattern_id: int
    pattern_type: str
    description: str
    evidence: List[Any]
    observation_count: int
    confidence: float
    active: bool


@dataclass
class ProjectMemory:
    project_id: str
    key: str
    value: str
    source: str = "observed"
    confidence: float = 0.8


@dataclass
class MemorySearchResult:
    layer: str
    key: str
    value: str
    confidence: float


class MemoryManager:
    """
    Unified manager for the 5-layer Memory Context Heap.
    """

    def __init__(self, db_path: Optional[Path | str] = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.row_factory = sqlite3.Row
        return conn

    def _log_access(self, layer: str, key_accessed: str, accessed_by: str, purpose: str = "") -> None:
        conn = self._get_conn()
        now = datetime.now(timezone.utc).isoformat()
        try:
            conn.execute(
                """
                INSERT INTO memory_access_log (layer, key_accessed, accessed_by, purpose, included_in_llm_call, accessed_at)
                VALUES (?, ?, ?, ?, 0, ?);
                """,
                (layer, key_accessed, accessed_by, purpose, now),
            )
            conn.commit()
        finally:
            conn.close()

    # --- Layer 1: Identity ---
    def set_identity(self, key: str, value: str, source: str = "explicit", confidence: float = 1.0) -> None:
        conn = self._get_conn()
        now = datetime.now(timezone.utc).isoformat()
        try:
            conn.execute(
                """
                INSERT INTO memory_identity (key, value, source, confidence, set_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    source = excluded.source,
                    confidence = excluded.confidence,
                    updated_at = excluded.updated_at;
                """,
                (key, value, source, confidence, now, now),
            )
            conn.commit()
        finally:
            conn.close()

    def get_identity(self, key: str, accessed_by: str = "main_agent") -> Optional[str]:
        self._log_access("identity", key, accessed_by)
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT value FROM memory_identity WHERE key = ?", (key,)).fetchone()
            return row["value"] if row else None
        finally:
            conn.close()

    # --- Layer 2: Preferences ---
    def set_preference(
        self,
        category: str,
        key: str,
        value: str,
        source: str = "explicit",
        confidence: float = 1.0,
        context: Optional[str] = None,
    ) -> None:
        conn = self._get_conn()
        now = datetime.now(timezone.utc).isoformat()
        try:
            conn.execute(
                """
                INSERT INTO memory_preferences (category, key, value, source, confidence, context, set_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(category, key) DO UPDATE SET
                    value = excluded.value,
                    source = excluded.source,
                    confidence = excluded.confidence,
                    context = excluded.context,
                    updated_at = excluded.updated_at;
                """,
                (category, key, value, source, confidence, context, now, now),
            )
            conn.commit()
        finally:
            conn.close()

    def get_preference(self, category: str, key: str, accessed_by: str = "main_agent") -> Optional[str]:
        self._log_access("preference", f"{category}.{key}", accessed_by)
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT value FROM memory_preferences WHERE category = ? AND key = ?", (category, key)).fetchone()
            return row["value"] if row else None
        finally:
            conn.close()

    # --- Layer 3: Behavioral Patterns ---
    def record_behavioral_observation(
        self,
        pattern_type: str,
        description: str,
        evidence_item: Any,
    ) -> BehavioralPattern:
        conn = self._get_conn()
        now = datetime.now(timezone.utc).isoformat()
        try:
            cur = conn.execute("SELECT * FROM memory_behavioral WHERE description = ?", (description,))
            row = cur.fetchone()
            if row:
                evidence = json.loads(row["evidence"])
                evidence.append(evidence_item)
                count = row["observation_count"] + 1
                # Bayesian-style confidence growth: 1 - 0.7 * (0.8^count)
                new_conf = min(0.99, 1.0 - (0.7 * (0.8 ** count)))
                conn.execute(
                    """
                    UPDATE memory_behavioral
                    SET evidence = ?, observation_count = ?, confidence = ?, last_seen = ?, active = 1
                    WHERE pattern_id = ?;
                    """,
                    (json.dumps(evidence), count, new_conf, now, row["pattern_id"]),
                )
                pid = row["pattern_id"]
            else:
                evidence = [evidence_item]
                count = 1
                new_conf = 0.35
                cur_ins = conn.execute(
                    """
                    INSERT INTO memory_behavioral (pattern_type, description, evidence, observation_count, confidence, first_seen, last_seen, decay_after_days, active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 30, 1);
                    """,
                    (pattern_type, description, json.dumps(evidence), count, new_conf, now, now),
                )
                pid = cur_ins.lastrowid

            conn.commit()
            return BehavioralPattern(pid, pattern_type, description, evidence, count, new_conf, True)
        finally:
            conn.close()

    # --- Layer 4: Project Memory ---
    def set_project_context(
        self,
        project_id: str,
        key: str,
        value: str,
        source: str = "observed",
        confidence: float = 0.8,
    ) -> None:
        conn = self._get_conn()
        now = datetime.now(timezone.utc).isoformat()
        try:
            conn.execute(
                """
                INSERT INTO memory_project (project_id, key, value, source, confidence, set_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id, key) DO UPDATE SET
                    value = excluded.value,
                    source = excluded.source,
                    confidence = excluded.confidence,
                    updated_at = excluded.updated_at;
                """,
                (project_id, key, value, source, confidence, now, now),
            )
            conn.commit()
        finally:
            conn.close()

    def get_project_context(self, project_id: str, key: str, accessed_by: str = "main_agent") -> Optional[str]:
        self._log_access("project", f"{project_id}.{key}", accessed_by)
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT value FROM memory_project WHERE project_id = ? AND key = ?", (project_id, key)).fetchone()
            return row["value"] if row else None
        finally:
            conn.close()

    # --- Layer 5: Conversational Working Memory ---
    def add_conversation_entry(
        self,
        session_id: str,
        content: str,
        content_type: str = "context",
        importance: float = 0.5,
    ) -> int:
        conn = self._get_conn()
        now = datetime.now(timezone.utc).isoformat()
        try:
            cur = conn.execute(
                """
                INSERT INTO memory_conversational (session_id, content, content_type, importance, created_at)
                VALUES (?, ?, ?, ?, ?);
                """,
                (session_id, content, content_type, importance, now),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    # --- Cross-Layer Keyword & Semantic Search ---
    def search(self, query: str, limit: int = 5) -> List[MemorySearchResult]:
        """Searches across all 5 memory layers."""
        conn = self._get_conn()
        results: List[MemorySearchResult] = []
        q_term = f"%{query}%"
        try:
            # Identity
            for r in conn.execute("SELECT key, value, confidence FROM memory_identity WHERE key LIKE ? OR value LIKE ?", (q_term, q_term)):
                results.append(MemorySearchResult("identity", r["key"], r["value"], r["confidence"]))

            # Preferences
            for r in conn.execute("SELECT category || '.' || key as k, value, confidence FROM memory_preferences WHERE key LIKE ? OR value LIKE ?", (q_term, q_term)):
                results.append(MemorySearchResult("preference", r["k"], r["value"], r["confidence"]))

            # Project
            for r in conn.execute("SELECT project_id || '.' || key as k, value, confidence FROM memory_project WHERE key LIKE ? OR value LIKE ?", (q_term, q_term)):
                results.append(MemorySearchResult("project", r["k"], r["value"], r["confidence"]))

            # Behavioral
            for r in conn.execute("SELECT pattern_type as k, description as value, confidence FROM memory_behavioral WHERE description LIKE ? AND active = 1", (q_term,)):
                results.append(MemorySearchResult("behavioral", r["k"], r["value"], r["confidence"]))

            # Conversational
            for r in conn.execute("SELECT content_type as k, content as value, importance as confidence FROM memory_conversational WHERE content LIKE ?", (q_term,)):
                results.append(MemorySearchResult("conversational", r["k"], r["value"], r["confidence"]))

            results.sort(key=lambda x: x.confidence, reverse=True)
            return results[:limit]
        finally:
            conn.close()
