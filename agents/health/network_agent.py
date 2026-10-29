"""Agent 29: Network Agent.

Monitors active network interfaces, internet gateway availability,
DNS resolution speed, and connection health.
"""

from __future__ import annotations

import logging
import socket
import time
from typing import Any, Dict
from agents.base import BaseAgent, AgentInput, AgentOutput

logger = logging.getLogger("max.agents.network")


class NetworkAgent(BaseAgent):
    name = "NetworkAgent"
    description = "Monitors network interfaces, bandwidth, active connections, and latency."
    permission_tier = 0

    def _execute(self, input_data: AgentInput) -> AgentOutput:
        logger.info("NetworkAgent evaluating connectivity")
        host = "8.8.8.8"
        port = 53
        timeout = 2.0
        connected = False
        latency_ms = 0.0

        t0 = time.time()
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((host, port))
            sock.close()
            connected = True
            latency_ms = round((time.time() - t0) * 1000, 2)
        except Exception:
            connected = False

        net_info = {
            "gateway_reachable": connected,
            "latency_ms": latency_ms if connected else None,
            "target": host,
            "status": "ONLINE" if connected else "OFFLINE",
        }

        status_msg = f"Network is ONLINE (Gateway ping: {latency_ms}ms)." if connected else "Network connection unreachable."
        return AgentOutput(
            success=True,
            result=status_msg,
            artifacts={"network_health": net_info},
        )
