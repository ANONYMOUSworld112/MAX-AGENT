"""
Ollama Local LLM Provider
=========================

Interfaces with locally running Ollama instances for private, offline-capable
inference and low-latency local execution.
"""

from __future__ import annotations

import json
import logging
import urllib.request
from typing import Any, Dict, List, Optional

from core.providers.base import LLMProvider, LLMResponse

logger = logging.getLogger("max.providers.ollama")


class OllamaProvider(LLMProvider):
    """Local Ollama LLM provider."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model_name: str = "llama3.2",
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.timeout = timeout

    def provider_name(self) -> str:
        return f"ollama/{self.model_name}"

    def is_available(self) -> bool:
        """Pings Ollama tags endpoint to determine if daemon is running locally."""
        try:
            req = urllib.request.Request(f"{self.base_url}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                return resp.status == 200
        except Exception:
            return False

    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
    ) -> LLMResponse:
        endpoint = f"{self.base_url}/api/chat"

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        body = {
            "model": self.model_name,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }

        req_data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            endpoint,
            data=req_data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                resp_json = json.loads(resp.read().decode("utf-8"))

            content = resp_json.get("message", {}).get("content", "")
            return LLMResponse(
                content=content,
                model=self.model_name,
                usage={
                    "prompt_eval_count": resp_json.get("prompt_eval_count", 0),
                    "eval_count": resp_json.get("eval_count", 0),
                },
            )
        except Exception as exc:
            logger.error("Ollama API call failed: %s", exc)
            raise RuntimeError(f"Ollama generation error: {exc}") from exc
