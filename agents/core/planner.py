"""Agent 2: Decomposition Planner.

Breaks complex instructions down into atomic, dependency-ordered subtask DAGs.
Ensures tasks have explicit inputs, outputs, and validation criteria.
"""

from __future__ import annotations

import logging
from agents.base import BaseAgent, AgentInput, AgentOutput

logger = logging.getLogger("max.agents.planner")


class DecompositionPlanner(BaseAgent):
    name = "DecompositionPlanner"
    description = "Decomposes complex requests into atomic subtasks with dependency graphs."
    permission_tier = 0

    def _execute(self, input_data: AgentInput) -> AgentOutput:
        """Not yet implemented (Rule 1-H1 Honesty)."""
        raise NotImplementedError(f"Agent '{self.name}' is not implemented")
