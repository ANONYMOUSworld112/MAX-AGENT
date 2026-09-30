"""Agent 4: Model Router.

Selects the optimal model/endpoint based on latency, reasoning depth, and cost budget.
"""

from __future__ import annotations

import logging
from agents.base import BaseAgent, AgentInput, AgentOutput

logger = logging.getLogger("max.agents.model_router")


class ModelRouter(BaseAgent):
    name = "ModelRouter"
    description = "Selects the optimal LLM (Gemini 2.5 Flash, Gemini 1.5 Pro, or Local ONNX) for the task."
    permission_tier = 0

    def _execute(self, input_data: AgentInput) -> AgentOutput:
        """Not yet implemented (Rule 1-H1 Honesty)."""
        raise NotImplementedError(f"Agent '{self.name}' is not implemented")
