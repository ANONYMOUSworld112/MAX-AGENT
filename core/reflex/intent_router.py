"""System 1 Reflex Intent Router powered by Laya.

Evaluates user voice or text input in sub-50ms to decide:
1. Lane A (Instant direct response / read query) vs Lane B (Autonomous task queue)
2. Target agent from the 33-agent ecosystem
3. Whether the operation is modifying / high risk
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from core.reflex.laya_engine import LayaReflexEngine

logger = logging.getLogger("max.reflex.intent_router")


class LaneType(str, Enum):
    LANE_A = "LANE_A"  # Fast voice stream (<2s, read-only)
    LANE_B = "LANE_B"  # Autonomous background task queue


@dataclass
class IntentDecision:
    lane: LaneType
    cluster: str
    target_agent: str
    confidence: float
    is_modifying: bool
    summary: str


class ReflexIntentRouter:
    def __init__(self, fallback_mode: bool = False) -> None:
        self.engine = LayaReflexEngine(fallback_mode=fallback_mode)

    def route_input(self, text: str) -> IntentDecision:
        text_lower = text.lower()

        # Check modifying intent
        is_modifying = any(
            verb in text_lower
            for verb in [
                "create", "delete", "remove", "refactor", "update", "write",
                "modify", "deploy", "commit", "push", "schedule", "send", "book"
            ]
        )

        # 1. Routing to Lane A vs Lane B
        lane_options = {
            "LANE_A": "Quick facts, time, date, volume, weather, simple read queries",
            "LANE_B": "Writing code, refactoring, deploying, scheduling meetings, sending emails, background jobs"
        }
        lane_str, lane_conf = self.engine.classify_choice(
            state=text,
            question="Does this need real-time instant voice facts (LANE_A) or autonomous task execution (LANE_B)?",
            options=lane_options,
        )
        lane = LaneType.LANE_B if is_modifying or lane_str == "LANE_B" else LaneType.LANE_A

        # 2. Agent selection
        if any(w in text_lower for w in ["code", "refactor", "function", "fix bug", "pytest", "python"]):
            cluster = "software"
            target_agent = "PolyglotDeveloper"
        elif any(w in text_lower for w in ["schedule", "meeting", "calendar", "event"]):
            cluster = "productivity"
            target_agent = "CalendarAgent"
        elif any(w in text_lower for w in ["email", "inbox", "mail"]):
            cluster = "productivity"
            target_agent = "InboxAgent"
        elif any(w in text_lower for w in ["cpu", "ram", "memory", "battery", "gpu", "telemetry"]):
            cluster = "health"
            target_agent = "SystemMonitor"
        elif any(w in text_lower for w in ["architect", "system design", "adr", "schema"]):
            cluster = "software"
            target_agent = "SystemArchitect"
        elif any(w in text_lower for w in ["kill", "abort", "emergency stop"]):
            cluster = "safety"
            target_agent = "EmergencyInterrupter"
        else:
            cluster = "core"
            target_agent = "MasterOrchestrator"

        return IntentDecision(
            lane=lane,
            cluster=cluster,
            target_agent=target_agent,
            confidence=lane_conf,
            is_modifying=is_modifying,
            summary=f"Routed to {target_agent} on {lane.value}"
        )

    def route(self, name: str, args: Optional[dict] = None) -> IntentDecision:
        """Route tool call name and arguments to Lane A or Lane B."""
        args_dict = args or {}
        text_parts = [name]
        for k, v in args_dict.items():
            if isinstance(v, (str, int, float, bool)):
                text_parts.append(str(v))
        return self.route_input(" ".join(text_parts))

