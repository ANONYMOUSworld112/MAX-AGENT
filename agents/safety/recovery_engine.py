"""Agent 27: Recovery Engine.

Executes the 8-step failure recovery pipeline when an automation action or tool fails:
1. re-observe
2. refresh state
3. search again
4. alternative method
5. retry
6. change strategy
7. replan
8. ask user
Operates at Permission Tier 0 (Safe Read / Recovery Orchestrator).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List
from agents.base import BaseAgent, AgentInput, AgentOutput

logger = logging.getLogger("max.agents.recovery_engine")


class RecoveryEngine(BaseAgent):
    name = "RecoveryEngine"
    description = "Executes the 8-step failure recovery pipeline for interrupted or failed operations."
    permission_tier = 0  # Safe Read

    RECOVERY_STEPS: List[str] = [
        "re-observe",
        "refresh_state",
        "search_again",
        "alternative_method",
        "retry",
        "change_strategy",
        "replan",
        "ask_user",
    ]

    def _execute(self, input_data: AgentInput) -> AgentOutput:
        desc = input_data.task_description
        logger.info("RecoveryEngine handling failure: %s", desc)

        failure_reason = input_data.parameters.get("error", desc)
        attempt_count = input_data.parameters.get("attempt", 1)

        # Select recovery step based on failure attempt
        step_index = min(attempt_count - 1, len(self.RECOVERY_STEPS) - 1)
        recommended_step = self.RECOVERY_STEPS[step_index]

        artifacts: Dict[str, Any] = {
            "failure_reason": failure_reason,
            "attempt": attempt_count,
            "recommended_step": recommended_step,
            "pipeline_steps": self.RECOVERY_STEPS,
            "escalate_to_user": recommended_step == "ask_user",
        }

        return AgentOutput(
            success=True,
            result=f"Recovery strategy for attempt {attempt_count}: '{recommended_step}'",
            artifacts=artifacts,
        )
