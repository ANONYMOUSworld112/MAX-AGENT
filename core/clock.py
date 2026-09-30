"""
MAX-AGENT Injectable Clock
============================

Abstracts time access so that task deadlines, scheduler aging, TTL
expirations, and DST handling can be tested deterministically.

Usage (production):
    clock = SystemClock()
    now = clock.now()

Usage (tests):
    clock = FakeClock(datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc))
    clock.advance(seconds=60)  # now is 09:01
    clock.advance(minutes=5)   # now is 09:06

Master Spec references:
    - Section 8 (task deadlines, TTL)
    - Section 7 (reminder scheduling, DST)
    - Section 27 (deterministic test infrastructure)
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Protocol, runtime_checkable


@runtime_checkable
class Clock(Protocol):
    """Protocol for time providers."""

    def now(self) -> datetime:
        """Return the current time as a timezone-aware datetime (UTC)."""
        ...

    def monotonic(self) -> float:
        """Return a monotonic clock value in seconds (for elapsed time)."""
        ...


class SystemClock:
    """Production clock backed by the real system time."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)

    def monotonic(self) -> float:
        return time.monotonic()


class FakeClock:
    """
    Deterministic clock for testing.

    Allows manual time control:
        fake = FakeClock(start)
        fake.advance(seconds=30)
        fake.set_time(specific_datetime)
    """

    def __init__(self, start: datetime | None = None):
        if start is None:
            start = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        self._current = start
        self._monotonic_base = 0.0
        self._monotonic_offset = 0.0

    def now(self) -> datetime:
        return self._current

    def monotonic(self) -> float:
        return self._monotonic_base + self._monotonic_offset

    def advance(
        self,
        *,
        seconds: float = 0,
        minutes: float = 0,
        hours: float = 0,
        days: float = 0,
    ) -> datetime:
        """
        Advance the clock by the specified duration.

        Returns the new current time.
        """
        delta = timedelta(
            seconds=seconds,
            minutes=minutes,
            hours=hours,
            days=days,
        )
        total_seconds = delta.total_seconds()
        self._current += delta
        self._monotonic_offset += total_seconds
        return self._current

    def set_time(self, dt: datetime) -> None:
        """
        Set the clock to a specific datetime.

        The monotonic clock advances by the difference.
        """
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        diff = (dt - self._current).total_seconds()
        self._current = dt
        self._monotonic_offset += max(0.0, diff)
