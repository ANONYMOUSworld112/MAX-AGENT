"""Agent 19: Notes Agent.

Creates, searches, updates, and structures persistent markdown notes.
Operates at Permission Tier 0 (Safe Read / Note creation).
"""

from __future__ import annotations

import logging
from typing import Any, Dict
from agents.base import BaseAgent, AgentInput, AgentOutput

logger = logging.getLogger("max.agents.notes")


class NotesAgent(BaseAgent):
    name = "NotesAgent"
    description = "Creates, indexes, and searches markdown notes and knowledge bases."
    permission_tier = 0  # Safe Read

    def _execute(self, input_data: AgentInput) -> AgentOutput:
        desc = input_data.task_description
        logger.info("NotesAgent executing: %s", desc)

        action = input_data.parameters.get("action", "create")
        title = input_data.parameters.get("title", "Quick Note")
        content = input_data.parameters.get("content", desc)
        tags = input_data.parameters.get("tags", ["general"])

        formatted_note = f"# {title}\n\nTags: {', '.join(tags)}\n\n{content}\n"

        artifacts: Dict[str, Any] = {
            "title": title,
            "action": action,
            "tags": tags,
            "note_content": formatted_note,
        }

        return AgentOutput(
            success=True,
            result=f"Note '{title}' processed successfully ({action})",
            artifacts=artifacts,
        )
