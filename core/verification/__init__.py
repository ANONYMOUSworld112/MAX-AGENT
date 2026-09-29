"""Verification Engine.

Provides deterministic before/after state verification for all system actions.
Returns strictly SUCCESS, FAILURE, or UNKNOWN.
"""

from core.verification.engine import VerificationEngine, VerificationOutcome, VerificationReport
from core.verification.window_verifier import WindowVerifier
from core.verification.process_verifier import ProcessVerifier
from core.verification.element_verifier import ElementVerifier
from core.verification.text_verifier import TextVerifier
from core.verification.url_verifier import URLVerifier
from core.verification.file_verifier import FileVerifier
from core.verification.state_diff_verifier import StateDiffVerifier

__all__ = [
    "VerificationEngine",
    "VerificationOutcome",
    "VerificationReport",
    "WindowVerifier",
    "ProcessVerifier",
    "ElementVerifier",
    "TextVerifier",
    "URLVerifier",
    "FileVerifier",
    "StateDiffVerifier",
]
