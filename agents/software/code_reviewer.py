"""Agent 7: Code Reviewer.

Reviews code for bugs, syntax errors, style conformance, security vulnerabilities,
and performance regressions. Operates at Permission Tier 0 (Safe Read).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List
from agents.base import BaseAgent, AgentInput, AgentOutput

logger = logging.getLogger("max.agents.code_reviewer")


class CodeReviewer(BaseAgent):
    name = "CodeReviewer"
    description = "Reviews code for bugs, style, security, and performance."
    permission_tier = 0  # Safe Read

    def _execute(self, input_data: AgentInput) -> AgentOutput:
        """Not yet implemented (Rule 1-H1 Honesty)."""
        raise NotImplementedError(f"Agent '{self.name}' is not implemented")
