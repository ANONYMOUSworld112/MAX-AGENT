"""
MAX OS - Risk Engine
core/risk_engine.py

Every action carries a RiskLevel. The engine decides autonomous-execute vs
ask-human, using the CapabilityProfile as the ceiling. It never asks the
action itself, or any LLM output, what the ceiling should be.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from core.command_model import ActionRequest as CanonicalActionRequest
from core.platform.detector import CapabilityProfile, RiskLevel, detect_capability_profile
from core.security.security_gate import RiskTier, SecurityGate


@dataclass
class ActionRequest:
    description: str
    risk: RiskLevel
    agent: str
    task_id: str
    target: str = ""
    action_type: str = "observe"


@dataclass
class ActionDecision:
    approved: bool
    autonomous: bool
    reason: str


ConfirmationCallback = Callable[[ActionRequest], bool]
"""Returns True if the human approved the action, False otherwise."""


class RiskEngine:
    def __init__(
        self,
        profile: Optional[CapabilityProfile] = None,
        confirmation_callback: Optional[ConfirmationCallback] = None,
        security_gate: Optional[SecurityGate] = None,
    ) -> None:
        self.profile = profile or detect_capability_profile()
        self._confirm = confirmation_callback or self._default_confirmation
        self.security_gate = security_gate or SecurityGate()

    def enforce(self, request: ActionRequest | CanonicalActionRequest) -> ActionDecision:
        # Harmonize request representation
        if isinstance(request, CanonicalActionRequest):
            req_risk = request.risk_level
            req_agent = request.agent_id
            req_desc = request.description or request.action_type
            req_target = request.target
            req_type = request.action_type
        else:
            req_risk = request.risk
            req_agent = request.agent
            req_desc = request.description
            req_target = request.target
            req_type = request.action_type

        # Check Security Gate classification
        sec_eval = self.security_gate.classify_action_risk(req_type, req_target)
        if sec_eval.risk_tier == RiskTier.TIER_2 or sec_eval.is_destructive_or_irreversible:
            req_risk = RiskLevel.CRITICAL

        # Hard gate first, before anything else touches this decision.
        if req_risk == RiskLevel.CRITICAL:
            approved = self._confirm(request)
            return ActionDecision(
                approved=approved,
                autonomous=False,
                reason="CRITICAL actions always require explicit human confirmation.",
            )

        if self.profile.can_run_autonomously(req_risk):
            return ActionDecision(
                approved=True,
                autonomous=True,
                reason=f"Within autonomous ceiling ({self.profile.max_autonomous_risk.value}) "
                f"for {self.profile.os_family.value}.",
            )

        approved = self._confirm(request)
        return ActionDecision(
            approved=approved,
            autonomous=False,
            reason=f"Above autonomous ceiling ({self.profile.max_autonomous_risk.value}); "
            "human confirmation required.",
        )

    @staticmethod
    def _default_confirmation(request: Any) -> bool:
        # Placeholder for CLI/UI wiring.
        agent = getattr(request, "agent", getattr(request, "agent_id", "Agent"))
        desc = getattr(request, "description", getattr(request, "action_type", "Action"))
        risk = getattr(request, "risk", getattr(request, "risk_level", RiskLevel.CRITICAL))
        risk_val = risk.value if hasattr(risk, "value") else str(risk)
        answer = input(
            f"[CONFIRM REQUIRED] {agent}: {desc} "
            f"(risk={risk_val}) — allow? [y/N] "
        )
        return answer.strip().lower() == "y"

