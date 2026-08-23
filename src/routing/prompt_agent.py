"""
MAX OS — Prompt Builder Agent
Build Order: #19 (Layer 4D)
═══════════════════════════════════════════════════════

Constructs structured prompts with context injection for target agent modules.
Passes all text through data boundary.
"""

from __future__ import annotations

import logging
from src.infra import data_boundary

logger = logging.getLogger("max.routing.prompt_agent")


def build_agent_prompt(agent_name: str, task_text: str, context_items: list[str] = None) -> str:
    """Build structured agent prompt with safety sanitization."""
    clean_task = data_boundary.sanitize(task_text)
    ctx_str = "\n".join([f"- {data_boundary.sanitize(c)}" for c in (context_items or [])])

    prompt = f"""[MAX OS AGENT DIRECTIVE]
TARGET AGENT: {agent_name.upper()}
SYSTEM TIER: ENFORCED

USER COMMAND:
{clean_task}

CONTEXT HEAP:
{ctx_str if ctx_str else "None"}

INSTRUCTIONS:
Execute task safely, maintaining transaction integrity and logging step events.
"""
    return prompt
