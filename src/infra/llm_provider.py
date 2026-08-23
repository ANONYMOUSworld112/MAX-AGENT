"""
MAX OS — Multi-Provider LLM Engine
Build Order: #23 (Layer 5D)
═══════════════════════════════════════════════════════

Unified LLM completion router supporting:
- Local Ollama (Gemma:7b / Llama3)
- Anthropic Claude 3.5 Sonnet
- Google Gemini 1.5 Pro / Flash
- OpenAI GPT-4o / GPT-4o-mini
- Custom OpenAI-Compatible Endpoints (Groq, Together, DeepSeek, vLLM)
"""

from __future__ import annotations

import os
import logging
import requests
from typing import Optional, Dict, Any

from src.infra import data_boundary, vault

try:
    import dotenv
    dotenv.load_dotenv()
except Exception:
    pass

logger = logging.getLogger("max.infra.llm_provider")


def query_local_ollama(prompt: str, model_name: str = "gemma:7b", timeout: int = 15) -> Optional[str]:
    """Query local Ollama instance on http://localhost:11434 with fast timeout."""
    try:
        base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
        url = f"{base_url}/api/generate"
        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": False,
        }
        res = requests.post(url, json=payload, timeout=timeout)
        if res.status_code == 200:
            data = res.json()
            return data.get("response", "").strip()
        else:
            logger.warning("Ollama returned status code %d: %s", res.status_code, res.text)
            return None
    except Exception as e:
        logger.warning("Ollama call failed or not responding: %s", e)
        return None


def generate_llm_response(
    prompt: str = "",
    prompt_text: str = "",
    model_name: str = "auto",
    system_prompt: str = "",
    override_keys: Optional[Dict[str, str]] = None,
    **kwargs: Any,
) -> str:
    """
    Generate direct LLM response using available model provider.
    Accepts prompt or prompt_text, sanitizes text, and routes intelligently.
    """
    raw_prompt = prompt or prompt_text or kwargs.get("text", "") or ""
    clean_prompt = data_boundary.sanitize(str(raw_prompt).strip())
    model_lower = str(model_name).lower() if model_name else "auto"
    keys = override_keys or {}

    # Check available credentials
    v = vault.get_vault()
    gemini_key = keys.get("gemini_key") or v.get_secret("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
    anthropic_key = keys.get("anthropic_key") or v.get_secret("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    openai_key = keys.get("openai_key") or v.get_secret("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    custom_key = keys.get("custom_key") or v.get_secret("CUSTOM_LLM_API_KEY") or os.environ.get("CUSTOM_LLM_API_KEY")
    custom_url = keys.get("custom_base_url") or v.get_secret("CUSTOM_LLM_BASE_URL") or os.environ.get("CUSTOM_LLM_BASE_URL")

    # ── 1. Google Gemini API ──────────────────────────────────
    if "gemini" in model_lower or (model_lower == "auto" and gemini_key):
        if gemini_key:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}"
                headers = {"Content-Type": "application/json"}
                prompt_payload = f"{system_prompt}\n\n{clean_prompt}" if system_prompt else clean_prompt
                body = {
                    "contents": [{"parts": [{"text": prompt_payload}]}]
                }
                res = requests.post(url, headers=headers, json=body, timeout=15)
                if res.status_code == 200:
                    data = res.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            return parts[0].get("text", "").strip()
                logger.warning("Gemini API error %d: %s", res.status_code, res.text)
            except Exception as e:
                logger.warning("Gemini connection error: %s", e)

    # ── 2. Anthropic Claude API ────────────────────────────────
    if "claude" in model_lower or "anthropic" in model_lower or (model_lower == "auto" and anthropic_key):
        if anthropic_key:
            try:
                headers = {
                    "x-api-key": anthropic_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                }
                body = {
                    "model": "claude-3-5-sonnet-20241022",
                    "max_tokens": 1000,
                    "messages": [{"role": "user", "content": clean_prompt}],
                }
                if system_prompt:
                    body["system"] = system_prompt
                res = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=body, timeout=15)
                if res.status_code == 200:
                    return res.json()["content"][0]["text"].strip()
                logger.warning("Claude API error %d: %s", res.status_code, res.text)
            except Exception as e:
                logger.warning("Claude connection error: %s", e)

    # ── 3. OpenAI GPT API ─────────────────────────────────────
    if "gpt" in model_lower or "openai" in model_lower or (model_lower == "auto" and openai_key):
        if openai_key:
            try:
                headers = {
                    "Authorization": f"Bearer {openai_key}",
                    "Content-Type": "application/json",
                }
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": clean_prompt})
                body = {
                    "model": "gpt-4o-mini",
                    "messages": messages,
                }
                res = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=body, timeout=15)
                if res.status_code == 200:
                    return res.json()["choices"][0]["message"]["content"].strip()
                logger.warning("OpenAI API error %d: %s", res.status_code, res.text)
            except Exception as e:
                logger.warning("OpenAI connection error: %s", e)

    # ── 4. Custom LLM Provider ─────────────────────────────────
    if "custom" in model_lower or custom_key or custom_url:
        if custom_url or custom_key:
            target_url = (custom_url or "https://api.openai.com/v1").rstrip("/")
            endpoint = f"{target_url}/chat/completions" if not target_url.endswith("/chat/completions") else target_url
            headers = {"Content-Type": "application/json"}
            if custom_key:
                headers["Authorization"] = f"Bearer {custom_key}"
            body = {
                "model": keys.get("custom_model") or os.environ.get("CUSTOM_LLM_MODEL_NAME", "default"),
                "messages": [
                    {"role": "system", "content": system_prompt or "You are MAX AI assistant."},
                    {"role": "user", "content": clean_prompt},
                ],
            }
            try:
                res = requests.post(endpoint, headers=headers, json=body, timeout=15)
                if res.status_code == 200:
                    return res.json()["choices"][0]["message"]["content"].strip()
            except Exception as e:
                logger.warning("Custom LLM connection error: %s", e)

    # ── 5. Local Ollama ───────────────────────────────────────
    ollama_res = query_local_ollama(clean_prompt, model_name="gemma:7b", timeout=5)
    if ollama_res:
        return ollama_res

    # ── 6. Deterministic Conversational Fallback ───────────────
    return (
        f"Greetings, Sir. I am online and all multi-agent pipelines (Calendar, Notes, Coding, Deploy, "
        f"Research, Filesystem, and Desktop Control) are standing by to execute your tasks."
    )
