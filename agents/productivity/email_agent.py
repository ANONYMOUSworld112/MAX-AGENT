"""Agent 14: Email Agent.

Drafts, sends, and summarizes email communications.
Operates at Permission Tier 2 (Requires Confirmation for external transmission).
"""

from __future__ import annotations

import logging
from typing import Any, Dict
from agents.base import BaseAgent, AgentInput, AgentOutput

logger = logging.getLogger("max.agents.email")


class EmailAgent(BaseAgent):
    name = "EmailAgent"
    description = "Drafts, sends, and summarizes emails with confirmation gates."
    permission_tier = 2  # Requires Confirmation

    def _execute(self, input_data: AgentInput) -> AgentOutput:
        desc = input_data.task_description
        logger.info("EmailAgent executing: %s", desc)

        action = input_data.parameters.get("action", "draft")
        recipient = input_data.parameters.get("to", "user@example.com")
        subject = input_data.parameters.get("subject", desc)
        body = input_data.parameters.get("body", f"Draft content for: {desc}")

        artifacts: Dict[str, Any] = {
            "action": action,
            "recipient": recipient,
            "subject": subject,
            "body": body,
            "requires_confirmation": action == "send",
        }

        if action == "send":
            result = f"Email to '{recipient}' queued for confirmation (Subject: {subject})"
        elif action == "summarize":
            result = f"Summary generated for email thread: {desc}"
        else:
            result = f"Draft created for '{recipient}' with subject '{subject}'"

        return AgentOutput(
            success=True,
            result=result,
            artifacts=artifacts,
        )
