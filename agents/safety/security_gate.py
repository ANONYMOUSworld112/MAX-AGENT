"""Agent 26: Security Gate.

Enforces system security policy across T0–T3 permission tiers.
Blocks dangerous operations, irreversible disk formats, and unchoked side-effects.
"""

from __future__ import annotations

import logging
from typing import Any, Dict
from agents.base import BaseAgent, AgentInput, AgentOutput
from core.reflex.guardrails import ReflexGuardrails, RiskTier

logger = logging.getLogger("max.agents.security_gate")


class SecurityGate(BaseAgent):
    name = "SecurityGate"
    description = "Enforces permission tiers (T0-T3) and blocks dangerous operations without confirmation."
    permission_tier = 0

    def _execute(self, input_data: AgentInput) -> AgentOutput:
        command = input_data.task_description or "Check system safety"
        logger.info("SecurityGate evaluating command safety: %s", command)

        guardrails = ReflexGuardrails(fallback_mode=True)
        decision = guardrails.check_safety(command)

        tier_name = f"Tier {decision.risk_tier.value}"
        is_blocked = (decision.risk_tier == RiskTier.TIER_3_HARD_BLOCKED)
        requires_approval = (decision.risk_tier == RiskTier.TIER_2_CONFIRM_ON_WRITE)

        if is_blocked:
            return AgentOutput(
                success=False,
                error=f"Hard-blocked by SecurityGate: {decision.reason} ({tier_name})",
                artifacts={"tier": tier_name, "blocked": True},
            )

        return AgentOutput(
            success=True,
            result=f"SecurityGate evaluated: {tier_name} ({'Requires Confirmation' if requires_approval else 'Allowed'}).",
            artifacts={"tier": tier_name, "requires_approval": requires_approval, "reason": decision.reason},
        )
