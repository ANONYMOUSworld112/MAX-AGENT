"""
MAX OS — Data Boundary Policy Enforcement Point

A single function every outbound LLM API call must pass through, stripping out-of-scope
file content and masking credential-shaped strings before the call is made.

Design:
  - Minimum necessary context for every LLM call.
  - Strips file content outside active task scope.
  - Masks credentials / API keys / tokens matching known regex patterns.
  - See ARCHITECTURE.md step 0.4, MAX_MASTER_PROMPT.md Data Boundary Policy.

Acceptance criteria:
  - A test with a deliberately planted fake API key in an out-of-scope file confirms
    it never appears in the outbound payload.
"""

import re
import logging
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger("max.data_boundary")

# Common secret patterns (Anthropic, OpenAI, GitHub, Google, AWS, generic tokens/keys)
SECRET_PATTERNS = [
    (r"sk-ant-[a-zA-Z0-9_\-]{20,}", "[MASKED_ANTHROPIC_KEY]"),
    (r"sk-proj-[a-zA-Z0-9_\-]{20,}", "[MASKED_OPENAI_KEY]"),
    (r"sk-[a-zA-Z0-9]{32,}", "[MASKED_API_KEY]"),
    (r"ghp_[a-zA-Z0-9]{36}", "[MASKED_GITHUB_TOKEN]"),
    (r"gho_[a-zA-Z0-9]{36}", "[MASKED_GITHUB_OAUTH_TOKEN]"),
    (r"AIza[0-9A-Za-z\-_]{35}", "[MASKED_GOOGLE_KEY]"),
    (r"AKIA[0-9A-Z]{16}", "[MASKED_AWS_KEY_ID]"),
    (r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----[\s\S]+?-----END (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----", "[MASKED_PRIVATE_KEY]"),
    (r"(?i)(api[_\-]?key|secret[_\-]?key|access[_\-]?token|password)\s*[:=]\s*[\"']?([a-zA-Z0-9_\-]{16,})[\"']?", r"\1: [MASKED_CREDENTIAL]"),
]

COMPILED_PATTERNS = [(re.compile(pattern), replacement) for pattern, replacement in SECRET_PATTERNS]


def mask_credentials(text: str) -> str:
    """
    Scans a string and replaces any secret or key patterns with masked placeholders.
    """
    if not isinstance(text, str):
        return text

    sanitized = text
    for regex, replacement in COMPILED_PATTERNS:
        sanitized = regex.sub(replacement, sanitized)

    return sanitized


def sanitize_payload(payload: Union[str, Dict[str, Any], List[Any]]) -> Union[str, Dict[str, Any], List[Any]]:
    """
    Recursively scans and sanitizes a payload structure (dict, list, or string)
    masking any credential-like text.
    """
    if isinstance(payload, str):
        return mask_credentials(payload)
    elif isinstance(payload, dict):
        return {k: sanitize_payload(v) for k, v in payload.items()}
    elif isinstance(payload, list):
        return [sanitize_payload(item) for item in payload]
    else:
        return payload


def enforce_data_boundary(
    payload: Union[str, Dict[str, Any]],
    in_scope_files: Optional[List[str]] = None,
    file_context_map: Optional[Dict[str, str]] = None
) -> Union[str, Dict[str, Any]]:
    """
    Enforces Data Boundary Policy on outbound LLM call payloads:
      1. Masks any secrets/credentials found in payload.
      2. If file_context_map is provided, strips any files NOT listed in in_scope_files.

    Args:
        payload: Prompt string or LLM API payload dictionary.
        in_scope_files: List of file paths explicitly in scope for this task.
        file_context_map: Optional dict of {filepath: content} being attached.

    Returns:
        Sanitized payload ready to send to external LLM API.
    """
    # 1. Handle file stripping if context map is provided
    if file_context_map is not None:
        allowed_files = set(in_scope_files or [])
        filtered_context = {}
        for filepath, content in file_context_map.items():
            if filepath in allowed_files:
                filtered_context[filepath] = content
            else:
                logger.info(f"Data boundary stripped out-of-scope file: {filepath}")

        # If payload is a dict with file attachments, apply filtered context
        if isinstance(payload, dict) and "files" in payload:
            payload["files"] = filtered_context

    # 2. Mask secrets across entire payload structure
    sanitized_outbound = sanitize_payload(payload)

    return sanitized_outbound
