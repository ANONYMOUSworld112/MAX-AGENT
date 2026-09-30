"""
Unit tests for LLM Providers (Task 9.1)
=======================================

Covers:
- Provider protocol conformance across Mock, Gemini, and Ollama providers
- Standardized LLMResponse format and token tracking
- Availability checks and error handling
"""

import pytest
from core.providers.base import LLMProvider, LLMResponse
from core.providers.mock import MockProvider
from core.providers.gemini import GeminiProvider
from core.providers.ollama import OllamaProvider


def test_mock_provider_conformance():
    provider = MockProvider(name="test-mock", default_response="Synthesized answer 42.")
    assert provider.provider_name() == "test-mock"
    assert provider.is_available() is True

    res = provider.generate("What is the answer?", system_prompt="Be concise.")
    assert isinstance(res, LLMResponse)
    assert res.content == "Synthesized answer 42."
    assert res.model == "test-mock"
    assert res.usage["prompt_tokens"] > 0
    assert provider.last_prompt == "What is the answer?"
    assert provider.last_system_prompt == "Be concise."


def test_provider_availability_toggles():
    mock = MockProvider()
    assert mock.is_available() is True
    mock.set_available(False)
    assert mock.is_available() is False

    # Gemini without API key is unavailable
    gemini = GeminiProvider(api_key=None)
    assert gemini.is_available() is False

    # Gemini with API key is available
    gemini_active = GeminiProvider(api_key="AIzaSyDummyKeyForTestingPurposes1234567")
    assert gemini_active.is_available() is True


def test_ollama_unreachable_defaults_to_unavailable():
    # Pointing to non-existent local port
    ollama = OllamaProvider(base_url="http://127.0.0.1:54321")
    assert ollama.is_available() is False
