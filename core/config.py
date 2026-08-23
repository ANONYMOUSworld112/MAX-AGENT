"""
MAX OS - Configuration
core/config.py
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ModelProviderConfig:
    name: str
    api_key_env: str
    base_url: Optional[str] = None
    is_local: bool = False

    @property
    def api_key(self) -> Optional[str]:
        return os.environ.get(self.api_key_env)

    @property
    def available(self) -> bool:
        return self.is_local or bool(self.api_key)


@dataclass
class MaxOSConfig:
    assistant_name: str = "MAX"
    log_dir: str = "logs"
    db_url: str = field(
        default_factory=lambda: os.environ.get(
            "MAX_OS_DB_URL", "postgresql://localhost:5432/max_os"
        )
    )
    vector_db_url: str = field(
        default_factory=lambda: os.environ.get("MAX_OS_QDRANT_URL", "http://localhost:6333")
    )
    model_providers: List[ModelProviderConfig] = field(
        default_factory=lambda: [
            ModelProviderConfig(name="anthropic", api_key_env="ANTHROPIC_API_KEY"),
            ModelProviderConfig(name="ollama", api_key_env="", base_url="http://localhost:11434", is_local=True),
        ]
    )

    def first_available_provider(self) -> Optional[ModelProviderConfig]:
        for provider in self.model_providers:
            if provider.available:
                return provider
        return None


def load_config() -> MaxOSConfig:
    return MaxOSConfig()
