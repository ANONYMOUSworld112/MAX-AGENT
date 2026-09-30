"""
Unit tests for Self-Correction Loop & Budget Enforcement (Task 8.3)
===================================================================

Covers:
- Successful convergence on iteration 2 (simulating test/syntax fix)
- Alternative approach trigger on repeated identical failure
- Hard iteration budget enforcement with escalation and rollback
- Wall-clock timeout enforcement
"""

import time
import pytest

from core.contracts import ErrorClass, VerificationOutcome
from core.recovery_engine import (
    CorrectionStrategy,
    FailureCritique,
    RecoveryEngine,
    SelfCorrectionResult,
)
from core.verification.engine import VerificationReport


def test_self_correction_converges_on_second_iteration():
    engine = RecoveryEngine(max_correction_iterations=3)

    attempts = 0

    def mock_worker(critique: FailureCritique) -> VerificationReport:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            assert critique.iteration == 1
            assert critique.suggested_strategy == CorrectionStrategy.FIX_DIRECT_ERROR
            return VerificationReport(
                outcome=VerificationOutcome.FAILURE,
                errors=["SyntaxError: invalid syntax on line 4"],
            )
        # Attempt 2 succeeds
        return VerificationReport(outcome=VerificationOutcome.SUCCESS)

    res = engine.run_self_correction_loop(
        worker_fn=mock_worker,
        initial_error="SyntaxError: unexpected token",
    )

    assert res.success is True
    assert res.iterations_used == 2
    assert res.rolled_back is False
    assert len(res.critiques) == 2


def test_self_correction_triggers_alternative_approach_on_repeated_error():
    engine = RecoveryEngine(max_correction_iterations=3)

    def mock_worker(critique: FailureCritique) -> VerificationReport:
        # Returns the EXACT same error on every iteration
        return VerificationReport(
            outcome=VerificationOutcome.FAILURE,
            errors=["AssertionError: expected 10 but got 0"],
        )

    res = engine.run_self_correction_loop(
        worker_fn=mock_worker,
        initial_error="AssertionError: expected 10 but got 0",
    )

    assert res.success is False
    assert res.iterations_used == 3
    # Check that second critique switched to ALTERNATIVE_APPROACH
    assert res.critiques[0].suggested_strategy == CorrectionStrategy.FIX_DIRECT_ERROR
    assert res.critiques[1].suggested_strategy == CorrectionStrategy.ALTERNATIVE_APPROACH


def test_self_correction_timeout_budget():
    # Wall clock timeout of 0.15s
    engine = RecoveryEngine(
        max_correction_iterations=5,
        wall_clock_timeout_seconds=0.15,
    )

    def slow_worker(critique: FailureCritique) -> VerificationReport:
        time.sleep(0.1)
        return VerificationReport(
            outcome=VerificationOutcome.FAILURE,
            errors=["Slow compilation failed"],
        )

    res = engine.run_self_correction_loop(
        worker_fn=slow_worker,
        initial_error="Compilation error",
    )

    assert res.success is False
    # Stopped before completing all 5 iterations due to timeout
    assert res.iterations_used <= 2
