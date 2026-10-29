"""
Central Verification Engine (Task 8.1)
=====================================

Multi-tier verification system aggregating deterministic before/after
verification checks across processes, files, windows, and active probes.

Verification Levels (Master Spec Section 14):
  - L0_EXECUTION:   Action completed without unhandled exceptions.
  - L1_OBSERVATION: Target entity exists (process running, file on disk, window created).
  - L2_SEMANTIC:    Target state matches contract (file contents, window title, UIA property).
  - L3_PROBE:       Functional verification (independent test pass, network probe, health check).

Rule 1-H1: UNKNOWN is NEVER treated as SUCCESS.
"""

from __future__ import annotations

import enum
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Union

from core.contracts import ActionRequest, VerificationOutcome

logger = logging.getLogger("max.verification.engine")


class VerificationLevel(enum.IntEnum):
    """Hierarchical verification assurance levels."""
    L0_EXECUTION = 0
    L1_OBSERVATION = 1
    L2_SEMANTIC = 2
    L3_PROBE = 3


@dataclass
class VerificationReport:
    """Detailed audit report of a verification evaluation."""
    outcome: VerificationOutcome
    level: VerificationLevel = VerificationLevel.L0_EXECUTION
    details: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    @property
    def is_verified(self) -> bool:
        return self.outcome == VerificationOutcome.SUCCESS


def poll_until(
    check_fn: Callable[[], VerificationReport],
    timeout: float = 3.0,
    interval: float = 0.2,
) -> VerificationReport:
    """
    Polls check_fn until it returns a SUCCESS report or timeout expires.
    Eliminates race conditions with slow-spawning UI and processes.
    """
    deadline = time.monotonic() + timeout
    last_report: Optional[VerificationReport] = None

    while time.monotonic() < deadline:
        try:
            report = check_fn()
            last_report = report
            if report.outcome == VerificationOutcome.SUCCESS:
                return report
        except Exception as exc:
            last_report = VerificationReport(
                outcome=VerificationOutcome.UNKNOWN,
                details={"error": str(exc)},
                errors=[str(exc)],
            )
        time.sleep(interval)

    # If timeout expired without SUCCESS:
    if last_report and last_report.outcome == VerificationOutcome.FAILURE:
        return last_report

    return VerificationReport(
        outcome=VerificationOutcome.FAILURE,
        level=last_report.level if last_report else VerificationLevel.L1_OBSERVATION,
        details={
            "timeout_seconds": timeout,
            "last_details": last_report.details if last_report else {},
        },
        errors=[f"Verification timed out after {timeout:.1f}s without reaching SUCCESS"],
    )


