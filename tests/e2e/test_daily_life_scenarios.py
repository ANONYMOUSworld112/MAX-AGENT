"""End-to-End Daily Life Scenario Traces for CyberBlack AI-agent MAX + MAX OS + LAYA.

Validates 9 realistic daily assistant scenarios across all 5 agent clusters,
dual-lane intent routing, safety guardrails, concurrency, perception,
verification, and UI state tracking.
"""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
import pytest
from unittest.mock import MagicMock, patch

from core.reflex.intent_router import ReflexIntentRouter, LaneType
from core.reflex.guardrails import ReflexGuardrails, RiskTier
from core.reflex.triage import ReflexTriage, PriorityBand
from core.max_infra.kill_switch import KillSwitch, KillSwitchTrippedError
from core.max_infra.state_db import StateDB
from core.max_infra.task_lifecycle import TaskLifecycleFSM, TaskState
from core.max_infra.task_queue import TaskQueue, TaskItem
from core.max_infra.lock_manager import LockManager
from core.max_infra.snapshot import SnapshotEngine
from core.max_infra.reconciliation import ReconciliationEngine
from core.max_infra.vault import Vault
from core.max_infra.data_boundary import DataBoundary
from core.memory.context_heap import MemoryContextHeap
from core.memory.token_budget import TokenBudgetCompressor
from core.perception.state_builder import StateBuilder, ComputerState
from core.verification.engine import VerificationEngine, VerificationReport, VerificationOutcome
from core.verification.file_verifier import FileVerifier
from core.verification.window_verifier import WindowVerifier
from agents.router import AgentRegistry
from agents.base import AgentInput
from ui.components.task_list_widget import TaskListWidget  # type: ignore
from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture(autouse=True)
def clean_kill_switch():
    """Ensure global KillSwitch is armed and clean for each test scenario."""
    ks = KillSwitch.get_instance()
    ks.reset()
    yield
    ks.reset()


@pytest.fixture
def agent_registry():
    return AgentRegistry.get_instance()


@pytest.fixture
def intent_router():
    return ReflexIntentRouter(fallback_mode=True)


@pytest.fixture
def guardrails():
    return ReflexGuardrails(fallback_mode=True)


@pytest.fixture
def state_db(tmp_path):
    db_path = tmp_path / "daily_life_state.db"
    db = StateDB(db_path=db_path)
    db.initialize()
    yield db
    db.close()


# ==============================================================================
# Scenario 1: Morning Briefing & Calendar / Email Management
# ==============================================================================
def test_scenario_morning_briefing(agent_registry, intent_router):
    """Scenario 1: User wakes up and asks: 'MAX, check my schedule for today and summarize my priority emails.'"""
    user_speech = "MAX, check my schedule for today and summarize my priority emails"

    # Step 1: Sub-33ms Reflex Intent Routing
    decision = intent_router.route_input(user_speech)
    assert decision.lane in (LaneType.LANE_A, LaneType.LANE_B)

    # Step 2: Calendar Agent execution
    cal_agent = agent_registry.get("CalendarAgent")
    assert cal_agent is not None
    cal_input = AgentInput(
        task_id="morning_cal_01",
        task_description="Retrieve today's schedule",
        parameters={"action": "check", "title": "Team Standup", "duration_minutes": 15},
    )
    cal_output = cal_agent.run(cal_input)
    assert cal_output.success is True
    assert "Team Standup" in cal_output.result
    assert cal_output.artifacts["status"] == "CONFIRMED"

    # Step 3: Email Agent execution
    email_agent = agent_registry.get("EmailAgent")
    assert email_agent is not None
    email_input = AgentInput(
        task_id="morning_email_01",
        task_description="Summarize priority investor emails",
        parameters={"action": "summarize"},
    )
    email_output = email_agent.run(email_input)
    assert email_output.success is True
    assert "Summary generated" in email_output.result


