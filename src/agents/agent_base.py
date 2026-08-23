"""
MAX OS — Base Agent Contract (ABC)
Build Order: #20 (Layer 5A)
═══════════════════════════════════════════════════════

Abstract base class for all MAX AI sub-agents.
Defines required interface contract for classify, tier, execute, and report.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from src.routing.permissions import PermissionTier

logger = logging.getLogger("max.agents.base")


@dataclass
class AgentResult:
    success: bool
    agent_name: str
    action: str
    output: str
    data: dict[str, Any]
    error_message: str = ""


class BaseAgent(ABC):
    """Abstract base class for MAX OS agents."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the agent module."""
        pass

    @property
    @abstractmethod
    def default_tier(self) -> PermissionTier:
        """Default permission tier for this agent."""
        pass

    @abstractmethod
    def execute(self, task_id: str, prompt: str, payload: dict = None) -> AgentResult:
        """Execute the assigned task and return structured AgentResult."""
        pass

    def report(self, result: AgentResult) -> str:
        """Format human-readable summary of execution output."""
        if result.success:
            return f"[{result.agent_name.upper()} SUCCESS]: {result.output}"
        return f"[{result.agent_name.upper()} FAILED]: {result.error_message}"
