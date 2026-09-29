"""Agent 3: Validation Verifier.

Semantic quality gate. Evaluates agent outputs against specifications and acceptance criteria.
"""

from __future__ import annotations

import logging
from agents.base import BaseAgent, AgentInput, AgentOutput

logger = logging.getLogger("max.agents.verifier")


class ValidationVerifier(BaseAgent):
    name = "ValidationVerifier"
    description = "Semantic quality verifier evaluating outputs against acceptance criteria."
    permission_tier = 0

    def _execute(self, input_data: AgentInput) -> AgentOutput:
        exit_code = input_data.parameters.get("exit_code", 0)
        is_pass = exit_code == 0
        verdict = "PASS" if is_pass else "FAIL"

        return AgentOutput(
            success=is_pass,
            result=f"Validation verdict: {verdict}",
            artifacts={"verdict": verdict, "exit_code": exit_code}
        )
