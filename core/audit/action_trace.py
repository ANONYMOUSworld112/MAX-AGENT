"""
MAX OS — Action Trace Collector (Section 23)
core/audit/action_trace.py

Captures end-to-end action execution timelines:
USER_REQUEST -> PLAN -> ACTION -> RISK_DECISION -> CONFIRMATION -> AGENT -> TOOL -> SYSTEM_ACTION -> OBSERVATION -> VERIFICATION -> RESULT -> RECOVERY -> ROLLBACK -> FINAL_RESPONSE.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.audit.audit_logger import AuditEvent, AuditLogger, redact_secrets
from core.audit.event_store import EventStore


@dataclass
class ActionTrace:
    task_id: str
    plan_id: str
    user_request: str
    events: List[AuditEvent] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    final_status: str = "PENDING"

    def record_step(
        self,
        event_type: str,
        agent_id: str,
        payload: Dict[str, Any],
        action_id: str = "",
        risk_level: str = "LOW",
        status: str = "SUCCESS",
    ) -> AuditEvent:
        event = AuditEvent(
            event_id=f"evt_{len(self.events) + 1}",
            timestamp=time.time(),
            event_type=event_type,
            task_id=self.task_id,
            agent_id=agent_id,
            action_id=action_id,
            payload=payload,
            risk_level=risk_level,
            status=status,
        )
        self.events.append(event)
        return event


class ActionTraceCollector:
    """
    Manages active action traces across task execution timelines.
    """

    def __init__(self, logger: Optional[AuditLogger] = None, store: Optional[EventStore] = None):
        self.logger = logger or AuditLogger()
        self.store = store or EventStore()
        self._traces: Dict[str, ActionTrace] = {}

    def start_trace(self, task_id: str, plan_id: str, user_request: str) -> ActionTrace:
        trace = ActionTrace(task_id=task_id, plan_id=plan_id, user_request=user_request)
        self._traces[task_id] = trace
        self.logger.log_event("USER_REQUEST", task_id, "user", {"request": user_request})
        return trace

    def record_event(
        self,
        task_id: str,
        event_type: str,
        agent_id: str,
        payload: Dict[str, Any],
        action_id: str = "",
        risk_level: str = "LOW",
        status: str = "SUCCESS",
    ) -> Optional[AuditEvent]:
        trace = self._traces.get(task_id)
        evt = self.logger.log_event(event_type, task_id, agent_id, payload, action_id, risk_level, status)
        try:
            self.store.store_event(evt)
        except Exception:
            pass
        if trace:
            trace.events.append(evt)
        return evt
