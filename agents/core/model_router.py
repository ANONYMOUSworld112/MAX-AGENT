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
        desc = input_data.task_description.lower()
        if "deep" in desc or "complex" in desc or "architect" in desc:
            selected = "gemini-1.5-pro"
        elif "local" in desc or "reflex" in desc:
            selected = "laya-onnx-local"
        else:
            selected = "gemini-2.5-flash"

        return AgentOutput(
            success=True,
            result=f"Selected model '{selected}' for task.",
            artifacts={"selected_model": selected}
        )
