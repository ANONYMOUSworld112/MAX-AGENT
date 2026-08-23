"""
MAX OS - Observability Logging Setup
core/logging_setup.py
"""
from __future__ import annotations

import json
import logging
import logging.handlers
import os
from datetime import datetime, timezone
from typing import Any, Optional

LOG_CHANNELS = ("execution", "agent", "tool", "error", "security", "memory", "model")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "channel": record.name,
            "level": record.levelname,
            "message": record.getMessage(),
        }
        extra = getattr(record, "extra_fields", None)
        if extra:
            payload.update(extra)
        return json.dumps(payload, default=str)


def setup_logging(log_dir: str = "logs") -> dict[str, logging.Logger]:
    os.makedirs(log_dir, exist_ok=True)
    loggers = {}
    for channel in LOG_CHANNELS:
        logger = logging.getLogger(f"max_os.{channel}")
        logger.setLevel(logging.INFO)
        handler = logging.handlers.RotatingFileHandler(
            os.path.join(log_dir, f"{channel}.log"), maxBytes=5_000_000, backupCount=3
        )
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.propagate = False
        loggers[channel] = logger
    return loggers


def log_action(
    logger: logging.Logger,
    *,
    task_id: str,
    agent: str,
    tool: Optional[str],
    action: str,
    result: Any,
    duration_ms: float,
    risk: str,
    permission: Optional[str],
    verified: Optional[bool],
) -> None:
    logger.info(
        action,
        extra={
            "extra_fields": {
                "task_id": task_id,
                "agent": agent,
                "tool": tool,
                "result": str(result)[:500],
                "duration_ms": duration_ms,
                "risk": risk,
                "permission": permission,
                "verified": verified,
            }
        },
    )
