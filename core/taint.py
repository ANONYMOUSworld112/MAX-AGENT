"""
core/taint.py — Security Taint Tracking Engine for FRIDAY.

Tracks whether untrusted content (web pages, emails, files, OCR text, third-party data)
has been ingested during the current reasoning turn. Once context is tainted, any
subsequent T1 (reversible) or T2 (sensitive) action is escalated to require explicit
human confirmation, preventing indirect prompt injection attacks from performing
unauthorized side-effects.
"""
from __future__ import annotations

import logging
from typing import Optional, Set

logger = logging.getLogger("friday.security.taint")

# Tools that ingest untrusted external data
UNTRUSTED_INGESTION_TOOLS: Set[str] = {
    "read_file",
    "browser_read",
    "browser_search",
    "browser_summarize",
    "read_email",
    "fetch_webpage",
    "vision_read_text",
    "vision_describe",
    "screen_describe",
}


class TaintTracker:
    """Tracks untrusted data provenance across the conversational session."""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self._is_tainted: bool = False
        self._taint_sources: list[str] = []

    def reset(self, explicit_session_clear: bool = False) -> None:
        """
        Only reset taint if the session context is explicitly wiped.
        A turn transition alone does NOT clear taint because tainted text remains in context.
        """
        if explicit_session_clear:
            self._is_tainted = False
            self._taint_sources.clear()
            logger.info("Context taint cleared by explicit session reset.")

    def record_tool_result(self, tool_name: str, output: any) -> None:
        """Inspect executed tool and apply taint if it ingests untrusted data."""
        if not self.enabled:
            return

        if tool_name in UNTRUSTED_INGESTION_TOOLS:
            self._is_tainted = True
            if tool_name not in self._taint_sources:
                self._taint_sources.append(tool_name)
            logger.warning(
                "SESSION TAINTED: Tool '%s' ingested untrusted content. "
                "All subsequent side-effects require human confirmation until session is cleared.",
                tool_name
            )

    def tag_memory_item(self, payload: dict) -> dict:
        """Attach provenance metadata to memory writes to prevent poisoned facts."""
        result = dict(payload)
        if self.is_tainted:
            result["provenance"] = "untrusted"
            result["tainted"] = True
            result["taint_sources"] = list(self._taint_sources)
        else:
            result["provenance"] = "trusted"
            result["tainted"] = False
        return result

    @property
    def is_tainted(self) -> bool:
        return self._is_tainted if self.enabled else False

    @property
    def taint_sources(self) -> list[str]:
        return list(self._taint_sources)

    def requires_confirmation_escalation(self, permission_tier: str) -> bool:
        """
        Check if an action must be escalated to require confirmation.
        If context is tainted, any T1 or T2 action must be confirmed by the boss.
        """
        if not self.is_tainted:
            return permission_tier in ("T2",)
        # Escalated: T1 actions now also require confirmation because input was untrusted!
        return permission_tier in ("T1", "T2")
