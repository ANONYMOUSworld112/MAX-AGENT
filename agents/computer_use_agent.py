"""
MAX OS — Universal Computer-Use Agent (Section 8 & Target Architecture).
The universal, application-agnostic operator that composes Perception, Controllers,
Input Arbitration, Security Gate, Verification Engine, and Recovery into a cohesive
goal-driven system.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional

from core.command_model import ActionObject, CommandModel, TaskPlan
from core.controllers.keyboard_controller import KeyboardController
from core.controllers.mouse_controller import MouseController
from core.execution_loop import PlanExecutionResult, StepExecutionResult, UniversalExecutionLoop
from core.input_arbiter import InputArbiter, OwnershipLease
from core.kill_switch import get_kill_switch, require_armed
from core.perception.state_builder import ComputerState, ComputerStateBuilder
from core.recovery.recovery_engine import RecoveryEngine
from core.security.security_gate import RiskTier, SecurityGate
from core.single_tts_queue import speak
from core.verification.engine import VerificationEngine


from core.llm_computer_use_engine import ComputerUseObservation, LLMComputerUseEngine, LLMConfig
from core.fast_replay_engine import FastReplayEngine, ReplayAnchor
from core.human_operator_suite import HumanOperatorSuite
from tasks.task_system import Task
from tools.backends.computer_control import ComputerControlBackend
from tools.interfaces import ComputerTool


from core.computer_control import (
    ActionToolRegistry,
    CheckpointManager,
    ComputerEnvironment,
    ControlMode,
    PermissionFirewall,
    ScreenDiffEngine,
    TurboExecutor,
    VisionFallbackEngine,
)


class ComputerUseAgent:
    """
    Master Universal Computer-Use AI Agent.
    Receives high-level natural language objectives and operates the computer
    dynamically using Multi-Provider LLM reasoning, Turbo Executor, Fast Replays, and Human-Like capabilities.
    Uses ComputerControlBackend via ComputerTool interface seam.
    """

    def __init__(
        self,
        arbiter: Optional[InputArbiter] = None,
        state_builder: Optional[ComputerStateBuilder] = None,
        security_gate: Optional[SecurityGate] = None,
        verification_engine: Optional[VerificationEngine] = None,
        recovery_engine: Optional[RecoveryEngine] = None,
        command_model: Optional[CommandModel] = None,
        llm_engine: Optional[LLMComputerUseEngine] = None,
        fast_replay_engine: Optional[FastReplayEngine] = None,
        computer_tool: Optional[ComputerTool] = None,
    ):
        self.computer_tool = computer_tool or ComputerControlBackend()

        self.arbiter = arbiter or InputArbiter.get_instance()
        self.state_builder = state_builder or ComputerStateBuilder()
        self.security_gate = security_gate or SecurityGate()
        self.verification = verification_engine or VerificationEngine()
        self.recovery = recovery_engine or RecoveryEngine()
        self.command_model = command_model or CommandModel(security_gate=self.security_gate)
        self.llm_engine = llm_engine or LLMComputerUseEngine(security_gate=self.security_gate)
        self.fast_replay_engine = fast_replay_engine or FastReplayEngine()
        self.human_suite = HumanOperatorSuite()

        self.mouse = MouseController(arbiter=self.arbiter)
        self.keyboard = KeyboardController(arbiter=self.arbiter, mouse_controller=self.mouse)

        self.firewall = PermissionFirewall(security_gate=self.security_gate, mode=ControlMode.TURBO_AUTONOMOUS)
        self.turbo_executor = TurboExecutor(
            arbiter=self.arbiter,
            state_builder=self.state_builder,
            security_gate=self.security_gate,
            permission_firewall=self.firewall,
            verification_engine=self.verification,
            recovery_engine=self.recovery,
            mouse_controller=self.mouse,
            keyboard_controller=self.keyboard,
        )

        self.loop = UniversalExecutionLoop(
            state_builder=self.state_builder,
            arbiter=self.arbiter,
            security_gate=self.security_gate,
            verification_engine=self.verification,
            recovery_engine=self.recovery,
            mouse_controller=self.mouse,
            keyboard_controller=self.keyboard,
        )

    def narrate(self, text: str) -> None:
        """Speaks execution status aloud through the non-overlapping Single TTS Queue."""
        speak(text)

    def set_api_key(self, api_key: str, provider: str = "auto", model_name: Optional[str] = None) -> None:
        """Sets active LLM API Key for autonomous computer-use operations."""
        from core.llm_computer_use_engine import LLMProvider
        prov_enum = LLMProvider(provider) if provider in [p.value for p in LLMProvider] else LLMProvider.AUTO
        self.llm_engine.set_api_key(api_key=api_key, provider=prov_enum, model_name=model_name)

    def execute_goal(
        self,
        goal: str,
        task_id: Optional[str] = None,
        approval_tokens: Optional[Dict[str, str]] = None,
        on_step_callback: Optional[Callable[[StepExecutionResult], None]] = None,
    ) -> PlanExecutionResult:
        """
        Executes a natural language goal:
          1. Check Fast Replay cache (zero-drift lightning replay)
          2. If cache miss / drift, OBSERVE machine state & consult LLM Computer Use Engine
          3. Settle-time convergence & Peripheral awareness check
          4. ACT, VERIFY, & RECORD entities into Task-Scoped Referential Memory
          5. Save verified workflow into Fast Replay Catalog
        """
        require_armed(get_kill_switch())

        # 1. Capture initial observation
        initial_state = self.state_builder.capture_state()
        active_win = ""
        if initial_state.active_window:
            active_win = initial_state.active_window.title if hasattr(initial_state.active_window, "title") else str(initial_state.active_window)

        elements = []
        if hasattr(initial_state, "detected_elements") and initial_state.detected_elements:
            elements = [el.to_dict() if hasattr(el, "to_dict") else dict(el) for el in initial_state.detected_elements]

        visible_wins = []
        if hasattr(initial_state, "visible_windows") and initial_state.visible_windows:
            visible_wins = [w.title if hasattr(w, "title") else str(w) for w in initial_state.visible_windows]

        # 2. Check for opportunistic peripheral interference (rogue modals / cookie consent)
        interference = self.human_suite.peripheral.scan_and_remedy(elements)
        if interference.found and interference.dismiss_action:
            self.narrate(f"Dismissing overlay dialog: {interference.details}")
            # Dismiss overlay before executing goal
            temp_plan = TaskPlan(plan_id="dismiss_overlay", goal="Dismiss overlay", actions=[interference.dismiss_action])
            self.security_gate.grant_tier1_task_approval(temp_plan.plan_id)
            self.loop.execute_plan(temp_plan, agent_id="computer_use_master")

        # 3. Check Fast Replay catalog
        cached_plan, is_hit = self.fast_replay_engine.get_or_compile_plan(
            goal=goal,
            current_window=active_win,
            current_elements=elements,
        )

        if is_hit and cached_plan:
            self.narrate(f"Fast Replay matched for: '{goal[:30]}'. Executing at native machine speed, Sir.")
            plan = cached_plan
        else:
            # 4. Propose plan via LLM Computer Use Engine
            obs = ComputerUseObservation(
                active_window=active_win,
                visible_windows=visible_wins,
                uia_elements=elements,
                screenshot_b64=None,
                screen_width=1920,
                screen_height=1080,
            )
            proposal = self.llm_engine.propose_actions_for_goal(
                goal=goal,
                observation=obs,
                working_memory=self.human_suite.memory.export_state(),
            )

            # Check confidence branch
            branch = self.human_suite.brancher.evaluate_branch(proposal.confidence, proposal.actions[0] if proposal.actions else ActionObject(action_id="act", type="observe"))
            if branch == "HALT_AND_ASK":
                self.narrate(f"Confidence low ({proposal.confidence:.0%}) for goal: {goal}. Halting for clarification, Sir.")
                return PlanExecutionResult(
                    plan_id=task_id or "plan_low_conf",
                    goal=goal,
                    total_steps=len(proposal.actions),
                    completed_steps=0,
                    success=False,
                    escalated_to_user=True,
                    details=f"Halted due to low confidence: {proposal.thought}",
                )

            plan = TaskPlan(
                plan_id=task_id or f"plan_{int(time.time())}",
                goal=goal,
                actions=proposal.actions,
            )

            # Record extracted entities into referential memory
            for k, v in proposal.referential_entities.items():
                self.human_suite.memory.record_entity(k, v)

        # 5. Authorize and execute plan via Turbo Executor
        self.security_gate.grant_tier1_task_approval(plan.plan_id)
        batch_res = self.turbo_executor.execute_action_batch(
            plan=plan,
            agent_id="computer_use_master",
            approval_tokens=approval_tokens,
        )

        result = PlanExecutionResult(
            plan_id=plan.plan_id,
            goal=plan.goal,
            total_steps=batch_res.total_actions,
            completed_steps=batch_res.executed_actions,
            success=batch_res.success,
            escalated_to_user=(batch_res.state == "AWAITING_PERMISSION"),
            details=batch_res.details,
        )

        # 6. If plan succeeded and was not from cache, save to Fast Replay catalog
        if result.success and not is_hit:
            anchors = [
                ReplayAnchor(name=a.target, expected_window=active_win)
                for a in plan.actions if a.target
            ]
            self.fast_replay_engine.catalog.save_replay(goal=goal, plan=plan, anchors=anchors)

        return result


def computer_use_agent_executor(task: Task) -> Any:
    """
    Standard agent_executor interface signature: def agent_executor(task: Task) -> Any
    """
    agent = ComputerUseAgent()
    res = agent.execute_goal(goal=task.description)
    return {"goal": task.description, "success": res.success}

