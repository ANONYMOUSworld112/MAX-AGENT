"""
MAX OS — Notes & Semantic Memory Agent
Build Order: #22 (Layer 5C)
═══════════════════════════════════════════════════════

Manages storing and querying notes with semantic similarity.
AUTO tier.
"""

from __future__ import annotations

import logging
from src.agents.agent_base import BaseAgent, AgentResult
from src.routing.permissions import PermissionTier
from src.infra import memory

logger = logging.getLogger("max.agents.notes")


class NotesAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "notes"

    @property
    def default_tier(self) -> PermissionTier:
        return PermissionTier.AUTO

    def execute(self, task_id: str, prompt: str, payload: dict = None) -> AgentResult:
        logger.info("NotesAgent executing task '%s': prompt='%s'", task_id, prompt)
        
        mem = memory.get_memory()
        mem.push_conversational("active_session", prompt, content_type="context", importance=0.7)

        return AgentResult(
            success=True,
            agent_name=self.name,
            action="save_note",
            output=f"Note stored in memory heap: '{prompt[:50]}...'",
            data={"note_text": prompt, "stored": True},
        )
