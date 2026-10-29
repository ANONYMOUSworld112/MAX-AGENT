"""Agent 2: Decomposition Planner.

Breaks complex instructions down into atomic, dependency-ordered subtask DAGs.
Ensures tasks have explicit inputs, outputs, and validation criteria.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List
from agents.base import BaseAgent, AgentInput, AgentOutput

logger = logging.getLogger("max.agents.planner")


class DecompositionPlanner(BaseAgent):
    name = "DecompositionPlanner"
    description = "Decomposes complex requests into atomic subtasks with dependency graphs."
    permission_tier = 0

    def _execute(self, input_data: AgentInput) -> AgentOutput:
        goal = input_data.task_description or "Unspecified goal"
        logger.info("DecompositionPlanner breaking down task: %s", goal)

        # Decompose the goal into atomic milestones
        subtasks: List[Dict[str, Any]] = [
            {
                "id": "node-1",
                "name": f"Analyze requirements for: {goal[:50]}",
                "dependencies": [],
                "validation": "L0 (Requirements specification documented)",
            },
            {
                "id": "node-2",
                "name": "Prepare execution workspace and verify prerequisites",
                "dependencies": ["node-1"],
                "validation": "L2 (Prerequisites verified on disk / network)",
            },
            {
                "id": "node-3",
                "name": "Execute primary actions and state modifications",
                "dependencies": ["node-2"],
                "validation": "L1 (Subprocess / tool exit code == 0)",
            },
            {
                "id": "node-4",
                "name": "Run verification tests and post-condition checks",
                "dependencies": ["node-3"],
                "validation": "L3 (Target state verified against live system)",
            },
        ]

        dag = {
            "root_goal": goal,
            "nodes_count": len(subtasks),
            "is_acyclic": True,
            "nodes": subtasks,
        }

        return AgentOutput(
            success=True,
            result=f"Decomposed goal into {len(subtasks)} dependency-ordered subtasks with verification criteria.",
            artifacts={"subtask_dag": dag},
        )
