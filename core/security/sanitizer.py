"""
Credential & Secret Sanitizer (Task 7.3)
========================================

Eliminates credential exposure in logs, audit events, StateDB storage,
and error messages through high-precision redaction patterns.

Patterns covered:
- Google AI / Gemini API keys (AIza...)
- OpenAI API keys (sk-...)
- Anthropic API keys (sk-ant-...)
- GitHub tokens (ghp_, gho_, ghu_, ghs_, ghr_)
- AWS Access Keys (AKIA...)
- HTTP Bearer Tokens (Bearer ...)
- Passwords and secrets in JSON/key-value pairs
- Passwords in connection URLs (e.g. postgresql://user:pass@host)
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Set, Tuple, Union

# Compiled pattern rules: (Pattern, Replacement)
SANITIZATION_RULES = [
    # Anthropic API Keys (must be before generic sk- rule)
    (re.compile(r"\bsk-ant-[A-Za-z0-9\-_]{20,}\b"), "[REDACTED_ANTHROPIC_KEY]"),
    # Google AI / Gemini Keys: AIza... (typically 39 chars, match 30-45 chars after AIza)
    (re.compile(r"\bAIza[0-9A-Za-z\-_]{30,45}\b"), "[REDACTED_GEMINI_KEY]"),
    # OpenAI API Keys
    (re.compile(r"\bsk-[A-Za-z0-9\-_]{20,}\b"), "[REDACTED_OPENAI_KEY]"),
    # GitHub personal / app tokens
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{36,255}\b"), "[REDACTED_GITHUB_TOKEN]"),
    # AWS Access Key IDs
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[REDACTED_AWS_KEY]"),
    # HTTP Bearer Tokens
    (re.compile(r"(?i)\bBearer\s+([A-Za-z0-9\-_=\.]{20,})\b"), "Bearer [REDACTED_TOKEN]"),
    # Embedded credentials in URLs (e.g., protocol://user:pass@host)
    (re.compile(r"(://[^:\s/]+:)([^@\s/]+)(@)"), r"\1[REDACTED_PASSWORD]\3"),
    # Key-Value assignments in JSON or query params: "api_key": "xyz" or password=xyz
    (
        re.compile(
            r'(?i)(["\']?(?:password|passwd|secret|api_key|apikey|private_key|access_token|refresh_token)["\']?\s*[:=]\s*["\'])([^"\'\s,}{]+)(["\']?)'
        ),
        r"\1[REDACTED_SECRET]\3",
    ),
]

SENSITIVE_KEY_NAMES = {
    "password",
    "passwd",
    "secret",
    "api_key",
    "apikey",
    "token",
    "access_token",
    "refresh_token",
    "auth",
    "authorization",
    "private_key",
    "client_secret",
}


def sanitize_text(text: str) -> str:
    """Sanitizes text by replacing sensitive API keys, tokens, and passwords with redaction markers."""
    if not text or not isinstance(text, str):
        return text

    sanitized = text
    for pattern, replacement in SANITIZATION_RULES:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized


def sanitize_data(data: Any) -> Any:
    """Recursively walks arbitrary Python data structures and redacts sensitive credentials."""
    if isinstance(data, str):
        return sanitize_text(data)

    if isinstance(data, dict):
        cleaned: Dict[str, Any] = {}
        for k, v in data.items():
            k_lower = str(k).lower().strip()
            # If the key itself is explicitly a credential name
            if any(sens in k_lower for sens in SENSITIVE_KEY_NAMES):
                if isinstance(v, str):
                    cleaned[k] = "[REDACTED_SECRET]"
                elif isinstance(v, (dict, list)):
                    cleaned[k] = sanitize_data(v)
                else:
                    cleaned[k] = "[REDACTED_SECRET]"
            else:
                cleaned[k] = sanitize_data(v)
        return cleaned

    if isinstance(data, list):
        return [sanitize_data(item) for item in data]

    if isinstance(data, tuple):
        return tuple(sanitize_data(item) for item in data)

    if isinstance(data, set):
        return {sanitize_data(item) for item in data}

    return data


class SanitizedLogFilter(logging.Filter):
    """Logging filter that scrubs sensitive credentials from record messages and arguments."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = sanitize_text(record.msg)
        elif record.msg:
            record.msg = sanitize_data(record.msg)

        if record.args:
            if isinstance(record.args, dict):
                record.args = sanitize_data(record.args)
            elif isinstance(record.args, tuple):
                record.args = tuple(sanitize_data(arg) for arg in record.args)
            elif isinstance(record.args, list):
                record.args = [sanitize_data(arg) for arg in record.args]
        return True
