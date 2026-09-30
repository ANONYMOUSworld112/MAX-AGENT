"""
Unit tests for Credential & Secret Sanitizer (Task 7.3)
========================================================

Covers:
- Gemini API key redaction (AIza...)
- OpenAI and Anthropic key redaction
- GitHub token redaction
- AWS access key redaction
- HTTP Bearer token redaction
- Embedded URL credential redaction
- Key-value JSON and config scrubbing
- Recursive sanitization of nested dicts, lists, and tuples
- SanitizedLogFilter integration with standard logging
"""

import logging
import pytest

from core.security.sanitizer import (
    SanitizedLogFilter,
    sanitize_data,
    sanitize_text,
)


def test_sanitize_gemini_key():
    raw = "Found key AIzaSyD-1234567890abcdefghijklmnopqrst in configuration."
    clean = sanitize_text(raw)
    assert "AIzaSyD" not in clean
    assert "[REDACTED_GEMINI_KEY]" in clean


def test_sanitize_openai_and_anthropic_keys():
    raw_openai = "Connecting with sk-abc12345678901234567890abcdef to OpenAI"
    clean_openai = sanitize_text(raw_openai)
    assert "sk-abc" not in clean_openai
    assert "[REDACTED_OPENAI_KEY]" in clean_openai

    raw_anthropic = "Using Anthropic token sk-ant-api03-abcdef123456789012345 for Claude"
    clean_anthropic = sanitize_text(raw_anthropic)
    assert "sk-ant" not in clean_anthropic
    assert "[REDACTED_ANTHROPIC_KEY]" in clean_anthropic


def test_sanitize_github_and_aws_keys():
    raw_gh = "Pushing repo with token ghp_1234567890abcdefghijklmnopqrstuvwxyz12"
    clean_gh = sanitize_text(raw_gh)
    assert "ghp_" not in clean_gh
    assert "[REDACTED_GITHUB_TOKEN]" in clean_gh

    raw_aws = "Deploying to AWS using AKIAIOSFODNN7EXAMPLE credentials"
    clean_aws = sanitize_text(raw_aws)
    assert "AKIAIOSFODNN7EXAMPLE" not in clean_aws
    assert "[REDACTED_AWS_KEY]" in clean_aws


def test_sanitize_bearer_token():
    raw = "Headers: Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.e30.k"
    clean = sanitize_text(raw)
    assert "eyJhbG" not in clean
    assert "Bearer [REDACTED_TOKEN]" in clean


def test_sanitize_database_url():
    raw = "Connecting to postgresql://admin:SuperSecretPass123!@db.internal:5432/max_agent"
    clean = sanitize_text(raw)
    assert "SuperSecretPass123!" not in clean
    assert "postgresql://admin:[REDACTED_PASSWORD]@db.internal:5432/max_agent" in clean


def test_sanitize_recursive_data():
    payload = {
        "user": "alice",
        "api_key": "AIzaSyD-1234567890abcdefghijklmnopqrst",
        "password": "ClearTextPassword!",
        "details": {
            "token": "secret_token_val",
            "nested_list": [
                "normal item",
                "sk-123456789012345678901234567890",
                {"deep_secret": "my_pass"},
            ],
        },
    }

    clean = sanitize_data(payload)
    assert clean["user"] == "alice"
    assert clean["api_key"] == "[REDACTED_SECRET]"
    assert clean["password"] == "[REDACTED_SECRET]"
    assert clean["details"]["token"] == "[REDACTED_SECRET]"
    assert clean["details"]["nested_list"][0] == "normal item"
    assert clean["details"]["nested_list"][1] == "[REDACTED_OPENAI_KEY]"
    assert clean["details"]["nested_list"][2]["deep_secret"] == "[REDACTED_SECRET]"


def test_sanitized_log_filter():
    logger = logging.getLogger("test_sanitizer_logger")
    logger.setLevel(logging.INFO)

    class ListHandler(logging.Handler):
        def __init__(self):
            super().__init__()
            self.records = []

        def emit(self, record):
            self.records.append(record)

    handler = ListHandler()
    handler.addFilter(SanitizedLogFilter())
    logger.addHandler(handler)

    logger.info("Initializing provider with key %s", "AIzaSyD-1234567890abcdefghijklmnopqrst")

    assert len(handler.records) == 1
    rec = handler.records[0]
    msg = rec.getMessage()
    assert "AIzaSyD" not in msg
    assert "[REDACTED_GEMINI_KEY]" in msg
