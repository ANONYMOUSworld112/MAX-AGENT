"""Process verifier: verifies process execution, PID existence, and exit codes."""

from __future__ import annotations

import logging
import psutil
from typing import Optional
from core.verification.engine import VerificationOutcome, VerificationReport

logger = logging.getLogger("max.verification.process")


class ProcessVerifier:
    def verify_process_running(self, process_name: str) -> VerificationReport:
        """Verifies if a process with process_name is actively running."""
        try:
            name_lower = process_name.lower()
            matching = [p.info["name"] for p in psutil.process_iter(["name"]) if p.info.get("name") and name_lower in p.info["name"].lower()]
            if matching:
                return VerificationReport(
                    outcome=VerificationOutcome.SUCCESS,
                    details={"process_name": process_name, "running": True, "count": len(matching)},
                )
            return VerificationReport(
                outcome=VerificationOutcome.FAILURE,
                details={"process_name": process_name, "running": False},
                errors=[f"Process '{process_name}' is not running."],
            )
        except Exception as exc:
            return VerificationReport(
                outcome=VerificationOutcome.UNKNOWN,
                details={"process_name": process_name, "error": str(exc)},
                errors=[str(exc)],
            )

    def verify_exit_code(self, exit_code: Optional[int], expected_code: int = 0) -> VerificationReport:
        """Verifies process termination status."""
        if exit_code is None:
            return VerificationReport(
                outcome=VerificationOutcome.UNKNOWN,
                details={"exit_code": None, "reason": "Process did not return an exit code."},
                errors=["Exit code unavailable"],
            )
        if exit_code == expected_code:
            return VerificationReport(
                outcome=VerificationOutcome.SUCCESS,
                details={"exit_code": exit_code, "expected": expected_code},
            )
        return VerificationReport(
            outcome=VerificationOutcome.FAILURE,
            details={"exit_code": exit_code, "expected": expected_code},
            errors=[f"Process exited with code {exit_code}, expected {expected_code}"],
        )
