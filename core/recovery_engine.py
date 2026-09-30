"""
MAX Recovery Engine & Self-Correction (Tasks 8.2 & 8.3)
======================================================

Implements deterministic error classification, bounded retry with backoff,
safe rollback to pre-task git checkpoints, and a structured self-correction
loop with hard iteration and wall-clock budget limits.

Master Spec References:
  - Section 14 (Verification & Self-Correction)
  - Section 15 (Failure Recovery, Error Classes)
  - docs/audit/FAILURE_RECOVERY.md
"""

from __future__ import annotations

import logging
import random
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from core.contracts import ErrorClass, IdempotencyClass, VerificationOutcome
from core.process_manager import ProcessManager
from core.verification.engine import VerificationReport

logger = logging.getLogger("max.recovery")


# ---------------------------------------------------------------------------
# Error Classification (Task 8.2)
# ---------------------------------------------------------------------------

_TRANSIENT_PATTERNS = [
    re.compile(r"(?i)\b(?:timeout|timed out|temporary|connection reset|connection refused|econnreset)\b"),
    re.compile(r"(?i)\b(?:429|502|503|504|too many requests|rate limit|busy|deadlock)\b"),
]

_ENVIRONMENT_PATTERNS = [
    re.compile(r"(?i)\b(?:not found|no such file|command not found|cannot find|executable not found)\b"),
    re.compile(r"(?i)\b(?:permission denied|access is denied|eacces|eperm)\b"),
    re.compile(r"(?i)\b(?:modulenotfounderror|importerror)\b"),
]

_LOGIC_PATTERNS = [
    re.compile(r"(?i)\b(?:syntaxerror|indentationerror|typeerror|valueerror|indexerror|keyerror|attributeerror)\b"),
    re.compile(r"(?i)\b(?:assertionerror|assertion failed|test failed|compilation failed|build failed)\b"),
]

_RESOURCE_PATTERNS = [
    re.compile(r"(?i)\b(?:disk full|no space left on device|enospc|out of memory|oom|vram exhausted)\b"),
]

_EXTERNAL_PATTERNS = [
    re.compile(r"(?i)\b(?:401|403|unauthorized|forbidden|invalid api key|quota exceeded)\b"),
]


def classify_error(error: Union[Exception, str, Dict[str, Any]]) -> ErrorClass:
    """
    Deterministically classifies exceptions or error messages into ErrorClass categories.
    """
    if isinstance(error, Exception):
        msg = f"{type(error).__name__}: {str(error)}"
    elif isinstance(error, dict):
        msg = str(error.get("error") or error.get("message") or error)
    else:
        msg = str(error)

    # 1. Resource check
    for pat in _RESOURCE_PATTERNS:
        if pat.search(msg):
            return ErrorClass.RESOURCE

    # 2. External auth/quota check
    for pat in _EXTERNAL_PATTERNS:
        if pat.search(msg):
            return ErrorClass.EXTERNAL

    # 3. Environment check
    for pat in _ENVIRONMENT_PATTERNS:
        if pat.search(msg):
            return ErrorClass.ENVIRONMENT

    # 4. Logic check
    for pat in _LOGIC_PATTERNS:
        if pat.search(msg):
            return ErrorClass.LOGIC

    # 5. Transient check
    for pat in _TRANSIENT_PATTERNS:
        if pat.search(msg):
            return ErrorClass.TRANSIENT

    # Default fallback
    return ErrorClass.LOGIC


def calculate_backoff(
    retry_count: int,
    base_delay: float = 0.5,
    max_delay: float = 8.0,
    jitter: bool = False,
) -> float:
    """
    Computes exponential backoff with optional jitter: base * 2^(retry - 1).
    """
    if retry_count <= 0:
        return 0.0
    delay = min(max_delay, base_delay * (2 ** (retry_count - 1)))
    if jitter:
        delay += random.uniform(0, 0.1 * delay)
    return delay


# ---------------------------------------------------------------------------
# Git Checkpoint Rollback
# ---------------------------------------------------------------------------

