"""Agent 26: Security Gate Agent.

Enforces static and behavioral risk classification across all incoming requests.
Delegates to ReflexGuardrails to categorize actions into Tier 0/1/2/3.
Operates at Permission Tier 3 (Guard evaluator).
"""

from __future__ import annotations

import logging
from typing import Any, Dict
from agents.base import BaseAgent, AgentInput, AgentOutput
from core.reflex.guardrails import ReflexGuardrails, RiskTier

logger = logging.getLogger("max.agents.security_gate")


class SecurityGate(BaseAgent):
    name = "SecurityGate"
    description = "Evaluates instructions against 4-tier security guardrails and detects blocked actions."
    permission_tier = 3  # Hard Block evaluator

    def __init__(self, guardrails: ReflexGuardrails | None = None, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.guardrails = guardrails or ReflexGuardrails(fallback_mode=True)

    def _execute(self, input_data: AgentInput) -> AgentOutput:
        desc = input_data.task_description
        logger.info("SecurityGate evaluating: %s", desc)

        guard_result = self.guardrails.check_safety(desc)

        artifacts: Dict[str, Any] = {
            "is_safe": guard_result.is_safe,
            "risk_tier": int(guard_result.risk_tier),
            "tier_name": guard_result.risk_tier.name,
            "reason": guard_result.reason,
        }

        if guard_result.risk_tier == RiskTier.TIER_3_HARD_BLOCKED:
            return AgentOutput(
                success=False,
                error=f"SECURITY_ALERT: Instruction blocked ({guard_result.reason})",
                artifacts=artifacts,
            )

        return AgentOutput(
            success=True,
            result=f"Security assessment: {guard_result.risk_tier.name} (Safe={guard_result.is_safe})",
            artifacts=artifacts,
        )
