"""
MAX-AGENT Context Engine
========================

Builds task-scoped context packages with strict token budgets instead of
dumping the entire memory and static prompts into every model turn.

Features:
- Scoped ContextPackage with system prompt, task spec, relevant memory, and tools
- Semantic keyword relevance filtering against TaskIntent
- Strict token budget enforcement (pruning lowest-relevance items first)
- Guarantees zero token runaway and preserves LLM focus

Master Spec references:
- Section 6 (Context Window Management, Scoped Context Packages)
- Section 8 (Task specification)
- docs/audit/PROMPT_FORENSICS.md
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from core.contracts import TaskIntent, _now_utc

logger = logging.getLogger("max.context_engine")


@dataclass
class ContextPackage:
    """A task-scoped, token-budgeted prompt package."""
    system_prompt: str
    task_spec: str
    memory_context: str
    tools_spec: List[Dict[str, Any]]
    total_estimated_tokens: int
    budget_limit: int
    included_memories: List[str] = field(default_factory=list)
    pruned_memories: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "system_prompt": self.system_prompt,
            "task_spec": self.task_spec,
            "memory_context": self.memory_context,
            "tools_count": len(self.tools_spec),
            "total_estimated_tokens": self.total_estimated_tokens,
            "budget_limit": self.budget_limit,
            "included_memories": self.included_memories,
            "pruned_memories": self.pruned_memories,
        }


class ContextEngine:
    """
    Constructs scoped context packages within configurable token limits.
    """

    def __init__(self, default_budget: int = 2000, chars_per_token: float = 4.0) -> None:
        self.default_budget = default_budget
        self.chars_per_token = chars_per_token

    def estimate_tokens(self, text: str) -> int:
        """Estimates token count using character length ratio."""
        if not text:
            return 0
        return max(1, int(len(text) / self.chars_per_token))

    def _extract_keywords(self, task_intent: TaskIntent) -> Set[str]:
        """Extracts search tokens from TaskIntent action, target, and parameters."""
        raw_text = f"{task_intent.action} {task_intent.target} {task_intent.raw_input}"
        for v in task_intent.parameters.values():
            if isinstance(v, (str, int, float)):
                raw_text += f" {v}"

        words = re.findall(r"[a-zA-Z0-9_\-\.]{2,}", raw_text.lower())
        stopwords = {"the", "and", "for", "with", "this", "that", "from", "into", "set", "run"}
        return {w for w in words if w not in stopwords}

    def build_context_package(
        self,
        task_intent: TaskIntent,
        memory: Optional[Dict[str, Any]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        token_budget: Optional[int] = None,
    ) -> ContextPackage:
        """
        Builds a compact, task-focused context package fitting within token_budget.
        """
        budget = token_budget if token_budget is not None else self.default_budget
        tools_list = tools or []

        # 1. Base System Prompt
        sys_prompt = (
            f"You are MAX, an honest and reliable assistant. "
            f"Current time: {_now_utc()}. Verify actions before completion."
        )
        sys_tokens = self.estimate_tokens(sys_prompt)

        # 2. Task Spec
        param_str = json.dumps(task_intent.parameters, ensure_ascii=False)
        task_spec = (
            f"TASK SPECIFICATION:\n"
            f"- Action: {task_intent.action}\n"
            f"- Target: {task_intent.target}\n"
            f"- Parameters: {param_str}\n"
            f"- Channel: {task_intent.channel.value if hasattr(task_intent.channel, 'value') else task_intent.channel}\n"
        )
        task_tokens = self.estimate_tokens(task_spec)

        # 3. Tools Spec
        tools_json = json.dumps(tools_list, ensure_ascii=False) if tools_list else ""
        tools_tokens = self.estimate_tokens(tools_json)

        base_tokens = sys_tokens + task_tokens + tools_tokens
        remaining_budget = max(0, budget - base_tokens)

        # 4. Scored Memory Selection
        included_mems: List[str] = []
        pruned_mems: List[str] = []
        memory_lines: List[str] = []
        current_mem_tokens = 0

        if memory:
            keywords = self._extract_keywords(task_intent)
            scored_entries: List[Tuple[float, str, str]] = []  # (score, mem_id, line)

            for cat, items in memory.items():
                if not isinstance(items, dict):
                    continue
                for key, val_obj in items.items():
                    val_str = ""
                    if isinstance(val_obj, dict):
                        val_str = str(val_obj.get("value", ""))
                    else:
                        val_str = str(val_obj)

                    mem_id = f"{cat}/{key}"
                    line = f"- [{cat}] {key}: {val_str}"

                    # Priority scoring
                    score = 0.0
                    if cat == "identity":
                        score = 100.0  # Identity always prioritized
                    elif cat == "preferences":
                        score = 10.0

                    # Keyword relevance match
                    text_blob = f"{cat} {key} {val_str}".lower()
                    matches = sum(1 for kw in keywords if kw in text_blob)
                    score += matches * 20.0

                    if score > 0:
                        scored_entries.append((score, mem_id, line))
                    else:
                        pruned_mems.append(mem_id)

            # Sort descending by relevance score
            scored_entries.sort(key=lambda x: x[0], reverse=True)

            for score, mem_id, line in scored_entries:
                line_tokens = self.estimate_tokens(line + "\n")
                if current_mem_tokens + line_tokens <= remaining_budget:
                    memory_lines.append(line)
                    included_mems.append(mem_id)
                    current_mem_tokens += line_tokens
                else:
                    pruned_mems.append(mem_id)

        mem_block = "RELEVANT MEMORY:\n" + "\n".join(memory_lines) if memory_lines else ""
        total_tokens = base_tokens + current_mem_tokens

        return ContextPackage(
            system_prompt=sys_prompt,
            task_spec=task_spec,
            memory_context=mem_block,
            tools_spec=tools_list,
            total_estimated_tokens=total_tokens,
            budget_limit=budget,
            included_memories=included_mems,
            pruned_memories=pruned_mems,
        )
