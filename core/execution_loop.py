"""
MAX OS — Reactive Computer-Use Execution Loop (Section 10).
Applies the rigorous single-step reactive pipeline:
  OBSERVE -> UNDERSTAND -> PLAN -> ACT -> VERIFY -> RECOVER
Guarantees MAX never executes multi-step plans blind.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from core.command_model import ActionObject, CommandModel, TaskPlan
from core.controllers.keyboard_controller import KeyboardController
from core.controllers.mouse_controller import MouseController
from core.input_arbiter import InputArbiter, OwnershipLease
from core.kill_switch import get_kill_switch, require_armed
from core.perception.state_builder import ComputerState, ComputerStateBuilder, TaskContext
from core.recovery.recovery_engine import FailureClass, RecoveryEngine, RecoveryStrategy
from core.security.security_gate import RiskTier, SecurityGate
from core.verification.engine import VerificationEngine, VerificationOutcome, VerificationResult


@dataclass
class StepExecutionResult:
    step_index: int
    action: ActionObject
    before_state: ComputerState
    after_state: ComputerState
    verification: VerificationResult
    recovery_attempts: int = 0
    success: bool = False
    duration_ms: int = 0


@dataclass
class PlanExecutionResult:
    plan_id: str
    goal: str
    total_steps: int
    completed_steps: int
    step_results: List[StepExecutionResult] = field(default_factory=list)
    success: bool = False
    escalated_to_user: bool = False
    details: str = ""


class UniversalExecutionLoop:
    """
    Reactive Single-Step Computer-Use Execution Loop.
    Executes one action at a time with live re-observation and verification.
    """

    def __init__(
        self,
        state_builder: Optional[ComputerStateBuilder] = None,
        arbiter: Optional[InputArbiter] = None,
        security_gate: Optional[SecurityGate] = None,
        verification_engine: Optional[VerificationEngine] = None,
        recovery_engine: Optional[RecoveryEngine] = None,
        mouse_controller: Optional[MouseController] = None,
        keyboard_controller: Optional[KeyboardController] = None,
    ):
        self.state_builder = state_builder or ComputerStateBuilder()
        self.arbiter = arbiter or InputArbiter.get_instance()
        self.security_gate = security_gate or SecurityGate()
        self.verification = verification_engine or VerificationEngine()
        self.recovery = recovery_engine or RecoveryEngine()
        self.mouse = mouse_controller or MouseController(arbiter=self.arbiter)
        self.keyboard = keyboard_controller or KeyboardController(arbiter=self.arbiter, mouse_controller=self.mouse)

    def execute_plan(
        self,
        plan: TaskPlan,
        agent_id: str = "computer_use_agent",
        approval_tokens: Optional[Dict[str, str]] = None,
        on_step_callback: Optional[Callable[[StepExecutionResult], None]] = None,
    ) -> PlanExecutionResult:
        """
        Executes a TaskPlan step-by-step with live re-observation and verification.
        """
        require_armed(get_kill_switch())
        tokens = approval_tokens or {}
        step_results: List[StepExecutionResult] = []

        with self.arbiter.acquire(agent_id) as lease:
            while not plan.is_completed:
                action = plan.current_action
                if not action:
                    break

                step_res = self.execute_single_step(
                    action=action,
                    task_id=plan.plan_id,
                    step_index=plan.current_step_index,
                    agent_id=agent_id,
                    lease=lease,
                    approval_token=tokens.get(action.action_id),
                )
                step_results.append(step_res)

                if on_step_callback:
                    on_step_callback(step_res)

                if not step_res.success:
                    # If step could not be verified or recovered
                    return PlanExecutionResult(
                        plan_id=plan.plan_id,
                        goal=plan.goal,
                        total_steps=len(plan.actions),
                        completed_steps=len(step_results) - 1,
                        step_results=step_results,
                        success=False,
                        escalated_to_user=True,
                        details=f"Step {plan.current_step_index} ('{action.type}') failed verification: {step_res.verification.evidence}",
                    )

                plan.advance()

        return PlanExecutionResult(
            plan_id=plan.plan_id,
            goal=plan.goal,
            total_steps=len(plan.actions),
            completed_steps=len(step_results),
            step_results=step_results,
            success=True,
            escalated_to_user=False,
            details="All steps executed and positively verified.",
        )

    def execute_single_step(
        self,
        action: ActionObject,
        task_id: str,
        step_index: int,
        agent_id: str,
        lease: OwnershipLease,
        approval_token: Optional[str] = None,
    ) -> StepExecutionResult:
        """
        Executes ONE single action:
          1. OBSERVE (capture fresh ComputerState)
          2. AUTHORIZE (check SecurityGate)
          3. ACT (dispatch physical controller action)
          4. OBSERVE (rebuild post-action ComputerState)
          5. VERIFY (evaluate positive evidence)
          6. RECOVER (if verification is UNKNOWN or FAILURE)
        """
        start_mono = time.monotonic()

        # 1. OBSERVE (Pre-action ground truth)
        from core.perception.live_stream import ContinuousDesktopStreamer
        streamer = ContinuousDesktopStreamer.get_instance()
        action_desc = f"{action.type} -> {action.semantic_target or action.target}"
        streamer.set_current_action(task=task_id, action=action_desc, verif="ACTING")

        before_state = self.state_builder.capture_state()

        # 2. AUTHORIZE via SecurityGate
        self.security_gate.authorize_action(
            action_type=action.type,
            target=action.target,
            task_id=task_id,
            action_id=action.action_id,
            approval_token=approval_token,
            action_payload=action.payload,
        )

        # 3. ACT
        self._dispatch_action(action, before_state, lease)

        # 4. OBSERVE (Post-action ground truth)
        time.sleep(0.15)  # Allow UI reflow to settle
        after_state = self.state_builder.capture_state(
            task_context=TaskContext(previous_action=action.to_dict())
        )

        # 5. VERIFY
        verif_res = self.verification.verify_action(
            action_type=action.type,
            expected=action.expected_result,
            before_state=before_state,
            after_state=after_state,
        )
        streamer.set_current_action(task=task_id, action=action_desc, verif=verif_res.outcome.value)

        recovery_count = 0

        # 6. RECOVER if not verified as SUCCESS
        if verif_res.outcome != VerificationOutcome.SUCCESS:
            failure_cls = self.recovery.classify_failure(
                error=verif_res.evidence, evidence=str(verif_res.mismatches)
            )
            # Execute progressive recovery attempts
            while verif_res.outcome != VerificationOutcome.SUCCESS:
                strategy = self.recovery.get_next_strategy(task_id, action.action_id, failure_cls)
                if strategy == RecoveryStrategy.ESCALATE_USER:
                    break

                recovery_count += 1
                # Apply strategy
                if strategy == RecoveryStrategy.REOBSERVE:
                    after_state = self.state_builder.capture_state()
                elif strategy == RecoveryStrategy.RETRY:
                    self._dispatch_action(action, after_state, lease)
                    time.sleep(0.2)
                    after_state = self.state_builder.capture_state()

                # Re-verify after recovery attempt
                verif_res = self.verification.verify_action(
                    action_type=action.type,
                    expected=action.expected_result,
                    before_state=before_state,
                    after_state=after_state,
                )
                self.recovery.record_attempt(
                    task_id=task_id,
                    action_id=action.action_id,
                    failure_class=failure_cls,
                    strategy=strategy,
                    success=(verif_res.outcome == VerificationOutcome.SUCCESS),
                    details=verif_res.evidence,
                )

        duration_ms = int((time.monotonic() - start_mono) * 1000)

        return StepExecutionResult(
            step_index=step_index,
            action=action,
            before_state=before_state,
            after_state=after_state,
            verification=verif_res,
            recovery_attempts=recovery_count,
            success=(verif_res.outcome == VerificationOutcome.SUCCESS),
            duration_ms=duration_ms,
        )

    def _dispatch_action(
        self, action: ActionObject, state: ComputerState, lease: OwnershipLease
    ) -> None:
        """Translates semantic ActionObject into live controller and launcher calls."""
        from core.app_launcher import LiveAppLauncher
        act_type = action.type.lower()

        if act_type in {"open_application", "launch_app", "launch"}:
            LiveAppLauncher.launch_live_application(action.target, wait_seconds=1.5)

        elif act_type in {"navigate", "open_url"}:
            if state.active_window and any(b in state.active_window.process_name.lower() for b in ("edge", "chrome", "brave", "firefox")):
                self.keyboard.hotkey("ctrl", "l", lease=lease)
                time.sleep(0.2)
                self.keyboard.type_text(action.target, human_cadence=False, lease=lease)
                time.sleep(0.1)
                self.keyboard.enter(lease=lease)
                time.sleep(1.5)
            else:
                LiveAppLauncher.open_live_url(action.target, wait_seconds=2.0)

        elif act_type in {"click", "click_element"}:
            target_elem = state.find_element(action.semantic_target or action.target)
            if target_elem:
                self.mouse.click_element(target_elem, lease=lease)
            else:
                self.mouse.click(lease=lease)

        elif act_type in {"type", "type_text"}:
            target_elem = state.find_element(action.semantic_target or action.target) if action.target else None
            self.keyboard.focus_and_type(
                element=target_elem,
                text=action.value or action.target,
                human_cadence=True,
                lease=lease,
            )

        elif act_type == "scroll":
            self.mouse.scroll(direction=action.payload.get("direction", "down"), lease=lease)

        elif act_type == "submit":
            self.keyboard.enter(lease=lease)
            time.sleep(0.8)

        elif act_type == "observe":
            time.sleep(0.3)

        elif act_type in {"speak", "narrate"}:
            from core.single_tts_queue import speak
            speak(action.value or action.target)
