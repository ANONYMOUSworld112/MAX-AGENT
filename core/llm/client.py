"""
core/llm/client.py — Unified LLM Client with Tool Calling, Fallback Chain & Budget Guard.

Supports:
  1. Google Gemini (primary) via google.genai
  2. Anthropic Claude (fallback) via direct HTTP / SDK
  3. Local Ollama (offline fallback)
  4. Mock Provider (for deterministic testing)
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional, Tuple

import requests

from core.config_loader import AppConfig, get_config

logger = logging.getLogger("friday.llm")


class BudgetExceededError(Exception):
    """Raised when cumulative monthly LLM spend exceeds the configured budget cap."""
    pass


@dataclass
class ToolCallRequest:
    name: str
    arguments: dict[str, Any]
    call_id: str = ""
    human_description: str = ""


@dataclass
class LLMResponse:
    text: str
    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    provider_used: str = ""
    model_used: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


class BudgetTracker:
    """Persists and checks monthly LLM token usage and dollar spend."""

    def __init__(self, storage_path: Path, budget_cap_usd: float = 25.0) -> None:
        self.storage_path = storage_path
        self.budget_cap_usd = budget_cap_usd
        self._load()

    def _load(self) -> None:
        self.data: dict[str, Any] = {
            "current_month": time.strftime("%Y-%m"),
            "total_spend_usd": 0.0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
        }
        if self.storage_path.exists():
            try:
                loaded = json.loads(self.storage_path.read_text(encoding="utf-8"))
                current_month = time.strftime("%Y-%m")
                if loaded.get("current_month") == current_month:
                    self.data = loaded
                else:
                    # New month reset
                    self.data["current_month"] = current_month
                    self._save()
            except Exception:
                pass

    def _save(self) -> None:
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            self.storage_path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning("Could not save budget tracking data: %e", e)

    def check_budget(self) -> None:
        spend = self.data.get("total_spend_usd", 0.0)
        if self.budget_cap_usd > 0 and spend >= self.budget_cap_usd:
            raise BudgetExceededError(
                f"Monthly API budget of ${self.budget_cap_usd:.2f} exceeded. "
                f"Current spend: ${spend:.2f}. API calls blocked."
            )

    def record_usage(self, input_tokens: int, output_tokens: int, cost_usd: float) -> None:
        self.data["total_input_tokens"] = self.data.get("total_input_tokens", 0) + input_tokens
        self.data["total_output_tokens"] = self.data.get("total_output_tokens", 0) + output_tokens
        self.data["total_spend_usd"] = round(self.data.get("total_spend_usd", 0.0) + cost_usd, 6)
        self._save()

    @property
    def current_spend(self) -> float:
        return float(self.data.get("total_spend_usd", 0.0))


class UnifiedLLMClient:
    """Orchestrates primary and fallback LLM models with retry logic and tool conversion."""

    def __init__(self, config: Optional[AppConfig] = None) -> None:
        self.config = config or get_config()
        base_dir = Path(__file__).resolve().parent.parent.parent
        budget_path = base_dir / "memory" / "budget_tracking.json"
        self.budget_tracker = BudgetTracker(
            storage_path=budget_path,
            budget_cap_usd=self.config.llm.monthly_budget_usd
        )
        self._mock_response: Optional[LLMResponse] = None

    def set_mock_response(self, response: Optional[LLMResponse]) -> None:
        """Used in automated unit tests for deterministic testing without external API calls."""
        self._mock_response = response

    def _calculate_cost(self, model: str, in_tokens: int, out_tokens: int) -> float:
        # Rates per 1M tokens
        rates = {
            "gemini-3.8-flash": (0.10, 0.40),
            "gemini-flash-latest": (0.10, 0.40),
            "gemini-2.0-flash": (0.10, 0.40),
            "claude-3-5-sonnet-20241022": (3.00, 15.00),
            "qwen2.5:7b": (0.0, 0.0),
        }
        in_rate, out_rate = rates.get(model, (0.20, 0.80))
        cost = (in_tokens / 1_000_000.0) * in_rate + (out_tokens / 1_000_000.0) * out_rate
        return round(cost, 6)

    async def generate(
        self,
        messages: list[dict[str, Any]],
        system_prompt: str = "",
        tools: Optional[list[dict[str, Any]]] = None,
        on_chunk: Optional[Callable[[str], None]] = None,
    ) -> LLMResponse:
        """
        Execute completion with budget check, provider fallback, and tool support.
        """
        # 1. Budget enforcement check
        self.budget_tracker.check_budget()

        # 2. Check if mock is active (for test isolation)
        if self._mock_response is not None:
            mock = self._mock_response
            if on_chunk and mock.text:
                on_chunk(mock.text)
            self.budget_tracker.record_usage(mock.input_tokens, mock.output_tokens, mock.cost_usd)
            return mock

        # 3. Provider sequence: Primary -> Fallback -> Local
        providers = [
            (self.config.llm.primary_provider, self.config.llm.primary_model),
            (self.config.llm.fallback_provider, self.config.llm.fallback_model),
        ]

        last_error = None
        for provider_name, model_name in providers:
            try:
                logger.info("Attempting LLM call with %s (%s)...", provider_name, model_name)
                response = await self._call_provider_with_retry(
                    provider_name=provider_name,
                    model_name=model_name,
                    messages=messages,
                    system_prompt=system_prompt,
                    tools=tools,
                    on_chunk=on_chunk,
                )
                cost = self._calculate_cost(model_name, response.input_tokens, response.output_tokens)
                response.cost_usd = cost
                self.budget_tracker.record_usage(response.input_tokens, response.output_tokens, cost)
                return response
            except BudgetExceededError:
                raise
            except Exception as e:
                logger.warning("Provider %s (%s) failed: %s. Falling back...", provider_name, model_name, e)
                last_error = e

        raise RuntimeError(f"All LLM providers in fallback chain failed. Last error: {last_error}")

    async def _call_provider_with_retry(
        self,
        provider_name: str,
        model_name: str,
        messages: list[dict[str, Any]],
        system_prompt: str,
        tools: Optional[list[dict[str, Any]]],
        on_chunk: Optional[Callable[[str], None]],
    ) -> LLMResponse:
        retries = self.config.llm.max_retries
        backoff = self.config.llm.backoff_factor

        for attempt in range(retries):
            try:
                if provider_name == "gemini":
                    return await self._call_gemini(model_name, messages, system_prompt, tools, on_chunk)
                elif provider_name == "anthropic":
                    return await self._call_anthropic(model_name, messages, system_prompt, tools, on_chunk)
                elif provider_name == "ollama":
                    return await self._call_ollama(model_name, messages, system_prompt, tools, on_chunk)
                else:
                    raise ValueError(f"Unknown LLM provider: {provider_name}")
            except Exception as e:
                if attempt == retries - 1:
                    raise
                wait_time = backoff ** attempt
                logger.debug("Retry %d for %s in %.1fs: %s", attempt + 1, provider_name, wait_time, e)
                await asyncio.sleep(wait_time)

        raise RuntimeError("Retries exhausted")

    async def _call_gemini(
        self,
        model_name: str,
        messages: list[dict[str, Any]],
        system_prompt: str,
        tools: Optional[list[dict[str, Any]]],
        on_chunk: Optional[Callable[[str], None]],
    ) -> LLMResponse:
        api_key = self.config.gemini_api_key or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set.")

        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)

        # Build contents from messages
        contents = []
        for m in messages:
            role = "user" if m.get("role") in ("user", "system") else "model"
            contents.append(types.Content(
                role=role,
                parts=[types.Part.from_text(text=m.get("content", ""))]
            ))

        # Format function declarations if tools provided
        genai_tools = None
        if tools:
            func_decls = []
            for t in tools:
                func_decls.append(types.FunctionDeclaration(
                    name=t["name"],
                    description=t.get("description", ""),
                    parameters=t.get("parameters", {"type": "OBJECT", "properties": {}}),
                ))
            genai_tools = [types.Tool(function_declarations=func_decls)]

        config = types.GenerateContentConfig(
            system_instruction=system_prompt if system_prompt else None,
            tools=genai_tools,
            temperature=0.2,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )

        loop = asyncio.get_running_loop()
        resp = await loop.run_in_executor(
            None,
            lambda: client.models.generate_content(
                model=model_name,
                contents=contents,
                config=config,
            )
        )

        tool_calls: list[ToolCallRequest] = []
        text_parts: list[str] = []

        if resp.candidates:
            cand = resp.candidates[0]
            if cand.content and cand.content.parts:
                for part in cand.content.parts:
                    if part.text:
                        text_parts.append(part.text)
                        if on_chunk:
                            on_chunk(part.text)
                    if part.function_call:
                        fc = part.function_call
                        args = dict(fc.args) if fc.args else {}
                        tool_calls.append(ToolCallRequest(
                            name=fc.name,
                            arguments=args,
                            call_id=f"call_{int(time.time()*1000)}",
                            human_description=f"call {fc.name} with arguments {json.dumps(args)}"
                        ))

        usage = resp.usage_metadata
        in_tok = getattr(usage, "prompt_token_count", 0) or 0
        out_tok = getattr(usage, "candidates_token_count", 0) or 0

        return LLMResponse(
            text="".join(text_parts),
            tool_calls=tool_calls,
            provider_used="gemini",
            model_used=model_name,
            input_tokens=in_tok,
            output_tokens=out_tok,
        )

    async def _call_anthropic(
        self,
        model_name: str,
        messages: list[dict[str, Any]],
        system_prompt: str,
        tools: Optional[list[dict[str, Any]]],
        on_chunk: Optional[Callable[[str], None]],
    ) -> LLMResponse:
        api_key = self.config.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is not set.")

        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        # Convert tool format
        anthropic_tools = None
        if tools:
            anthropic_tools = []
            for t in tools:
                anthropic_tools.append({
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "input_schema": t.get("parameters", {"type": "object", "properties": {}}),
                })

        # Format messages (Anthropic expects alternating user/assistant)
        anthropic_msgs = []
        for m in messages:
            role = "assistant" if m.get("role") == "assistant" else "user"
            anthropic_msgs.append({"role": role, "content": m.get("content", "")})

        payload: dict[str, Any] = {
            "model": model_name,
            "max_tokens": 2048,
            "messages": anthropic_msgs,
        }
        if system_prompt:
            payload["system"] = system_prompt
        if anthropic_tools:
            payload["tools"] = anthropic_tools

        loop = asyncio.get_running_loop()
        res = await loop.run_in_executor(
            None,
            lambda: requests.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload,
                timeout=self.config.llm.timeout_seconds,
            )
        )

        if res.status_code != 200:
            raise RuntimeError(f"Anthropic API returned {res.status_code}: {res.text}")

        data = res.json()
        tool_calls: list[ToolCallRequest] = []
        text_parts: list[str] = []

        for block in data.get("content", []):
            if block.get("type") == "text":
                txt = block.get("text", "")
                text_parts.append(txt)
                if on_chunk:
                    on_chunk(txt)
            elif block.get("type") == "tool_use":
                tool_calls.append(ToolCallRequest(
                    name=block.get("name", ""),
                    arguments=block.get("input", {}),
                    call_id=block.get("id", ""),
                    human_description=f"execute {block.get('name')} with parameters {json.dumps(block.get('input', {}))}"
                ))

        usage = data.get("usage", {})
        in_tok = usage.get("input_tokens", 0)
        out_tok = usage.get("output_tokens", 0)

        return LLMResponse(
            text="".join(text_parts),
            tool_calls=tool_calls,
            provider_used="anthropic",
            model_used=model_name,
            input_tokens=in_tok,
            output_tokens=out_tok,
        )

    async def _call_ollama(
        self,
        model_name: str,
        messages: list[dict[str, Any]],
        system_prompt: str,
        tools: Optional[list[dict[str, Any]]],
        on_chunk: Optional[Callable[[str], None]],
    ) -> LLMResponse:
        url = f"{self.config.llm.local_fallback_url}/api/chat"
        ollama_msgs = []
        if system_prompt:
            ollama_msgs.append({"role": "system", "content": system_prompt})
        ollama_msgs.extend(messages)

        loop = asyncio.get_running_loop()
        res = await loop.run_in_executor(
            None,
            lambda: requests.post(
                url,
                json={"model": model_name, "messages": ollama_msgs, "stream": False},
                timeout=self.config.llm.timeout_seconds,
            )
        )
        if res.status_code != 200:
            raise RuntimeError(f"Ollama server returned {res.status_code}: {res.text}")

        msg = res.json().get("message", {})
        text = msg.get("content", "")
        if on_chunk and text:
            on_chunk(text)
        return LLMResponse(
            text=text,
            tool_calls=[],
            provider_used="ollama",
            model_used=model_name,
            input_tokens=100,
            output_tokens=100,
        )
