"""
MAX OS — Error Taxonomy
Build Order: #6 (Layer 2A)
═══════════════════════════════════════════════════════

5-class error classification. Only transient and systemic ever retry.
Validation fails immediately. Permission refuses immediately.
Destructive risk escalates to a gate.

Design: ADR-007 in decisions.md
Source: MAX_OS_v3_Synchronized_Pipeline.md §4
Gate:   classify() returns correct class for each error type
"""

from __future__ import annotations

import re
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("max.infra.errors")


class ErrorClass(str, Enum):
    """Five error classes — each gets different handling."""
    TRANSIENT = "transient"             # Network timeout, API rate limit → retry
    VALIDATION = "validation"           # Bad input, file not found → fail immediately
    PERMISSION = "permission"           # Blocked-tier action → refuse immediately
    DESTRUCTIVE_RISK = "destructive_risk"  # Needs confirmation gate → escalate
    SYSTEMIC = "systemic"               # Agent crash, reconciliation mismatch → circuit breaker


# Retry policy per error class
RETRY_POLICY = {
    ErrorClass.TRANSIENT: {"retryable": True, "max_retries": 3},
    ErrorClass.VALIDATION: {"retryable": False, "max_retries": 0},
    ErrorClass.PERMISSION: {"retryable": False, "max_retries": 0},
    ErrorClass.DESTRUCTIVE_RISK: {"retryable": False, "max_retries": 0},
    ErrorClass.SYSTEMIC: {"retryable": True, "max_retries": 2},
}


@dataclass
class MaxError:
    """Structured error with classification, context, and recovery info."""
    error_class: ErrorClass
    code: str                            # e.g. 'FILE_NOT_FOUND', 'API_TIMEOUT'
    message: str                         # human-readable
    operation: str = ""                  # what was being attempted
    retryable: bool = False
    recovery_suggestion: str = ""
    rollback_available: bool = False
    original_exception: Optional[Exception] = None
    context: dict = field(default_factory=dict)
    
    def __str__(self) -> str:
        return f"[{self.error_class.value}:{self.code}] {self.message}"
    
    @property
    def retry_policy(self) -> dict:
        return RETRY_POLICY[self.error_class]


# ── Custom Exception Classes ──────────────────────────────────

class MaxBaseError(Exception):
    """Base exception for all MAX OS errors."""
    def __init__(self, error: MaxError):
        self.error = error
        super().__init__(str(error))


class TransientError(MaxBaseError):
    """Retryable transient errors (network, API rate limit)."""
    pass


class ValidationError(MaxBaseError):
    """Non-retryable input/data errors."""
    pass


class PermissionError_(MaxBaseError):
    """Non-retryable permission violations. Underscore avoids shadowing builtin."""
    pass


class DestructiveRiskError(MaxBaseError):
    """Requires escalation to confirmation gate."""
    pass


class SystemicError(MaxBaseError):
    """Agent crash, reconciliation mismatch — circuit breaker territory."""
    pass


# Map error class to exception class
_EXCEPTION_MAP = {
    ErrorClass.TRANSIENT: TransientError,
    ErrorClass.VALIDATION: ValidationError,
    ErrorClass.PERMISSION: PermissionError_,
    ErrorClass.DESTRUCTIVE_RISK: DestructiveRiskError,
    ErrorClass.SYSTEMIC: SystemicError,
}


def raise_error(error: MaxError) -> None:
    """Raise the appropriate typed exception for a MaxError."""
    exc_class = _EXCEPTION_MAP.get(error.error_class, MaxBaseError)
    raise exc_class(error)


# ── Classification Engine ─────────────────────────────────────

# Patterns for automatic classification
_TRANSIENT_PATTERNS = [
    re.compile(r"timeout", re.I),
    re.compile(r"rate.?limit", re.I),
    re.compile(r"connection.?(refused|reset|error)", re.I),
    re.compile(r"(502|503|504|429)", re.I),
    re.compile(r"temporary", re.I),
    re.compile(r"retry", re.I),
    re.compile(r"ECONNRESET", re.I),
    re.compile(r"ETIMEDOUT", re.I),
]

_VALIDATION_PATTERNS = [
    re.compile(r"(file|path|directory).*(not found|doesn.t exist|missing)", re.I),
    re.compile(r"invalid.*(input|argument|parameter|format|type)", re.I),
    re.compile(r"(required|missing).*(field|param|argument)", re.I),
    re.compile(r"(cannot|can.t).*(parse|decode|deserialize)", re.I),
    re.compile(r"schema.*(validation|error)", re.I),
    re.compile(r"(malformed|corrupt)", re.I),
]

