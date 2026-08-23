"""
MAX OS — Sensitive UI & Credential Detector (Section 10)
core/perception/sensitive_detector.py

Detects password fields, OTP inputs, credit card forms, banking inputs, API keys,
authentication forms, and security settings controls within UI Automation and DOM structures.

Classification Tiers:
- PUBLIC
- NORMAL
- SENSITIVE
- CREDENTIAL
- CRITICAL
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from core.perception.accessibility import ElementDescriptor


class SensitivityLevel(str, enum.Enum):
    PUBLIC = "PUBLIC"
    NORMAL = "NORMAL"
    SENSITIVE = "SENSITIVE"
    CREDENTIAL = "CREDENTIAL"
    CRITICAL = "CRITICAL"


# Heuristic patterns for sensitive control detection
CREDENTIAL_PATTERNS = [
    re.compile(r"password", re.IGNORECASE),
    re.compile(r"passcode", re.IGNORECASE),
    re.compile(r"secret", re.IGNORECASE),
    re.compile(r"api[_\-\s]?key", re.IGNORECASE),
    re.compile(r"private[_\-\s]?key", re.IGNORECASE),
    re.compile(r"token", re.IGNORECASE),
    re.compile(r"auth[_\-\s]?code", re.IGNORECASE),
    re.compile(r"otp", re.IGNORECASE),
    re.compile(r"2fa", re.IGNORECASE),
    re.compile(r"cvv|cvc", re.IGNORECASE),
    re.compile(r"credit[_\-\s]?card", re.IGNORECASE),
    re.compile(r"ssn|social[_\-\s]?security", re.IGNORECASE),
]

SENSITIVE_PATTERNS = [
    re.compile(r"username", re.IGNORECASE),
    re.compile(r"email", re.IGNORECASE),
    re.compile(r"account[_\-\s]?number", re.IGNORECASE),
    re.compile(r"billing", re.IGNORECASE),
    re.compile(r"payment", re.IGNORECASE),
    re.compile(r"address", re.IGNORECASE),
    re.compile(r"phone[_\-\s]?number", re.IGNORECASE),
]


@dataclass
class SensitivityEvaluation:
    level: SensitivityLevel
    matched_pattern: Optional[str] = None
    reason: str = ""
    is_masked_input: bool = False


class SensitiveUIDetector:
    """
    Evaluates sensitivity level of detected UI elements to prevent unauthorized logging
    or unconfirmed interaction with credential controls.
    """

    def evaluate_element(self, element: ElementDescriptor) -> SensitivityEvaluation:
        text = (element.text or "").lower()
        auto_id = (element.accessibility_id or "").lower()
        role = (element.role or "").lower()

        # 1. Check if edit control is a password field (UIA raw control type / password mask)
        if role == "edit" and any(kw in auto_id or kw in text for kw in ("password", "pwd", "passcode")):
            return SensitivityEvaluation(
                level=SensitivityLevel.CREDENTIAL,
                matched_pattern="password_control",
                reason="Element identified as password field.",
                is_masked_input=True,
            )

        # 2. Check Credential Patterns
        for pat in CREDENTIAL_PATTERNS:
            if pat.search(text) or pat.search(auto_id):
                return SensitivityEvaluation(
                    level=SensitivityLevel.CREDENTIAL,
                    matched_pattern=pat.pattern,
                    reason=f"Element text/ID matched credential pattern '{pat.pattern}'.",
                    is_masked_input=True,
                )

        # 3. Check Sensitive Patterns
        for pat in SENSITIVE_PATTERNS:
            if pat.search(text) or pat.search(auto_id):
                return SensitivityEvaluation(
                    level=SensitivityLevel.SENSITIVE,
                    matched_pattern=pat.pattern,
                    reason=f"Element text/ID matched sensitive pattern '{pat.pattern}'.",
                    is_masked_input=False,
                )

        return SensitivityEvaluation(
            level=SensitivityLevel.NORMAL,
            reason="Standard public UI control.",
            is_masked_input=False,
        )
