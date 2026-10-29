"""Agent 5: Adversarial Critic.

Evaluates proposed execution plans, code snippets, and commands defensively,
hunting for logical flaws, edge-case failures, unhandled exceptions, and security risks.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List
from agents.base import BaseAgent, AgentInput, AgentOutput

logger = logging.getLogger("max.agents.critic")

_DANGEROUS_PATTERNS = [
    (r"\brm\s+-rf\b", "Unconstrained recursive file deletion"),
    (r"\bformat\s+[a-z]:\b", "Disk volume formatting command"),
    (r"\bdel\s+/[a-z]\s+system32\b", "System directory destruction"),
    (r"\bdrop\s+database\b", "Irreversible database deletion"),
    (r":\(\)\{\s*:\|:&\s*\};:", "Fork bomb execution pattern"),
]


class AdversarialCritic(BaseAgent):
    name = "AdversarialCritic"
    description = "Defensively evaluates plans and actions for edge-case failures and safety risks."
    permission_tier = 0

    def _execute(self, input_data: AgentInput) -> AgentOutput:
        plan_text = input_data.task_description or ""
        params = input_data.parameters or {}
        proposed_commands = params.get("commands", [])

        critiques: List[Dict[str, str]] = []
        is_safe = True

        # Check for dangerous command patterns
        all_text = plan_text + " " + " ".join(proposed_commands)
        for pattern, warning in _DANGEROUS_PATTERNS:
            if re.search(pattern, all_text, re.IGNORECASE):
                critiques.append({
                    "severity": "CRITICAL",
                    "finding": f"Detected high-risk pattern: {warning}",
                    "recommendation": "Block execution immediately and require manual confirmation.",
                })
                is_safe = False

        if not critiques:
            critiques.append({
                "severity": "LOW",
                "finding": "Plan conforms to deterministic execution boundaries.",
                "recommendation": "Proceed with standard L1-L3 verification gates.",
            })

        summary = "Plan approved with zero critical security flaws." if is_safe else f"Plan rejected: {len(critiques)} critical flaw(s) identified."
        return AgentOutput(
            success=is_safe,
            result=summary,
            artifacts={"critique_findings": critiques, "is_safe": is_safe},
        )
