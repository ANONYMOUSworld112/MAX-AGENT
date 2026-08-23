"""
MAX OS — Jittered Backoff Retry Policy (Step 4.2).
Principle #7: Only transient and systemic errors ever retry, each bounded, with jittered exponential backoff.
Prevents thundering herd problems by spreading out retry times.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, TypeVar

from core.errors import ErrorClass, classify_error

T = TypeVar("T")


class MaxRetriesExceededError(Exception):
    """Raised when maximum retries for a task are exhausted."""
    def __init__(self, task_id: str, error_class: ErrorClass, attempts: int, last_error: Exception):
        super().__init__(f"Task {task_id} exhausted {attempts} retries. Last error ({error_class.value}): {last_error}")
        self.task_id = task_id
        self.error_class = error_class
        self.attempts = attempts
        self.last_error = last_error


@dataclass
class RetryConfig:
    max_retries: int = 3
    base_delay_s: float = 0.1
    max_delay_s: float = 5.0
    jitter_factor: float = 0.5  # spread factor +/-


DEFAULT_RETRY_CONFIGS: Dict[ErrorClass, RetryConfig] = {
    ErrorClass.TRANSIENT: RetryConfig(max_retries=3, base_delay_s=0.1, max_delay_s=3.0, jitter_factor=0.5),
    ErrorClass.SYSTEMIC: RetryConfig(max_retries=2, base_delay_s=0.2, max_delay_s=4.0, jitter_factor=0.5),
    ErrorClass.VALIDATION: RetryConfig(max_retries=0),
    ErrorClass.PERMISSION: RetryConfig(max_retries=0),
    ErrorClass.DESTRUCTIVE_RISK: RetryConfig(max_retries=0),
}


class RetryManager:
    """
    Manages bounded retries with jittered exponential backoff.
    """

    def __init__(self, configs: Optional[Dict[ErrorClass, RetryConfig]] = None):
        self.configs = configs or DEFAULT_RETRY_CONFIGS

    def calculate_delay(self, attempt: int, error_class: ErrorClass) -> float:
        """Calculates jittered exponential backoff delay."""
        cfg = self.configs.get(error_class, RetryConfig(max_retries=0))
        if cfg.max_retries == 0:
            return 0.0

        # Exponential backoff: base * 2^(attempt - 1)
        raw_delay = min(cfg.max_delay_s, cfg.base_delay_s * (2 ** max(0, attempt - 1)))
        
        # Add random jitter spread
        jitter_range = raw_delay * cfg.jitter_factor
        jitter = random.uniform(-jitter_range, jitter_range)
        return max(0.01, raw_delay + jitter)

    def execute_with_retry(
        self,
        fn: Callable[[], T],
        task_id: str = "task-anon",
        on_retry: Optional[Callable[[int, Exception, float], None]] = None,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> T:
        """
        Executes fn, classifying any exception. Retries boundedly with jitter if retryable.
        """
        attempt = 0
        while True:
            try:
                return fn()
            except Exception as e:
                attempt += 1
                error_class = classify_error(e)
                cfg = self.configs.get(error_class, RetryConfig(max_retries=0))

                if attempt > cfg.max_retries or cfg.max_retries == 0:
                    if cfg.max_retries > 0:
                        raise MaxRetriesExceededError(task_id, error_class, attempt, e) from e
                    # Non-retryable error
                    raise

                delay = self.calculate_delay(attempt, error_class)
                if on_retry:
                    on_retry(attempt, e, delay)
                sleep_fn(delay)
