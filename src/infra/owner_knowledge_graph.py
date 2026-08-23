"""
MAX OS — Deep Owner Knowledge Graph & Bayesian Habit Matrix (Supreme Layer).
══════════════════════════════════════════════════════════════════════════════
Maintains deep parametric & non-parametric memory about the system's Owner:
1. Biographical Profile & Clearance Level (Identity, Voiceprint, Biometric token).
2. Behavioral Patterns & Habits with Bayesian Confidence Learning.
3. Daily Routines & Focus Windows.
4. Active Projects, Technical Goals, & Coding Preferences.
5. Continuous Self-Improvement Heuristics.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("max.infra.owner_knowledge_graph")

DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "max_state.db"


@dataclass
class OwnerProfile:
    owner_id: str = "primary_owner"
    full_name: str = "Tony Stark"
    alias: str = "Sir"
    clearance_level: str = "ALPHA_CREATOR"
    preferred_voice: str = "JARVIS_BRITISH_PRO"
    preferred_ide: str = "VSCode / Antigravity"
    preferred_shell: str = "bash"
    primary_language: str = "Python / TypeScript"
    timezone: str = "UTC"
    face_auth_enrolled: bool = True
    voice_auth_enrolled: bool = True
    bio: str = "Visionary creator, lead architect, and primary operator."
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class BehavioralHabit:
    habit_id: str
    category: str  # coding, communication, schedule, workspace, security
    description: str
    observation_count: int = 1
    confidence: float = 0.5
    preferred_action: str = ""
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    last_observed: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class OwnerKnowledgeGraph:
    """
    Super-Advanced Context Memory & Knowledge Graph for the Owner.
    Stores and evolves understanding of the Owner across all sessions.
    """

    def __init__(self, db_path: Optional[Path | str] = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self._init_tables()
        self._ensure_default_profile()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self) -> None:
        conn = self._get_conn()
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS owner_profile (
                    owner_id TEXT PRIMARY KEY,
                    full_name TEXT NOT NULL,
                    alias TEXT NOT NULL,
                    clearance_level TEXT NOT NULL,
                    preferred_voice TEXT NOT NULL,
                    preferred_ide TEXT NOT NULL,
                    preferred_shell TEXT NOT NULL,
                    primary_language TEXT NOT NULL,
                    timezone TEXT NOT NULL,
                    face_auth_enrolled INTEGER NOT NULL,
                    voice_auth_enrolled INTEGER NOT NULL,
                    bio TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS owner_habits (
                    habit_id TEXT PRIMARY KEY,
                    category TEXT NOT NULL,
                    description TEXT NOT NULL,
                    observation_count INTEGER NOT NULL DEFAULT 1,
                    confidence REAL NOT NULL DEFAULT 0.5,
                    preferred_action TEXT,
                    evidence TEXT NOT NULL,
                    last_observed TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS owner_project_memory (
                    project_id TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    category TEXT DEFAULT 'general',
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (project_id, key)
                );

                CREATE TABLE IF NOT EXISTS self_evolution_metrics (
                    metric_id TEXT PRIMARY KEY,
                    task_type TEXT NOT NULL,
                    success_rate REAL NOT NULL,
                    avg_latency_ms REAL NOT NULL,
                    optimal_strategy TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            conn.commit()
        finally:
            conn.close()

    def _ensure_default_profile(self) -> None:
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT owner_id FROM owner_profile WHERE owner_id = 'primary_owner';").fetchone()
            if not row:
                prof = OwnerProfile()
                conn.execute(
                    """
                    INSERT INTO owner_profile (
                        owner_id, full_name, alias, clearance_level, preferred_voice,
                        preferred_ide, preferred_shell, primary_language, timezone,
                        face_auth_enrolled, voice_auth_enrolled, bio, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        prof.owner_id, prof.full_name, prof.alias, prof.clearance_level,
                        prof.preferred_voice, prof.preferred_ide, prof.preferred_shell,
                        prof.primary_language, prof.timezone, int(prof.face_auth_enrolled),
                        int(prof.voice_auth_enrolled), prof.bio, prof.created_at, prof.updated_at,
                    ),
                )
                conn.commit()
        finally:
            conn.close()

    # ── Profile Management ────────────────────────────────────
    def get_profile(self, owner_id: str = "primary_owner") -> OwnerProfile:
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM owner_profile WHERE owner_id = ?;", (owner_id,)).fetchone()
            if row:
                return OwnerProfile(
                    owner_id=row["owner_id"],
                    full_name=row["full_name"],
                    alias=row["alias"],
                    clearance_level=row["clearance_level"],
                    preferred_voice=row["preferred_voice"],
                    preferred_ide=row["preferred_ide"],
                    preferred_shell=row["preferred_shell"],
                    primary_language=row["primary_language"],
                    timezone=row["timezone"],
                    face_auth_enrolled=bool(row["face_auth_enrolled"]),
                    voice_auth_enrolled=bool(row["voice_auth_enrolled"]),
                    bio=row["bio"] or "",
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
            return OwnerProfile()
        finally:
            conn.close()

    def update_profile(self, **kwargs) -> OwnerProfile:
        prof = self.get_profile()
        for k, v in kwargs.items():
            if hasattr(prof, k):
                setattr(prof, k, v)
        prof.updated_at = datetime.now(timezone.utc).isoformat()

        conn = self._get_conn()
        try:
            conn.execute(
                """
                UPDATE owner_profile SET
                    full_name = ?, alias = ?, clearance_level = ?, preferred_voice = ?,
                    preferred_ide = ?, preferred_shell = ?, primary_language = ?, timezone = ?,
                    face_auth_enrolled = ?, voice_auth_enrolled = ?, bio = ?, updated_at = ?
                WHERE owner_id = ?;
                """,
                (
                    prof.full_name, prof.alias, prof.clearance_level, prof.preferred_voice,
                    prof.preferred_ide, prof.preferred_shell, prof.primary_language, prof.timezone,
                    int(prof.face_auth_enrolled), int(prof.voice_auth_enrolled), prof.bio,
                    prof.updated_at, prof.owner_id,
                ),
            )
            conn.commit()
            return prof
        finally:
            conn.close()

    # ── Bayesian Habit Learning ───────────────────────────────
    def observe_habit(
        self,
        category: str,
        description: str,
        preferred_action: str = "",
        evidence_payload: Optional[Dict[str, Any]] = None,
    ) -> BehavioralHabit:
        """
        Records an observation of owner behavior and updates Bayesian confidence scaling.
        """
        import uuid
        now = datetime.now(timezone.utc).isoformat()
        evidence_item = evidence_payload or {"timestamp": now}

        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM owner_habits WHERE category = ? AND description = ?;",
                (category, description),
            ).fetchone()

            if row:
                habit_id = row["habit_id"]
                obs_count = row["observation_count"] + 1
                evidence_list = json.loads(row["evidence"])
                evidence_list.append(evidence_item)
                # Bayesian confidence scaling formula
                confidence = min(0.99, row["confidence"] + 0.08)
                action = preferred_action or row["preferred_action"]

                conn.execute(
                    """
                    UPDATE owner_habits
                    SET observation_count = ?, confidence = ?, preferred_action = ?, evidence = ?, last_observed = ?
                    WHERE habit_id = ?;
                    """,
                    (obs_count, confidence, action, json.dumps(evidence_list[-20:]), now, habit_id),
                )
            else:
                habit_id = f"habit_{uuid.uuid4().hex[:8]}"
                obs_count = 1
                confidence = 0.50
                conn.execute(
                    """
                    INSERT INTO owner_habits (habit_id, category, description, observation_count, confidence, preferred_action, evidence, last_observed)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (habit_id, category, description, obs_count, confidence, preferred_action, json.dumps([evidence_item]), now),
                )

            conn.commit()
            return BehavioralHabit(
                habit_id=habit_id,
                category=category,
                description=description,
                observation_count=obs_count,
                confidence=confidence,
                preferred_action=preferred_action,
                evidence=[evidence_item],
                last_observed=now,
            )
        finally:
            conn.close()

    def get_all_habits(self, min_confidence: float = 0.4) -> List[BehavioralHabit]:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM owner_habits WHERE confidence >= ? ORDER BY confidence DESC;",
                (min_confidence,),
            ).fetchall()
            return [
                BehavioralHabit(
                    habit_id=r["habit_id"],
                    category=r["category"],
                    description=r["description"],
                    observation_count=r["observation_count"],
                    confidence=r["confidence"],
                    preferred_action=r["preferred_action"] or "",
                    evidence=json.loads(r["evidence"]) if r["evidence"] else [],
                    last_observed=r["last_observed"],
                )
                for r in rows
            ]
        finally:
            conn.close()

    # ── Project Context Memory ────────────────────────────────
    def set_project_fact(self, project_id: str, key: str, value: str, category: str = "general") -> None:
        now = datetime.now(timezone.utc).isoformat()
        conn = self._get_conn()
        try:
            conn.execute(
                """
                INSERT INTO owner_project_memory (project_id, key, value, category, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(project_id, key) DO UPDATE SET value = ?, category = ?, updated_at = ?;
                """,
                (project_id, key, value, category, now, value, category, now),
            )
            conn.commit()
        finally:
            conn.close()

    def get_project_facts(self, project_id: str) -> Dict[str, str]:
        conn = self._get_conn()
        try:
            rows = conn.execute("SELECT key, value FROM owner_project_memory WHERE project_id = ?;", (project_id,)).fetchall()
            return {r["key"]: r["value"] for r in rows}
        finally:
            conn.close()

    # ── Full Context Prompt Synthesis ─────────────────────────
    def synthesize_owner_context_block(self) -> str:
        """
        Synthesizes the complete, high-density system context block injected into every agent prompt.
        """
        prof = self.get_profile()
        habits = self.get_all_habits(min_confidence=0.5)

        lines = [
            "═════════════════════════════════════════════════════════════════════════",
            f"🧠 JARVIS DEEP OWNER CONTEXT & BIOMETRIC PROFILE",
            "═════════════════════════════════════════════════════════════════════════",
            f"• Owner Name    : {prof.full_name} (Address as '{prof.alias}')",
            f"• Clearance     : {prof.clearance_level} (Highest Authority)",
            f"• Preferred Voice: {prof.preferred_voice}",
            f"• Dev Stack     : {prof.primary_language} | IDE: {prof.preferred_ide} | Shell: {prof.preferred_shell}",
            f"• Timezone      : {prof.timezone}",
            f"• Biometric Auth: Face Auth: {'Enrolled' if prof.face_auth_enrolled else 'Pending'} | Voice: {'Enrolled' if prof.voice_auth_enrolled else 'Pending'}",
            "",
            "📊 Bayesian Learned Habits & Operator Patterns:",
        ]

        if habits:
            for h in habits[:6]:
                lines.append(f"  - [{h.category.upper()}] {h.description} (Confidence: {h.confidence * 100:.0f}%, Observed: {h.observation_count}x)")
        else:
            lines.append("  - [DEFAULT] Prefers high-velocity concise outputs and proactive execution.")

        lines.append("═════════════════════════════════════════════════════════════════════════")
        return "\n".join(lines)
