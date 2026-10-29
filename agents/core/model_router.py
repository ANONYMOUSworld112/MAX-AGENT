"""Agent 4: Model Router.

Dynamically selects the best LLM or local model backend based on task complexity,
token budget, latency requirements, and system network connectivity.
"""

from __future__ import annotations

import logging
from typing import Any, Dict
from agents.base import BaseAgent, AgentInput, AgentOutput

logger = logging.getLogger("max.agents.model_router")


class ModelRouter(BaseAgent):
    name = "ModelRouter"
    description = "Dynamically routes requests to optimal LLM or local Ollama backends."
    permission_tier = 0

    def _execute(self, input_data: AgentInput) -> AgentOutput:
        prompt = input_data.task_description or ""
        params = input_data.parameters or {}
        estimated_tokens = int(params.get("estimated_tokens", len(prompt.split()) * 2))
        latency_sensitive = bool(params.get("latency_sensitive", False))
        offline_required = bool(params.get("offline_required", False))

        # Model routing logic
        if offline_required:
            selected_model = "ollama/qwen2.5-coder:7b"
            provider = "OllamaLocal"
            rationale = "Offline execution requested; selected local Ollama provider."
        elif estimated_tokens > 8000:
            selected_model = "models/gemini-1.5-pro"
            provider = "GoogleCloud"
            rationale = "High token context exceeds standard window; routed to Gemini Pro."
        elif latency_sensitive:
            selected_model = "models/gemini-2.5-flash-live"
            provider = "GoogleLiveWebSocket"
            rationale = "Ultra-low latency required; routed to live streaming audio/text channel."
        else:
            selected_model = "models/gemini-2.5-flash"
            provider = "GoogleCloud"
            rationale = "Optimal cost/latency trade-off for standard cognitive tasks."

        decision = {
            "selected_model": selected_model,
            "provider": provider,
            "estimated_tokens": estimated_tokens,
            "rationale": rationale,
        }

        return AgentOutput(
            success=True,
            result=f"Routed task to {selected_model} via {provider}: {rationale}",
            artifacts={"routing_decision": decision},
        )
