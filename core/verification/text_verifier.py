"""Text content verifier."""

from __future__ import annotations

import logging
from typing import List, Optional
from core.verification.engine import VerificationOutcome, VerificationReport

logger = logging.getLogger("max.verification.text")


class TextVerifier:
    def verify_contains(
        self,
        content: str,
        expected_substring: str,
        case_sensitive: bool = False,
    ) -> VerificationReport:
        """Verifies if expected_substring is present in content."""
        haystack = content if case_sensitive else content.lower()
        needle = expected_substring if case_sensitive else expected_substring.lower()

        found = needle in haystack
        if found:
            return VerificationReport(
                outcome=VerificationOutcome.SUCCESS,
                details={"expected": expected_substring, "matched": True},
            )
        return VerificationReport(
            outcome=VerificationOutcome.FAILURE,
            details={"expected": expected_substring, "matched": False},
            errors=[f"Expected text '{expected_substring}' was not found in content."],
        )

    def verify_all_present(
        self,
        content: str,
        expected_tokens: List[str],
    ) -> VerificationReport:
        """Verifies that all specified tokens exist within the content."""
        missing = [t for t in expected_tokens if t.lower() not in content.lower()]
        if not missing:
            return VerificationReport(
                outcome=VerificationOutcome.SUCCESS,
                details={"all_tokens_found": True, "count": len(expected_tokens)},
            )
        return VerificationReport(
            outcome=VerificationOutcome.FAILURE,
            details={"missing_tokens": missing},
            errors=[f"Missing required tokens: {', '.join(missing)}"],
        )
