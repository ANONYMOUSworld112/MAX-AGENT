"""ComputerState difference verifier."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from core.verification.engine import VerificationOutcome, VerificationReport
from core.perception.state_builder import ComputerState

logger = logging.getLogger("max.verification.state_diff")


class StateDiffVerifier:
    def verify_state_transition(
        self,
        before: ComputerState,
        after: ComputerState,
        expected_window_change: Optional[bool] = None,
        expected_cursor_moved: Optional[bool] = None,
    ) -> VerificationReport:
        """Verifies if the system transitioned correctly between two ComputerStates."""
        errors = []
        details: Dict[str, Any] = {
            "before_active_window": before.active_window,
            "after_active_window": after.active_window,
            "before_cursor": before.cursor_pos,
            "after_cursor": after.cursor_pos,
        }

        window_changed = before.active_window != after.active_window
        details["window_changed"] = window_changed
        if expected_window_change is not None and window_changed != expected_window_change:
            errors.append(
                f"Window change was {window_changed}, expected {expected_window_change} "
                f"('{before.active_window}' -> '{after.active_window}')"
            )

        cursor_moved = before.cursor_pos != after.cursor_pos
        details["cursor_moved"] = cursor_moved
        if expected_cursor_moved is not None and cursor_moved != expected_cursor_moved:
            errors.append(
                f"Cursor move was {cursor_moved}, expected {expected_cursor_moved} "
                f"({before.cursor_pos} -> {after.cursor_pos})"
            )

        if errors:
            return VerificationReport(
                outcome=VerificationOutcome.FAILURE,
                details=details,
                errors=errors,
            )

        return VerificationReport(
            outcome=VerificationOutcome.SUCCESS,
            details=details,
        )