class VerificationEngine:
    """
    Engine coordinating multi-level verification of executed actions.
    """

    def __init__(
        self,
        file_verifier: Any = None,
        process_verifier: Any = None,
        window_verifier: Any = None,
        element_verifier: Any = None,
    ) -> None:
        self._file_verifier = file_verifier
        self._process_verifier = process_verifier
        self._window_verifier = window_verifier
        self._element_verifier = element_verifier

    @property
    def file_verifier(self):
        if self._file_verifier is None:
            from core.verification.file_verifier import FileVerifier
            self._file_verifier = FileVerifier()
        return self._file_verifier

    @property
    def process_verifier(self):
        if self._process_verifier is None:
            from core.verification.process_verifier import ProcessVerifier
            self._process_verifier = ProcessVerifier()
        return self._process_verifier

    @property
    def window_verifier(self):
        if self._window_verifier is None:
            from core.verification.window_verifier import WindowVerifier
            self._window_verifier = WindowVerifier()
        return self._window_verifier

    @property
    def element_verifier(self):
        if self._element_verifier is None:
            from core.verification.element_verifier import ElementVerifier
            self._element_verifier = ElementVerifier()
        return self._element_verifier

    def evaluate(self, reports: List[VerificationReport]) -> VerificationReport:
        """Aggregates multiple verification reports into a unified verdict."""
        if not reports:
            return VerificationReport(
                outcome=VerificationOutcome.UNKNOWN,
                details={"reason": "No verification checks provided"},
            )

        all_details: Dict[str, Any] = {}
        all_errors: List[str] = []
        max_level = max(r.level for r in reports)

        for idx, rep in enumerate(reports):
            all_details[f"check_{idx}"] = rep.details
            all_errors.extend(rep.errors)

        if any(rep.outcome == VerificationOutcome.FAILURE for rep in reports):
            return VerificationReport(
                outcome=VerificationOutcome.FAILURE,
                level=max_level,
                details=all_details,
                errors=all_errors,
            )

        if any(rep.outcome == VerificationOutcome.UNKNOWN for rep in reports):
            return VerificationReport(
                outcome=VerificationOutcome.UNKNOWN,
                level=max_level,
                details=all_details,
                errors=all_errors,
            )

        return VerificationReport(
            outcome=VerificationOutcome.SUCCESS,
            level=max_level,
            details=all_details,
            errors=[],
        )

    def verify_action(self, request: ActionRequest, output: Any) -> VerificationReport:
        """
        Evaluates an action execution and produces an evidence-backed verification report.
        """
        params = request.parameters or {}
        action = request.action.lower()

        # 1. Check for explicit verification spec in request parameters
        if "verify_file" in params:
            file_path = params["verify_file"]
            if "verify_content" in params:
                return self.file_verifier.verify_file_content(file_path, params["verify_content"])
            return self.file_verifier.verify_files_exist([file_path])

        if "verify_process" in params:
            proc_name = params["verify_process"]
            timeout = float(params.get("verify_timeout", 2.0))
            return poll_until(
                lambda: self.process_verifier.verify_process_running(proc_name),
                timeout=timeout,
            )

        if "verify_window" in params:
            win_title = params["verify_window"]
            timeout = float(params.get("verify_timeout", 2.0))
            return poll_until(
                lambda: self.window_verifier.verify_window_open(win_title),
                timeout=timeout,
            )

        # 2. If output already contains verification details from adapter/handler
        if isinstance(output, dict):
            if output.get("verified") is True:
                return VerificationReport(
                    outcome=VerificationOutcome.SUCCESS,
                    level=VerificationLevel.L2_SEMANTIC,
                    details=output,
                )
            if output.get("verified") is False:
                return VerificationReport(
                    outcome=VerificationOutcome.FAILURE,
                    level=VerificationLevel.L2_SEMANTIC,
                    details=output,
                    errors=[output.get("error", "Action marked unverified by handler")],
                )
            if output.get("error"):
                return VerificationReport(
                    outcome=VerificationOutcome.FAILURE,
                    level=VerificationLevel.L0_EXECUTION,
                    details={"output": output},
                    errors=[str(output.get("error"))],
                )

        # 3. If the request explicitly requested verification
        if params.get("verify") is True:
            if action in ("launch_app", "open_app"):
                app_name = params.get("app_name") or params.get("name")
                if app_name:
                    timeout = float(params.get("verify_timeout", 2.0))
                    return poll_until(
                        lambda: self.process_verifier.verify_process_running(app_name),
                        timeout=timeout,
                    )
            if action in ("file_write", "create_file", "write_file"):
                path = params.get("path") or params.get("file_path")
                if path:
                    content = params.get("content")
                    if content and isinstance(content, str):
                        snippet = content[:64] if len(content) > 64 else content
                        return self.file_verifier.verify_file_content(path, snippet)
                    return self.file_verifier.verify_files_exist([path])

        if action in ("run_command", "exec_command", "run_test"):
            # Check exit code in output if present
            if isinstance(output, dict) and "exit_code" in output:
                return self.process_verifier.verify_exit_code(output["exit_code"], expected_code=0)

        # 4. Default L0 Verification (Execution completed without error)
        return VerificationReport(
            outcome=VerificationOutcome.SUCCESS,
            level=VerificationLevel.L0_EXECUTION,
            details={"action": request.action, "status": "executed_without_error"},
        )
