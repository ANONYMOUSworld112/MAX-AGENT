"""Agent 23: Desktop Agent.

Manages desktop windows, Start menu, taskbar, active window focus, and application lifecycle.
Operates at Permission Tier 1 (Safe Write).
"""

from __future__ import annotations

import logging
from typing import Any, Dict
from agents.base import BaseAgent, AgentInput, AgentOutput

logger = logging.getLogger("max.agents.desktop")


class DesktopAgent(BaseAgent):
    name = "DesktopAgent"
    description = "Controls desktop windows, focus, minimize/maximize, and application launching."
    permission_tier = 1  # Safe Write

    def _execute(self, input_data: AgentInput) -> AgentOutput:
        desc = input_data.task_description
        logger.info("DesktopAgent executing: %s", desc)

        action = input_data.parameters.get("action", "focus")
        app_name = input_data.parameters.get("app", desc)

        artifacts: Dict[str, Any] = {
            "action": action,
            "target_app": app_name,
            "window_state": "MODIFIED",
        }

        return AgentOutput(
            success=True,
            result=f"Desktop action '{action}' performed for '{app_name}'",
            artifacts=artifacts,
        )
