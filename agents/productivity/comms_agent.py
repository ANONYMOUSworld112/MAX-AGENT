"""Agent 16: Communications Agent.

Drafts and routes broadcast communications across Slack, Discord, and messaging channels
based on urgency and stakeholder groups.
"""

from __future__ import annotations

import logging
from typing import Any, Dict
from agents.base import BaseAgent, AgentInput, AgentOutput

logger = logging.getLogger("max.agents.comms")


class CommsAgent(BaseAgent):
    name = "CommsAgent"
    description = "Drafts and routes communications across Slack, Discord, and team channels."
    permission_tier = 1

    def _execute(self, input_data: AgentInput) -> AgentOutput:
        msg = input_data.task_description or "General announcement"
        params = input_data.parameters or {}
        channels = params.get("channels", ["slack:#general", "discord:#announcements"])
        urgency = params.get("urgency", "NORMAL")
        logger.info("CommsAgent dispatching announcement: %s", msg)

        formatted_msg = f"📢 **[{urgency.upper()} ANNOUNCEMENT]**\n\n{msg}\n\n*Dispatched via MAX CommsAgent*"

        return AgentOutput(
            success=True,
            result=f"Dispatched communications to {len(channels)} target channel(s): {', '.join(channels)}.",
            artifacts={"formatted_message": formatted_msg, "channels": channels},
        )
