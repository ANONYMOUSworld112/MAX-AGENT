"""Agent 20: Task Tracker.

Maintains active task queues, tracks progress across projects, and integrates
with ReminderWorker to alert on impending deadlines.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict
from agents.base import BaseAgent, AgentInput, AgentOutput
from workers.reminder_worker import ReminderWorker

logger = logging.getLogger("max.agents.task_tracker")


class TaskTracker(BaseAgent):
    name = "TaskTracker"
    description = "Maintains task queues, tracks progress, and alerts on deadlines."
    permission_tier = 1

    def _execute(self, input_data: AgentInput) -> AgentOutput:
        task_text = input_data.task_description or "Check daily goals"
        params = input_data.parameters or {}
        due_in_seconds = float(params.get("due_in_seconds", 1800.0))
        priority = params.get("priority", "NORMAL")

        logger.info("TaskTracker registering task: %s", task_text)
        try:
            worker = ReminderWorker()
            rem = worker.create_reminder(
                text=task_text,
                due_time=time.time() + due_in_seconds,
                priority=priority,
            )
            return AgentOutput(
                success=True,
                result=f"Registered task '{task_text}' (Priority: {priority}, Reminder ID: {rem.id}).",
                artifacts={"task_id": rem.id, "due_time": rem.due_time, "priority": priority},
            )
        except Exception as e:
            return AgentOutput(
                success=False,
                error=f"TaskTracker error: {e}",
            )
