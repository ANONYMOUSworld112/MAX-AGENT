"""
MAX OS — Intent Classifier & Cheap Router (Phase 1).
Deterministic keyword matching first (cheap router).
Unambiguous coding requests never trigger an LLM classification call.
Ambiguous input asks a clarifying question instead of guessing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Set

CODING_ACTION_KEYWORDS: Set[str] = {
    "write",
    "code",
    "script",
    "function",
    "class",
    "create",
    "build",
    "implement",
    "fix",
    "bug",
    "debug",
    "refactor",
    "test",
    "unittest",
    "pytest",
    "program",
    "python",
    "javascript",
    "html",
    "css",
    "backend",
    "frontend",
    "endpoint",
    "api",
    "module",
    "package",
    "patch",
    "compile",
    "lint",
}

NON_CODING_AMBIGUOUS_PATTERNS: List[re.Pattern] = [
    re.compile(r"^(hi|hello|hey|greetings|help|what can you do)\b", re.IGNORECASE),
    re.compile(r"^(what is|who is|explain|tell me about)\b", re.IGNORECASE),
    re.compile(r"^\s*$", re.IGNORECASE),
]


@dataclass
class IntentResult:
    agent: Optional[str]
    intent: str
    confidence: float
    used_llm: bool
    clarification_prompt: Optional[str] = None
    extracted_spec: Optional[Dict[str, Any]] = None


class IntentClassifier:
    """
    Two-stage intent classification:
    1. Cheap deterministic router (regex / keywords) — 0 latency, 0 cost.
    2. Fallback / Clarifier: if intent is ambiguous, asks a clarifying question.
    """

    def __init__(self, llm_client: Optional[Callable[[str], str]] = None):
        self.llm_client = llm_client

    def classify(self, user_input: str) -> IntentResult:
        cleaned = user_input.strip()
        if not cleaned:
            return IntentResult(
                agent=None,
                intent="clarification_needed",
                confidence=0.0,
                used_llm=False,
                clarification_prompt="Input was empty. What would you like me to build or help you with?",
            )

        # 1. Cheap deterministic router
        words = set(re.findall(r"\b[a-zA-Z_]+\b", cleaned.lower()))
        matched_coding_keywords = words.intersection(CODING_ACTION_KEYWORDS)

        # Check for explicitly ambiguous / non-coding phrasing
        is_ambiguous_pattern = any(p.search(cleaned) for p in NON_CODING_AMBIGUOUS_PATTERNS)

        if matched_coding_keywords and not is_ambiguous_pattern:
            # Determine specific coding intent
            intent = "write_code"
            if any(w in matched_coding_keywords for w in {"fix", "bug", "debug"}):
                intent = "fix_bug"
            elif any(w in matched_coding_keywords for w in {"test", "unittest", "pytest"}):
                intent = "run_test"
            elif "refactor" in matched_coding_keywords:
                intent = "refactor"

            return IntentResult(
                agent="coding",
                intent=intent,
                confidence=1.0,
                used_llm=False,
                extracted_spec={"prompt": cleaned},
            )

        # Check if LLM fallback client provided
        if self.llm_client is not None:
            # Pass through data boundary before calling LLM
            from core.data_boundary import sanitize_payload
            safe_payload = sanitize_payload({"prompt": cleaned})
            llm_response = self.llm_client(str(safe_payload))
            if "coding" in llm_response.lower():
                return IntentResult(
                    agent="coding",
                    intent="write_code",
                    confidence=0.8,
                    used_llm=True,
                    extracted_spec={"prompt": cleaned},
                )

        # Ambiguous / non-coding input without confident match
        return IntentResult(
            agent=None,
            intent="clarification_needed",
            confidence=0.0,
            used_llm=False,
            clarification_prompt=(
                f"I am not sure how to route your request: '{cleaned}'. "
                "Are you asking me to write, test, or modify code? Please clarify your target task."
            ),
        )
