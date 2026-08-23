"""
MAX OS — Decomposition Planner
Build Order: #18 (Layer 4C)
═══════════════════════════════════════════════════════

Decomposes complex, multi-step prompt inputs into ordered sub-tasks
with dependency links for execution by task_queue.
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field

from src.routing import intent_classifier

logger = logging.getLogger("max.routing.planner")


@dataclass
class PlannedSubTask:
    step_id: int
    agent: str
    intent: str
    prompt_snippet: str
    depends_on: list[int] = field(default_factory=list)


def plan(prompt_text: str) -> list[PlannedSubTask]:
    """Decompose compound prompt into sequence of sub-tasks."""
    # Split on conjunctions or clauses if multi-step (e.g. "and then", "first ... second ...")
    delimiters = [r"\band then\b", r"\bthen\b", r"\bafter that\b", r";"]
    pattern = "|".join(delimiters)
    clauses = [c.strip() for c in re.split(pattern, prompt_text, flags=re.I) if c.strip()]

    if len(clauses) <= 1:
        # Single task
        res = intent_classifier.classify(prompt_text)
        return [PlannedSubTask(step_id=1, agent=res.agent, intent=res.intent, prompt_snippet=prompt_text)]

    tasks = []
    prev_step_id = None
    for idx, clause in enumerate(clauses, start=1):
        res = intent_classifier.classify(clause)
        deps = [prev_step_id] if prev_step_id else []
        tasks.append(PlannedSubTask(
            step_id=idx,
            agent=res.agent,
            intent=res.intent,
            prompt_snippet=clause,
            depends_on=deps
        ))
        prev_step_id = idx

    logger.info("Decomposed prompt into %d planned sub-tasks", len(tasks))
    return tasks
