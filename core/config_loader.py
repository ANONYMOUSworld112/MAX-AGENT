"""
core/config_loader.py — Unified Pydantic Configuration Loader for FRIDAY.

Loads from:
  1. config/config.yaml (structured defaults)
  2. config/api_keys.json (legacy credential store)
  3. .env and system environment variables
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def get_base_dir() -> Path:
    return Path(__file__).resolve().parent.parent


BASE_DIR = get_base_dir()


class AssistantSettings(BaseModel):
    name: str = "FRIDAY"
    title: str = "boss"
    tone: str = "tactical"
    spoken_sentence_limit: int = 3


class LLMSettings(BaseModel):
    primary_provider: str = "gemini"
    primary_model: str = "gemini-3.8-flash"
    fallback_provider: str = "anthropic"
    fallback_model: str = "claude-sonnet-5-5"
    fast_voice_model: str = "claude-haiku-5-5"
    local_fallback_url: str = "http://localhost:11434"
    local_fallback_model: str = "qwen2.5:7b"
    monthly_budget_usd: float = 25.0
    timeout_seconds: float = 30.0
    max_retries: int = 3
    backoff_factor: float = 1.5


class HardwareSettings(BaseModel):
    target: str = "rtx3050"
    max_gpu_models_mb: int = 3000
    whisper_device: str = "cuda"
    whisper_compute: str = "int8"
    yolo_device: str = "cuda"
    yolo_max_fps: int = 10
    low_power_profile: bool = False


class ToolsSettings(BaseModel):
    directory: str = "tools"
    default_timeout_seconds: float = 15.0
    hot_reload: bool = True
    auto_confirm_tier1: bool = True
    dry_run: bool = False


class SafetySettings(BaseModel):
    kill_switch_hotkey: str = "ctrl+alt+shift+k"
    tamper_evident_audit: bool = True
    taint_tracking_enabled: bool = True
    prompt_injection_defense: bool = True


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    assistant: AssistantSettings = Field(default_factory=AssistantSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    hardware: HardwareSettings = Field(default_factory=HardwareSettings)
    tools: ToolsSettings = Field(default_factory=ToolsSettings)
    safety: SafetySettings = Field(default_factory=SafetySettings)

    # API keys loaded from env or api_keys.json
    gemini_api_key: Optional[str] = Field(default=None, alias="GEMINI_API_KEY")
    anthropic_api_key: Optional[str] = Field(default=None, alias="ANTHROPIC_API_KEY")
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> AppConfig:
        cfg_file = config_path or (BASE_DIR / "config" / "config.yaml")
        yaml_data: Dict[str, Any] = {}
        if cfg_file.exists():
            try:
                loaded = yaml.safe_load(cfg_file.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    yaml_data = loaded
            except Exception as e:
                print(f"[Config] Warning: could not parse {cfg_file}: {e}")

        # Check config/api_keys.json for fallback keys
        api_keys_file = BASE_DIR / "config" / "api_keys.json"
        keys_data: Dict[str, Any] = {}
        if api_keys_file.exists():
            try:
                keys_data = json.loads(api_keys_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        # Merge YAML
        merged: Dict[str, Any] = dict(yaml_data)
        if "gemini_api_key" not in merged and "gemini_api_key" in keys_data:
            merged["gemini_api_key"] = keys_data["gemini_api_key"]
            merged["GEMINI_API_KEY"] = keys_data["gemini_api_key"]
        if "anthropic_api_key" not in merged and "anthropic_api_key" in keys_data:
            merged["anthropic_api_key"] = keys_data["anthropic_api_key"]
            merged["ANTHROPIC_API_KEY"] = keys_data["anthropic_api_key"]

        return cls(**merged)


_GLOBAL_CONFIG: Optional[AppConfig] = None


def get_config(reload: bool = False) -> AppConfig:
    global _GLOBAL_CONFIG
    if _GLOBAL_CONFIG is None or reload:
        _GLOBAL_CONFIG = AppConfig.load()
    return _GLOBAL_CONFIG


load_config = get_config
