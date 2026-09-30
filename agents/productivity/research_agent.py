"""Agent 17: Research Agent.

Conducts multi-source web and document research with citations.
Wraps the existing web_search action with structured output parsing.
Operates at Permission Tier 0 (Safe Read).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List
from agents.base import BaseAgent, AgentInput, AgentOutput

logger = logging.getLogger("max.agents.research")


class ResearchAgent(BaseAgent):
    name = "ResearchAgent"
    description = "Conducts multi-source web and document research with citations."
    permission_tier = 0  # Safe Read

    def _execute(self, input_data: AgentInput) -> AgentOutput:
        """Not yet implemented (Rule 1-H1 Honesty)."""
        raise NotImplementedError(f"Agent '{self.name}' is not implemented")
