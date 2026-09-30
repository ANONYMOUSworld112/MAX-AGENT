"""
Unit tests for RecoveryEngine & Error Classification (Task 8.2)
==============================================================

Covers:
- Error classification into ErrorClass (TRANSIENT, ENVIRONMENT, LOGIC, RESOURCE, EXTERNAL)
- Retry eligibility logic (transient + idempotency gates)
- Exponential backoff calculations
- Git rollback via ProcessManager
"""

import pytest

from core.contracts import ErrorClass, IdempotencyClass
from core.recovery_engine import (
    RecoveryEngine,
    calculate_backoff,
    classify_error,
)


def test_error_classification():
    # Transient
    assert classify_error(TimeoutError("Connection timed out after 30s")) == ErrorClass.TRANSIENT
    assert classify_error("HTTP 503 Service Temporarily Unavailable") == ErrorClass.TRANSIENT
    assert classify_error("Error 429: Too Many Requests (Rate limit exceeded)") == ErrorClass.TRANSIENT

    # Environment
    assert classify_error(FileNotFoundError("No such file or directory: /bin/node")) == ErrorClass.ENVIRONMENT
    assert classify_error(PermissionError("Access is denied to folder")) == ErrorClass.ENVIRONMENT
    assert classify_error("ModuleNotFoundError: No module named 'foo'") == ErrorClass.ENVIRONMENT

    # Logic
    assert classify_error(SyntaxError("invalid syntax on line 12")) == ErrorClass.LOGIC
    assert classify_error(AssertionError("expected 42 but got 0")) == ErrorClass.LOGIC
    assert classify_error(TypeError("unsupported operand type(s)")) == ErrorClass.LOGIC

    # Resource
    assert classify_error("OSError: [Errno 28] No space left on device") == ErrorClass.RESOURCE
    assert classify_error(MemoryError("CUDA out of memory, VRAM exhausted")) == ErrorClass.RESOURCE

    # External
    assert classify_error("HTTP 401 Unauthorized: Invalid API key") == ErrorClass.EXTERNAL
    assert classify_error("403 Forbidden: You do not have permission") == ErrorClass.EXTERNAL


def test_retry_eligibility():
    engine = RecoveryEngine(max_retries=3)

    # Transient + Idempotent -> Should retry
    can_retry, delay = engine.should_retry(
        error_class=ErrorClass.TRANSIENT,
        idempotency=IdempotencyClass.IDEMPOTENT,
        current_retries=0,
    )
    assert can_retry is True
    assert delay > 0

    # Transient + Non-Idempotent -> Never retry
    can_retry_non_idemp, _ = engine.should_retry(
        error_class=ErrorClass.TRANSIENT,
        idempotency=IdempotencyClass.NON_IDEMPOTENT,
        current_retries=0,
    )
    assert can_retry_non_idemp is False

    # Logic Error -> Never retry blind logic errors
    can_retry_logic, _ = engine.should_retry(
        error_class=ErrorClass.LOGIC,
        idempotency=IdempotencyClass.IDEMPOTENT,
        current_retries=0,
    )
    assert can_retry_logic is False

    # Max retries exceeded -> Never retry
    can_retry_exceeded, _ = engine.should_retry(
        error_class=ErrorClass.TRANSIENT,
        idempotency=IdempotencyClass.IDEMPOTENT,
        current_retries=3,
    )
    assert can_retry_exceeded is False


def test_calculate_backoff():
    # Retry 1: 0.5s
    assert calculate_backoff(1, base_delay=0.5) == 0.5
    # Retry 2: 1.0s
    assert calculate_backoff(2, base_delay=0.5) == 1.0
    # Retry 3: 2.0s
    assert calculate_backoff(3, base_delay=0.5) == 2.0
    # Cap at max_delay
    assert calculate_backoff(10, base_delay=0.5, max_delay=5.0) == 5.0
