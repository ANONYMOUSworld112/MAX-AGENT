"""
MAX OS — Tier & Permissions Enforcement
Build Order: #17 (Layer 4B)
═══════════════════════════════════════════════════════

Enforces execution safety tiers:
- AUTO: Non-destructive, read-only or low-risk actions (Calendar, Notes, Info)
- CONFIRM: File edits, shell commands, installs (Coding, Terminal)
- PRODUCTION_GATE: Repo deployment, DB drops, server restarts (Deploy)
"""

from __future__ import annotations

import logging
from enum import Enum

logger = logging.getLogger("max.routing.permissions")


class PermissionTier(str, Enum):
    AUTO = "auto"
    CONFIRM = "confirm"
    PRODUCTION_GATE = "production_gate"


# Default permission tier map per agent and action keyword
_AGENT_DEFAULT_TIERS: dict[str, PermissionTier] = {
    "calendar": PermissionTier.AUTO,
    "notes": PermissionTier.AUTO,
    "research": PermissionTier.AUTO,
    "coding": PermissionTier.CONFIRM,
    "terminal": PermissionTier.CONFIRM,
    "deploy": PermissionTier.PRODUCTION_GATE,
    "system": PermissionTier.CONFIRM,
}


def get_permission_tier(agent: str, action: str = "") -> PermissionTier:
    """Determine permission tier for an agent and action."""
    action_lower = action.lower()

    # Destructive keywords escalate to PRODUCTION_GATE
    if any(k in action_lower for k in ["deploy", "drop table", "rm -rf", "reboot", "format"]):
        return PermissionTier.PRODUCTION_GATE

    if any(k in action_lower for k in ["write", "create", "delete", "edit", "install"]):
        return PermissionTier.CONFIRM

    return _AGENT_DEFAULT_TIERS.get(agent.lower(), PermissionTier.CONFIRM)
