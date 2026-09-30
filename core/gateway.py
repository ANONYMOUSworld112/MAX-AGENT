"""
MAX-AGENT Execution Gateway
==============================

The single choke point for ALL side-effect execution in MAX.

Every action that modifies the host operating system, filesystem,
network, or user-facing state MUST pass through this gateway.

Pipeline:
  1. Validate ActionRequest schema
  2. Compute risk tier via PolicyEngine
  3. Check confirmation status (auto / HUD / typed phrase / rejected)
  4. Execute with timeout
  5. Capture ActionResult
  6. Emit audit event via AuditWriter

Design decisions:
  - Gateway does NOT execute actions itself; it delegates to registered
    action handlers after policy clearance.
  - If confirmation is required and not yet granted, the gateway returns
    a PENDING result that the caller must resolve via HUD/UI.
  - The gateway never catches and swallows exceptions silently.
  - Thread-safe: multiple tasks can submit requests concurrently.

Master Spec references:
  - Section 13 (ExecutionGateway contract)
  - Section 1-S2 (single choke point)
"""

from __future__ import annotations

import logging
import time
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from core.contracts import (
    ActionRequest,
    ActionResult,
    ErrorClass,
    RiskLevel,
    VerificationOutcome,
    _new_id,
    _now_utc,
)
from core.policy import PolicyEngine, PolicyDecision, ConfirmationType
from core.events import EventBus, AuditWriter, EventEnvelope
from core.verification.engine import VerificationEngine

logger = logging.getLogger("max.gateway")


# ---------------------------------------------------------------------------
# Action Handler Protocol
# ---------------------------------------------------------------------------

# Action handlers are callables: (action_name, parameters) -> dict
ActionHandler = Callable[[str, dict[str, Any]], dict[str, Any]]


class ExecutionGatewayError(Exception):
    """Base exception for gateway errors."""
    pass


class ActionNotRegisteredError(ExecutionGatewayError):
    """Raised when an action has no registered handler."""
    pass


class PolicyRejectionError(ExecutionGatewayError):
    """Raised when policy rejects an action."""
    pass


class ConfirmationRequiredError(ExecutionGatewayError):
    """Raised when human confirmation is needed before execution."""

    def __init__(self, decision: PolicyDecision):
        self.decision = decision
        super().__init__(
            f"Confirmation required for '{decision.action}': "
            f"{decision.confirmation.value} (risk={decision.risk_level.value})"
        )


class ExecutionTimeoutError(ExecutionGatewayError):
    """Raised when action execution exceeds its timeout."""
    pass


# ---------------------------------------------------------------------------
# Confirmation State Tracker
# ---------------------------------------------------------------------------

class ConfirmationTracker:
    """
    Tracks which ActionRequests have been confirmed by the user.

    Confirmations are one-time tokens: once consumed, they are removed.
    """

    def __init__(self):
        self._confirmed: dict[str, bool] = {}
        self._lock = threading.Lock()

    def grant(self, request_id: str) -> None:
        """Mark a request as confirmed."""
        with self._lock:
            self._confirmed[request_id] = True

    def is_confirmed(self, request_id: str) -> bool:
        """Check if a request has been confirmed."""
        with self._lock:
            return self._confirmed.get(request_id, False)

    def consume(self, request_id: str) -> bool:
        """Check and consume a confirmation (one-time use)."""
        with self._lock:
            if self._confirmed.pop(request_id, False):
                return True
            return False


# ---------------------------------------------------------------------------
# Execution Gateway
# ---------------------------------------------------------------------------