_PERMISSION_PATTERNS = [
    re.compile(r"(permission|access).*(denied|forbidden|blocked)", re.I),
    re.compile(r"(401|403)", re.I),
    re.compile(r"unauthorized", re.I),
    re.compile(r"blocked.*(by|per).*(policy|tier|security)", re.I),
    re.compile(r"insufficient.*(privilege|permission)", re.I),
]

_DESTRUCTIVE_PATTERNS = [
    re.compile(r"(delete|remove|wipe|destroy|drop).*(all|recursive|database|table)", re.I),
    re.compile(r"(format|overwrite).*(disk|drive|partition)", re.I),
    re.compile(r"(shutdown|reboot|restart).*(system|server|machine)", re.I),
    re.compile(r"(disable|stop).*(firewall|security|antivirus)", re.I),
]


def classify(
    exception: Exception,
    operation: str = "",
    context: dict = None,
) -> MaxError:
    """
    Classify an exception into one of the 5 error classes.
    
    Classification priority:
    1. Known exception types (explicit classification)
    2. Message pattern matching
    3. Default to SYSTEMIC (safest default — triggers circuit breaker)
    
    Returns:
        MaxError with classification, retry policy, and recovery suggestion
    """
    msg = str(exception)
    ctx = context or {}
    
    # ── Already classified ────────────────────────────────
    if isinstance(exception, MaxBaseError):
        return exception.error
    
    # ── Known Python exceptions ───────────────────────────
    if isinstance(exception, FileNotFoundError):
        return MaxError(
            error_class=ErrorClass.VALIDATION,
            code="FILE_NOT_FOUND",
            message=msg,
            operation=operation,
            recovery_suggestion="Check the file path and try again.",
            original_exception=exception,
            context=ctx,
        )
    
    if isinstance(exception, PermissionError):
        return MaxError(
            error_class=ErrorClass.PERMISSION,
            code="OS_PERMISSION_DENIED",
            message=msg,
            operation=operation,
            recovery_suggestion="Run with appropriate permissions or check file ownership.",
            original_exception=exception,
            context=ctx,
        )
    
    if isinstance(exception, (TimeoutError, ConnectionError)):
        return MaxError(
            error_class=ErrorClass.TRANSIENT,
            code="CONNECTION_ERROR",
            message=msg,
            operation=operation,
            retryable=True,
            recovery_suggestion="Check network connectivity and retry.",
            original_exception=exception,
            context=ctx,
        )
    
    if isinstance(exception, (ValueError, TypeError, KeyError)):
        return MaxError(
            error_class=ErrorClass.VALIDATION,
            code="INVALID_INPUT",
            message=msg,
            operation=operation,
            recovery_suggestion="Check the input format and types.",
            original_exception=exception,
            context=ctx,
        )
    
    # ── Pattern matching on message ───────────────────────
    for pattern in _TRANSIENT_PATTERNS:
        if pattern.search(msg):
            return MaxError(
                error_class=ErrorClass.TRANSIENT,
                code="TRANSIENT_PATTERN_MATCH",
                message=msg,
                operation=operation,
                retryable=True,
                original_exception=exception,
                context=ctx,
            )
    
    for pattern in _PERMISSION_PATTERNS:
        if pattern.search(msg):
            return MaxError(
                error_class=ErrorClass.PERMISSION,
                code="PERMISSION_PATTERN_MATCH",
                message=msg,
                operation=operation,
                original_exception=exception,
                context=ctx,
            )
    
    for pattern in _VALIDATION_PATTERNS:
        if pattern.search(msg):
            return MaxError(
                error_class=ErrorClass.VALIDATION,
                code="VALIDATION_PATTERN_MATCH",
                message=msg,
                operation=operation,
                original_exception=exception,
                context=ctx,
            )
    
    for pattern in _DESTRUCTIVE_PATTERNS:
        if pattern.search(msg):
            return MaxError(
                error_class=ErrorClass.DESTRUCTIVE_RISK,
                code="DESTRUCTIVE_PATTERN_MATCH",
                message=msg,
                operation=operation,
                original_exception=exception,
                context=ctx,
            )
    
    # ── Default: SYSTEMIC (safest — triggers circuit breaker) ─
    logger.warning("Unclassified error defaulting to SYSTEMIC: %s", msg)
    return MaxError(
        error_class=ErrorClass.SYSTEMIC,
        code="UNCLASSIFIED",
        message=msg,
        operation=operation,
        retryable=True,
        recovery_suggestion="Unexpected error — investigation needed.",
        original_exception=exception,
        context=ctx,
    )