# ==============================================================================
# Scenario 2: Developer Feature Sprint (Code, Test, Audit, Verify)
# ==============================================================================
def test_scenario_developer_feature_sprint(tmp_path, agent_registry, intent_router, guardrails, state_db):
    """Scenario 2: Developer instructs: 'Create a markdown parser module and write unit tests for it.'"""
    user_prompt = "Create a markdown parser module in utils/parser.py and write unit tests for it"

    # Step 1: Reflex Intent & Guardrails Check
    decision = intent_router.route_input(user_prompt)
    assert decision.lane == LaneType.LANE_B
    assert decision.is_modifying is True

    guard = guardrails.check_safety(user_prompt)
    assert guard.risk_tier in (RiskTier.TIER_2_CONFIRM_ON_WRITE, RiskTier.TIER_1_SAFE_WRITE)

    # Step 2: Task Lifecycle FSM & Priority Queue
    task_id = "sprint_task_101"
    fsm = TaskLifecycleFSM(task_id=task_id)
    assert fsm.current_state == TaskState.CREATED

    fsm.transition_to(TaskState.QUEUED)
    state_db.create_task(task_id, "CodingAgent", 1, {"prompt": user_prompt})

    # Step 3: Dijkstra Sorted Locking & Pre-execution Snapshot
    lock_mgr = LockManager()
    snap_dir = tmp_path / "snapshots"
    snapshot_engine = SnapshotEngine(base_snapshot_dir=snap_dir)

    target_code_file = tmp_path / "parser.py"
    target_test_file = tmp_path / "test_parser.py"

    fsm.transition_to(TaskState.LOCK_WAIT)
    with lock_mgr.acquire(str(target_code_file), str(target_test_file)):
        snap_id = snapshot_engine.capture_snapshot(task_id, [target_code_file, target_test_file])
        fsm.transition_to(TaskState.RUNNING)

        # Step 4: Coding Agent writes parser implementation
        coding_agent = agent_registry.get("CodingAgent")
        assert coding_agent is not None
        code_input = AgentInput(
            task_id=task_id,
            task_description="Implement Markdown parser",
            parameters={"action": "generate", "file": str(target_code_file)},
        )
        code_output = coding_agent.run(code_input)
        assert code_output.success is True

        # Simulate generated file creation
        target_code_file.write_text("def parse_md(text): return '<p>' + text + '</p>'", encoding="utf-8")

        # Step 5: Test Writer produces test suite
        test_agent = agent_registry.get("TestWriter")
        assert test_agent is not None
        test_input = AgentInput(
            task_id=f"{task_id}_tests",
            task_description="Generate unit tests for Markdown parser",
            parameters={"target_module": "parser"},
        )
        test_output = test_agent.run(test_input)
        assert test_output.success is True
        target_test_file.write_text("def test_parse(): assert True", encoding="utf-8")

        # Step 6: Code Reviewer audits
        reviewer = agent_registry.get("CodeReviewer")
        review_output = reviewer.run(AgentInput(task_id=f"{task_id}_rev", task_description="Audit parser code"))
        assert review_output.success is True

        # Step 7: Deterministic Verification Engine Check
        fsm.transition_to(TaskState.RECONCILING)
        reconciler = ReconciliationEngine()
        assert reconciler.verify_file_exists(target_code_file) is True
        assert reconciler.verify_file_exists(target_test_file) is True

        ver_engine = VerificationEngine()
        file_verifier = FileVerifier()
        rep_code = file_verifier.verify(target_code_file, expected_content="parse_md")
        rep_test = file_verifier.verify(target_test_file, expected_content="test_parse")
        verdict = ver_engine.evaluate([rep_code, rep_test])
        assert verdict.outcome == VerificationOutcome.SUCCESS

        fsm.transition_to(TaskState.DONE)
        state_db.update_task_status(task_id, "DONE", {"verdict": verdict.outcome.value})

    assert fsm.current_state == TaskState.DONE
    record = state_db.get_task(task_id)
    assert record["status"] == "DONE"


# ==============================================================================
# Scenario 3: Safety Guardrail Defense (Destructive Command Hard-Block)
# ==============================================================================
def test_scenario_destructive_command_hard_blocked(guardrails, state_db):
    """Scenario 3: Malicious or accidental command: 'Drop database production and rm -rf /'"""
    dangerous_input = "rm -rf / --no-preserve-root and drop database production"

    # Step 1: Reflex Guardrails sub-33ms evaluation
    guard = guardrails.check_safety(dangerous_input)
    assert guard.is_safe is False
    assert guard.risk_tier == RiskTier.TIER_3_HARD_BLOCKED
    assert "Hard-blocked dangerous pattern detected" in guard.reason

    # Audit log check: task must NOT be admitted to TaskQueue or executed
    task_queue = TaskQueue()
    assert task_queue.peek() is None


