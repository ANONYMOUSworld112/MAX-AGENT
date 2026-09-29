"""Agent 16: Comms Agent.

Manages communications across external platforms (Slack, Discord, Microsoft Teams).
Operates at Permission Tier 2 (Requires Confirmation before sending external messages).
"""

from __future__ import annotations

import logging
from typing import Any, Dict
from agents.base import BaseAgent, AgentInput, AgentOutput

logger = logging.getLogger("max.agents.comms")


class CommsAgent(BaseAgent):
    name = "CommsAgent"
    description = "Dispatches and summarizes messages across Slack, Teams, and Discord."
    permission_tier = 2  # Requires Confirmation

    def _execute(self, input_data: AgentInput) -> AgentOutput:
        desc = input_data.task_description
        logger.info("CommsAgent dispatching: %s", desc)

        platform = input_data.parameters.get("platform", "slack")
        channel = input_data.parameters.get("channel", "general")
        message = input_data.parameters.get("message", desc)
        action = input_data.parameters.get("action", "send")

        artifacts: Dict[str, Any] = {
            "platform": platform,
            "channel": channel,
            "message": message,
            "action": action,
            "requires_confirmation": action == "send",
        }

        return AgentOutput(
            success=True,
            result=f"Comms message queued for {platform} #{channel}: '{message}'",
            artifacts=artifacts,
        )
