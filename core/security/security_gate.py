"""
MAX OS — Security Gate (Hardened, Section 13).
Deterministic, hardcoded risk classification outside LLM control.
Enforces:
  - 3-Tier Risk Hierarchy (Tier 0: Auto, Tier 1: Confirm once, Tier 2: Confirm every instance)
  - Prompt-Injection & Untrusted Environmental Content Quarantine Filter
  - Irreversible Action Guard & Single-Use Approval Tokens
  - Emergency Kill Switch Preemption
"""

from __future__ import annotations

import enum
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from core.kill_switch import get_kill_switch, require_armed


class RiskTier(int, enum.Enum):
    TIER_0 = 0  # Auto-execute (read-only, navigate, observe, scroll)
    TIER_1 = 1  # Confirm once per task (click, standard form fill, in-app interaction)
    TIER_2 = 2  # Confirm EVERY single instance (delete, send, pay, install, admin, overwrite)


# Static hardcoded mapping: Action Types to minimum mandatory risk tiers
ACTION_TYPE_RISK_MAP: Dict[str, RiskTier] = {
    # Tier 0 Actions
    "open_application": RiskTier.TIER_0,
    "launch_app": RiskTier.TIER_0,
    "navigate": RiskTier.TIER_0,
    "open_url": RiskTier.TIER_0,
    "search_web": RiskTier.TIER_0,
    "read_screen": RiskTier.TIER_0,
    "read_file": RiskTier.TIER_0,
    "scroll": RiskTier.TIER_0,
    "find_element": RiskTier.TIER_0,
    "observe": RiskTier.TIER_0,
    "safe_type": RiskTier.TIER_0,

    # Tier 1 Actions
    "click": RiskTier.TIER_1,
    "click_element": RiskTier.TIER_1,
    "type": RiskTier.TIER_1,
    "type_text": RiskTier.TIER_1,
    "submit_form": RiskTier.TIER_1,
    "save_as_new": RiskTier.TIER_1,
    "drag": RiskTier.TIER_1,

    # Tier 2 Actions (Destructive / Sensitive / Irreversible)
    "format": RiskTier.TIER_2,
    "format_disk": RiskTier.TIER_2,
    "diskpart": RiskTier.TIER_2,
    "delete": RiskTier.TIER_2,
    "delete_file": RiskTier.TIER_2,
    "delete_all": RiskTier.TIER_2,
    "send_message": RiskTier.TIER_2,
    "send_email": RiskTier.TIER_2,
    "send_external": RiskTier.TIER_2,
    "purchase": RiskTier.TIER_2,
    "payment": RiskTier.TIER_2,
    "install_software": RiskTier.TIER_2,
    "execute_admin_command": RiskTier.TIER_2,
    "modify_system_settings": RiskTier.TIER_2,
    "upload_data": RiskTier.TIER_2,
    "overwrite_file": RiskTier.TIER_2,
    "kill_process": RiskTier.TIER_2,
    "wipe_database": RiskTier.TIER_2,
}

# Dangerous keyword heuristics in action targets that statically force Tier 2
TIER_2_TARGET_KEYWORDS: Set[str] = {
    "delete", "rmdir", "remove", "unlink", "truncate", "wipe", "format",
    "send", "publish", "post", "tweet", "submit_application",
    "pay", "buy", "checkout", "purchase", "credit_card",
    "admin", "elevated", "sudo", "reg add", "netsh", "diskpart",
    "overwrite", "replace_all", "shutdown", "reboot",
}

