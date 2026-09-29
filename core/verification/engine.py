"""Central Verification Engine.

Aggregates deterministic before/after verification checks across windows,
processes, files, elements, and full computer states.
Outcome is strictly SUCCESS, FAILURE, or UNKNOWN.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger("max.verification.engine")


class VerificationOutcome(str, Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    UNKNOWN = "UNKNOWN"


@dataclass
class VerificationReport:
    outcome: VerificationOutcome
    details: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    @property
    def is_verified(self) -> bool:
        return self.outcome == VerificationOutcome.SUCCESS


class VerificationEngine:
    def __init__(self) -> None:
        pass

    def evaluate(self, reports: List[VerificationReport]) -> VerificationReport:
        """Aggregates multiple verification reports into a unified verdict."""
        if not reports:
            return VerificationReport(
                outcome=VerificationOutcome.UNKNOWN,
                details={"reason": "No verification checks provided"},
            )

        all_details: Dict[str, Any] = {}
        all_errors: List[str] = []

        for idx, rep in enumerate(reports):
            all_details[f"check_{idx}"] = rep.details
            all_errors.extend(rep.errors)

        if any(rep.outcome == VerificationOutcome.FAILURE for rep in reports):
            return VerificationReport(
                outcome=VerificationOutcome.FAILURE,
                details=all_details,
                errors=all_errors,
            )

        if any(rep.outcome == VerificationOutcome.UNKNOWN for rep in reports):
            return VerificationReport(
                outcome=VerificationOutcome.UNKNOWN,
                details=all_details,
                errors=all_errors,
            )

        return VerificationReport(
            outcome=VerificationOutcome.SUCCESS,
            details=all_details,
            errors=[],
        )
