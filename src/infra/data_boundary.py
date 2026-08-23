"""
MAX OS — Data Boundary Sanitizer
Build Order: #5 (Layer 1B)
═══════════════════════════════════════════════════════

Sanitizes outbound payloads to prevent API keys, credentials, and PII leakage.
Every LLM call passes through this module before leaving the machine.
"""

from __future__ import annotations

import re
import logging

logger = logging.getLogger("max.infra.data_boundary")

# Common API key and secret patterns
_SENSITIVE_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9_-]{20,}", re.I),
    re.compile(r"ghp_[a-zA-Z0-9]{36}", re.I),
    re.compile(r"gho_[a-zA-Z0-9]{36}", re.I),
    re.compile(r"glpat-[a-zA-Z0-9_-]{20,}", re.I),
    re.compile(r"xox[b-p]-[a-zA-Z0-9_-]{10,}", re.I),
    re.compile(r"AKIA[0-9A-Z]{16}", re.I),
    re.compile(r"([a-zA-Z0-9+/]{40})", re.I),
    re.compile(r"Bearer\s+[a-zA-Z0-9._-]{20,}", re.I),
]


def sanitize(text: str) -> str:
    """
    Mask any API keys, credentials, or sensitive token patterns in outbound text.
    """
    if not text:
        return text

    sanitized = text
    for pattern in _SENSITIVE_PATTERNS:
        sanitized = pattern.sub("[MASKED_SECRET]", sanitized)

    return sanitized


def check_outbound_safe(text: str) -> bool:
    """Return True if no raw API keys or credentials are detected."""
    for pattern in _SENSITIVE_PATTERNS:
        if pattern.search(text):
            return False
    return True
