"""System 1 Reflex Triage & Priority Scoring powered by Laya.

Assigns incoming tasks to one of 5 Priority Bands (0 to 4):
- Band 0 (Critical): Kill switch, security alerts, user aborts
- Band 1 (Interactive): Real-time voice tool calls, fast UI queries (<2s)
- Band 2 (Active Workflow): Code generation, refactoring, running test suites
- Band 3 (Background): Email triage, meeting summaries, web research
- Band 4 (Maintenance): Log rotation, cache clearing, index vacuuming
"""

from __future__ import annotations

import logging
from enum import IntEnum
from typing import Optional

from core.reflex.laya_engine import LayaReflexEngine

logger = logging.getLogger("max.reflex.triage")


class PriorityBand(IntEnum):
    BAND_0_CRITICAL = 0
    BAND_1_INTERACTIVE = 1
    BAND_2_ACTIVE_WORKFLOW = 2
    BAND_3_BACKGROUND = 3
    BAND_4_MAINTENANCE = 4


class ReflexTriage:
    def __init__(self, fallback_mode: bool = False) -> None:
        self.engine = LayaReflexEngine(fallback_mode=fallback_mode)

    def assign_priority(self, task_description: str) -> PriorityBand:
        desc_lower = task_description.lower()

        # Band 0: Emergency / Kill switch / Critical security
        if any(w in desc_lower for w in ["kill switch", "emergency", "security breach", "cve critical", "abort all"]):
            return PriorityBand.BAND_0_CRITICAL

        # Band 4: Maintenance
        if any(w in desc_lower for w in ["vacuum", "rotate log", "clean old", "cache files", "garbage collect"]):
            return PriorityBand.BAND_4_MAINTENANCE

        # Band 3: Background batch jobs
        if any(w in desc_lower for w in ["newsletter", "in background", "summarize daily", "scrape", "triage inbox"]):
            return PriorityBand.BAND_3_BACKGROUND

        # Band 2: Active engineering workflow
        if any(w in desc_lower for w in ["refactor", "pytest", "build", "deploy", "git commit", "code", "author spec"]):
            return PriorityBand.BAND_2_ACTIVE_WORKFLOW

        # Default Band 1: Interactive query
        return PriorityBand.BAND_1_INTERACTIVE
