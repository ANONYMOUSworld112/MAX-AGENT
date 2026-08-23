"""
MAX OS — Retry Policy Engine
Build Order: #10 (Layer 2E)
═══════════════════════════════════════════════════════

Exponential backoff with full jitter for transient and systemic errors.
Refuses to retry validation, permission, or destructive risk errors.
"""

from __future__ import annotations

import time
import random
import logging

from src.infra.errors import MaxError, ErrorClass, RETRY_POLICY

logger = logging.getLogger("max.core.retry")


def calculate_backoff_seconds(attempt: int, base_delay: float = 1.0, max_delay: float = 30.0) -> float:
    """Calculate exponential backoff with full jitter."""
    exp = min(max_delay, base_delay * (2 ** attempt))
    jittered = random.uniform(0, exp)
    return jittered


def should_retry(error: MaxError, current_attempt: int) -> bool:
    """Determine if a task error should be retried."""
    policy = RETRY_POLICY.get(error.error_class, {"retryable": False, "max_retries": 0})
    if not policy["retryable"]:
        return False

    return current_attempt < policy["max_retries"]


def execute_with_retry(func, task_id: str, max_retries: int = 3):
    """Wrap execution of a function with retry policy."""
    attempt = 0
    while True:
        try:
            return func()
        except MaxError as err:
            attempt += 1
            if should_retry(err, attempt):
                delay = calculate_backoff_seconds(attempt)
                logger.warning(
                    "Task '%s' failed with %s. Retrying attempt %d/%d after %.2fs...",
                    task_id, err.error_class.value, attempt, max_retries, delay
                )
                time.sleep(delay)
            else:
                raise err
        except Exception as exc:
            from src.infra.errors import classify
            err = classify(exc)
            attempt += 1
            if should_retry(err, attempt):
                delay = calculate_backoff_seconds(attempt)
                logger.warning(
                    "Task '%s' failed with %s. Retrying attempt %d/%d after %.2fs...",
                    task_id, err.error_class.value, attempt, max_retries, delay
                )
                time.sleep(delay)
            else:
                raise exc