def rollback_git_checkpoint(
    worktree_path: str,
    checkpoint_commit: Optional[str] = None,
    pm: Optional[ProcessManager] = None,
) -> bool:
    """
    Restores a git worktree to clean state or specific checkpoint commit.
    Uses ProcessManager to avoid unchoked subprocess calls.
    """
    mgr = pm or ProcessManager()
    try:
        if checkpoint_commit:
            res_reset = mgr.run_command(
                ["git", "reset", "--hard", checkpoint_commit],
                cwd=worktree_path,
                timeout=10.0,
            )
            if not res_reset.success:
                logger.error("Git reset to checkpoint %s failed: %s", checkpoint_commit, res_reset.stderr)
                return False
        else:
            res_checkout = mgr.run_command(
                ["git", "checkout", "--", "."],
                cwd=worktree_path,
                timeout=10.0,
            )
            if not res_checkout.success:
                logger.error("Git checkout failed: %s", res_checkout.stderr)
                return False

        res_clean = mgr.run_command(
            ["git", "clean", "-fd"],
            cwd=worktree_path,
            timeout=10.0,
        )
        return res_clean.success
    except Exception as exc:
        logger.error("Exception during git rollback: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Self-Correction Loop (Task 8.3)
# ---------------------------------------------------------------------------

class CorrectionStrategy(str, Enum):
    FIX_DIRECT_ERROR = "FIX_DIRECT_ERROR"
    ALTERNATIVE_APPROACH = "ALTERNATIVE_APPROACH"
    ESCALATE_TO_USER = "ESCALATE_TO_USER"


@dataclass
class FailureCritique:
    iteration: int
    error_class: ErrorClass
    error_summary: str
    suggested_strategy: CorrectionStrategy
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SelfCorrectionResult:
    success: bool
    iterations_used: int
    duration_ms: float
    final_report: Optional[VerificationReport] = None
    rolled_back: bool = False
    critiques: List[FailureCritique] = field(default_factory=list)


class RecoveryEngine:
    """
    Coordinates failure recovery, bounded retries, and self-correction loops.
    """

    def __init__(
        self,
        max_retries: int = 3,
        max_correction_iterations: int = 3,
        wall_clock_timeout_seconds: float = 60.0,
        process_manager: Optional[ProcessManager] = None,
    ) -> None:
        self.max_retries = max_retries
        self.max_correction_iterations = max_correction_iterations
        self.wall_clock_timeout_seconds = wall_clock_timeout_seconds
        self.pm = process_manager or ProcessManager()

    def should_retry(
        self,
        error_class: ErrorClass,
        idempotency: IdempotencyClass,
        current_retries: int,
    ) -> Tuple[bool, float]:
        """
        Determines if an action is eligible for automated retry and returns delay.
        """
        if current_retries >= self.max_retries:
            return False, 0.0

        if error_class != ErrorClass.TRANSIENT:
            return False, 0.0

        if idempotency not in (IdempotencyClass.IDEMPOTENT, IdempotencyClass.CONDITIONALLY_IDEMPOTENT):
            return False, 0.0

        delay = calculate_backoff(current_retries + 1)
        return True, delay

    def run_self_correction_loop(
        self,
        worker_fn: Callable[[FailureCritique], VerificationReport],
        initial_error: Union[Exception, str, Dict[str, Any]],
        worktree_path: Optional[str] = None,
        checkpoint_commit: Optional[str] = None,
    ) -> SelfCorrectionResult:
        """
        Executes bounded self-correction loop:
        Critique -> Worker Re-attempt -> Verify -> Repeat until success or budget exhausted.
        """
        start_t = time.monotonic()
        critiques: List[FailureCritique] = []
        last_error_text = str(initial_error)
        last_report: Optional[VerificationReport] = None

        for iteration in range(1, self.max_correction_iterations + 1):
            elapsed = time.monotonic() - start_t
            if elapsed >= self.wall_clock_timeout_seconds:
                logger.warning("Self-correction timed out after %.2fs", elapsed)
                break

            err_cls = classify_error(last_error_text)

            # Strategy formulation
            if iteration == 1:
                strategy = CorrectionStrategy.FIX_DIRECT_ERROR
            elif len(critiques) >= 1 and critiques[-1].error_summary == last_error_text[:200]:
                # Same error repeated twice in a row: switch to alternative approach
                strategy = CorrectionStrategy.ALTERNATIVE_APPROACH
            else:
                strategy = CorrectionStrategy.FIX_DIRECT_ERROR

            critique = FailureCritique(
                iteration=iteration,
                error_class=err_cls,
                error_summary=last_error_text[:200],
                suggested_strategy=strategy,
            )
            critiques.append(critique)

            try:
                report = worker_fn(critique)
                last_report = report
                if report.outcome == VerificationOutcome.SUCCESS:
                    total_dur = (time.monotonic() - start_t) * 1000.0
                    return SelfCorrectionResult(
                        success=True,
                        iterations_used=iteration,
                        duration_ms=total_dur,
                        final_report=report,
                        rolled_back=False,
                        critiques=critiques,
                    )
                # Next error summary from report errors
                last_error_text = "; ".join(report.errors) if report.errors else "Verification check failed"
            except Exception as exc:
                last_error_text = str(exc)

        # Budget exhausted or timed out: Roll back git worktree if path was provided
        rolled_back = False
        if worktree_path:
            logger.info("Self-correction budget exhausted. Rolling back worktree at %s", worktree_path)
            rolled_back = rollback_git_checkpoint(worktree_path, checkpoint_commit, pm=self.pm)

        total_dur = (time.monotonic() - start_t) * 1000.0
        return SelfCorrectionResult(
            success=False,
            iterations_used=len(critiques),
            duration_ms=total_dur,
            final_report=last_report,
            rolled_back=rolled_back,
            critiques=critiques,
        )
