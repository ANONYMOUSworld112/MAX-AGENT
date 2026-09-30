"""
MAX-AGENT Core Data Contracts
==============================

Immutable data models for the MAX task lifecycle.

These contracts define the canonical types exchanged between:
  InputGateway → IntentEngine → TaskPlanner → TaskGraph →
  AgentRouter → ExecutionGateway → VerificationEngine → AuditLog

Design decisions:
  - dataclass(frozen=True) for immutability after construction.
  - All IDs are UUIDs (str) to avoid int(time.time()) collisions
    found in the old task_fsm.py.
  - Enums use UPPER_SNAKE for machine processing; .label property
    for human-readable display.
  - JSON round-trip via to_dict() / from_dict() class methods.
  - No external dependencies beyond stdlib.

Master Spec references:
  - Section 6  (component list)
  - Section 8  (task state machine — see state_machine.py)
  - Section 13 (ExecutionGateway contract)
  - Section 14 (verification outcomes)
"""

from __future__ import annotations

import uuid
import enum
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Optional, Sequence


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class RiskLevel(enum.Enum):
    """Action risk classification (Master Spec Section 13)."""
    LOW = "LOW"                   # Read-only queries, status inspection
    MEDIUM = "MEDIUM"             # Package installs, project modifications
    HIGH = "HIGH"                 # File deletion, process termination
    CRITICAL = "CRITICAL"         # Irreversible OS modifications
    PROHIBITED = "PROHIBITED"     # Always rejected (e.g., format C:)

    @property
    def label(self) -> str:
        return self.value


class ChannelTrust(enum.Enum):
    """Input channel trust level (Master Spec Section 5)."""
    TRUSTED = "TRUSTED"           # Owner keyboard / local HUD
    SEMI_TRUSTED = "SEMI_TRUSTED" # Voice input (mic)
    UNTRUSTED = "UNTRUSTED"       # Screen OCR, web content, LLM output


class TaskStatus(enum.Enum):
    """
    14-state task lifecycle (Master Spec Section 8).

    Terminal states: COMPLETED, FAILED, CANCELLED, EXPIRED.
    See state_machine.py for the transition table.
    """
    CREATED = "CREATED"
    PLANNED = "PLANNED"
    QUEUED = "QUEUED"
    BLOCKED = "BLOCKED"
    RUNNING = "RUNNING"
    VERIFYING = "VERIFYING"
    RETRYING = "RETRYING"
    PAUSED = "PAUSED"
    CANCELLING = "CANCELLING"
    INTERRUPTED = "INTERRUPTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"

    @property
    def is_terminal(self) -> bool:
        return self in (
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
            TaskStatus.EXPIRED,
        )


class BlockedReason(enum.Enum):
    """Why a task is in BLOCKED state (Master Spec Section 8)."""
    DEPENDENCY = "DEPENDENCY"       # Waiting on upstream task
    RESOURCE = "RESOURCE"           # Resource lease unavailable
    SCHEDULE = "SCHEDULE"           # Scheduled for future time
    USER_INPUT = "USER_INPUT"       # Awaiting user clarification
    CONFIRMATION = "CONFIRMATION"   # Awaiting human approval


class VerificationOutcome(enum.Enum):
    """
    Verification result vocabulary (Master Spec Section 14).

    UNKNOWN is NEVER treated as SUCCESS.
    """
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    UNKNOWN = "UNKNOWN"


class ErrorClass(enum.Enum):
    """Error classification for recovery decisions (Master Spec Section 15)."""
    TRANSIENT = "TRANSIENT"         # Network timeout, temporary lock
    ENVIRONMENT = "ENVIRONMENT"     # Missing dependency, wrong OS
    LOGIC = "LOGIC"                 # Bug in agent/tool logic
    RESOURCE = "RESOURCE"           # Disk full, OOM
    EXTERNAL = "EXTERNAL"           # Third-party API failure
    SECURITY = "SECURITY"           # Policy violation detected


class IdempotencyClass(enum.Enum):
    """Action idempotency for retry/recovery safety."""
    IDEMPOTENT = "IDEMPOTENT"           # Safe to retry (e.g., read file)
    CONDITIONALLY_IDEMPOTENT = "CONDITIONALLY_IDEMPOTENT"  # Safe if precondition re-checked
    NON_IDEMPOTENT = "NON_IDEMPOTENT"   # Dangerous to retry (e.g., send email)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _new_id() -> str:
    """Generate a collision-free UUID4 string."""
    return str(uuid.uuid4())


def _now_utc() -> str:
    """ISO-8601 timestamp in UTC."""
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Core Data Contracts
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TaskIntent:
    """
    The parsed, validated representation of what the user wants.

    Produced by the IntentEngine from raw input.
    """
    id: str = field(default_factory=_new_id)
    raw_input: str = ""
    action: str = ""                         # Canonical action name
    target: str = ""                         # Primary target (app name, file, etc.)
    parameters: dict[str, Any] = field(default_factory=dict)
    channel: ChannelTrust = ChannelTrust.UNTRUSTED
    origin: str = ""                         # "voice", "text", "hud", "dashboard", "api"
    timestamp: str = field(default_factory=_now_utc)
    is_compound: bool = False                # True if multi-step decomposition needed

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["channel"] = self.channel.value
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskIntent:
        data = dict(data)  # shallow copy
        if "channel" in data and isinstance(data["channel"], str):
            data["channel"] = ChannelTrust(data["channel"])
        return cls(**data)