# Prompt Injection Patterns found in observed environmental data
PROMPT_INJECTION_PATTERNS: List[re.Pattern] = [
    re.compile(r"ignore\s+(?:all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\s+(?:all\s+)?prior\s+commands", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(?:a\s+)?(?:dan|unrestricted|god\s*mode)", re.IGNORECASE),
    re.compile(r"new\s+system\s+prompt\s*:", re.IGNORECASE),
    re.compile(r"system\s*override\s*:", re.IGNORECASE),
    re.compile(r"delete\s+(?:all\s+)?files", re.IGNORECASE),
    re.compile(r"format\s+[a-zA-Z]:", re.IGNORECASE),
    re.compile(r"send\s+(?:my|the)\s+password", re.IGNORECASE),
    re.compile(r"exfiltrate\s+to", re.IGNORECASE),
]


class SecurityGateBlockedError(Exception):
    """Raised when an unconfirmed Tier 1/2 or dangerous action is blocked by the Security Gate."""
    pass


class PromptInjectionDetectedError(Exception):
    """Raised when active adversarial prompt-injection text is detected in environmental data."""
    pass


@dataclass
class ActionSecurityEvaluation:
    action_type: str
    target: str
    risk_tier: RiskTier
    requires_confirmation: bool
    confirmation_reason: Optional[str]
    is_destructive_or_irreversible: bool
    quarantined_prompt_injections: List[str] = field(default_factory=list)


class SecurityGate:
    """
    Hardcoded Static Security Gate.
    The planning LLM can propose actions, but CANNOT assign or downgrade risk tiers.
    """

    def __init__(self):
        self._task_approved_tier1: Set[str] = set()  # task_ids with Tier 1 batch approval
        self._consumed_tier2_tokens: Set[str] = set()
        self._valid_tier2_tokens: Dict[str, str] = {}  # token -> action_id

    def classify_action_risk(
        self,
        action_type: str,
        target: str = "",
        action_payload: Optional[Dict[str, Any]] = None,
    ) -> ActionSecurityEvaluation:
        """
        Computes the immutable static risk tier for an action.
        Planning LLM self-reported risk tiers are ignored.
        """
        act_lower = action_type.lower().strip()
        target_lower = target.lower().strip()
        payload = action_payload or {}

        # 1. Start with base action mapping
        tier = ACTION_TYPE_RISK_MAP.get(act_lower, RiskTier.TIER_1)

        # 2. Check target for Tier 2 escalation keywords
        is_escalated = any(kw in target_lower for kw in TIER_2_TARGET_KEYWORDS) or any(
            kw in str(payload).lower() for kw in TIER_2_TARGET_KEYWORDS
        )

        if is_escalated:
            tier = RiskTier.TIER_2

        # 3. Check for specific dangerous payload flags
        if payload.get("overwrite") is True or payload.get("elevated") is True:
            tier = RiskTier.TIER_2

        is_tier_2 = (tier == RiskTier.TIER_2)
        is_tier_1 = (tier == RiskTier.TIER_1)

        reason = None
        if is_tier_2:
            reason = f"Tier 2 sensitive action '{act_lower}' on '{target}' requires mandatory per-instance confirmation."
        elif is_tier_1:
            reason = f"Tier 1 action '{act_lower}' on '{target}' requires task acceptance confirmation."

        return ActionSecurityEvaluation(
            action_type=act_lower,
            target=target,
            risk_tier=tier,
            requires_confirmation=(is_tier_1 or is_tier_2),
            confirmation_reason=reason,
            is_destructive_or_irreversible=is_tier_2,
        )

    def authorize_action(
        self,
        action_type: str,
        target: str,
        task_id: str,
        action_id: str,
        approval_token: Optional[str] = None,
        action_payload: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Evaluates authorization for an action.
        - Tier 0: Passes automatically.
        - Tier 1: Passes if task_id was pre-approved OR valid token supplied.
        - Tier 2: Requires explicit single-use approval token matching action_id.
        """
        require_armed(get_kill_switch())
        eval_res = self.classify_action_risk(action_type, target, action_payload)

        # Tier 0: Auto-execute
        if eval_res.risk_tier == RiskTier.TIER_0:
            return True

        # Tier 1: Confirm once per task
        if eval_res.risk_tier == RiskTier.TIER_1:
            if task_id in self._task_approved_tier1:
                return True
            if approval_token and self._verify_token(approval_token, action_id):
                return True
            raise SecurityGateBlockedError(
                f"[SecurityGate TIER 1 BLOCKED] Action '{action_type}' on '{target}' requires task approval."
            )

        # Tier 2: Confirm every single instance (Single-use token required)
        if eval_res.risk_tier == RiskTier.TIER_2:
            if not approval_token:
                raise SecurityGateBlockedError(
                    f"[SecurityGate TIER 2 BLOCKED] Destructive/sensitive action '{action_type}' on '{target}' "
                    f"strictly requires per-instance confirmation token."
                )
            if not self._consume_tier2_token(approval_token, action_id):
                raise SecurityGateBlockedError(
                    f"[SecurityGate TIER 2 BLOCKED] Invalid or already-consumed confirmation token for '{action_id}'."
                )
            return True

        return False

    def grant_tier1_task_approval(self, task_id: str) -> None:
        """Grants task-wide approval for Tier 1 non-destructive actions."""
        self._task_approved_tier1.add(task_id)

    def issue_tier2_approval_token(self, action_id: str) -> str:
        """Issues a single-use per-instance confirmation token for a Tier 2 action."""
        token = f"tier2_token_{uuid.uuid4().hex}"
        self._valid_tier2_tokens[token] = action_id
        return token

    def _verify_token(self, token: str, action_id: str) -> bool:
        return self._valid_tier2_tokens.get(token) == action_id

    def _consume_tier2_token(self, token: str, action_id: str) -> bool:
        if token in self._consumed_tier2_tokens:
            return False
        if self._valid_tier2_tokens.get(token) == action_id:
            self._consumed_tier2_tokens.add(token)
            del self._valid_tier2_tokens[token]
            return True
        return False

    # --- Prompt Injection Quarantine Filter (Section 13.3) ---
    def sanitize_environmental_data(self, raw_observed_text: str) -> Tuple[str, List[str]]:
        """
        Inspects environmental text (webpage content, file contents, OCR, terminal text).
        Quarantines instruction-shaped text and returns (safe_data_text, flagged_threats).
        """
        if not raw_observed_text or not isinstance(raw_observed_text, str):
            return "", []

        flagged_threats: List[str] = []
        sanitized = raw_observed_text

        for pattern in PROMPT_INJECTION_PATTERNS:
            matches = pattern.findall(sanitized)
            for m in matches:
                flagged_threats.append(str(m))
                # Quarantine match in observed data
                sanitized = pattern.sub(f"[QUARANTINED_UNTRUSTED_INSTRUCTION: {m}]", sanitized)

        return sanitized, flagged_threats
