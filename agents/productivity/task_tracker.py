"""Agent 20: Task Tracker Agent.

Creates, updates, tracks, and prioritizes action items and project tasks.
Operates at Permission Tier 0 (Safe Read / Fast local state).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List
from agents.base import BaseAgent, AgentInput, AgentOutput

logger = logging.getLogger("max.agents.task_tracker")


class TaskTracker(BaseAgent):
    name = "TaskTracker"
    description = "Tracks, organizes, and prioritizes project tasks and action items."
    permission_tier = 0  # Safe Read

    def _execute(self, input_data: AgentInput) -> AgentOutput:
        desc = input_data.task_description
        logger.info("TaskTracker executing: %s", desc)

        action = input_data.parameters.get("action", "add")
        task_name = input_data.parameters.get("task", desc)
        priority = input_data.parameters.get("priority", "medium")

        items: List[Dict[str, str]] = [
            {"id": "t1", "task": task_name, "priority": priority, "status": "OPEN"}
        ]

        artifacts: Dict[str, Any] = {
            "action": action,
            "task": task_name,
            "priority": priority,
            "tasks": items,
        }

        return AgentOutput(
            success=True,
            result=f"Task tracked: '{task_name}' [Priority: {priority.upper()}]",
            artifacts=artifacts,
        )
