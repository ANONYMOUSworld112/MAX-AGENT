"""
MAX OS — Terminal & Shell Execution Agent
═══════════════════════════════════════════════════════
Executes verified shell commands, script execution, and environment management.
"""

from __future__ import annotations

import logging
from src.agents.agent_base import BaseAgent, AgentResult
from src.routing.permissions import PermissionTier
from src.system.adapters.base import get_adapter

logger = logging.getLogger("max.agents.terminal")


class TerminalAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "terminal"

    @property
    def default_tier(self) -> PermissionTier:
        return PermissionTier.CONFIRM

    def execute(self, task_id: str, prompt: str, payload: dict = None) -> AgentResult:
        logger.info("TerminalAgent executing task '%s': prompt='%s'", task_id, prompt)
        
        adapter = get_adapter()
        # Clean command prompt
        clean_cmd = prompt.replace("run command", "").replace("execute", "").strip() or "status"
        res = adapter.execute_command(clean_cmd, timeout=15)
        
        output = res.get("stdout", "").strip() or f"Command '{clean_cmd}' executed successfully (exit code: {res.get('exit_code', 0)})"
        
        return AgentResult(
            success=(res.get("exit_code", 0) == 0),
            agent_name=self.name,
            action="execute_shell_command",
            output=output[:200],
            data=res,
        )