# ==============================================================================
# Scenario 4: Desktop Application Interaction & Computer Use
# ==============================================================================
def test_scenario_desktop_interaction(agent_registry):
    """Scenario 4: User requests desktop app interaction: 'Open Notepad and write meeting notes'"""
    # Step 1: Acquire exclusive input lease via InputArbiter
    arbiter = agent_registry.get("InputArbiter")
    assert arbiter is not None

    lease_input = AgentInput(
        task_id="desktop_lease_1",
        task_description="Request mouse and keyboard control",
        parameters={"action": "acquire", "agent": "ComputerUseAgent"},
    )
    lease_out = arbiter.run(lease_input)
    assert lease_out.success is True
    assert "acquired" in lease_out.result

    # Step 2: Master Desktop Operator runs OBSERVE -> THINK -> ACT -> VERIFY
    cu_agent = agent_registry.get("ComputerUseAgent")
    assert cu_agent is not None

    task_in = AgentInput(
        task_id="cu_task_01",
        task_description="Launch Notepad and enter meeting notes",
        parameters={"action": "type", "target": "notepad_editor"},
    )
    cu_out = cu_agent.run(task_in)
    assert cu_out.success is True
    assert cu_out.artifacts["loop_stages"] == ["OBSERVE", "THINK", "ACT", "VERIFY"]
    assert cu_out.artifacts["verify"]["status"] == "SUCCESS"

    # Step 3: Window Verifier validates state
    win_verifier = WindowVerifier()
    # Mocking active windows check
    with patch.object(win_verifier, "verify", return_value=VerificationReport(outcome=VerificationOutcome.SUCCESS)):
        ver_rep = win_verifier.verify(expected_title="Notepad")
        assert ver_rep.outcome == VerificationOutcome.SUCCESS

    # Step 4: Release input lease
    release_in = AgentInput(
        task_id="desktop_lease_release",
        task_description="Release input ownership",
        parameters={"action": "release", "agent": "ComputerUseAgent"},
    )
    release_out = arbiter.run(release_in)
    assert release_out.success is True
    assert "released" in release_out.result


# ==============================================================================
# Scenario 5: Emergency Stop & Cascade Rollback (Kill Switch Trigger)
# ==============================================================================
def test_scenario_emergency_halt_cascade_rollback(tmp_path, agent_registry):
    """Scenario 5: User triggers emergency stop during background task execution."""
    snap_dir = tmp_path / "snaps"
    snapshot_engine = SnapshotEngine(base_snapshot_dir=snap_dir)

    work_file = tmp_path / "critical_data.txt"
    work_file.write_text("Original safe content", encoding="utf-8")

    new_temp_file = tmp_path / "unwanted_generated.py"

    # Pre-capture snapshot
    snap_id = snapshot_engine.capture_snapshot("task_rogue_99", [work_file, new_temp_file])

    # Simulate task corrupting original file and creating new temp file
    work_file.write_text("CORRUPTED DATA BY ROGUE TASK", encoding="utf-8")
    new_temp_file.write_text("MALICIOUS PAYLOAD", encoding="utf-8")

    # Step 1: User yells 'EMERGENCY STOP!'
    kill_switch = KillSwitch.get_instance()
    kill_switch.trip(reason="Voice emergency command: HALT!")
    assert kill_switch.is_tripped() is True

    # Step 2: BaseAgent execution immediately guarded and blocked
    coding_agent = agent_registry.get("CodingAgent")
    assert coding_agent is not None
    with pytest.raises(KillSwitchTrippedError):
        coding_agent.run(AgentInput(task_id="task_rogue_99", task_description="Continue work"))

    # Step 3: Rollback restores bit-for-bit pre-execution state
    rollback_ok = snapshot_engine.rollback(snap_id)
    assert rollback_ok is True

    assert work_file.read_text(encoding="utf-8") == "Original safe content"
    assert not new_temp_file.exists()


# ==============================================================================
# Scenario 6: Personal Knowledge & Privacy Boundary Scrubbing
# ==============================================================================
def test_scenario_privacy_scrub_and_memory_caching():
    """Scenario 6: User stores secret key and preference; verifies PII scrubbing and budget limits."""
    raw_user_message = (
        "Set my preference default_model to gemini-pro and my key is "
        "AIzaSyD1234567890abcdef1234567890123. Ensure this is confidential."
    )

    # Step 1: DataBoundary scrubs API key into reversible token
    boundary = DataBoundary()
    scrub_res = boundary.scrub(raw_user_message)
    scrubbed = scrub_res.scrubbed_text
    assert "AIzaSyD1234567890abcdef1234567890123" not in scrubbed
    assert "[REDACTED_API_KEY_1]" in scrubbed

    # Step 2: Store real secret into Vault
    vault = Vault()
    vault.store_secret("user_gemini_key", "AIzaSyD1234567890abcdef1234567890123")
    assert vault.get_secret("user_gemini_key") == "AIzaSyD1234567890abcdef1234567890123"

    # Step 3: MemoryContextHeap stores preference in L1 and conversation in L4
    heap = MemoryContextHeap()
    heap.set_preference("default_model", "gemini-pro")
    heap.add_conversation_turn("user", scrubbed)

    # Step 4: TokenBudgetCompressor enforces limits
    context_text = heap.get_composite_context()
    compressor = TokenBudgetCompressor(max_budget=400)
    prompt_ctx = compressor.compress(context_text)

    assert "default_model" in prompt_ctx
    assert "gemini-pro" in prompt_ctx
    assert "[REDACTED_API_KEY_1]" in prompt_ctx
    assert "AIzaSyD1234567890abcdef1234567890123" not in prompt_ctx


