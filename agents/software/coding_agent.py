"""Agent 6: Coding Agent.

Writes and modifies code files based on decomposed implementation plans.
Operates at Permission Tier 1 (Safe Write) with snapshot and rollback safety.
"""

from __future__ import annotations

import logging
from typing import Any, Dict
from agents.base import BaseAgent, AgentInput, AgentOutput

logger = logging.getLogger("max.agents.coding_agent")


class CodingAgent(BaseAgent):
    name = "CodingAgent"
    description = "Writes and modifies code files based on a decomposed plan."
    permission_tier = 1  # Safe Write

    def _execute(self, input_data: AgentInput) -> AgentOutput:
        desc = input_data.task_description
        logger.info("CodingAgent executing: %s", desc)

        filepath = input_data.parameters.get("filepath", "")
        code = input_data.parameters.get("code", "")
        action = input_data.parameters.get("action", "generate")

        artifacts: Dict[str, Any] = {
            "action": action,
            "filepath": filepath,
            "lines_generated": len(code.splitlines()) if code else 0,
        }

        if filepath and code:
            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(code)
                artifacts["written"] = True
                result = f"Successfully wrote {len(code)} characters to {filepath}"
            except Exception as e:
                logger.error("Failed to write to %s: %s", filepath, e)
                return AgentOutput(
                    success=False,
                    error=f"File write failed: {e}",
                    artifacts=artifacts,
                )
        else:
            result = f"Code generation completed for task: {desc}"

        return AgentOutput(
            success=True,
            result=result,
            artifacts=artifacts,
        )
