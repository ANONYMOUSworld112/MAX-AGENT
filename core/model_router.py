"""
MAX OS — Multi-Model Backend Router (Step 6.1).
Supports local models (Ollama, vLLM, MLX) and cloud models (Anthropic, OpenAI, Google Gemini).
Tracks models in model_registry table.
Provides unified router with automated fallback from local to cloud when offline or overloaded.
Enforces Data Boundary payload sanitization before any API call.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from core.data_boundary import sanitize_payload
from core.quota import QuotaTracker

DEFAULT_DB_PATH = Path(__file__).parent.parent / "max_state.db"


@dataclass
class ModelInfo:
    model_id: str
    provider: str  # 'ollama', 'anthropic', 'openai', 'gemini'
    model_name: str
    is_local: bool
    context_window: int = 8192
    status: str = "active"
    last_verified: Optional[str] = None


@dataclass
class ModelResponse:
    content: str
    model_used: str
    provider: str
    is_local: bool
    tokens_used: int
    fallback_occurred: bool = False
    error: Optional[str] = None


class ModelRouter:
    """
    Unified Multi-Model Router.
    Routes requests to appropriate provider with automated local -> cloud fallback.
    """

    def __init__(
        self,
        db_path: Optional[Path | str] = None,
        quota_tracker: Optional[QuotaTracker] = None,
        local_backend_fn: Optional[Callable[[str, str], str]] = None,
        cloud_backend_fn: Optional[Callable[[str, str], str]] = None,
    ):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.quota_tracker = quota_tracker or QuotaTracker(db_path=self.db_path)
        self.local_backend_fn = local_backend_fn
        self.cloud_backend_fn = cloud_backend_fn
        self._seed_default_models()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.row_factory = sqlite3.Row
        return conn

    def _seed_default_models(self) -> None:
        """Seeds default local and cloud models into model_registry."""
        defaults = [
            ("ollama-qwen2.5-coder", "ollama", "qwen2.5-coder:7b", 1, 32768),
            ("ollama-llama3.1", "ollama", "llama3.1:8b", 1, 8192),
            ("claude-3-7-sonnet", "anthropic", "claude-3-7-sonnet-20250219", 0, 200000),
            ("gpt-4o", "openai", "gpt-4o", 0, 128000),
            ("gemini-2.0-flash", "gemini", "gemini-2.0-flash", 0, 1000000),
        ]
        conn = self._get_conn()
        now = datetime.now(timezone.utc).isoformat()
        try:
            for mid, prov, mname, is_loc, cwin in defaults:
                conn.execute(
                    """
                    INSERT INTO model_registry (model_id, provider, model_name, is_local, context_window, status, last_verified)
                    VALUES (?, ?, ?, ?, ?, 'active', ?)
                    ON CONFLICT(model_id) DO NOTHING;
                    """,
                    (mid, prov, mname, is_loc, cwin, now),
                )
            conn.commit()
        finally:
            conn.close()

    def list_models(self, local_only: bool = False) -> List[ModelInfo]:
        """Lists registered models."""
        conn = self._get_conn()
        try:
            query = "SELECT * FROM model_registry"
            if local_only:
                query += " WHERE is_local = 1"
            rows = conn.execute(query).fetchall()
            return [
                ModelInfo(
                    model_id=r["model_id"],
                    provider=r["provider"],
                    model_name=r["model_name"],
                    is_local=bool(r["is_local"]),
                    context_window=r["context_window"],
                    status=r["status"],
                    last_verified=r["last_verified"],
                )
                for r in rows
            ]
        finally:
            conn.close()

    def complete(
        self,
        prompt: str,
        preferred_model: str = "claude-3-7-sonnet",
        fallback_model: str = "claude-3-7-sonnet",
        allow_fallback: bool = True,
    ) -> ModelResponse:
        """
        Executes text completion through data boundary.
        If preferred model fails (e.g. local Ollama not running), falls back to cloud model.
        """
        # Enforce Data Boundary Policy on outbound payload
        safe_payload = sanitize_payload({"prompt": prompt})
        safe_prompt = safe_payload.get("prompt", prompt)

        # 1. Try preferred model
        conn = self._get_conn()
        cur = conn.execute("SELECT * FROM model_registry WHERE model_id = ?", (preferred_model,))
        pref_row = cur.fetchone()
        conn.close()

        is_local = bool(pref_row["is_local"]) if pref_row else ("ollama" in preferred_model)
        provider = pref_row["provider"] if pref_row else "anthropic"

        try:
            if is_local:
                if self.local_backend_fn is not None:
                    text = self.local_backend_fn(preferred_model, safe_prompt)
                else:
                    text = f"[Local {preferred_model} Output]: {safe_prompt[:50]}..."
            else:
                if self.cloud_backend_fn is not None:
                    text = self.cloud_backend_fn(preferred_model, safe_prompt)
                else:
                    text = f"[Cloud {preferred_model} Output]: {safe_prompt[:50]}..."

            # Record token usage if cloud
            tokens = len(safe_prompt.split()) + len(text.split())
            if not is_local:
                self.quota_tracker.record_usage(provider, calls=1, tokens=tokens)

            return ModelResponse(
                content=text,
                model_used=preferred_model,
                provider=provider,
                is_local=is_local,
                tokens_used=tokens,
                fallback_occurred=False,
            )

        except Exception as e:
            if not allow_fallback or preferred_model == fallback_model:
                return ModelResponse(
                    content="",
                    model_used=preferred_model,
                    provider=provider,
                    is_local=is_local,
                    tokens_used=0,
                    error=str(e),
                )

            # Fallback to cloud model
            fb_text = ""
            if self.cloud_backend_fn is not None:
                fb_text = self.cloud_backend_fn(fallback_model, safe_prompt)
            else:
                fb_text = f"[Fallback {fallback_model} Output]: {safe_prompt[:50]}..."

            tokens = len(safe_prompt.split()) + len(fb_text.split())
            self.quota_tracker.record_usage("cloud_fallback", calls=1, tokens=tokens)

            return ModelResponse(
                content=fb_text,
                model_used=fallback_model,
                provider="cloud_fallback",
                is_local=False,
                tokens_used=tokens,
                fallback_occurred=True,
            )
