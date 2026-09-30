"""
Gemini Cloud LLM Provider
=========================

Interfaces with Google Gemini APIs for high-capacity reasoning, multimodal input,
and complex task execution.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.request
from typing import Any, Dict, List, Optional

from core.providers.base import LLMProvider, LLMResponse

logger = logging.getLogger("max.providers.gemini")


class GeminiProvider(LLMProvider):
    """Google Gemini LLM provider."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gemini-2.5-flash",
        timeout: float = 30.0,
    ) -> None:
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.model_name = model_name
        self.timeout = timeout

    def provider_name(self) -> str:
        return f"gemini/{self.model_name}"

    def is_available(self) -> bool:
        return bool(self.api_key and len(self.api_key.strip()) > 10)

    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
    ) -> LLMResponse:
        if not self.is_available():
            raise RuntimeError("GeminiProvider is not available (missing or invalid GEMINI_API_KEY).")

        endpoint = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent"
            f"?key={self.api_key}"
        )

        contents = []
        if system_prompt:
            contents.append({"role": "user", "parts": [{"text": f"System Instructions:\n{system_prompt}"}]})
            contents.append({"role": "model", "parts": [{"text": "Understood."}]})

        contents.append({"role": "user", "parts": [{"text": prompt}]})

        body = {
            "contents": contents,
            "generationConfig": {
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

            candidates = resp_json.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                text = "".join(p.get("text", "") for p in parts)
                return LLMResponse(
                    content=text,
                    model=self.model_name,
                    usage=resp_json.get("usageMetadata", {}),
                )
            return LLMResponse(content="", model=self.model_name)
        except Exception as exc:
            logger.error("Gemini API call failed: %s", exc)
            raise RuntimeError(f"Gemini API generation error: {exc}") from exc
