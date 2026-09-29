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
        desc = input_data.task_description
        logger.info("SystemMonitorAgent reading metrics: %s", desc)

        metrics: Dict[str, Any] = {}
        try:
            from actions.system_monitor import get_system_status
            metrics = get_system_status()
        except Exception as exc:
            logger.warning("Falling back to psutil for metrics: %s", exc)
            import psutil
            metrics = {
                "cpu_percent": psutil.cpu_percent(interval=None),
                "ram_percent": psutil.virtual_memory().percent,
                "process_count": len(psutil.pids()),
            }

        cpu_val = metrics.get("cpu_percent", 0.0)
        ram_val = metrics.get("ram_percent", 0.0)
        summary = f"System Status: CPU {cpu_val}%, RAM {ram_val}%, Processes: {metrics.get('process_count', 0)}"

        return AgentOutput(
            success=True,
            result=summary,
            artifacts={"metrics": metrics},
        )
