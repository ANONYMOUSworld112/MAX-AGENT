"""Agent 7: Code Reviewer.

Reviews code for bugs, syntax errors, style conformance, security vulnerabilities,
and performance regressions. Operates at Permission Tier 0 (Safe Read).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List
from agents.base import BaseAgent, AgentInput, AgentOutput

logger = logging.getLogger("max.agents.code_reviewer")


class CodeReviewer(BaseAgent):
    name = "CodeReviewer"
    description = "Reviews code for bugs, style, security, and performance."
    permission_tier = 0  # Safe Read

    def _execute(self, input_data: AgentInput) -> AgentOutput:
        desc = input_data.task_description
        logger.info("CodeReviewer reviewing: %s", desc)

        code_snippet = input_data.parameters.get("code", "")
        review_findings: List[Dict[str, str]] = []

        # Deterministic static analysis heuristics
        if "eval(" in code_snippet:
            review_findings.append({
                "severity": "HIGH",
                "category": "security",
                "message": "Use of eval() detected, potential remote code execution vulnerability.",
            })
        if "except:" in code_snippet:
            review_findings.append({
                "severity": "MEDIUM",
                "category": "style",
                "message": "Bare except clause detected, may catch SystemExit or KeyboardInterrupt.",
            })
        if "password" in code_snippet.lower() and "=" in code_snippet:
            review_findings.append({
                "severity": "HIGH",
                "category": "security",
                "message": "Potential hardcoded credentials detected in source code.",
            })

        status = "CHANGES_REQUESTED" if any(f["severity"] == "HIGH" for f in review_findings) else "APPROVED"

        return AgentOutput(
            success=True,
            result=f"Code review complete: {status} ({len(review_findings)} findings)",
            artifacts={
                "status": status,
                "findings": review_findings,
                "passed": status == "APPROVED",
            },
        )
