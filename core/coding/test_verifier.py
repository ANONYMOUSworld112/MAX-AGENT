"""
Independent Test Verification Engine
=====================================

Independently runs tests and verifies exit codes, assertion counts,
and failure patterns. Enforces the Claude-style verification principle:
never trust worker self-reports of success.

Master Spec references:
  - Section 14 (VerificationEngine)
  - docs/evolution/CLAUDE_STYLE_COMPARISON.md
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

from core.adapters import git_adapter

logger = logging.getLogger("max.coding.test_verifier")


@dataclass(frozen=True)
class TestReport:
    """Summary of a test execution run."""
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    total: int = 0
    duration_seconds: float = 0.0
    exit_code: int = 0
    raw_output: str = ""

    @property
    def is_success(self) -> bool:
        return self.exit_code == 0 and self.failed == 0 and self.errors == 0 and self.passed > 0


class TestWeakeningError(RuntimeError):
    """Raised when an agent weakens a test suite by deleting or commenting out tests."""
    pass


class TestVerifier:
    """Independent validator of test execution results."""

    @classmethod
    def parse_pytest_output(cls, output: str, exit_code: int) -> TestReport:
        """Parse pytest summary lines to extract pass/fail/skip counts."""
        passed = 0
        failed = 0
        skipped = 0
        errors = 0
        duration = 0.0

        # Pattern: "= 15 passed, 2 failed, 1 skipped in 1.23s ="
        m_passed = re.search(r"(\d+)\s+passed", output)
        if m_passed:
            passed = int(m_passed.group(1))

        m_failed = re.search(r"(\d+)\s+failed", output)
        if m_failed:
            failed = int(m_failed.group(1))

        m_skipped = re.search(r"(\d+)\s+skipped", output)
        if m_skipped:
            skipped = int(m_skipped.group(1))

        m_errors = re.search(r"(\d+)\s+error", output)
        if m_errors:
            errors = int(m_errors.group(1))

        m_time = re.search(r"in\s+([\d\.]+)\s*s", output)
        if m_time:
            duration = float(m_time.group(1))

        total = passed + failed + skipped + errors

        return TestReport(
            passed=passed,
            failed=failed,
            skipped=skipped,
            errors=errors,
            total=total,
            duration_seconds=duration,
            exit_code=exit_code,
            raw_output=output,
        )

    def run_and_verify(
        self,
        worktree_path: Path | str,
        test_command: str = "pytest",
        baseline_report: Optional[TestReport] = None,
        timeout: float = 60.0,
    ) -> Tuple[bool, TestReport, List[str]]:
        """Run tests inside worktree and independently evaluate outcome against baseline."""
        exit_code, stdout, stderr = git_adapter.run_sandboxed_command(
            cmd=test_command,
            cwd=str(worktree_path),
            timeout=timeout,
        )

        combined_output = stdout + "\n" + stderr
        current_report = self.parse_pytest_output(combined_output, exit_code)
        violations: List[str] = []

        if current_report.exit_code != 0:
            violations.append(f"Test command exited with non-zero status ({current_report.exit_code})")
        if current_report.failed > 0:
            violations.append(f"Test suite had {current_report.failed} failing tests")
        if current_report.errors > 0:
            violations.append(f"Test suite had {current_report.errors} collection or runtime errors")

        # Weakening detection against baseline
        if baseline_report:
            if current_report.passed < baseline_report.passed:
                violations.append(
                    f"Test weakening detected: passed count decreased from {baseline_report.passed} to {current_report.passed}"
                )
            if current_report.total < baseline_report.total:
                violations.append(
                    f"Test count decreased from {baseline_report.total} to {current_report.total}"
                )

        is_valid = len(violations) == 0 and current_report.is_success
        return is_valid, current_report, violations
