"""Agent 15: Calendar Agent.

Coordinates meeting schedules, analyzes calendar conflicts using RFC 5545 interval arithmetic,
and proposes optimal availability slots.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict
from agents.base import BaseAgent, AgentInput, AgentOutput
from workers.calendar_worker import CalendarWorker

logger = logging.getLogger("max.agents.calendar")


class CalendarAgent(BaseAgent):
    name = "CalendarAgent"
    description = "Coordinates schedules, checks RFC 5545 interval conflicts, and manages calendar events."
    permission_tier = 1

    def _execute(self, input_data: AgentInput) -> AgentOutput:
        summary = input_data.task_description or "Team Meeting"
        params = input_data.parameters or {}
        now = time.time()
        start_val = params.get("start_time", now + 3600.0)
        try:
            start_time = float(start_val)
        except (ValueError, TypeError):
            from datetime import datetime
            try:
                start_time = datetime.fromisoformat(str(start_val)).timestamp()
            except Exception:
                start_time = now + 3600.0

        end_val = params.get("end_time", start_time + 1800.0)
        try:
            end_time = float(end_val)
        except (ValueError, TypeError):
            from datetime import datetime
            try:
                end_time = datetime.fromisoformat(str(end_val)).timestamp()
            except Exception:
                end_time = start_time + 1800.0
        logger.info("CalendarAgent scheduling '%s' from %s to %s", summary, start_time, end_time)

        try:
            worker = CalendarWorker()
            conflicts = worker.check_conflicts(start_time, end_time)
            if conflicts:
                return AgentOutput(
                    success=False,
                    error=f"Schedule conflict detected with {len(conflicts)} existing event(s).",
                    artifacts={"conflicts": [c.summary for c in conflicts]},
                )

            event = worker.create_event(summary, start_time, end_time, allow_conflicts=True)
            return AgentOutput(
                success=True,
                result=f"Scheduled '{summary}' without conflicts (Event ID: {event.id}).",
                artifacts={"event_id": event.id, "start": start_time, "end": end_time},
            )
        except Exception as e:
            return AgentOutput(
                success=False,
                error=f"Calendar error: {e}",
            )