@dataclass
class Task:
    """
    A concrete unit of work tracked through the 14-state lifecycle.

    Mutable: status and metadata change as the task progresses.
    """
    id: str = field(default_factory=_new_id)
    intent_id: str = ""                      # FK to TaskIntent.id
    parent_task_id: Optional[str] = None     # For subtasks in a TaskGraph
    status: TaskStatus = TaskStatus.CREATED
    blocked_reason: Optional[BlockedReason] = None
    action: str = ""
    target: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    risk_level: RiskLevel = RiskLevel.LOW
    assigned_agent: Optional[str] = None
    assigned_worker: Optional[str] = None
    resources_required: list[str] = field(default_factory=list)
    resources_held: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=_now_utc)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    verification_outcome: Optional[VerificationOutcome] = None
    verification_evidence: dict[str, Any] = field(default_factory=dict)
    error_class: Optional[ErrorClass] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    result: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        d["risk_level"] = self.risk_level.value
        if self.blocked_reason:
            d["blocked_reason"] = self.blocked_reason.value
        if self.verification_outcome:
            d["verification_outcome"] = self.verification_outcome.value
        if self.error_class:
            d["error_class"] = self.error_class.value
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Task:
        data = dict(data)
        if "status" in data and isinstance(data["status"], str):
            data["status"] = TaskStatus(data["status"])
        if "risk_level" in data and isinstance(data["risk_level"], str):
            data["risk_level"] = RiskLevel(data["risk_level"])
        if data.get("blocked_reason") and isinstance(data["blocked_reason"], str):
            data["blocked_reason"] = BlockedReason(data["blocked_reason"])
        if data.get("verification_outcome") and isinstance(data["verification_outcome"], str):
            data["verification_outcome"] = VerificationOutcome(data["verification_outcome"])
        if data.get("error_class") and isinstance(data["error_class"], str):
            data["error_class"] = ErrorClass(data["error_class"])
        return cls(**data)


@dataclass(frozen=True)
class ActionRequest:
    """
    A request to execute a side-effect, submitted to the ExecutionGateway.

    The gateway validates, risk-checks, and applies confirmation before executing.
    """
    id: str = field(default_factory=_new_id)
    task_id: str = ""                        # FK to Task.id
    action: str = ""                         # Canonical action name
    parameters: dict[str, Any] = field(default_factory=dict)
    risk_level: RiskLevel = RiskLevel.LOW
    idempotency: IdempotencyClass = IdempotencyClass.NON_IDEMPOTENT
    required_resources: list[str] = field(default_factory=list)
    timeout_seconds: float = 30.0
    channel_trust: ChannelTrust = ChannelTrust.UNTRUSTED
    timestamp: str = field(default_factory=_now_utc)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["risk_level"] = self.risk_level.value
        d["idempotency"] = self.idempotency.value
        d["channel_trust"] = self.channel_trust.value
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ActionRequest:
        data = dict(data)
        if "risk_level" in data and isinstance(data["risk_level"], str):
            data["risk_level"] = RiskLevel(data["risk_level"])
        if "idempotency" in data and isinstance(data["idempotency"], str):
            data["idempotency"] = IdempotencyClass(data["idempotency"])
        if "channel_trust" in data and isinstance(data["channel_trust"], str):
            data["channel_trust"] = ChannelTrust(data["channel_trust"])
        return cls(**data)


@dataclass(frozen=True)
class ActionResult:
    """
    The outcome of an executed ActionRequest.

    Produced by the ExecutionGateway after execution and verification.
    """
    id: str = field(default_factory=_new_id)
    request_id: str = ""                     # FK to ActionRequest.id
    task_id: str = ""                        # FK to Task.id
    success: bool = False
    output: dict[str, Any] = field(default_factory=dict)
    error_class: Optional[ErrorClass] = None
    error_message: Optional[str] = None
    verification_outcome: VerificationOutcome = VerificationOutcome.UNKNOWN
    verification_evidence: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0
    timestamp: str = field(default_factory=_now_utc)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["verification_outcome"] = self.verification_outcome.value
        if self.error_class:
            d["error_class"] = self.error_class.value
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ActionResult:
        data = dict(data)
        if "verification_outcome" in data and isinstance(data["verification_outcome"], str):
            data["verification_outcome"] = VerificationOutcome(data["verification_outcome"])
        if data.get("error_class") and isinstance(data["error_class"], str):
            data["error_class"] = ErrorClass(data["error_class"])
        return cls(**data)


@dataclass(frozen=True)
class EventEnvelope:
    """
    A structured event record for the append-only audit log.

    Every event is hash-chained to its predecessor for tamper detection.
    """
    id: str = field(default_factory=_new_id)
    event_type: str = ""                     # e.g., "task.created", "action.executed"
    correlation_id: str = ""                 # Groups related events (usually task_id)
    parent_event_id: Optional[str] = None
    timestamp: str = field(default_factory=_now_utc)
    actor: str = ""                          # "system", "user", agent name, worker name
    payload: dict[str, Any] = field(default_factory=dict)
    prev_hash: str = ""                      # SHA-256 of previous event
    hash: str = ""                           # SHA-256 of this event

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EventEnvelope:
        return cls(**data)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Routing Decision Record (for explainability)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RoutingDecision:
    """
    Audit record explaining why a particular agent/worker was chosen.

    Master Spec Section 10 requires every routing decision to be logged.
    """
    id: str = field(default_factory=_new_id)
    task_id: str = ""
    intent_action: str = ""
    candidates: list[str] = field(default_factory=list)
    selected: str = ""
    reason: str = ""
    capability_match_score: float = 0.0
    circuit_breaker_status: dict[str, str] = field(default_factory=dict)
    resource_availability: dict[str, bool] = field(default_factory=dict)
    timestamp: str = field(default_factory=_now_utc)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RoutingDecision:
        return cls(**data)
