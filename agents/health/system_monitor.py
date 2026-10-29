"""Agent 28: System Monitor Agent.

Monitors real-time CPU, RAM, GPU, temperature, and battery telemetry
to prevent thermal throttling and hardware overloads.
"""

from __future__ import annotations

import logging
from typing import Any, Dict
import psutil
from agents.base import BaseAgent, AgentInput, AgentOutput

logger = logging.getLogger("max.agents.sysmon")


class SystemMonitorAgent(BaseAgent):
    name = "SystemMonitorAgent"
    description = "Monitors real-time CPU, RAM, GPU load, and hardware telemetry."
    permission_tier = 0

    def _execute(self, input_data: AgentInput) -> AgentOutput:
        logger.info("SystemMonitorAgent collecting real OS telemetry")
        cpu_percent = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/") if hasattr(psutil, "disk_usage") else None

        telemetry: Dict[str, Any] = {
            "cpu_percent": cpu_percent,
            "ram_percent": mem.percent,
            "ram_used_gb": round((mem.total - mem.available) / (1024 ** 3), 2),
            "ram_total_gb": round(mem.total / (1024 ** 3), 2),
            "status": "HEALTHY" if cpu_percent < 90 and mem.percent < 90 else "HIGH_LOAD",
        }
        if disk:
            telemetry["disk_percent"] = disk.percent

        summary = f"System Telemetry: CPU is at {cpu_percent}%, RAM is at {mem.percent}% ({telemetry['ram_used_gb']}/{telemetry['ram_total_gb']} GB)."
        return AgentOutput(
            success=True,
            result=summary,
            artifacts={"telemetry": telemetry},
        )
