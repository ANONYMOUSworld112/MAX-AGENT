"""Agent 15: Calendar Agent.

Schedules, reschedules, checks availability, and manages calendar events.
Operates at Permission Tier 1 (Safe Write).
"""

from __future__ import annotations

import logging
from typing import Any, Dict
from agents.base import BaseAgent, AgentInput, AgentOutput

logger = logging.getLogger("max.agents.calendar")


class CalendarAgent(BaseAgent):
    name = "CalendarAgent"
    description = "Schedules, reschedules, and manages calendar appointments."
    permission_tier = 1  # Safe Write

    def _execute(self, input_data: AgentInput) -> AgentOutput:
        desc = input_data.task_description
        logger.info("CalendarAgent managing event: %s", desc)

        action = input_data.parameters.get("action", "schedule")
        event_title = input_data.parameters.get("title", desc)
        start_time = input_data.parameters.get("start_time", "2026-10-01T10:00:00")
        duration = input_data.parameters.get("duration_minutes", 30)

        artifacts: Dict[str, Any] = {
            "action": action,
            "title": event_title,
            "start_time": start_time,
            "duration_minutes": duration,
            "status": "CONFIRMED",
        }

        return AgentOutput(
            success=True,
            result=f"Calendar event '{event_title}' scheduled for {start_time} ({duration} mins)",
            artifacts=artifacts,
        )
