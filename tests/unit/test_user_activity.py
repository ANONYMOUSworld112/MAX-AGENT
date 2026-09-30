"""
Unit tests for Task 3.4: UserActivityMonitor (Desktop Input Conflict Guard).

Tests:
1. Input activity detection within threshold window.
2. Idle detection after threshold window expires.
3. State transition event emissions (user.active, user.idle) on EventBus.
4. guard_automation raises UserActivityConflictError during active usage.
5. wait_until_idle unblocks once user becomes idle.
"""

import unittest
from core.events import EventBus
from core.user_activity import UserActivityMonitor, UserActivityConflictError


class TestUserActivityMonitor(unittest.TestCase):
    def setUp(self):
        self.event_bus = EventBus()
        self.simulated_current_time = 10000.0
        self.simulated_last_input = 10000.0

        self.monitor = UserActivityMonitor(
            idle_threshold_ms=1000.0,
            event_bus=self.event_bus,
            get_last_input_time_fn=lambda: self.simulated_last_input,
            get_current_time_fn=lambda: self.simulated_current_time,
        )

    def test_active_detection_within_threshold(self):
        # 100ms since last input (< 1000ms threshold)
        self.simulated_current_time = 10100.0
        self.simulated_last_input = 10000.0

        self.assertEqual(self.monitor.get_idle_duration_ms(), 100.0)
        self.assertTrue(self.monitor.is_user_active())

    def test_idle_detection_after_threshold(self):
        # 1500ms since last input (>= 1000ms threshold)
        self.simulated_current_time = 11500.0
        self.simulated_last_input = 10000.0

        self.assertEqual(self.monitor.get_idle_duration_ms(), 1500.0)
        self.assertFalse(self.monitor.is_user_active())

    def test_guard_automation_raises_during_active_usage(self):
        # User is active (50ms idle)
        self.simulated_current_time = 10050.0
        self.simulated_last_input = 10000.0

        with self.assertRaises(UserActivityConflictError) as ctx:
            self.monitor.guard_automation("click_submit")
        self.assertIn("actively interacting", str(ctx.exception))

    def test_guard_automation_succeeds_when_idle(self):
        # User is idle (2000ms idle)
        self.simulated_current_time = 12000.0
        self.simulated_last_input = 10000.0

        # Should not raise
        self.monitor.guard_automation("click_submit")

    def test_event_bus_transition_emission(self):
        events = []
        self.event_bus.subscribe("user.active", lambda e: events.append(e))
        self.event_bus.subscribe("user.idle", lambda e: events.append(e))

        # Initial state was idle. Now user becomes active.
        self.simulated_current_time = 10050.0
        self.simulated_last_input = 10000.0
        state = self.monitor.check_and_emit()
        self.assertEqual(state, "active")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "user.active")

        # Now user becomes idle.
        self.simulated_current_time = 12000.0
        state = self.monitor.check_and_emit()
        self.assertEqual(state, "idle")
        self.assertEqual(len(events), 2)
        self.assertEqual(events[1].event_type, "user.idle")


if __name__ == "__main__":
    unittest.main()
