"""
LLM Provider Abstraction & Model Router (Tasks 9.1 & 9.2)
========================================================

Defines the core provider protocol, standardized response models,
and deterministic capability- and privacy-aware model routing.

Master Spec References:
  - Section 1-H1 (honesty, no fake offline claims)
  - docs/evolution/IMPROVEMENT_MATRIX.md (Provider Abstraction)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, Set

logger = logging.getLogger("max.providers")


@dataclass
class LLMResponse:
    """Standardized completion response from any LLM provider."""
    content: str
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    model: str = ""
    usage: Dict[str, int] = field(default_factory=dict)
    finish_reason: str = "stop"


class LLMProvider(Protocol):
    """Protocol that all model backends must implement."""

    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
    ) -> LLMResponse:
        ...

    def is_available(self) -> bool:
        ...

    def provider_name(self) -> str:
        ...


@dataclass
class ModelRoutingCriteria:
    """Criteria used by ModelRouter to select the optimal model backend."""
    complexity: str = "MEDIUM"      # LOW, MEDIUM, HIGH
    privacy: str = "NORMAL"         # NORMAL, LOCAL_ONLY
    task_type: str = "general"       # general, coding, routing, reflex, extraction
    max_cost: float = 1.0


class ModelRouter:
    """
    Selects model providers based on task complexity, privacy constraints,
    latency, and live backend availability.
    """

    def __init__(self) -> None:
        self._providers: Dict[str, LLMProvider] = {}
        self._is_local: Dict[str, bool] = {}
        self._capabilities: Dict[str, Set[str]] = {}

    def register_provider(
        self,
        name: str,
        provider: LLMProvider,
        is_local: bool = False,
        capabilities: Optional[Set[str]] = None,
    ) -> None:
        """Registers a provider with its locality and capability flags."""
        self._providers[name] = provider
        self._is_local[name] = is_local
        self._capabilities[name] = capabilities or {"general"}

    def get_provider(self, name: str) -> Optional[LLMProvider]:
        return self._providers.get(name)

    def route(self, criteria: ModelRoutingCriteria) -> LLMProvider:
        """
        Deterministically selects the most appropriate available provider.
        """
        # 1. Filter by Privacy requirements
        candidate_names = list(self._providers.keys())
        if criteria.privacy == "LOCAL_ONLY":
            candidate_names = [name for name in candidate_names if self._is_local.get(name, False)]
            if not candidate_names:
                raise RuntimeError(
                    "No local provider registered or available for LOCAL_ONLY privacy task."
                )

        # 2. Filter by Live Availability
        available = [name for name in candidate_names if self._providers[name].is_available()]
        if not available:
            raise RuntimeError(
                f"No available LLM providers found matching privacy='{criteria.privacy}'"
            )

        # 3. Sort/Prioritize based on Task Type & Complexity
        # Preferred capabilities
        req_cap = "coding" if criteria.task_type == "coding" else "general"

        def _sort_key(name: str) -> tuple[int, int, int]:
            caps = self._capabilities.get(name, set())
            has_cap = 1 if req_cap in caps else 0

            # Complexity matching
            if criteria.complexity == "HIGH":
                # Prefer cloud or large models (non-local or explicitly capable)
                pref = 1 if not self._is_local.get(name, False) or "deep_reasoning" in caps else 0
            elif criteria.complexity == "LOW":
                # Prefer fast local models
                pref = 1 if self._is_local.get(name, False) or "fast" in caps else 0
            else:
                pref = 1

            return (has_cap, pref, 1)

        available.sort(key=_sort_key, reverse=True)
        chosen_name = available[0]
        chosen = self._providers[chosen_name]

        logger.info(
            "ModelRouter selected '%s' (local=%s) for task_type=%s, complexity=%s, privacy=%s",
            chosen_name,
            self._is_local.get(chosen_name, False),
            criteria.task_type,
            criteria.complexity,
            criteria.privacy,
        )
        return chosen
