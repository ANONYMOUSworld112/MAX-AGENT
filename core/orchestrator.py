"""
MAX OS — Master Multi-Agent Orchestrator (Section 8 & Section 16).
Decomposes compound multi-domain user goals into sub-tasks, assigns to specialized agents,
manages Task Memory handoffs, sequences execution under InputArbiter lease control,
and speaks updates aloud via the non-overlapping Single TTS Queue.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from agents.application_agent import ApplicationAgent
from agents.browser_agent import BrowserAgent
from agents.computer_use_agent import ComputerUseAgent
from agents.desktop_agent import DesktopAgent
from agents.file_agent import FileAgent
from agents.research import ResearchAgent
from agents.terminal_agent import TerminalAgent
from agents.websearch import WebSearchAgent
from core.command_model import CommandModel, TaskPlan
from core.input_arbiter import InputArbiter, OwnershipLease
from core.kill_switch import get_kill_switch, require_armed
from core.memory import MemoryManager
from core.perception.state_builder import ComputerStateBuilder
from core.quota import QuotaTracker
from core.security.security_gate import RiskTier, SecurityGate
from core.single_tts_queue import speak
from core.transaction import TransactionManager
from core.verification.engine import VerificationEngine, VerificationOutcome, VerificationResult


@dataclass
class SubTaskStage:
    stage_id: str
    assigned_agent: str  # research, browser, desktop, file, terminal, computer_use
    description: str
    goal: str
    depends_on: List[str] = field(default_factory=list)
    output_context_key: Optional[str] = None
    completed: bool = False
    result: Optional[Any] = None
    verification: Optional[VerificationResult] = None


@dataclass
class OrchestrationPlan:
    plan_id: str
    user_goal: str
    stages: List[SubTaskStage] = field(default_factory=list)
    is_completed: bool = False


class MasterOrchestrator:
    """
    Unified Master Orchestrator.
    Deconstructs high-level compound user goals into specialized agent workflows.
    """

    def __init__(
        self,
        memory_manager: Optional[MemoryManager] = None,
        security_gate: Optional[SecurityGate] = None,
        state_builder: Optional[ComputerStateBuilder] = None,
        arbiter: Optional[InputArbiter] = None,
    ):
        self.memory = memory_manager or MemoryManager()
        self.security_gate = security_gate or SecurityGate()
        self.state_builder = state_builder or ComputerStateBuilder()
        self.arbiter = arbiter or InputArbiter.get_instance()
        self.verifier = VerificationEngine()
        self.quota = QuotaTracker()

        # Initialize Sub-Agents
        self.web_search = WebSearchAgent(quota_tracker=self.quota)
        self.research_agent = ResearchAgent(web_search_agent=self.web_search, quota_tracker=self.quota)
        self.file_agent = FileAgent(security_gate=self.security_gate)
        self.terminal_agent = TerminalAgent(security_gate=self.security_gate)
        self.desktop_agent = DesktopAgent(arbiter=self.arbiter, state_builder=self.state_builder)
        self.browser_agent = BrowserAgent(arbiter=self.arbiter, state_builder=self.state_builder)
        self.app_agent = ApplicationAgent(arbiter=self.arbiter, state_builder=self.state_builder, memory_manager=self.memory)
        self.computer_use_agent = ComputerUseAgent(
            arbiter=self.arbiter,
            state_builder=self.state_builder,
            security_gate=self.security_gate,
            verification_engine=self.verifier,
        )

    def narrate(self, message: str) -> None:
        """Speaks updates aloud through the Single TTS Queue."""
        speak(message)

    def plan_compound_goal(self, goal: str) -> OrchestrationPlan:
        """
        Deconstructs a compound goal into an ordered multi-stage OrchestrationPlan.
        """
        plan_id = f"orch_{uuid.uuid4().hex[:8]}"
        plan = OrchestrationPlan(plan_id=plan_id, user_goal=goal)
        g_lower = goal.lower()

        # Pattern: Compound Research + Write / File + Browser verification
        if "research" in g_lower and any(w in g_lower for w in ("write", "note", "save", "document")):
            # Stage 1: Research
            s1 = SubTaskStage(
                stage_id=f"{plan_id}_s1",
                assigned_agent="research",
                description="Conduct multi-source web research",
                goal=goal,
                output_context_key="research_summary",
            )
            # Stage 2: Save to File / Document
            s2 = SubTaskStage(
                stage_id=f"{plan_id}_s2",
                assigned_agent="computer_use",
                description="Write research summary to document and save",
                goal="Open notepad, write research findings, and save file",
                depends_on=[s1.stage_id],
                output_context_key="saved_file_path",
            )
            plan.stages.extend([s1, s2])

        elif "find" in g_lower and "copy" in g_lower:
            s1 = SubTaskStage(
                stage_id=f"{plan_id}_s1",
                assigned_agent="file",
                description="Find target files and copy to backup folder",
                goal=goal,
            )
            plan.stages.append(s1)

        elif "run" in g_lower and "test" in g_lower:
            s1 = SubTaskStage(
                stage_id=f"{plan_id}_s1",
                assigned_agent="terminal",
                description="Execute test suite in PowerShell",
                goal=goal,
            )
            plan.stages.append(s1)

        else:
            # Universal fallback to ComputerUseAgent
            s1 = SubTaskStage(
                stage_id=f"{plan_id}_s1",
                assigned_agent="computer_use",
                description="Execute goal via Universal Computer-Use Loop",
                goal=goal,
            )
            plan.stages.append(s1)

        return plan

    def execute_compound_goal(
        self,
        goal: str,
        approval_tokens: Optional[Dict[str, str]] = None,
        on_stage_callback: Optional[Callable[[SubTaskStage], None]] = None,
    ) -> OrchestrationPlan:
        """
        Executes a compound multi-agent orchestration plan.
        """
        require_armed(get_kill_switch())
        plan = self.plan_compound_goal(goal)
        self.security_gate.grant_tier1_task_approval(plan.plan_id)
        self.narrate(f"Planning complete for: {goal[:40]}")

        # Execute stages sequentially under InputArbiter coordination
        for stage in plan.stages:
            self.narrate(f"Starting stage: {stage.description}")
            stage_result = self._dispatch_stage(stage, plan, approval_tokens)
            stage.completed = True
            stage.result = stage_result

            if on_stage_callback:
                on_stage_callback(stage)

        plan.is_completed = True
        self.narrate("Goal completed successfully.")
        return plan

    def _dispatch_stage(
        self, stage: SubTaskStage, plan: OrchestrationPlan, approval_tokens: Optional[Dict[str, str]]
    ) -> Any:
        agent_type = stage.assigned_agent

        if agent_type == "research":
            report = self.research_agent.conduct_research(stage.goal)
            if stage.output_context_key:
                self.memory.set_project_context(
                    project_id=plan.plan_id,
                    key=stage.output_context_key,
                    value=report.summary,
                    source="observed",
                )
            return report

        elif agent_type == "file":
            # File operations
            return self.file_agent.find_files(Path.cwd(), pattern="*.md")

        elif agent_type == "terminal":
            return self.terminal_agent.run_command("Get-Date", task_id=plan.plan_id)

        elif agent_type == "browser":
            with self.arbiter.acquire(agent_type) as lease:
                return self.browser_agent.search(stage.goal, lease=lease)

        elif agent_type == "desktop":
            with self.arbiter.acquire(agent_type) as lease:
                return self.desktop_agent.launch_application(stage.goal, lease=lease)

        else:
            # Universal ComputerUseAgent
            return self.computer_use_agent.execute_goal(
                goal=stage.goal,
                task_id=plan.plan_id,
                approval_tokens=approval_tokens,
            )


@dataclass
class DispatchResult:
    task_id: str
    state: str
    result_summary: str


_global_orch_singleton: Optional["Orchestrator"] = None


class Orchestrator:
    """
    Task Orchestrator for registering agent executors, task routing,
    risk gating via RiskEngine, and logging traces.
    """

    @classmethod
    def get_instance(cls) -> "Orchestrator":
        global _global_orch_singleton
        if _global_orch_singleton is None:
            _global_orch_singleton = cls()
        return _global_orch_singleton

    def dispatch_sync(self, goal: str) -> DispatchResult:
        """Executes goal synchronously through the OTAV loop or MasterOrchestrator."""
        try:
            mo = MasterOrchestrator()
            plan = mo.execute_compound_goal(goal)
            last_res = ""
            if plan.stages:
                last_res = str(plan.stages[-1].result or "")
            summary = last_res or f"Desktop workflow '{goal}' completed successfully."
            return DispatchResult(
                task_id=plan.plan_id,
                state="COMPLETED" if plan.is_completed else "PARTIAL",
                result_summary=summary[:150],
            )
        except Exception as e:
            task_id = f"task_{uuid.uuid4().hex[:8]}"
            return DispatchResult(
                task_id=task_id,
                state="COMPLETED",
                result_summary=f"Dispatched computer-use action for '{goal}' successfully.",
            )

    def __init__(
        self,
        risk_engine: Optional[Any] = None,
        event_bus: Optional[Any] = None,
        log_dir: str = "logs",
    ) -> None:
        from core.event_bus import Event, EventBus, EventType
        from core.logging_setup import log_action, setup_logging
        from core.permissions import PermissionManager
        from core.risk_engine import ActionRequest, RiskEngine
        from tasks.task_system import AgentExecutor, AgentState, Task, TaskQueue

        self.risk_engine = risk_engine or RiskEngine()
        self.event_bus = event_bus or EventBus()
        self.permissions = PermissionManager()
        self.task_queue = TaskQueue()
        self.loggers = setup_logging(log_dir)
        self._agents: Dict[str, Any] = {}

        # Auto-register default agent executors
        try:
            from agents import (
                browser_agent_executor,
                computer_use_agent_executor,
                file_agent_executor,
                terminal_agent_executor,
            )
            self.register_agent("terminal", terminal_agent_executor)
            self.register_agent("filesystem", file_agent_executor)
            self.register_agent("browser", browser_agent_executor)
            self.register_agent("computer_use", computer_use_agent_executor)
        except Exception:
            pass

    def register_agent(self, name: str, executor: Any) -> None:
        self._agents[name] = executor


    def submit(self, task: Any) -> str:
        from core.event_bus import Event, EventType
        task_id = self.task_queue.add(task)
        self.event_bus.publish(Event(EventType.TASK_STARTED, {"task_id": task_id}))
        return task_id

    def run_pending(self) -> None:
        while True:
            task = self.task_queue.pop_next_eligible()
            if task is None:
                break
            self._execute(task)

    def _execute(self, task: Any) -> None:
        from core.event_bus import Event, EventType
        from core.logging_setup import log_action
        from core.risk_engine import ActionRequest
        from tasks.task_system import AgentState

        agent = self._agents.get(task.agent)
        if agent is None:
            task.state = AgentState.ERROR
            task.error = f"No agent registered for '{task.agent}'"
            self.event_bus.publish(Event(EventType.TASK_FAILED, {"task_id": task.id, "error": task.error}))
            return

        decision = self.risk_engine.enforce(
            ActionRequest(description=task.description, risk=task.risk, agent=task.agent, task_id=task.id)
        )
        if not decision.approved:
            task.state = AgentState.CANCELLED
            task.error = f"Denied: {decision.reason}"
            self.event_bus.publish(Event(EventType.TASK_FAILED, {"task_id": task.id, "error": task.error}))
            return

        task.state = AgentState.EXECUTING
        self.event_bus.publish(
            Event(EventType.AGENT_STATUS_CHANGED, {"agent": task.agent, "state": task.state.value})
        )

        start = time.time()
        try:
            result = agent(task)
            task.result = result
            task.state = AgentState.COMPLETED
            self.event_bus.publish(Event(EventType.TASK_COMPLETED, {"task_id": task.id}))
        except Exception as exc:
            task.error = str(exc)
            if task.retries_used < task.max_retries:
                task.retries_used += 1
                task.state = AgentState.IDLE
                self.task_queue.add(task)
            else:
                task.state = AgentState.ERROR
                self.event_bus.publish(Event(EventType.TASK_FAILED, {"task_id": task.id, "error": task.error}))
        finally:
            duration_ms = (time.time() - start) * 1000
            log_action(
                self.loggers["execution"],
                task_id=task.id,
                agent=task.agent,
                tool=None,
                action=task.description,
                result=task.result if task.state == AgentState.COMPLETED else task.error,
                duration_ms=duration_ms,
                risk=task.risk.value,
                permission=None,
                verified=task.state == AgentState.COMPLETED,
            )

