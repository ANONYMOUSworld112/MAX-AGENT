"""
MAX OS — Fast Replay & Watch-and-Learn Engine (NeuralAgent 3.0 Integration).
Implements:
  1. Fast Replay Caching & High-Speed Macro Execution
  2. Visual Drift & UI Anchor Verification (with graceful LLM VLM Fallback)
  3. Watch & Learn Recording Suite (Synthesizes physical user demonstrations into verified semantic TaskPlans)
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.command_model import ActionObject, TaskPlan
from core.kill_switch import get_kill_switch, require_armed
from core.security.security_gate import RiskTier, SecurityGate
from core.single_tts_queue import speak

DEFAULT_REPLAY_DB_PATH = Path(__file__).parent.parent / "max_state.db"


@dataclass
class ReplayAnchor:
    name: str
    role: str = ""
    expected_window: str = ""
    relative_x: Optional[float] = None
    relative_y: Optional[float] = None


@dataclass
class FastReplayRecord:
    replay_id: str
    task_signature: str
    goal: str
    plan_data: Dict[str, Any]
    anchors: List[ReplayAnchor] = field(default_factory=list)
    avg_runtime_sec: float = 0.0
    execution_count: int = 0
    created_at: float = field(default_factory=time.time)
    last_executed: Optional[float] = None


@dataclass
class DriftCheckResult:
    drift_detected: bool
    matching_anchor_count: int
    total_anchor_count: int
    confidence: float
    details: str = ""


class FastReplayCatalog:
    """
    Persistent SQLite storage for compiled Fast Replays.
    """

    def __init__(self, db_path: Optional[Path | str] = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_REPLAY_DB_PATH
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
                CREATE TABLE IF NOT EXISTS fast_replays (
                    replay_id TEXT PRIMARY KEY,
                    task_signature TEXT UNIQUE NOT NULL,
                    goal TEXT NOT NULL,
                    plan_json TEXT NOT NULL,
                    anchors_json TEXT NOT NULL,
                    avg_runtime_sec REAL DEFAULT 0.0,
                    execution_count INTEGER DEFAULT 0,
                    created_at REAL NOT NULL,
                    last_executed REAL
                );
                """
            )
            conn.commit()
        finally:
            conn.close()

    def save_replay(self, goal: str, plan: TaskPlan, anchors: Optional[List[ReplayAnchor]] = None) -> FastReplayRecord:
        """Saves or updates a compiled TaskPlan in the Fast Replay catalog."""
        sig = self._compute_signature(goal)
        rid = f"replay_{uuid.uuid4().hex[:8]}"
        plan_dict = {
            "plan_id": plan.plan_id,
            "goal": plan.goal,
            "actions": [a.to_dict() for a in plan.actions],
        }
        anchor_list = [asdict(a) for a in (anchors or [])]

        conn = self._get_conn()
        now = time.time()
        try:
            conn.execute(
                """
                INSERT INTO fast_replays (replay_id, task_signature, goal, plan_json, anchors_json, avg_runtime_sec, execution_count, created_at, last_executed)
                VALUES (?, ?, ?, ?, ?, 0.0, 1, ?, ?)
                ON CONFLICT(task_signature) DO UPDATE SET
                    plan_json = excluded.plan_json,
                    anchors_json = excluded.anchors_json,
                    execution_count = execution_count + 1,
                    last_executed = excluded.last_executed;
                """,
                (rid, sig, goal, json.dumps(plan_dict), json.dumps(anchor_list), now, now),
            )
            conn.commit()
        finally:
            conn.close()

        return FastReplayRecord(
            replay_id=rid,
            task_signature=sig,
            goal=goal,
            plan_data=plan_dict,
            anchors=anchors or [],
            execution_count=1,
            created_at=now,
            last_executed=now,
        )

    def find_replay(self, goal: str) -> Optional[FastReplayRecord]:
        """Finds an existing Fast Replay matching the goal or signature."""
        sig = self._compute_signature(goal)
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM fast_replays WHERE task_signature = ?", (sig,)).fetchone()
            if not row:
                # Try fuzzy word match
                words = [w for w in goal.lower().split() if len(w) > 3]
                if words:
                    clause = "%" + "%".join(words) + "%"
                    row = conn.execute("SELECT * FROM fast_replays WHERE LOWER(goal) LIKE ? LIMIT 1", (clause,)).fetchone()

            if not row:
                return None

            plan_dict = json.loads(row["plan_json"])
            anchors_raw = json.loads(row["anchors_json"])
            anchors = [ReplayAnchor(**a) for a in anchors_raw]

            return FastReplayRecord(
                replay_id=row["replay_id"],
                task_signature=row["task_signature"],
                goal=row["goal"],
                plan_data=plan_dict,
                anchors=anchors,
                avg_runtime_sec=float(row["avg_runtime_sec"]),
                execution_count=int(row["execution_count"]),
                created_at=float(row["created_at"]),
                last_executed=float(row["last_executed"]) if row["last_executed"] else None,
            )
        finally:
            conn.close()

    def list_all_replays(self) -> List[FastReplayRecord]:
        """Lists all registered fast replays."""
        conn = self._get_conn()
        replays: List[FastReplayRecord] = []
        try:
            for row in conn.execute("SELECT * FROM fast_replays ORDER BY execution_count DESC"):
                plan_dict = json.loads(row["plan_json"])
                anchors = [ReplayAnchor(**a) for a in json.loads(row["anchors_json"])]
                replays.append(
                    FastReplayRecord(
                        replay_id=row["replay_id"],
                        task_signature=row["task_signature"],
                        goal=row["goal"],
                        plan_data=plan_dict,
                        anchors=anchors,
                        avg_runtime_sec=float(row["avg_runtime_sec"]),
                        execution_count=int(row["execution_count"]),
                        created_at=float(row["created_at"]),
                        last_executed=float(row["last_executed"]) if row["last_executed"] else None,
                    )
                )
        finally:
            conn.close()
        return replays

    def _compute_signature(self, goal: str) -> str:
        """Computes a canonical normalized task signature."""
        cleaned = " ".join(sorted(set(re.findall(r"\w+", goal.lower()))))
        return hashlib.sha256(cleaned.encode("utf-8")).hexdigest()[:16]


