"""
MAX OS - Command Risk Classifier (Section 13)
tools/command_classifier.py

Deterministic pattern matcher for terminal command risk classification.
Maps shell commands to RiskLevel (LOW, MEDIUM, HIGH, CRITICAL).
"""
from __future__ import annotations

import re
from core.platform.detector import RiskLevel

_CRITICAL_PATTERNS = [
    # Unix & Destructive
    r"\brm\s+-[rRfF]*\s+/(?:\s|$)",
    r"\bdd\b",
    r"\bmkfs\b",
    r"\bshutdown\b",
    r"\breboot\b",
    r"\bsudo\b",
    r"\bpasswd\b",
    r"\biptables\s+-F\b",
    r">\s*/dev/sd",
    r"curl\b.*\|\s*bash",
    r"wget\b.*\|\s*bash",
    # Windows CRITICAL
    r"\bformat\s+[a-zA-Z]:",
    r"\bdiskpart\b",
    r"\bbcdedit\b",
    r"\bvssadmin\s+delete\b",
    r"\bnetsh\s+advfirewall\s+(?:reset|set)\b",
    r"\bnet\s+localgroup\s+administrators\b",
    r"\breg\s+delete\b",
    r"\bStop-Computer\b",
    r"\bRestart-Computer\b",
    r"\bsc\.exe\s+delete\b",
    r"\bwmic\s+shadowcopy\s+delete\b",
]

_HIGH_PATTERNS = [
    r"\brm\b",
    r"\bchmod\b",
    r"\bchown\b",
    r"\bkill\b",
    r"\bgit\s+push\s+--force\b",
    r"\bsystemctl\b",
    r"\bdel\b",
    r"\brmdir\b",
    r"\brdir\b",
    # Windows HIGH
    r"\bRemove-Item\b",
    r"\bStop-Process\b",
    r"\bSet-ExecutionPolicy\b",
    r"\breg\s+add\b",
    r"\bnetsh\b",
    r"\bnet\s+stop\b",
    r"\btaskkill\b",
]

_MEDIUM_PATTERNS = [
    r"\bgit\s+commit\b",
    r"\bpip\s+install\b",
    r"\bnpm\s+install\b",
    r"\bmkdir\b",
    r"\bmv\b",
    r"\bcp\b",
    # Windows MEDIUM
    r"\bNew-Item\b",
    r"\bCopy-Item\b",
    r"\bMove-Item\b",
    r"\bSet-Content\b",
    r"\bAdd-Content\b",
]

_LOW_PATTERNS = [
    r"^\s*ls\b",
    r"^\s*cat\b",
    r"^\s*git\s+status\b",
    r"^\s*ps\b",
    r"^\s*df\b",
    r"^\s*echo\b",
    r"^\s*dir\b",
    r"^\s*type\b",
    # Windows LOW
    r"^\s*Get-Process\b",
    r"^\s*Get-Service\b",
    r"^\s*Get-Date\b",
    r"^\s*whoami\b",
    r"^\s*hostname\b",
    r"^\s*python\s+--version\b",
]


def classify_command_risk(command: str) -> RiskLevel:
    cmd_strip = command.strip()

    for pattern in _CRITICAL_PATTERNS:
        if re.search(pattern, cmd_strip, re.IGNORECASE):
            return RiskLevel.CRITICAL

    for pattern in _HIGH_PATTERNS:
        if re.search(pattern, cmd_strip, re.IGNORECASE):
            return RiskLevel.HIGH

    for pattern in _MEDIUM_PATTERNS:
        if re.search(pattern, cmd_strip, re.IGNORECASE):
            return RiskLevel.MEDIUM

    for pattern in _LOW_PATTERNS:
        if re.search(pattern, cmd_strip, re.IGNORECASE):
            return RiskLevel.LOW

    # Default unclassified commands to MEDIUM for safety
    return RiskLevel.MEDIUM

