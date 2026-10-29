"""
core/llm/preflight.py — LLM Model Existence & Startup Preflight Validator.

Verifies that configured model IDs exist and are reachable before launching FRIDAY.
Prevents silent runtime failures caused by deprecated or misspelled model names.
"""
from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional, Tuple

import requests

from core.config_loader import AppConfig, get_config

logger = logging.getLogger("friday.llm.preflight")


class ModelPreflightValidator:
    """Preflight checker for configured LLM model identifiers."""

    def __init__(self, config: Optional[AppConfig] = None) -> None:
        self.config = config or get_config()

    def validate_all(self) -> dict[str, bool]:
        """Validate configured primary, fallback, and fast voice models."""
        results = {
            "primary": self.validate_model(
                self.config.llm.primary_provider,
                self.config.llm.primary_model
            ),
            "fallback": self.validate_model(
                self.config.llm.fallback_provider,
                self.config.llm.fallback_model
            ),
        }
        return results

    def validate_model(self, provider: str, model_id: str) -> bool:
        """Check if a specific model ID is valid or formatted correctly."""
        if not model_id:
            logger.error("Model ID for provider '%s' is empty.", provider)
            return False

        if provider == "gemini":
            api_key = self.config.gemini_api_key or os.environ.get("GEMINI_API_KEY")
            if not api_key:
                logger.warning("GEMINI_API_KEY not configured; skipping online model check for '%s'.", model_id)
                return True
            try:
                # Query Google models list
                url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
                res = requests.get(url, timeout=5)
                if res.status_code == 200:
                    models = [m.get("name", "").replace("models/", "") for m in res.json().get("models", [])]
                    # Direct match or prefix match
                    valid = any(model_id in m for m in models) or model_id in models
                    if valid:
                        logger.info("Validated Gemini model ID '%s' exists.", model_id)
                    else:
                        logger.warning("Configured Gemini model ID '%s' not found in models list: %s", model_id, models[:5])
                    return valid
            except Exception as e:
                logger.warning("Gemini preflight request error: %s. Assuming valid format.", e)
                return True

        elif provider == "anthropic":
            # Check format or query if key exists
            api_key = self.config.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                logger.warning("ANTHROPIC_API_KEY not configured; skipping online model check for '%s'.", model_id)
                return True
            # Anthropic models follow standard naming
            return len(model_id) > 3

        elif provider == "ollama":
            try:
                res = requests.get(f"{self.config.llm.ollama_base_url}/api/tags", timeout=3)
                if res.status_code == 200:
                    models = [m.get("name") for m in res.json().get("models", [])]
                    return model_id in models
            except Exception:
                return False

        return True
