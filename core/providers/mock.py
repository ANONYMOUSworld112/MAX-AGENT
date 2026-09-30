"""
Mock & Test LLM Provider
========================

Deterministic provider for unit testing, CI pipelines, and offline evaluation.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional
from core.providers.base import LLMProvider, LLMResponse


class MockProvider(LLMProvider):
    """Configurable mock provider that returns canned or synthesized responses."""

    def __init__(
        self,
        name: str = "mock-model",
        default_response: str = "Mock completion response.",
        available: bool = True,
    ) -> None:
        self.name = name
        self.default_response = default_response
        self._available = available
        self.last_prompt: Optional[str] = None
        self.last_system_prompt: Optional[str] = None
        self.call_count = 0
        self.response_generator: Optional[Callable[[str], str]] = None

    def provider_name(self) -> str:
        return self.name

    def is_available(self) -> bool:
        return self._available

    def set_available(self, available: bool) -> None:
        self._available = available

    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
    ) -> LLMResponse:
        self.last_prompt = prompt
        self.last_system_prompt = system_prompt
        self.call_count += 1

        if self.response_generator:
            content = self.response_generator(prompt)
        else:
            content = self.default_response

        return LLMResponse(
            content=content,
            model=self.name,
            usage={"prompt_tokens": len(prompt.split()), "completion_tokens": len(content.split())},
        )
