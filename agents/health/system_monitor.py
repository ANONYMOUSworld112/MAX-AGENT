"""Agent 28: System Monitor Agent.

Gathers real-time CPU, RAM, GPU, temperature, and process metrics.
Wraps the existing actions/system_monitor.py infrastructure.
Operates at Permission Tier 0 (Safe Read).
"""

from __future__ import annotations

import logging
from typing import Any, Dict
from agents.base import BaseAgent, AgentInput, AgentOutput

logger = logging.getLogger("max.agents.system_monitor")


class SystemMonitorAgent(BaseAgent):
    name = "SystemMonitorAgent"
    description = "Monitors real-time CPU, RAM, GPU, disk, and thermal metrics."
    permission_tier = 0  # Safe Read

    def _execute(self, input_data: AgentInput) -> AgentOutput:
        """Not yet implemented (Rule 1-H1 Honesty)."""
        raise NotImplementedError(f"Agent '{self.name}' is not implemented")
