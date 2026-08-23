"""
MAX OS — Autonomous Desktop Control & Computer-Use Agent
═══════════════════════════════════════════════════════
Drives the Observe->Think->Act->Verify (OTAV) desktop execution loop.
"""

from __future__ import annotations

import logging
from src.agents.agent_base import BaseAgent, AgentResult
from src.routing.permissions import PermissionTier

logger = logging.getLogger("max.agents.desktop")


class DesktopAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "desktop"

    @property
    def default_tier(self) -> PermissionTier:
        return PermissionTier.CONFIRM

    def execute(self, task_id: str, prompt: str, payload: dict = None) -> AgentResult:
        logger.info("DesktopAgent executing task '%s': prompt='%s'", task_id, prompt)
        
        from core.orchestrator import Orchestrator
        orch = Orchestrator.get_instance()
        res = orch.dispatch_sync(prompt)
        
        output = f"OTAV desktop workflow completed: {res.result_summary or 'State change verified'}"
        
        return AgentResult(
            success=(res.state == "COMPLETED" or res.state == "DONE"),
            agent_name=self.name,
            action="desktop_interaction",
            output=output,
            data={"state": res.state, "task_id": res.task_id},
        )
