"""Window state verifier: title, focus, and presence."""

from __future__ import annotations

import logging
from typing import Optional
from core.verification.engine import VerificationOutcome, VerificationReport

logger = logging.getLogger("max.verification.window")


class WindowVerifier:
    def verify(self, expected_title: str) -> VerificationReport:
        return self.verify_window_present(expected_title)

    def verify_window_present(self, expected_title_substring: str) -> VerificationReport:
        """Verifies if a window containing expected_title_substring exists."""
        try:
            import pywinauto
            desktop = pywinauto.Desktop(backend="uia")
            windows = desktop.windows()
            titles = [w.window_text() for w in windows]
            found = any(expected_title_substring.lower() in t.lower() for t in titles)
            if found:
                return VerificationReport(
                    outcome=VerificationOutcome.SUCCESS,
                    details={"target": expected_title_substring, "matched": True},
                )
            return VerificationReport(
                outcome=VerificationOutcome.FAILURE,
                details={"target": expected_title_substring, "matched": False, "open_windows": titles[:5]},
                errors=[f"Window with title '{expected_title_substring}' was not found."],
            )
        except Exception as exc:
            logger.warning("Window verification failed: %s", exc)
            return VerificationReport(
                outcome=VerificationOutcome.UNKNOWN,
                details={"target": expected_title_substring, "error": str(exc)},
                errors=[str(exc)],
            )
