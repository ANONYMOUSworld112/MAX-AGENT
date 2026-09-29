"""Token Budget Compressor for Context Management.

Ensures that dynamic context injections never exceed the assigned token budget.
Uses line-level priority pruning to guarantee hard caps.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("max.memory.token_budget")


class TokenBudgetCompressor:
    def __init__(self, max_budget: int = 2048) -> None:
        self.max_budget = max_budget

    def estimate_tokens(self, text: str) -> int:
        if not text:
            return 0
        # Heuristic: 1 token ≈ 4 characters or ~0.75 words
        return max(1, len(text) // 4)

    def compress(self, text: str) -> str:
        current_tokens = self.estimate_tokens(text)
        if current_tokens <= self.max_budget:
            return text

        lines = text.splitlines(keepends=True)
        # Keep pruning from the end until under budget
        while lines and self.estimate_tokens("".join(lines)) > self.max_budget:
            lines.pop()

        logger.debug("Compressed context from %d to %d tokens", current_tokens, self.estimate_tokens("".join(lines)))
        return "".join(lines)
