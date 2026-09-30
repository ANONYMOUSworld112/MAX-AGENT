"""
MAX-AGENT Policy Engine
========================

Deterministic risk classification and confirmation rules.

Every ActionRequest is assigned a RiskLevel based on a lookup table.
The PolicyEngine then determines whether the action can auto-execute
or requires human confirmation, and on which channel.

Design decisions:
  - Pure deterministic logic — no LLM calls.
  - Risk table is a dict keyed by canonical action name.
  - Unknown actions default to HIGH (fail-safe).
  - Confirmation requirements depend on (risk_level, channel_trust).
  - PROHIBITED actions are always rejected.

Master Spec references:
  - Section 13 (risk classification table)
  - Section 5  (channel trust levels)
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Optional

from core.contracts import (
    ActionRequest,
    RiskLevel,
    ChannelTrust,
    IdempotencyClass,
)


class ConfirmationType(enum.Enum):
    """What kind of human confirmation is needed."""
    NONE = "NONE"                    # Auto-execute
    HUD_BUTTON = "HUD_BUTTON"       # Click confirm in HUD
    TYPED_PHRASE = "TYPED_PHRASE"    # Type a specific phrase
    REJECTED = "REJECTED"           # Action is prohibited


@dataclass(frozen=True)
class PolicyDecision:
    """Result of policy evaluation for an ActionRequest."""
    action: str
    risk_level: RiskLevel
    confirmation: ConfirmationType
    reason: str
    requires_resource_lease: bool = False
    required_resources: list[str] | None = None
    max_timeout_seconds: float = 30.0

    @property
    def is_allowed(self) -> bool:
        return self.confirmation != ConfirmationType.REJECTED


# ---------------------------------------------------------------------------
# Risk Classification Table
# ---------------------------------------------------------------------------

# Maps canonical action names to their base risk levels.
# Actions not in this table default to HIGH.
_RISK_TABLE: dict[str, RiskLevel] = {
    # LOW — Read-only, no side effects
    "web_search": RiskLevel.LOW,
    "get_time": RiskLevel.LOW,
    "get_weather": RiskLevel.LOW,
    "system_info": RiskLevel.LOW,
    "screenshot": RiskLevel.LOW,
    "list_files": RiskLevel.LOW,
    "read_file": RiskLevel.LOW,
    "search_memory": RiskLevel.LOW,
    "screen_process": RiskLevel.LOW,

    # MEDIUM — Reversible modifications
    "open_app": RiskLevel.MEDIUM,
    "create_file": RiskLevel.MEDIUM,
    "write_file": RiskLevel.MEDIUM,
    "save_memory": RiskLevel.MEDIUM,
    "set_reminder": RiskLevel.MEDIUM,
    "play_music": RiskLevel.MEDIUM,
    "pip_install": RiskLevel.MEDIUM,
    "git_commit": RiskLevel.MEDIUM,
    "create_project": RiskLevel.MEDIUM,
    "close_app": RiskLevel.MEDIUM,

    # HIGH — Destructive or hard to reverse
    "delete_file": RiskLevel.HIGH,
    "move_file": RiskLevel.HIGH,
    "send_message": RiskLevel.HIGH,
    "send_email": RiskLevel.HIGH,
    "computer_control": RiskLevel.HIGH,
    "desktop_automation": RiskLevel.HIGH,
    "kill_process": RiskLevel.HIGH,
    "system_setting": RiskLevel.HIGH,
    "run_code": RiskLevel.HIGH,

    # CRITICAL — Irreversible system-level changes
    "format_drive": RiskLevel.PROHIBITED,
    "delete_system_file": RiskLevel.PROHIBITED,
    "modify_registry": RiskLevel.CRITICAL,
    "change_firewall": RiskLevel.CRITICAL,
    "install_service": RiskLevel.CRITICAL,
    "elevated_command": RiskLevel.CRITICAL,
}


# ---------------------------------------------------------------------------
# Confirmation Matrix
# ---------------------------------------------------------------------------

# Maps (risk_level, channel_trust) → required confirmation.
_CONFIRMATION_MATRIX: dict[tuple[RiskLevel, ChannelTrust], ConfirmationType] = {
    # LOW — always auto-execute regardless of channel
    (RiskLevel.LOW, ChannelTrust.TRUSTED): ConfirmationType.NONE,
    (RiskLevel.LOW, ChannelTrust.SEMI_TRUSTED): ConfirmationType.NONE,
    (RiskLevel.LOW, ChannelTrust.UNTRUSTED): ConfirmationType.NONE,

    # MEDIUM — auto from trusted, confirm from semi/untrusted
    (RiskLevel.MEDIUM, ChannelTrust.TRUSTED): ConfirmationType.NONE,
    (RiskLevel.MEDIUM, ChannelTrust.SEMI_TRUSTED): ConfirmationType.HUD_BUTTON,
    (RiskLevel.MEDIUM, ChannelTrust.UNTRUSTED): ConfirmationType.HUD_BUTTON,

    # HIGH — confirm from trusted, confirm from semi, reject from untrusted
    (RiskLevel.HIGH, ChannelTrust.TRUSTED): ConfirmationType.HUD_BUTTON,
    (RiskLevel.HIGH, ChannelTrust.SEMI_TRUSTED): ConfirmationType.HUD_BUTTON,
    (RiskLevel.HIGH, ChannelTrust.UNTRUSTED): ConfirmationType.REJECTED,

    # CRITICAL — typed phrase from trusted only
    (RiskLevel.CRITICAL, ChannelTrust.TRUSTED): ConfirmationType.TYPED_PHRASE,
    (RiskLevel.CRITICAL, ChannelTrust.SEMI_TRUSTED): ConfirmationType.REJECTED,
    (RiskLevel.CRITICAL, ChannelTrust.UNTRUSTED): ConfirmationType.REJECTED,

    # PROHIBITED — always rejected
    (RiskLevel.PROHIBITED, ChannelTrust.TRUSTED): ConfirmationType.REJECTED,
    (RiskLevel.PROHIBITED, ChannelTrust.SEMI_TRUSTED): ConfirmationType.REJECTED,
    (RiskLevel.PROHIBITED, ChannelTrust.UNTRUSTED): ConfirmationType.REJECTED,
}


class PolicyEngine:
    """
    Deterministic policy engine for risk classification and confirmation.

    Evaluates an ActionRequest and returns a PolicyDecision indicating
    the risk level, required confirmation type, and resource requirements.
    """

    def __init__(
        self,
        risk_table: dict[str, RiskLevel] | None = None,
        confirmation_matrix: dict[tuple[RiskLevel, ChannelTrust], ConfirmationType] | None = None,
    ):
        self._risk_table = risk_table or dict(_RISK_TABLE)
        self._confirmation_matrix = confirmation_matrix or dict(_CONFIRMATION_MATRIX)

    # Ordinal severity for risk comparison
    _RISK_SEVERITY: dict[RiskLevel, int] = {
        RiskLevel.LOW: 0,
        RiskLevel.MEDIUM: 1,
        RiskLevel.HIGH: 2,
        RiskLevel.CRITICAL: 3,
        RiskLevel.PROHIBITED: 4,
    }

    def evaluate(self, request: ActionRequest) -> PolicyDecision:
        """
        Evaluate an ActionRequest and return a PolicyDecision.

        Unknown actions default to HIGH risk.
        """
        action = request.action
        channel_trust = request.channel_trust

        # Look up risk level (default to HIGH for unknown actions)
        table_risk = self._risk_table.get(action, RiskLevel.HIGH)

        # Use the higher of table risk vs request-declared risk
        table_sev = self._RISK_SEVERITY.get(table_risk, 2)
        req_sev = self._RISK_SEVERITY.get(request.risk_level, 0)
        risk = table_risk if table_sev >= req_sev else request.risk_level

        # Look up confirmation requirement
        confirmation = self._confirmation_matrix.get(
            (risk, channel_trust),
            ConfirmationType.REJECTED,  # fail-safe default
        )

        # Build reason string
        if confirmation == ConfirmationType.REJECTED:
            reason = (
                f"Action '{action}' with risk={risk.value} is not permitted "
                f"from channel trust={channel_trust.value}"
            )
        elif confirmation == ConfirmationType.NONE:
            reason = f"Action '{action}' auto-approved (risk={risk.value}, trust={channel_trust.value})"
        elif confirmation == ConfirmationType.HUD_BUTTON:
            reason = f"Action '{action}' requires HUD confirmation (risk={risk.value})"
        elif confirmation == ConfirmationType.TYPED_PHRASE:
            reason = f"Action '{action}' requires typed confirmation phrase (risk={risk.value})"
        else:
            reason = f"Unknown confirmation type for '{action}'"

        return PolicyDecision(
            action=action,
            risk_level=risk,
            confirmation=confirmation,
            reason=reason,
            requires_resource_lease=len(request.required_resources) > 0,
            required_resources=list(request.required_resources),
            max_timeout_seconds=request.timeout_seconds,
        )

    def get_risk_level(self, action: str) -> RiskLevel:
        """Look up the base risk level for an action name."""
        return self._risk_table.get(action, RiskLevel.HIGH)

    def register_action_risk(self, action: str, risk: RiskLevel) -> None:
        """Register or update the risk level for an action."""
        self._risk_table[action] = risk
