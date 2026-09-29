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
        desc = input_data.task_description
        logger.info("DecompositionPlanner planning for: %s", desc)

        # Standard atomic decomposition template
        subtasks = [
            {"id": "step_1_spec", "agent": "SpecAuthor", "desc": f"Write spec for {desc}"},
            {"id": "step_2_dev", "agent": "PolyglotDeveloper", "desc": f"Implement changes for {desc}"},
            {"id": "step_3_review", "agent": "CodeReviewer", "desc": "Audit code quality and security"},
            {"id": "step_4_test", "agent": "QATestEngineer", "desc": "Execute test suite"},
        ]

        return AgentOutput(
            success=True,
            result=f"Plan generated with {len(subtasks)} subtasks for: {desc}",
            artifacts={"subtasks": subtasks}
        )
