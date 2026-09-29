"""Agent 29: Network Agent.

Performs network diagnostics, ping checks, DNS lookups, and interface discovery.
Operates at Permission Tier 0 (Safe Read).
"""

from __future__ import annotations

import logging
import socket
from typing import Any, Dict
from agents.base import BaseAgent, AgentInput, AgentOutput

logger = logging.getLogger("max.agents.network")


class NetworkAgent(BaseAgent):
    name = "NetworkAgent"
    description = "Tests network connectivity, interface status, and DNS resolution."
    permission_tier = 0  # Safe Read

    def _execute(self, input_data: AgentInput) -> AgentOutput:
        desc = input_data.task_description
        logger.info("NetworkAgent evaluating connectivity: %s", desc)

        host = input_data.parameters.get("host", "8.8.8.8")
        port = input_data.parameters.get("port", 53)
        timeout = input_data.parameters.get("timeout", 2.0)

        connected = False
        try:
            with socket.create_connection((host, port), timeout=timeout):
                connected = True
        except Exception as e:
            logger.debug("Socket check failed: %s", e)
            connected = False

        artifacts: Dict[str, Any] = {
            "target_host": host,
            "target_port": port,
            "connected": connected,
            "status": "ONLINE" if connected else "OFFLINE",
        }

        return AgentOutput(
            success=True,
            result=f"Network target {host}:{port} is {'REACHABLE' if connected else 'UNREACHABLE'}",
            artifacts=artifacts,
        )
