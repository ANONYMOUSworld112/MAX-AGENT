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
        """Not yet implemented (Rule 1-H1 Honesty)."""
        raise NotImplementedError(f"Agent '{self.name}' is not implemented")
