"""
MAX OS — Real-Time Web Search & Source Retrieval Agent
═══════════════════════════════════════════════════════
"""

from __future__ import annotations

import logging
from src.agents.agent_base import BaseAgent, AgentResult
from src.routing.permissions import PermissionTier

logger = logging.getLogger("max.agents.websearch")


class WebSearchAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "websearch"

    @property
    def default_tier(self) -> PermissionTier:
        return PermissionTier.AUTO

    def execute(self, task_id: str, prompt: str, payload: dict = None) -> AgentResult:
        logger.info("WebSearchAgent executing task '%s': prompt='%s'", task_id, prompt)
        
        from agents.websearch import WebSearchAgent as NativeWebSearch
        native = NativeWebSearch()
        res = native.search(prompt)
        
        output = f"Retrieved {len(res.get('sources', []))} search sources for '{prompt[:40]}'"
        
        return AgentResult(
            success=True,
            agent_name=self.name,
            action="web_search",
            output=output,
            data=res,
        )
