"""
MAX OS — Permission Firewall & Security Policy Subsystem (Phases 27, 28, 29, 30, 31, 32).
Prevents LLM hallucinated, unverified, or dangerous actions from taking uncontrolled OS actions.
"""

from __future__ import annotations

import enum
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from core.command_model import ActionObject
from core.security.security_gate import RiskTier, SecurityGate, SecurityGateBlockedError


class RiskLevel(str, enum.Enum):
    LOW = "low"            # Move mouse, scroll, read screen, inspect window
    MEDIUM = "medium"      # Launch app, create file, modify file, run normal command
    HIGH = "high"          # Delete files, system settings, registry modification
    CRITICAL = "critical"  # Credentials, financial actions, admin operations, wipe data


class ControlMode(str, enum.Enum):
    OBSERVE_ONLY = "observe_only"          # Analyze screen/window, execute no physical input
    ASSISTED = "assisted"                  # Propose actions, user must confirm every step
    AUTONOMOUS = "autonomous"              # Automatically run safe/permitted actions
    TURBO_AUTONOMOUS = "turbo_autonomous"  # Rapid local batch execution for low-risk actions
    RESTRICTED = "restricted"              # Strict allowlist of apps/directories only


@dataclass
class PolicyRules:
    allowed_applications: Set[str] = field(default_factory=lambda: {"chrome.exe", "msedge.exe", "code.exe", "notepad.exe", "cmd.exe", "powershell.exe", "brave.exe", "explorer.exe", "calc.exe"})
    blocked_applications: Set[str] = field(default_factory=lambda: {"keepass.exe", "1password.exe", "regedit.exe", "format.com"})
    allowed_directories: Set[str] = field(default_factory=lambda: {r"C:\Projects", r"E:\tem-jarvis", r"C:\Users", r"E:\MAX_OS_RUNNERS"})
    blocked_directories: Set[str] = field(default_factory=lambda: {r"C:\Windows\System32", r"C:\Windows"})
    blocked_commands: Set[str] = field(default_factory=lambda: {"format", "rmdir /s /q c:", "del /f /s /q c:", "reg add", "netsh", "diskpart"})


class PermissionFirewall:
    """
    Authoritative Permission Firewall for MAX High-Speed Computer Control Engine.
    Ensures LLM output NEVER bypasses security policy controls.
    """

    def __init__(
        self,
        security_gate: Optional[SecurityGate] = None,
        mode: ControlMode = ControlMode.TURBO_AUTONOMOUS,
        rules: Optional[PolicyRules] = None,
    ):
        self.security_gate = security_gate or SecurityGate()
        self.mode = mode
        self.rules = rules or PolicyRules()

    def set_mode(self, mode: ControlMode) -> None:
        """Sets active user control mode."""
        self.mode = mode

    def classify_risk(self, action: ActionObject) -> RiskLevel:
        """Classifies action into RiskLevel enum."""
        act_type = action.type.lower().strip()
        target = (action.target or "").lower().strip()

        # Check critical operations
        if any(w in act_type or w in target for w in ("credential", "password", "bank", "payment", "buy", "format", "wipe")):
            return RiskLevel.CRITICAL

        # Check high operations
        if any(w in act_type or w in target for w in ("delete", "remove", "registry", "admin", "system32", "kill")):
            return RiskLevel.HIGH

        # Check medium operations
        if act_type in ("open_application", "launch_app", "click", "click_element", "type", "type_text", "submit_form", "create_file", "write_file", "execute_command", "keypress", "hotkey"):
            return RiskLevel.MEDIUM

        return RiskLevel.LOW

    def evaluate_permission(
        self,
        action: ActionObject,
        task_id: str,
        approval_token: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Evaluates whether an action is authorized under current ControlMode and PolicyRules.
        Returns (is_allowed, reason).
        """
        # 1. OBSERVE_ONLY mode blocks all physical inputs
        if self.mode == ControlMode.OBSERVE_ONLY:
            if action.type.lower() not in ("observe", "read_screen", "screenshot", "active_window", "list_windows"):
                return False, "ControlMode is OBSERVE_ONLY. Physical computer actions are disabled."

        # 2. Check application blocklist
        if action.type.lower() in ("open_application", "launch_app", "focus_window"):
            target_app = (action.target or "").lower()
            if any(b_app in target_app for b_app in self.rules.blocked_applications):
                return False, f"Application '{action.target}' is blocked by security policy allowlist."

        # 3. Check filesystem blocked directories
        if action.type.lower() in ("create_file", "write_file", "delete_file", "move_file"):
            target_path = action.target or ""
            for b_dir in self.rules.blocked_directories:
                if target_path.lower().startswith(b_dir.lower()):
                    return False, f"Path '{target_path}' is inside protected directory '{b_dir}'."

        # 4. Check terminal command blocklist
        if action.type.lower() in ("execute_command", "command", "run_terminal"):
            cmd = (action.value or action.target or "").lower()
            for b_cmd in self.rules.blocked_commands:
                if b_cmd in cmd:
                    return False, f"Command '{cmd}' contains blocked shell instruction '{b_cmd}'."

        # 5. Evaluate Risk Tier against SecurityGate
        risk_eval = self.security_gate.classify_action_risk(
            action_type=action.type,
            target=action.target,
            action_payload=action.payload,
        )

        if risk_eval.risk_tier == RiskTier.TIER_0:
            return True, "TIER_0 action auto-permitted."

        # ASSISTED mode forces confirmation on everything except Tier 0
        if self.mode == ControlMode.ASSISTED and not approval_token:
            return False, "ControlMode ASSISTED requires user confirmation token."

        # TIER_1 actions check task approval or token
        if risk_eval.risk_tier == RiskTier.TIER_1:
            if (hasattr(self.security_gate, "_task_approved_tier1") and task_id in self.security_gate._task_approved_tier1) or approval_token or self.mode == ControlMode.TURBO_AUTONOMOUS:
                return True, "TIER_1 action permitted by task approval."
            return False, "TIER_1 action requires task approval or confirmation token."

        # TIER_2 actions require explicit single-use token
        if risk_eval.risk_tier == RiskTier.TIER_2:
            if approval_token and self.security_gate.verify_and_consume_tier2_token(approval_token, action.action_id):
                return True, "TIER_2 action authorized with verified token."
            return False, f"CRITICAL/TIER_2 action ('{action.type}') requires explicit single-use user approval."

        return True, "Permitted"