class ExecutionGateway:
    """
    The single choke point for all side-effect execution.

    Usage:
        gateway = ExecutionGateway(policy=policy, event_bus=bus, audit=audit)
        gateway.register_handler("open_app", open_app_handler)
        result = gateway.execute(action_request)

    If confirmation is required:
        try:
            result = gateway.execute(request)
        except ConfirmationRequiredError as e:
            # Show confirmation UI, then:
            gateway.confirm(request.id)
            result = gateway.execute(request)  # Now executes
    """

    def __init__(
        self,
        policy: PolicyEngine | None = None,
        event_bus: EventBus | None = None,
        audit: AuditWriter | None = None,
        verification_engine: VerificationEngine | None = None,
        max_workers: int = 4,
        default_timeout: float = 30.0,
    ):
        self._policy = policy or PolicyEngine()
        self._event_bus = event_bus or EventBus()
        self._audit = audit or AuditWriter()
        self._verification_engine = verification_engine or VerificationEngine()
        self._handlers: dict[str, ActionHandler] = {}
        self._confirmations = ConfirmationTracker()
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._default_timeout = default_timeout
        self._lock = threading.Lock()
        self._execution_count = 0

    def register_handler(self, action: str, handler: ActionHandler) -> None:
        """Register an action handler."""
        with self._lock:
            self._handlers[action] = handler

    def has_handler(self, action: str) -> bool:
        """Check if an action has a registered handler."""
        return action in self._handlers

    def confirm(self, request_id: str) -> None:
        """Grant confirmation for a pending request."""
        self._confirmations.grant(request_id)

    def execute(self, request: ActionRequest) -> ActionResult:
        """
        Execute an action through the full policy pipeline.

        Pipeline:
          1. Validate handler exists
          2. Evaluate policy (risk + confirmation)
          3. Check/require confirmation
          4. Execute with timeout
          5. Post-execution verification via VerificationEngine
          6. Record audit event
          7. Return result
        """
        start_time = time.monotonic()
        action = request.action

        # Step 1: Check handler exists
        handler = self._handlers.get(action)
        if handler is None:
            self._emit_event("action.rejected", request, reason="No handler registered")
            raise ActionNotRegisteredError(
                f"No handler registered for action '{action}'"
            )

        # Step 2: Evaluate policy
        decision = self._policy.evaluate(request)

        # Step 3: Check if action is allowed
        if not decision.is_allowed:
            self._emit_event("action.rejected", request, reason=decision.reason)
            raise PolicyRejectionError(decision.reason)

        # Step 4: Check confirmation requirement
        if decision.confirmation in (ConfirmationType.HUD_BUTTON, ConfirmationType.TYPED_PHRASE):
            if not self._confirmations.consume(request.id):
                self._emit_event("action.confirmation_required", request, reason=decision.reason)
                raise ConfirmationRequiredError(decision)

        # Step 5: Execute with timeout
        timeout = min(request.timeout_seconds, decision.max_timeout_seconds)
        self._emit_event("action.started", request)

        try:
            future = self._executor.submit(handler, action, request.parameters)
            output = future.result(timeout=timeout)
            duration_ms = (time.monotonic() - start_time) * 1000

            with self._lock:
                self._execution_count += 1

            # Step 6: Post-execution verification
            v_report = self._verification_engine.verify_action(request, output)
            verified_success = (v_report.outcome == VerificationOutcome.SUCCESS)

            result = ActionResult(
                request_id=request.id,
                task_id=request.task_id,
                success=verified_success,
                output=output if isinstance(output, dict) else {"result": str(output)},
                verification_outcome=v_report.outcome,
                duration_ms=duration_ms,
                error_class=None if verified_success else ErrorClass.LOGIC,
                error_message=None if verified_success else f"Post-execution verification failed: {v_report.errors}",
            )

            if verified_success:
                self._emit_event("action.completed", request, result=result)
            else:
                self._emit_event("action.verification_failed", request, result=result)
            return result

        except FuturesTimeoutError:
            duration_ms = (time.monotonic() - start_time) * 1000
            result = ActionResult(
                request_id=request.id,
                task_id=request.task_id,
                success=False,
                error_class=ErrorClass.TRANSIENT,
                error_message=f"Action '{action}' timed out after {timeout}s",
                verification_outcome=VerificationOutcome.FAILURE,
                duration_ms=duration_ms,
            )
            self._emit_event("action.timeout", request, result=result)
            raise ExecutionTimeoutError(
                f"Action '{action}' exceeded timeout of {timeout}s"
            ) from None

        except Exception as exc:
            duration_ms = (time.monotonic() - start_time) * 1000
            result = ActionResult(
                request_id=request.id,
                task_id=request.task_id,
                success=False,
                error_class=ErrorClass.LOGIC,
                error_message=str(exc),
                verification_outcome=VerificationOutcome.FAILURE,
                duration_ms=duration_ms,
            )
            self._emit_event("action.failed", request, result=result, error=str(exc))
            return result

    @property
    def execution_count(self) -> int:
        """Total number of successful executions."""
        return self._execution_count

    def _emit_event(
        self,
        event_type: str,
        request: ActionRequest,
        *,
        reason: str = "",
        result: ActionResult | None = None,
        error: str = "",
    ) -> None:
        """Emit an audit event and publish to event bus."""
        payload = {
            "action": request.action,
            "parameters": request.parameters,
            "risk_level": request.risk_level.value,
            "channel_trust": request.channel_trust.value,
        }
        if reason:
            payload["reason"] = reason
        if result:
            payload["success"] = result.success
            payload["duration_ms"] = result.duration_ms
        if error:
            payload["error"] = error

        envelope = self._audit.write(
            event_type=event_type,
            correlation_id=request.task_id,
            actor="gateway",
            payload=payload,
        )
        self._event_bus.publish(envelope)

    def shutdown(self) -> None:
        """Shutdown the thread pool executor."""
        self._executor.shutdown(wait=False)
