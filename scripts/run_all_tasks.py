"""CyberBlack AI-agent MAX: Master Multi-Task Execution Runner.

Executes a comprehensive battery of diverse tasks across all 5 agent clusters,
dual-lane intent routing, safety guardrails, task queue lifecycle, and StateDB.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from core.reflex.intent_router import ReflexIntentRouter, LaneType
from core.reflex.guardrails import ReflexGuardrails, RiskTier
from core.reflex.triage import ReflexTriage, PriorityBand
from core.max_infra.kill_switch import KillSwitch
from core.max_infra.state_db import StateDB
from core.max_infra.task_lifecycle import TaskLifecycleFSM, TaskState
from core.max_infra.task_queue import TaskQueue, TaskItem
from core.max_infra.data_boundary import DataBoundary
from core.max_infra.vault import Vault
from agents.router import AgentRegistry
from agents.base import AgentInput

# Agent clusters
from agents.core.orchestrator import MasterOrchestrator
from agents.core.planner import DecompositionPlanner
from agents.core.verifier import ValidationVerifier
from agents.core.model_router import ModelRouter
from agents.core.critic import AdversarialCritic

from agents.productivity import (
    CalendarAgent,
    EmailAgent,
    NotesAgent,
    TaskTracker,
    ResearchAgent,
    MeetingPrep,
    FileOrganizer,
    CommsAgent,
)

from agents.software import (
    CodingAgent,
    CodeReviewer,
    TestWriter,
    APIDesigner,
    DBAgent,
    DocWriter,
    DependencyMgr,
    DevOpsAgent,
)

from agents.health import (
    SystemMonitorAgent,
    NetworkAgent,
    HealthCheck,
    PerformanceAgent,
    BackupAgent,
)

from agents.safety import (
    DesktopAgent,
    BrowserAgent,
    ComputerUseAgent,
    InputArbiter,
    SecurityGate,
    RecoveryEngine,
)


def run_all_tasks():
    print("=" * 80)
    print("🚀 CYBERBLACK AI-AGENT MAX: EXECUTING MULTI-TASK BATTERY")
    print(f"   Root Directory: {PROJECT_ROOT}")
    print(f"   Python Version: {sys.version.split()[0]} ({sys.executable})")
    print("=" * 80)

    results = []

    def record(category: str, task_name: str, passed: bool, detail: str, duration_ms: float):
        status = "✅ PASS" if passed else "❌ FAIL"
        results.append((category, task_name, passed, detail, duration_ms))
        print(f"  [{status}] {category} :: {task_name} ({duration_ms:.1f}ms) — {detail}")

    # =========================================================================
    # 1. Reflex Intent Routing (Lane A vs Lane B)
    # =========================================================================
    print("\n--- [1/6] REFLEX INTENT ROUTER (Sub-33ms Dual-Lane Triage) ---")
    router = ReflexIntentRouter(fallback_mode=True)
    test_queries = [
        ("What time is it?", LaneType.LANE_A, "Lane A fast-read query"),
        ("Mute volume", LaneType.LANE_A, "Lane A device reflex"),
        ("Write a Python script to sort files", LaneType.LANE_B, "Lane B agentic dev task"),
        ("Schedule a meeting tomorrow at 3pm", LaneType.LANE_B, "Lane B calendar task"),
    ]
    for query, expected_lane, desc in test_queries:
        t0 = time.perf_counter()
        decision = router.route_input(query)
        dt = (time.perf_counter() - t0) * 1000.0
        ok = decision.lane == expected_lane
        record("Reflex Router", f"Route: '{query[:25]}...'", ok, f"{decision.lane.name} (target agent: {decision.target_agent})", dt)

    # =========================================================================
    # 2. Productivity Cluster Tasks
    # =========================================================================
    print("\n--- [2/6] PRODUCTIVITY CLUSTER TASKS ---")
    
    # 2.1 Calendar
    cal = CalendarAgent()
    t0 = time.perf_counter()
    out = cal.run(AgentInput(
        task_id="task_cal_01",
        task_description="Schedule Sprint Planning 2026",
        parameters={"title": "Sprint 42 Planning", "start_time": "2026-10-01T10:00:00", "duration_minutes": 45}
    ))
    dt = (time.perf_counter() - t0) * 1000.0
    record("Productivity", "CalendarAgent: Schedule Meeting", out.success, f"Status: {out.artifacts.get('status')}", dt)

    # 2.2 Notes
    notes = NotesAgent()
    t0 = time.perf_counter()
    out = notes.run(AgentInput(
        task_id="task_notes_01",
        task_description="Record architectural decision note",
        parameters={"title": "Dual-Lane Architecture ADR", "content": "Lane A reflex + Lane B full agentic swarm.", "tags": ["arch", "max"]}
    ))
    dt = (time.perf_counter() - t0) * 1000.0
    record("Productivity", "NotesAgent: Create ADR Note", out.success, f"Note ID: {out.artifacts.get('note_id', 'created')}", dt)

    # 2.3 TaskTracker
    tracker = TaskTracker()
    t0 = time.perf_counter()
    out = tracker.run(AgentInput(
        task_id="task_track_01",
        task_description="Update project milestone tracker",
        parameters={"action": "create", "task_name": "Deploy Agent Swarm v2", "priority": "high"}
    ))
    dt = (time.perf_counter() - t0) * 1000.0
    record("Productivity", "TaskTracker: Create Milestone Task", out.success, f"Result: {out.result[:40]}", dt)

    # 2.4 ResearchAgent
    research = ResearchAgent()
    t0 = time.perf_counter()
    out = research.run(AgentInput(
        task_id="task_res_01",
        task_description="Synthesize technical research",
        parameters={"topic": "Asynchronous TaskQueue aging algorithms in Python"}
    ))
    dt = (time.perf_counter() - t0) * 1000.0
    record("Productivity", "ResearchAgent: Synthesize Topic", out.success, f"Status: {out.artifacts.get('status', 'OK')}", dt)

    # 2.5 MeetingPrep
    mprep = MeetingPrep()
    t0 = time.perf_counter()
    out = mprep.run(AgentInput(
        task_id="task_prep_01",
        task_description="Assemble agenda for architectural sync",
        parameters={"meeting_name": "AI Agent Architecture Sync", "attendees": ["Team Lead", "Core Dev"]}
    ))
    dt = (time.perf_counter() - t0) * 1000.0
    record("Productivity", "MeetingPrep: Generate Agenda", out.success, f"Agenda items: {len(out.artifacts.get('agenda', []))}", dt)

    # =========================================================================
    # 3. Software Engineering Cluster Tasks
    # =========================================================================
    print("\n--- [3/6] SOFTWARE ENGINEERING CLUSTER TASKS ---")
    
    # 3.1 CodingAgent (Safe file generation)
    test_target = PROJECT_ROOT / ".snapshots" / "sample_tool.py"
    test_target.parent.mkdir(parents=True, exist_ok=True)
    coder = CodingAgent()
    t0 = time.perf_counter()
    out = coder.run(AgentInput(
        task_id="task_sw_01",
        task_description="Generate utility function",
        target_files=[str(test_target)],
        parameters={"filepath": str(test_target), "code": "def calculate_crc32(data: bytes) -> int:\n    import zlib\n    return zlib.crc32(data)\n", "action": "write"}
    ))
    dt = (time.perf_counter() - t0) * 1000.0
    record("Software", "CodingAgent: Generate Utility Code", out.success and test_target.exists(), f"File created: {test_target.name}", dt)

    # 3.2 CodeReviewer
    reviewer = CodeReviewer()
    t0 = time.perf_counter()
    out = reviewer.run(AgentInput(
        task_id="task_sw_02",
        task_description="Perform static security and quality review",
        parameters={"code": "import os\ndef bad(): pass\n"}
    ))
    dt = (time.perf_counter() - t0) * 1000.0
    record("Software", "CodeReviewer: Review Codebase Snippet", out.success, f"Verdict: {out.artifacts.get('verdict', 'reviewed')}", dt)

    # 3.3 TestWriter
    tw = TestWriter()
    t0 = time.perf_counter()
    out = tw.run(AgentInput(
        task_id="task_sw_03",
        task_description="Generate unit test suite",
        parameters={"target_module": "core.utils", "function_name": "calculate_crc32"}
    ))
    dt = (time.perf_counter() - t0) * 1000.0
    record("Software", "TestWriter: Scaffold Unit Test Suite", out.success, f"Generated tests: {len(out.artifacts.get('test_cases', []))}", dt)

    # 3.4 APIDesigner
    api_des = APIDesigner()
    t0 = time.perf_counter()
    out = api_des.run(AgentInput(
        task_id="task_sw_04",
        task_description="Design REST endpoint schema",
        parameters={"resource": "agents", "endpoints": ["GET /agents", "POST /agents/dispatch"]}
    ))
    dt = (time.perf_counter() - t0) * 1000.0
    record("Software", "APIDesigner: Draft REST API Spec", out.success, f"Endpoints: {len(out.artifacts.get('routes', []))}", dt)

    # 3.5 DBAgent
    db_agent = DBAgent()
    t0 = time.perf_counter()
    out = db_agent.run(AgentInput(
        task_id="task_sw_05",
        task_description="Validate database schema migration",
        parameters={"table": "tasks", "action": "add_column", "column": "trace_id TEXT"}
    ))
    dt = (time.perf_counter() - t0) * 1000.0
    record("Software", "DBAgent: Validate Schema Migration", out.success, f"Status: {out.artifacts.get('migration_status', 'OK')}", dt)

    # =========================================================================
    # 4. Health & Monitoring Cluster Tasks
    # =========================================================================
    print("\n--- [4/6] SYSTEM HEALTH & MONITORING CLUSTER TASKS ---")

    # 4.1 SystemMonitorAgent
    sys_mon = SystemMonitorAgent()
    t0 = time.perf_counter()
    out = sys_mon.run(AgentInput(task_id="task_hl_01", task_description="Sample host hardware telemetry"))
    dt = (time.perf_counter() - t0) * 1000.0
    cpu = out.artifacts.get("metrics", {}).get("cpu_percent", "N/A")
    mem = out.artifacts.get("metrics", {}).get("memory_percent", "N/A")
    record("Health", "SystemMonitorAgent: Host Hardware Telemetry", out.success, f"CPU: {cpu}% | RAM: {mem}%", dt)

    # 4.2 NetworkAgent
    net_agent = NetworkAgent()
    t0 = time.perf_counter()
    out = net_agent.run(AgentInput(
        task_id="task_hl_02",
        task_description="Test loopback network stack",
        parameters={"host": "127.0.0.1", "port": 80, "timeout": 0.2}
    ))
    dt = (time.perf_counter() - t0) * 1000.0
    record("Health", "NetworkAgent: Check Network Interface", out.success, f"Interface: 127.0.0.1", dt)

    # 4.3 HealthCheck
    hc = HealthCheck()
    t0 = time.perf_counter()
    out = hc.run(AgentInput(task_id="task_hl_03", task_description="Verify all subsystems healthy"))
    dt = (time.perf_counter() - t0) * 1000.0
    record("Health", "HealthCheck: Subsystem Diagnostic Scan", out.success, f"Overall health: {out.artifacts.get('status', 'HEALTHY')}", dt)

    # 4.4 PerformanceAgent
    perf = PerformanceAgent()
    t0 = time.perf_counter()
    out = perf.run(AgentInput(task_id="task_hl_04", task_description="Profile system latency bottlenecks"))
    dt = (time.perf_counter() - t0) * 1000.0
    record("Health", "PerformanceAgent: Latency & Bottleneck Scan", out.success, f"Efficiency: {out.artifacts.get('efficiency_score', 'OPTIMAL')}", dt)

    # =========================================================================
    # 5. Safety, Security & Guardrails Tasks
    # =========================================================================
    print("\n--- [5/6] SAFETY & SECURITY GUARDRAILS TASKS ---")
    guardrails = ReflexGuardrails(fallback_mode=True)
    triage = ReflexTriage(fallback_mode=True)

    # 5.1 Safe Read (Tier 0)
    t0 = time.perf_counter()
    assessment = guardrails.check_safety("What is the CPU usage?")
    dt = (time.perf_counter() - t0) * 1000.0
    record("Safety", "Guardrails: Safe Read Tier 0", assessment.risk_tier == RiskTier.TIER_0_AUTO, f"Tier: {assessment.risk_tier.name}", dt)

    # 5.2 Confirm On Write (Tier 2)
    t0 = time.perf_counter()
    assessment = guardrails.check_safety("Update database schema and delete unused customer columns")
    dt = (time.perf_counter() - t0) * 1000.0
    record("Safety", "Guardrails: Require Confirm Gate Tier 2", assessment.risk_tier == RiskTier.TIER_2_CONFIRM_ON_WRITE, f"Tier: {assessment.risk_tier.name}", dt)

    # 5.3 Hard Block (Tier 3)
    t0 = time.perf_counter()
    assessment = guardrails.check_safety("rm -rf / --no-preserve-root")
    dt = (time.perf_counter() - t0) * 1000.0
    record("Safety", "Guardrails: Block Destructive Command Tier 3", assessment.risk_tier == RiskTier.TIER_3_HARD_BLOCKED, f"Blocked: {assessment.risk_tier.name}", dt)

    # 5.4 Priority Triage
    t0 = time.perf_counter()
    p_emergency = triage.assign_priority("EMERGENCY KILL SWITCH ACTIVATED")
    p_interactive = triage.assign_priority("What time is it?")
    p_agentic = triage.assign_priority("Refactor auth module and run test suite")
    dt = (time.perf_counter() - t0) * 1000.0
    record("Safety", "Triage: Dynamic Priority Bands", p_emergency == 0 and p_interactive == 1 and p_agentic == 2, f"P0: Emergency, P1: Interactive, P2: Dev Task", dt)

    # 5.5 DataBoundary PII & Credential Scrubbing
    boundary = DataBoundary()
    t0 = time.perf_counter()
    raw_prompt = "Contact ceo@anthropic.com with key AIzaSyD1234567890abcdefghijklmnopqr for auth"
    scrub_res = boundary.scrub(raw_prompt)
    dt = (time.perf_counter() - t0) * 1000.0
    has_leak = "AIzaSyD1234567890abcdefghijklmnopqr" in scrub_res.scrubbed_text or "ceo@anthropic.com" in scrub_res.scrubbed_text
    record("Safety", "DataBoundary: Scrub Credentials & PII", not has_leak, f"Scrubbed: '{scrub_res.scrubbed_text[:45]}...'", dt)

    # 5.6 KillSwitch Arm & Safe Trip Check
    ks = KillSwitch.get_instance()
    ks.reset()
    t0 = time.perf_counter()
    is_tripped_before = ks.is_tripped()
    ks.trip(reason="Test Emergency Trip")
    is_tripped_after = ks.is_tripped()
    ks.reset()
    dt = (time.perf_counter() - t0) * 1000.0
    record("Safety", "KillSwitch: Emergency Cascade Circuit Breaker", (not is_tripped_before) and is_tripped_after and (not ks.is_tripped()), "Armed -> Tripped -> Disarmed cleanly", dt)

    # =========================================================================
    # 6. Core Orchestration & TaskQueue Lifecycle Tasks
    # =========================================================================
    print("\n--- [6/6] CORE ORCHESTRATION & TASK QUEUE LIFECYCLE ---")

    # 6.1 DecompositionPlanner
    planner = DecompositionPlanner()
    t0 = time.perf_counter()
    out = planner.run(AgentInput(
        task_id="core_plan_01",
        task_description="Build end-to-end user authentication microservice",
    ))
    dt = (time.perf_counter() - t0) * 1000.0
    subtasks = out.artifacts.get("subtasks", [])
    record("Core", "DecompositionPlanner: Break Down Complex Task", out.success and len(subtasks) > 0, f"Decomposed into {len(subtasks)} subtasks", dt)

    # 6.2 AdversarialCritic
    critic = AdversarialCritic()
    t0 = time.perf_counter()
    out = critic.run(AgentInput(
        task_id="core_crit_01",
        task_description="Critique deployment plan",
        parameters={"plan": ["Step 1: Terminate all databases", "Step 2: Re-deploy in production"]}
    ))
    dt = (time.perf_counter() - t0) * 1000.0
    record("Core", "AdversarialCritic: Plan Robustness & Risk Audit", out.success, f"Identified risks: {len(out.artifacts.get('critique', []))}", dt)

    # 6.3 ModelRouter
    mrouter = ModelRouter()
    t0 = time.perf_counter()
    out = mrouter.run(AgentInput(
        task_id="core_mr_01",
        task_description="Route fast voice audio stream",
        parameters={"modality": "audio", "latency_critical": True}
    ))
    dt = (time.perf_counter() - t0) * 1000.0
    record("Core", "ModelRouter: Dynamic Latency vs Quality Selection", out.success, f"Selected model: {out.artifacts.get('selected_model')}", dt)

    # 6.4 TaskQueue & Lifecycle FSM
    queue = TaskQueue(max_capacity=20)
    item = TaskItem(
        task_id="lifecycle_demo_01",
        priority_band=0,
        payload={"title": "Automated Health Scan", "agent": "HealthCheck"}
    )
    t0 = time.perf_counter()
    queue.enqueue(item)
    popped = queue.dequeue()
    dt = (time.perf_counter() - t0) * 1000.0

    fsm = TaskLifecycleFSM()
    state = TaskState.CREATED
    state = fsm.transition(state, TaskState.QUEUED)
    state = fsm.transition(state, TaskState.LOCK_WAIT)
    state = fsm.transition(state, TaskState.RUNNING)
    state = fsm.transition(state, TaskState.RECONCILING)
    state = fsm.transition(state, TaskState.DONE)
    record("Core", "TaskQueue & FSM: Priority Enqueue -> Running -> Done", popped.task_id == "lifecycle_demo_01" and state == TaskState.DONE, f"Final State: {state.name}", dt)

    # Clean up test artifact
    if test_target.exists():
        try:
            test_target.unlink()
        except Exception:
            pass

    # =========================================================================
    # Summary
    # =========================================================================
    total = len(results)
    passed = sum(1 for r in results if r[2])
    failed = total - passed

    print("\n" + "=" * 80)
    print(f"📊 TASK EXECUTION SUMMARY: {passed}/{total} PASSED ({failed} failed)")
    print("=" * 80)

    return passed == total


if __name__ == "__main__":
    success = run_all_tasks()
    sys.exit(0 if success else 1)
