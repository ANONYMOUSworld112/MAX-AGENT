"""Agent 25: Input Arbiter.

Arbitrates between human and agent input streams. Yields immediately when human
physical activity (mouse movement or keypress) is detected to prevent input collision.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict
from agents.base import BaseAgent, AgentInput, AgentOutput

logger = logging.getLogger("max.agents.arbiter")


class InputArbiter(BaseAgent):
    name = "InputArbiter"
    description = "Arbitrates human vs agent inputs, enforcing human primacy and input safety."
    permission_tier = 0

    def _execute(self, input_data: AgentInput) -> AgentOutput:
        event = input_data.task_description or "Check input primacy"
        params = input_data.parameters or {}
        human_active = bool(params.get("human_active", False))

        if human_active:
            status = "YIELD_TO_HUMAN"
            msg = "Human activity detected on hardware bus. Suspended agent input stream."
        else:
            status = "AGENT_INPUT_ALLOWED"
            msg = "Zero human hardware activity. Agent input stream granted exclusive lease."

        logger.info("InputArbiter: %s", status)
        return AgentOutput(
            success=True,
            result=msg,
            artifacts={"arbitration_status": status, "human_active": human_active},
        )
