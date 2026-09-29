"""UI element state verifier."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from core.verification.engine import VerificationOutcome, VerificationReport

logger = logging.getLogger("max.verification.element")


class ElementVerifier:
    def verify_element_state(
        self,
        element_data: Dict[str, Any],
        expected_enabled: Optional[bool] = None,
        expected_text: Optional[str] = None,
    ) -> VerificationReport:
        """Verifies state properties of a UI element dictionary."""
        errors = []
        details = dict(element_data)

        if expected_enabled is not None:
            actual_enabled = element_data.get("is_enabled", True)
            if actual_enabled != expected_enabled:
                errors.append(f"Element enabled state was {actual_enabled}, expected {expected_enabled}")

        if expected_text is not None:
            actual_text = element_data.get("text", "") or element_data.get("name", "")
            if expected_text.lower() not in actual_text.lower():
                errors.append(f"Element text '{actual_text}' did not contain expected '{expected_text}'")

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
