"""Agent 21: Meeting Prep Agent.

Generates pre-meeting briefings, attendee dossiers, agenda synthesis, and follow-up templates.
Operates at Permission Tier 0 (Safe Read).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List
from agents.base import BaseAgent, AgentInput, AgentOutput

logger = logging.getLogger("max.agents.meeting_prep")


class MeetingPrep(BaseAgent):
    name = "MeetingPrep"
    description = "Prepares meeting dossiers, agendas, background research, and notes templates."
    permission_tier = 0  # Safe Read

    def _execute(self, input_data: AgentInput) -> AgentOutput:
        desc = input_data.task_description
        logger.info("MeetingPrep preparing for: %s", desc)

        meeting_title = input_data.parameters.get("title", desc)
        attendees: List[str] = input_data.parameters.get("attendees", ["Founder", "Stakeholders"])
        agenda: List[str] = input_data.parameters.get("agenda", ["Status Update", "Architecture Decisions", "Next Steps"])

        artifacts: Dict[str, Any] = {
            "title": meeting_title,
            "attendees": attendees,
            "agenda": agenda,
            "briefing_doc": f"# Briefing: {meeting_title}\n\n## Attendees: {', '.join(attendees)}\n\n## Agenda:\n" + "\n".join(f"- {a}" for a in agenda),
        }

        return AgentOutput(
            success=True,
            result=f"Meeting briefing prepared for '{meeting_title}' with {len(attendees)} attendees",
            artifacts=artifacts,
        )
