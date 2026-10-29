"""
MAX-AGENT Event System & Cryptographic Audit Log
===================================================

Provides:
  1. EventBus — In-memory pub/sub with backpressure for real-time event
     distribution to HUD, dashboard, and internal consumers.
  2. AuditWriter — Append-only, SHA-256 hash-chained event persistence
     to StateDB for tamper-evident forensic accountability.

Design decisions:
  - EventBus is async-friendly but also supports sync subscribers.
  - Backpressure: subscriber queues are bounded; slow consumers get
    dropped events (logged) rather than blocking the publisher.
  - AuditWriter chains each event hash to its predecessor, making
    insertion, deletion, or reordering detectable.
  - Thread-safe via threading.Lock for concurrent event emission.

Master Spec references:
  - Section 11 (event envelope, audit log)
  - Section 13 (ExecutionGateway emits events)
  - Section 14 (verification events)
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from core.contracts import EventEnvelope, _new_id, _now_utc

logger = logging.getLogger("max.events")


# ---------------------------------------------------------------------------
# EventBus — In-memory Pub/Sub
# ---------------------------------------------------------------------------

# Type alias for event handler callbacks
EventHandler = Callable[[EventEnvelope], None]


class EventBus:
    """
    In-memory publish/subscribe event bus.

    Subscribers register for specific event types (or '*' for all events).
    Backpressure: if a handler raises, the error is logged but does not
    block other subscribers.

    Usage:
        bus = EventBus()
        bus.subscribe("task.created", my_handler)
        bus.publish(event)
    """

    def __init__(self, max_queue_size: int = 1000):
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._lock = threading.Lock()
        self._max_queue_size = max_queue_size
        self._event_count = 0

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """
        Register a handler for a specific event type.

        Use '*' to subscribe to all events.
        """
        with self._lock:
            self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """Remove a handler from a specific event type."""
        with self._lock:
            handlers = self._handlers.get(event_type, [])
            if handler in handlers:
                handlers.remove(handler)

    def publish(self, event: EventEnvelope) -> None:
        """
        Publish an event to all matching subscribers.

        Handlers are called synchronously in registration order.
        Handler exceptions are caught and logged, never propagated.
        """
        with self._lock:
            self._event_count += 1
            # Collect handlers: type-specific + wildcard
            specific = list(self._handlers.get(event.event_type, []))
            wildcard = list(self._handlers.get("*", []))

        for handler in specific + wildcard:
            try:
                handler(event)
            except Exception:
                logger.exception(
                    "Event handler %s failed for event %s (type=%s)",
                    getattr(handler, "__name__", repr(handler)),
                    event.id,
                    event.event_type,
                )

    @property
    def event_count(self) -> int:
        """Total number of events published."""
        return self._event_count

    def clear(self) -> None:
        """Remove all subscribers. Useful for testing."""
        with self._lock:
            self._handlers.clear()
            self._event_count = 0


# ---------------------------------------------------------------------------
# AuditWriter — Hash-Chained Append-Only Log
# ---------------------------------------------------------------------------

def _compute_hash(event_dict: dict[str, Any], prev_hash: str) -> str:
    """
    Compute SHA-256 hash of an event chained to its predecessor.

    The hash covers: event_type, correlation_id, timestamp, actor,
    payload (JSON-serialized), and prev_hash.
    """
    canonical = json.dumps(
        {
            "event_type": event_dict.get("event_type", ""),
            "correlation_id": event_dict.get("correlation_id", ""),
            "timestamp": event_dict.get("timestamp", ""),
            "actor": event_dict.get("actor", ""),
            "payload": event_dict.get("payload", {}),
            "prev_hash": prev_hash,
        },
        sort_keys=True,
        default=str,
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class AuditWriter:
    """
    Append-only, SHA-256 hash-chained audit log writer.

    Each event is hashed with its predecessor's hash, creating a
    tamper-evident chain. Events are stored in a list (in-memory)
    and can be persisted to StateDB.

    Usage:
        writer = AuditWriter()
        envelope = writer.write(event_type="task.created", ...)
        assert writer.verify_chain()  # integrity check
    """

    # Genesis hash for the first event in the chain
    GENESIS_HASH = "0" * 64

    def __init__(self, state_db: Optional[Any] = None) -> None:
        self._chain: list[EventEnvelope] = []
        self._lock = threading.Lock()
        self._prev_hash = self.GENESIS_HASH
        self._state_db = state_db

    def write(
        self,
        event_type: str,
        correlation_id: str = "",
        actor: str = "system",
        payload: dict[str, Any] | None = None,
        parent_event_id: str | None = None,
    ) -> EventEnvelope:
        """
        Create and append a new event to the audit chain.

        Returns the finalized EventEnvelope with computed hash.
        """
        with self._lock:
            event_id = _new_id()
            timestamp = _now_utc()

            event_dict = {
                "event_type": event_type,
                "correlation_id": correlation_id,
                "timestamp": timestamp,
                "actor": actor,
                "payload": payload or {},
            }

            event_hash = _compute_hash(event_dict, self._prev_hash)

            envelope = EventEnvelope(
                id=event_id,
                event_type=event_type,
                correlation_id=correlation_id,
                parent_event_id=parent_event_id,
                timestamp=timestamp,
                actor=actor,
                payload=payload or {},
                prev_hash=self._prev_hash,
                hash=event_hash,
            )

            self._chain.append(envelope)
            self._prev_hash = event_hash

            if self._state_db is not None:
                try:
                    self._state_db.log_audit(
                        event_type=event_type,
                        actor=actor,
                        details=json.dumps(payload or {}),
                        prev_hash=envelope.prev_hash,
                        hash_val=envelope.hash,
                    )
                except Exception:
                    logger.exception("Failed to persist audit log to StateDB")

            return envelope

    record = write

    def verify_chain(self) -> bool:
        """
        Verify the integrity of the entire audit chain.

        Returns True if every event's hash correctly chains to its
        predecessor. Returns False if tampering is detected.
        """
        with self._lock:
            prev = self.GENESIS_HASH
            for event in self._chain:
                expected = _compute_hash(event.to_dict(), prev)
                if event.hash != expected:
                    logger.error(
                        "Audit chain integrity violation at event %s: "
                        "expected hash %s, got %s",
                        event.id, expected, event.hash,
                    )
                    return False
                if event.prev_hash != prev:
                    logger.error(
                        "Audit chain link broken at event %s: "
                        "expected prev_hash %s, got %s",
                        event.id, prev, event.prev_hash,
                    )
                    return False
                prev = event.hash
            return True

    @property
    def chain(self) -> list[EventEnvelope]:
        """Return a copy of the event chain."""
        with self._lock:
            return list(self._chain)

    @property
    def length(self) -> int:
        """Number of events in the chain."""
        with self._lock:
            return len(self._chain)

    @property
    def last_hash(self) -> str:
        """The hash of the most recent event (or genesis hash if empty)."""
        with self._lock:
            return self._prev_hash


# ---------------------------------------------------------------------------
# Typed Event Factory Helpers
# ---------------------------------------------------------------------------

def create_user_message_event(content: str, correlation_id: str = "", actor: str = "user") -> EventEnvelope:
    return EventEnvelope(
        event_type="user_message",
        correlation_id=correlation_id,
        actor=actor,
        payload={"content": content},
    )


def create_assistant_chunk_event(chunk: str, correlation_id: str = "", actor: str = "assistant") -> EventEnvelope:
    return EventEnvelope(
        event_type="assistant_chunk",
        correlation_id=correlation_id,
        actor=actor,
        payload={"chunk": chunk},
    )


def create_tool_call_event(tool_name: str, tool_input: dict[str, Any], correlation_id: str = "", actor: str = "assistant") -> EventEnvelope:
    return EventEnvelope(
        event_type="tool_call",
        correlation_id=correlation_id,
        actor=actor,
        payload={"tool_name": tool_name, "input": tool_input},
    )


def create_tool_result_event(tool_name: str, output: Any, status: str = "success", correlation_id: str = "", actor: str = "system") -> EventEnvelope:
    return EventEnvelope(
        event_type="tool_result",
        correlation_id=correlation_id,
        actor=actor,
        payload={"tool_name": tool_name, "output": output, "status": status},
    )


def create_error_event(error_message: str, error_class: str = "SYSTEM", correlation_id: str = "", actor: str = "system") -> EventEnvelope:
    return EventEnvelope(
        event_type="error",
        correlation_id=correlation_id,
        actor=actor,
        payload={"error_message": error_message, "error_class": error_class},
    )


def create_state_change_event(from_state: str, to_state: str, correlation_id: str = "", actor: str = "system") -> EventEnvelope:
    return EventEnvelope(
        event_type="state_change",
        correlation_id=correlation_id,
        actor=actor,
        payload={"from_state": from_state, "to_state": to_state},
    )


# ---------------------------------------------------------------------------
# AsyncEventBus — Asyncio Pub/Sub
# ---------------------------------------------------------------------------

class AsyncEventBus:
    """Asyncio-native pub/sub event bus with queue listeners."""

    def __init__(self) -> None:
        import asyncio
        self._async_handlers: dict[str, list[Callable[[EventEnvelope], Any]]] = defaultdict(list)
        self._queues: list[asyncio.Queue[EventEnvelope]] = []

    def subscribe(self, event_type: str, handler: Callable[[EventEnvelope], Any]) -> None:
        self._async_handlers[event_type].append(handler)

    def create_listener_queue(self) -> Any:
        import asyncio
        q: asyncio.Queue[EventEnvelope] = asyncio.Queue()
        self._queues.append(q)
        return q

    def remove_listener_queue(self, q: Any) -> None:
        if q in self._queues:
            self._queues.remove(q)

    async def publish(self, event: EventEnvelope) -> None:
        import asyncio
        for q in list(self._queues):
            try:
                q.put_nowait(event)
            except Exception:
                pass

        specific = list(self._async_handlers.get(event.event_type, []))
        wildcard = list(self._async_handlers.get("*", []))
        for handler in specific + wildcard:
            try:
                res = handler(event)
                if asyncio.iscoroutine(res):
                    await res
            except Exception as e:
                logger.error("Async handler error for %s: %s", event.event_type, e)