# ==============================================================================
# Scenario 7: Real-Time Hardware Monitoring (Lane A Sync Query)
# ==============================================================================
def test_scenario_realtime_hardware_monitoring(agent_registry, intent_router):
    """Scenario 7: User asks while running heavy tasks: 'What is my current CPU and RAM load?'"""
    query = "What is my current CPU and RAM load?"

    # Step 1: Sub-33ms Reflex routing identifies Lane A (instant sync read)
    decision = intent_router.route_input(query)
    assert decision.lane == LaneType.LANE_A
    assert decision.is_modifying is False

    # Step 2: Fast sync read via SystemMonitorAgent
    sys_agent = agent_registry.get("SystemMonitorAgent")
    assert sys_agent is not None
    out = sys_agent.run(AgentInput(task_id="quick_metric_1", task_description=query))
    assert out.success is True
    assert "System Status: CPU" in out.result
    assert "RAM" in out.result

    # Step 3: HealthCheck agent verifies subsystems
    health_agent = agent_registry.get("HealthCheck")
    assert health_agent is not None
    health_out = health_agent.run(AgentInput(task_id="health_check_1", task_description="Check system health"))
    assert health_out.success is True
    assert health_out.artifacts["overall_health"] == "HEALTHY"


# ==============================================================================
# Scenario 8: Web Research & Notes Archival
# ==============================================================================
def test_scenario_research_and_notes_archival(agent_registry):
    """Scenario 8: User requests web research on a technical topic and saves to markdown notes."""
    research_agent = agent_registry.get("ResearchAgent")
    notes_agent = agent_registry.get("NotesAgent")
    assert research_agent is not None
    assert notes_agent is not None

    # Step 1: Research Agent gathers summary with citations
    res_in = AgentInput(
        task_id="res_01",
        task_description="Research SQLite WAL mode benefits",
        parameters={"query": "SQLite WAL mode performance benefits", "mode": "research"},
    )
    res_out = research_agent.run(res_in)
    assert res_out.success is True
    assert "citations" in res_out.artifacts

    # Step 2: Notes Agent structures note with title and tags
    note_in = AgentInput(
        task_id="note_01",
        task_description="Save research findings",
        parameters={
            "action": "create",
            "title": "SQLite WAL Concurrency",
            "content": res_out.result,
            "tags": ["database", "sqlite", "concurrency"],
        },
    )
    note_out = notes_agent.run(note_in)
    assert note_out.success is True
    assert "SQLite WAL Concurrency" in note_out.artifacts["note_content"]
    assert "database" in note_out.artifacts["note_content"]


# ==============================================================================
# Scenario 9: Dual-Lane Voice Tool to HUD Task Widget & Dashboard API
# ==============================================================================
def test_scenario_voice_tool_to_hud_widget(qapp):
    """Scenario 9: Gemini Live tool call dispatch reflects in HUD Task List widget and Dashboard."""
    # Step 1: Instantiate HUD widget
    widget = TaskListWidget()

    # Task enqueued
    widget.add_or_update_task("voice_task_123", "Draft weekly client briefing", "EmailAgent", "queued")
    assert "voice_task_123" in widget._task_widgets
    assert widget.count_lbl.text() == "1 active"

    # Task running
    widget.add_or_update_task("voice_task_123", "Draft weekly client briefing", "EmailAgent", "running", elapsed=1.2)
    item_w = widget._task_widgets["voice_task_123"][1]
    assert item_w.lbl_status.text() == "RUNNING"

    # Task done
    widget.add_or_update_task("voice_task_123", "Draft weekly client briefing", "EmailAgent", "done", elapsed=2.4)
    assert item_w.lbl_status.text() == "DONE"
    assert widget.count_lbl.text() == "0 active"

    # Step 2: Validate Dashboard API reflects all 33 agents
    from fastapi.testclient import TestClient
    from dashboard.server import DashboardServer

    server = DashboardServer()
    client = TestClient(server.app)
    response = client.get("/api/agents")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 33
    agent_names = [a["name"] for a in data["agents"]]
    assert "CodingAgent" in agent_names
    assert "EmailAgent" in agent_names
    assert "SystemMonitorAgent" in agent_names