class VisualDriftDetector:
    """
    Checks whether recorded UI anchors match the current active screen state.
    Triggers graceful fallback to full LLM VLM reasoning when visual drift is detected.
    """

    def check_drift(
        self,
        anchors: List[ReplayAnchor],
        active_window: str,
        current_elements: List[Dict[str, Any]],
    ) -> DriftCheckResult:
        """Evaluates whether current screen layout has drifted from recorded replay anchors."""
        if not anchors:
            return DriftCheckResult(drift_detected=False, matching_anchor_count=0, total_anchor_count=0, confidence=1.0, details="No anchors specified.")

        matched = 0
        element_names = {str(el.get("name") or el.get("text") or "").lower() for el in current_elements}
        active_win_lower = active_window.lower()

        for anc in anchors:
            # Check window anchor
            if anc.expected_window and anc.expected_window.lower() in active_win_lower:
                matched += 1
                continue
            # Check element name
            if anc.name.lower() in element_names:
                matched += 1

        match_ratio = matched / max(1, len(anchors))
        drift = match_ratio < 0.60
        details = f"Anchor match ratio: {matched}/{len(anchors)} ({match_ratio:.0%}). Active Window: '{active_window}'"

        return DriftCheckResult(
            drift_detected=drift,
            matching_anchor_count=matched,
            total_anchor_count=len(anchors),
            confidence=match_ratio,
            details=details,
        )


