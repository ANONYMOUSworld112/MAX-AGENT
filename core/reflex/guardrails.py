"""System 1 Reflex Safety Guardrails powered by Laya.

Evaluates incoming requests in sub-50ms to classify into one of 4 Risk Tiers:
- Tier 0: Auto (Read-only, zero side effects)
- Tier 1: Safe Write (Scratchpad, temp files, auto-undo logged)
- Tier 2: Confirm on Write (Requires user approval modal with diff)
- Tier 3: Hard Blocked (Unconditional rejection)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import IntEnum
from typing import List

from core.reflex.laya_engine import LayaReflexEngine

logger = logging.getLogger("max.reflex.guardrails")


class RiskTier(IntEnum):
    TIER_0_AUTO = 0
    TIER_1_SAFE_WRITE = 1
    TIER_2_CONFIRM_ON_WRITE = 2
    TIER_3_HARD_BLOCKED = 3


@dataclass
class GuardResult:
    is_safe: bool
    risk_tier: RiskTier
    reason: str


class ReflexGuardrails:
    # Deterministic hard-blocked signatures
    HARD_BLOCKED_PATTERNS: List[str] = [
        "rm -rf /",
        "format c:",
        "del /f /s /q c:",
        "mkfs",
        "drop database",
        "kill -9 1",
        ":(){ :|:& };:",
        "bypass kill switch",
    ]

    def __init__(self, fallback_mode: bool = False) -> None:
        self.engine = LayaReflexEngine(fallback_mode=fallback_mode)

    def check_safety(self, text: str) -> GuardResult:
        text_lower = text.lower()

        # 1. Deterministic Tier 3 Check
        for blocked in self.HARD_BLOCKED_PATTERNS:
            if blocked in text_lower:
                return GuardResult(
                    is_safe=False,
                    risk_tier=RiskTier.TIER_3_HARD_BLOCKED,
                    reason=f"Hard-blocked dangerous pattern detected: '{blocked}'",
                )

        # 2. Check Modifying / Destructive intent (Tier 2 vs Tier 1 vs Tier 0)
        modifying_words = [
            "delete", "remove", "drop", "truncate", "modify", "update",
            "refactor", "overwrite", "deploy", "git push", "send email"
        ]
        if any(w in text_lower for w in modifying_words):
            return GuardResult(
                is_safe=True,
                risk_tier=RiskTier.TIER_2_CONFIRM_ON_WRITE,
                reason="Operation modifies code, data, or external state. User confirmation required.",
            )

        safe_write_words = ["create", "write", "generate", "scratchpad", "log", "temp file"]
        if any(w in text_lower for w in safe_write_words):
            return GuardResult(
                is_safe=True,
                risk_tier=RiskTier.TIER_1_SAFE_WRITE,
                reason="Safe local write operation.",
            )

        return GuardResult(
            is_safe=True,
            risk_tier=RiskTier.TIER_0_AUTO,
            reason="Read-only query.",
        )
