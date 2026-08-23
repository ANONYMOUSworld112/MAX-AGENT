"""
MAX OS - Event Bus
core/event_bus.py
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List


class EventType(str, Enum):
    APP_OPENED = "APP_OPENED"
    APP_CLOSED = "APP_CLOSED"
    WINDOW_CHANGED = "WINDOW_CHANGED"
    SCREEN_CHANGED = "SCREEN_CHANGED"
    TASK_STARTED = "TASK_STARTED"
    TASK_COMPLETED = "TASK_COMPLETED"
    TASK_FAILED = "TASK_FAILED"
    FILE_CREATED = "FILE_CREATED"
    FILE_CHANGED = "FILE_CHANGED"
    DOWNLOAD_COMPLETED = "DOWNLOAD_COMPLETED"
    NETWORK_CHANGED = "NETWORK_CHANGED"
    BATTERY_CHANGED = "BATTERY_CHANGED"
    USER_SPEAKING = "USER_SPEAKING"
    USER_STOPPED = "USER_STOPPED"
    AGENT_STATUS_CHANGED = "AGENT_STATUS_CHANGED"


@dataclass
class Event:
    type: EventType
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


Subscriber = Callable[[Event], None]


class EventBus:
    def __init__(self) -> None:
        self._subscribers: Dict[EventType, List[Subscriber]] = defaultdict(list)
        self._history: List[Event] = []
        self._max_history = 1000

    def subscribe(self, event_type: EventType, callback: Subscriber) -> None:
        self._subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: EventType, callback: Subscriber) -> None:
        if callback in self._subscribers[event_type]:
            self._subscribers[event_type].remove(callback)

    def publish(self, event: Event) -> None:
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history.pop(0)
        for callback in self._subscribers.get(event.type, []):
            callback(event)

    def history(self, event_type: EventType | None = None) -> List[Event]:
        if event_type is None:
            return list(self._history)
        return [e for e in self._history if e.type == event_type]
