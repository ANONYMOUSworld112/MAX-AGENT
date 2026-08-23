"""
MAX OS — Centralized Audit Logger & Secret Redaction Engine (Section 23)
core/audit/audit_logger.py

Formats and records structured audit logs with automatic secret redaction for
passwords, API keys, tokens, bearer headers, and private keys.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

REDACT_PATTERNS = [
    re.compile(r"(?:password|passwd|pwd)[\s=:]+([^\s,;]+)", re.IGNORECASE),
    re.compile(r"(?:api[_\-]?key|secret|token)[\s=:]+([^\s,;]+)", re.IGNORECASE),
    re.compile(r"bearer\s+([a-zA-Z0-9\-\._~\+\/]+=*)", re.IGNORECASE),
    re.compile(r"-----BEGIN\s+PRIVATE\s+KEY-----[\s\S]+?-----END\s+PRIVATE\s+KEY-----", re.IGNORECASE),
]


def redact_secrets(data: Any) -> Any:
    """
    Recursively redacts sensitive values (passwords, tokens, keys) in data structures.
    """
    if isinstance(data, str):
        redacted = data
        for pat in REDACT_PATTERNS:
            redacted = pat.sub("[REDACTED_SECRET]", redacted)
        return redacted
    elif isinstance(data, dict):
        new_dict = {}
        for k, v in data.items():
            if any(sens in str(k).lower() for sens in ("password", "passwd", "secret", "token", "api_key", "private_key", "credentials")):
                new_dict[k] = "[REDACTED_SECRET]"
            else:
                new_dict[k] = redact_secrets(v)
        return new_dict
    elif isinstance(data, list):
        return [redact_secrets(item) for item in data]
    return data


@dataclass
class AuditEvent:
    event_id: str
    timestamp: float
    event_type: str  # USER_REQUEST, PLAN, ACTION, RISK_DECISION, CONFIRMATION, AGENT, TOOL, OBSERVATION, VERIFICATION, RESULT, RECOVERY, ROLLBACK, RESPONSE
    task_id: str
    agent_id: str
    action_id: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    risk_level: str = "LOW"
    status: str = "SUCCESS"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return redact_secrets(d)


class AuditLogger:
    """
    Central machine-readable audit logger persisting to structured JSONL logs.
    """

    def __init__(self, log_dir: Optional[str | Path] = None):
        self.log_dir = Path(log_dir) if log_dir else Path(__file__).parent.parent.parent / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / "max_audit.jsonl"
        self._logger = logging.getLogger("max.audit")

    def log_event(
        self,
        event_type: str,
        task_id: str,
        agent_id: str,
        payload: Dict[str, Any],
        action_id: str = "",
        risk_level: str = "LOW",
        status: str = "SUCCESS",
    ) -> AuditEvent:
        import uuid
        event = AuditEvent(
            event_id=f"evt_{uuid.uuid4().hex[:8]}",
            timestamp=time.time(),
            event_type=event_type,
            task_id=task_id,
            agent_id=agent_id,
            action_id=action_id,
            payload=payload,
            risk_level=risk_level,
            status=status,
        )

        event_dict = event.to_dict()
        line = json.dumps(event_dict)

        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception as e:
            self._logger.error(f"Failed writing audit log event: {e}")

        return event