class WatchAndLearnRecorder:
    """
    Records physical user demonstrations (mouse clicks, keystrokes, launches)
    and compiles them into a verified semantic TaskPlan.
    """

    def __init__(self):
        self._is_recording = False
        self._recorded_events: List[Dict[str, Any]] = []
        self._start_time: float = 0.0

    def start_recording(self, goal: str = "User Demonstration") -> None:
        """Starts recording user desktop interactions."""
        self._is_recording = True
        self._recorded_events = []
        self._start_time = time.time()
        speak(f"Watch and Learn recording started for: '{goal}'. Demonstrate your workflow now, Sir.")

    def record_action(self, action_type: str, target: str, value: Optional[str] = None, element_descriptor: Optional[Dict[str, Any]] = None) -> None:
        """Logs an interaction event."""
        if not self._is_recording:
            return
        self._recorded_events.append({
            "type": action_type,
            "target": target,
            "value": value,
            "element": element_descriptor or {},
            "timestamp": time.time() - self._start_time,
        })

    def stop_and_compile(self, goal: str) -> Tuple[TaskPlan, List[ReplayAnchor]]:
        """Stops recording and compiles events into a verified semantic TaskPlan and UI anchors."""
        self._is_recording = False
        actions: List[ActionObject] = []
        anchors: List[ReplayAnchor] = []

        for ev in self._recorded_events:
            act_type = ev.get("type", "click")
            target = ev.get("target", "target")
            val = ev.get("value")
            el = ev.get("element", {})

            actions.append(
                ActionObject(
                    action_id=f"act_{uuid.uuid4().hex[:6]}",
                    type=act_type,
                    target=target,
                    value=val,
                    semantic_target=el.get("name") or target,
                    risk_tier=RiskTier.TIER_0 if act_type in ("open_application", "observe") else RiskTier.TIER_1,
                )
            )

            if el.get("name"):
                anchors.append(
                    ReplayAnchor(
                        name=el.get("name"),
                        role=el.get("role", "control"),
                        expected_window=el.get("window", ""),
                    )
                )

        if not actions:
            actions.append(
                ActionObject(
                    action_id=f"act_{uuid.uuid4().hex[:6]}",
                    type="observe",
                    target="screen",
                    risk_tier=RiskTier.TIER_0,
                )
            )

        plan = TaskPlan(
            plan_id=f"plan_watch_learn_{uuid.uuid4().hex[:6]}",
            goal=goal,
            actions=actions,
        )

        speak(f"Watch and Learn complete. Compiled {len(actions)} actions into reusable Fast Replay, Sir.")
        return plan, anchors


class FastReplayEngine:
    """
    Unified Fast Replay Engine.
    Combines Catalog, Drift Detector, and Watch & Learn Recorder.
    """

    def __init__(self, db_path: Optional[Path | str] = None):
        self.catalog = FastReplayCatalog(db_path=db_path)
        self.drift_detector = VisualDriftDetector()
        self.recorder = WatchAndLearnRecorder()

    def get_or_compile_plan(
        self,
        goal: str,
        current_window: str = "",
        current_elements: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[Optional[TaskPlan], bool]:
        """
        Attempts to fetch a cached Fast Replay.
        Returns: (TaskPlan, is_fast_replay_cache_hit)
        """
        record = self.catalog.find_replay(goal)
        if not record:
            return None, False

        # Verify UI anchors if screen elements available
        if current_elements:
            drift = self.drift_detector.check_drift(record.anchors, current_window, current_elements)
            if drift.drift_detected:
                return None, False

        # Reconstruct TaskPlan from replay record
        raw_actions = record.plan_data.get("actions", [])
        actions = []
        for a in raw_actions:
            tier_val = a.get("risk_tier", 0)
            actions.append(
                ActionObject(
                    action_id=a.get("action_id", f"act_{uuid.uuid4().hex[:6]}"),
                    type=a.get("type", "observe"),
                    target=a.get("target", ""),
                    value=a.get("value"),
                    semantic_target=a.get("semantic_target"),
                    risk_tier=RiskTier(tier_val) if isinstance(tier_val, int) else RiskTier.TIER_0,
                    expected_result=a.get("expected_result", {}),
                    payload=a.get("payload", {}),
                )
            )

        plan = TaskPlan(
            plan_id=record.plan_data.get("plan_id", f"replay_{record.replay_id}"),
            goal=record.goal,
            actions=actions,
        )
        return plan, True
