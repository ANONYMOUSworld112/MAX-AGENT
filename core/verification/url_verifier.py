"""Browser URL verifier."""

from __future__ import annotations

import logging
from urllib.parse import urlparse
from core.verification.engine import VerificationOutcome, VerificationReport

logger = logging.getLogger("max.verification.url")


class URLVerifier:
    def verify_url_domain(self, current_url: str, expected_domain: str) -> VerificationReport:
        """Verifies if current_url belongs to the expected domain."""
        parsed = urlparse(current_url)
        domain = parsed.netloc.lower()
        if expected_domain.lower() in domain:
            return VerificationReport(
                outcome=VerificationOutcome.SUCCESS,
                details={"current_url": current_url, "domain": domain, "matched": True},
            )
        return VerificationReport(
            outcome=VerificationOutcome.FAILURE,
            details={"current_url": current_url, "expected_domain": expected_domain, "actual_domain": domain},
            errors=[f"URL domain '{domain}' does not match expected '{expected_domain}'"],
        )

    def verify_path_contains(self, current_url: str, expected_path_part: str) -> VerificationReport:
        """Verifies if URL path contains expected component."""
        parsed = urlparse(current_url)
        if expected_path_part.lower() in parsed.path.lower():
            return VerificationReport(
                outcome=VerificationOutcome.SUCCESS,
                details={"current_url": current_url, "path": parsed.path},
            )
        return VerificationReport(
            outcome=VerificationOutcome.FAILURE,
            details={"current_url": current_url, "expected_path": expected_path_part, "actual_path": parsed.path},
            errors=[f"URL path '{parsed.path}' does not contain expected '{expected_path_part}'"],
        )
