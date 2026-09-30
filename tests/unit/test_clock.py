"""
Unit tests for core/clock.py — Injectable Clock.
"""

import unittest
from datetime import datetime, timezone, timedelta
from core.clock import SystemClock, FakeClock, Clock


class TestSystemClock(unittest.TestCase):
    """SystemClock returns real wall time."""

    def test_now_returns_utc(self):
        clock = SystemClock()
        now = clock.now()
        self.assertIsNotNone(now.tzinfo)
        self.assertEqual(now.tzinfo, timezone.utc)

    def test_now_is_recent(self):
        clock = SystemClock()
        now = clock.now()
        diff = abs((datetime.now(timezone.utc) - now).total_seconds())
        self.assertLess(diff, 2.0)

    def test_monotonic_increases(self):
        clock = SystemClock()
        a = clock.monotonic()
        b = clock.monotonic()
        self.assertGreaterEqual(b, a)

    def test_conforms_to_protocol(self):
        self.assertIsInstance(SystemClock(), Clock)


class TestFakeClock(unittest.TestCase):
    """FakeClock provides deterministic time control."""

    def test_default_start(self):
        clock = FakeClock()
        self.assertEqual(clock.now().year, 2026)
        self.assertEqual(clock.now().month, 1)

    def test_custom_start(self):
        start = datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)
        clock = FakeClock(start)
        self.assertEqual(clock.now(), start)

    def test_advance_seconds(self):
        start = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
        clock = FakeClock(start)
        clock.advance(seconds=60)
        self.assertEqual(clock.now(), start + timedelta(seconds=60))

    def test_advance_minutes(self):
        start = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
        clock = FakeClock(start)
        clock.advance(minutes=5)
        self.assertEqual(clock.now(), start + timedelta(minutes=5))

    def test_advance_combined(self):
        start = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
        clock = FakeClock(start)
        result = clock.advance(hours=1, minutes=30, seconds=15)
        expected = start + timedelta(hours=1, minutes=30, seconds=15)
        self.assertEqual(result, expected)
        self.assertEqual(clock.now(), expected)

    def test_monotonic_advances_with_time(self):
        clock = FakeClock()
        m1 = clock.monotonic()
        clock.advance(seconds=30)
        m2 = clock.monotonic()
        self.assertAlmostEqual(m2 - m1, 30.0)

    def test_set_time(self):
        clock = FakeClock()
        target = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)
        clock.set_time(target)
        self.assertEqual(clock.now(), target)

    def test_set_time_adds_tzinfo(self):
        clock = FakeClock()
        naive = datetime(2026, 6, 15, 12, 0)
        clock.set_time(naive)
        self.assertIsNotNone(clock.now().tzinfo)

    def test_conforms_to_protocol(self):
        self.assertIsInstance(FakeClock(), Clock)


if __name__ == "__main__":
    unittest.main()
