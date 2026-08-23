"""
MAX OS — Error Taxonomy & Classification (Step 4.1).
Principle #7: Classify every error before handling it:
  - TRANSIENT: network timeouts, 429 rate limits, 503 service errors (retryable).
  - VALIDATION: syntax errors, bad formats, invalid arguments (non-retryable).
  - PERMISSION: gate required, missing approval token (ask user).
  - DESTRUCTIVE_RISK: data wipe, dangerous command (refuse or require hard gate).
  - SYSTEMIC: kill switch halt, lock timeout, disk failure (bounded restart / DLQ).
"""

from __future__ import annotations

import enum
import re
from typing import Any, Optional


class ErrorClass(str, enum.Enum):
    TRANSIENT = "transient"
    VALIDATION = "validation"
    PERMISSION = "permission"
    DESTRUCTIVE_RISK = "destructive_risk"
    SYSTEMIC = "systemic"


class MAXBaseError(Exception):
    """Base error for all MAX OS errors with taxonomy classification."""
    def __init__(
        self,
        message: str,
        error_class: ErrorClass = ErrorClass.SYSTEMIC,
        details: Optional[str] = None,
        retryable: bool = False,
    ):
        super().__init__(message)
        self.message = message
        self.error_class = error_class
        self.details = details or message
        self.retryable = retryable


class TransientError(MAXBaseError):
    def __init__(self, message: str, details: Optional[str] = None):
        super().__init__(message, ErrorClass.TRANSIENT, details, retryable=True)


class ValidationError(MAXBaseError):
    def __init__(self, message: str, details: Optional[str] = None):
        super().__init__(message, ErrorClass.VALIDATION, details, retryable=False)


class PermissionDeniedError(MAXBaseError):
    def __init__(self, message: str, details: Optional[str] = None):
        super().__init__(message, ErrorClass.PERMISSION, details, retryable=False)


# Alias for permission confirmation gates
GateRequiredError = PermissionDeniedError


class DestructiveRiskError(MAXBaseError):
    def __init__(self, message: str, details: Optional[str] = None):
        super().__init__(message, ErrorClass.DESTRUCTIVE_RISK, details, retryable=False)


class SystemicError(MAXBaseError):
    def __init__(self, message: str, details: Optional[str] = None):
        super().__init__(message, ErrorClass.SYSTEMIC, details, retryable=True)


# Classification heuristic for unhandled or 3rd-party exceptions
def classify_error(exc: Exception | str) -> ErrorClass:
    """
    Classifies any exception into the 5 MAX error classes before handling runs.
    """
    if isinstance(exc, MAXBaseError):
        return exc.error_class

    cls_name = exc.__class__.__name__.lower() if isinstance(exc, Exception) else ""
    msg = (f"{cls_name} {str(exc)}").lower()

    # Permission patterns
    if any(k in msg for k in ("permission", "approval token", "gate required", "unauthorized", "forbidden", "access denied", "blocked")):
        return ErrorClass.PERMISSION

    # Destructive risk patterns
    if any(k in msg for k in ("drop database", "rm -rf", "delete all", "destructive", "wipe table", "truncate")):
        return ErrorClass.DESTRUCTIVE_RISK

    # Validation patterns
    if any(k in msg for k in ("syntaxerror", "validation", "invalid argument", "missing required", "typeerror", "valueerror", "parse error", "malformed", "syntax")):
        return ErrorClass.VALIDATION

    # Transient patterns
    if any(k in msg for k in ("timeout", "timed out", "connection reset", "connection refused", "429", "503", "502", "504", "rate limit", "econnreset")):
        return ErrorClass.TRANSIENT

    # Systemic patterns
    if any(k in msg for k in ("kill switch", "deadlock", "disk full", "out of memory", "systemic", "oserror", "memoryerror")):
        return ErrorClass.SYSTEMIC

    return ErrorClass.SYSTEMIC
