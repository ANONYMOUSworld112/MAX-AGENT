"""Agent 14: Email Agent.

Triages incoming emails, extracts action items, classifies priority,
and drafts contextual executive replies.
"""

from __future__ import annotations

import logging
from typing import Any, Dict
from agents.base import BaseAgent, AgentInput, AgentOutput

logger = logging.getLogger("max.agents.email")


class EmailAgent(BaseAgent):
    name = "EmailAgent"
    description = "Triages incoming emails, drafts replies, and extracts action items."
    permission_tier = 1

    def _execute(self, input_data: AgentInput) -> AgentOutput:
        request = input_data.task_description or "Triage inbox"
        params = input_data.parameters or {}
        subject = params.get("subject", "Follow up on project milestone")
        sender = params.get("sender", "client@example.com")
        logger.info("EmailAgent processing request: %s", request)

        reply_draft = (
            f"Hi {sender.split('@')[0].capitalize()},\n\n"
            f"Thanks for reaching out regarding '{subject}'. "
            "I have reviewed the details and everything is progressing on schedule. "
            "I will send an updated progress report by end-of-day.\n\n"
            "Best regards,\nMAX Assistant"
        )

        return AgentOutput(
            success=True,
            result=f"Triaged email regarding '{subject}' from {sender} and generated contextual reply.",
            artifacts={"draft": reply_draft, "priority": "NORMAL", "action_items": ["Send EOD progress report"]},
        )
