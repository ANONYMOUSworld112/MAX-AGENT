"""
Unit tests for core/state_machine.py — 14-state task lifecycle.

Covers: all legal transitions, all illegal transitions, terminal state
enforcement, BLOCKED reason requirement, thread safety, and transition
history recording.
"""

import threading
import unittest
from core.contracts import TaskStatus, BlockedReason
from core.state_machine import TaskStateMachine, InvalidStateTransitionError


class TestLegalTransitions(unittest.TestCase):
    """Verify all legal transitions succeed."""

    def test_created_to_planned(self):
        fsm = TaskStateMachine(task_id="t1")
        record = fsm.transition(TaskStatus.PLANNED, reason="Plan generated")
        self.assertEqual(fsm.state, TaskStatus.PLANNED)
        self.assertEqual(record.from_state, TaskStatus.CREATED)
        self.assertEqual(record.to_state, TaskStatus.PLANNED)

    def test_created_to_queued_fast_path(self):
        fsm = TaskStateMachine()
        fsm.transition(TaskStatus.QUEUED, reason="Fast-path single action")
        self.assertEqual(fsm.state, TaskStatus.QUEUED)

    def test_full_happy_path(self):
        """CREATED → PLANNED → QUEUED → RUNNING → VERIFYING → COMPLETED"""
        fsm = TaskStateMachine()
        fsm.transition(TaskStatus.PLANNED)
        fsm.transition(TaskStatus.QUEUED)
        fsm.transition(TaskStatus.RUNNING)
        fsm.transition(TaskStatus.VERIFYING)
        fsm.transition(TaskStatus.COMPLETED)
        self.assertEqual(fsm.state, TaskStatus.COMPLETED)
        self.assertTrue(fsm.is_terminal)
        self.assertEqual(len(fsm.history), 5)

    def test_retry_path(self):
        """CREATED → QUEUED → RUNNING → VERIFYING → RETRYING → RUNNING → VERIFYING → COMPLETED"""
        fsm = TaskStateMachine()
        fsm.transition(TaskStatus.QUEUED)
        fsm.transition(TaskStatus.RUNNING)
        fsm.transition(TaskStatus.VERIFYING)
        fsm.transition(TaskStatus.RETRYING, reason="Verification failed")
        fsm.transition(TaskStatus.RUNNING, reason="Retry attempt")
        fsm.transition(TaskStatus.VERIFYING)
        fsm.transition(TaskStatus.COMPLETED)
        self.assertTrue(fsm.is_terminal)

    def test_pause_resume_path(self):
        """CREATED → QUEUED → RUNNING → PAUSED → RUNNING → VERIFYING → COMPLETED"""
        fsm = TaskStateMachine()
        fsm.transition(TaskStatus.QUEUED)
        fsm.transition(TaskStatus.RUNNING)
        fsm.transition(TaskStatus.PAUSED, reason="User activity detected")
        fsm.transition(TaskStatus.RUNNING, reason="User idle")
        fsm.transition(TaskStatus.VERIFYING)
        fsm.transition(TaskStatus.COMPLETED)
        self.assertTrue(fsm.is_terminal)

    def test_cancel_while_queued(self):
        fsm = TaskStateMachine()
        fsm.transition(TaskStatus.QUEUED)
        fsm.transition(TaskStatus.CANCELLED, reason="User cancelled")
        self.assertTrue(fsm.is_terminal)

    def test_cancel_while_running(self):
        """RUNNING → CANCELLING → CANCELLED"""
        fsm = TaskStateMachine()
        fsm.transition(TaskStatus.QUEUED)
        fsm.transition(TaskStatus.RUNNING)
        fsm.transition(TaskStatus.CANCELLING, reason="Cancel requested")
        fsm.transition(TaskStatus.CANCELLED)
        self.assertTrue(fsm.is_terminal)

    def test_interrupted_to_failed(self):
        fsm = TaskStateMachine()
        fsm.transition(TaskStatus.QUEUED)
        fsm.transition(TaskStatus.RUNNING)
        fsm.transition(TaskStatus.INTERRUPTED, reason="Kill switch")
        fsm.transition(TaskStatus.FAILED)
        self.assertTrue(fsm.is_terminal)

    def test_expired_while_queued(self):
        fsm = TaskStateMachine()
        fsm.transition(TaskStatus.QUEUED)
        fsm.transition(TaskStatus.EXPIRED, reason="Deadline passed")
        self.assertTrue(fsm.is_terminal)


class TestBlockedState(unittest.TestCase):
    """BLOCKED state requires a BlockedReason."""

    def test_blocked_requires_reason(self):
        fsm = TaskStateMachine()
        fsm.transition(TaskStatus.QUEUED)
        with self.assertRaises(InvalidStateTransitionError) as ctx:
            fsm.transition(TaskStatus.BLOCKED)
        self.assertIn("blocked_reason is required", str(ctx.exception))

    def test_blocked_with_reason(self):
        fsm = TaskStateMachine()
        fsm.transition(TaskStatus.QUEUED)
        fsm.transition(
            TaskStatus.BLOCKED,
            blocked_reason=BlockedReason.RESOURCE,
            reason="desktop-input lease unavailable",
        )
        self.assertEqual(fsm.state, TaskStatus.BLOCKED)
        self.assertEqual(fsm.blocked_reason, BlockedReason.RESOURCE)

    def test_blocked_reason_cleared_on_unblock(self):
        fsm = TaskStateMachine()
        fsm.transition(TaskStatus.QUEUED)
        fsm.transition(TaskStatus.BLOCKED, blocked_reason=BlockedReason.DEPENDENCY)
        self.assertIsNotNone(fsm.blocked_reason)
        fsm.transition(TaskStatus.QUEUED, reason="Dependency resolved")
        self.assertIsNone(fsm.blocked_reason)


class TestIllegalTransitions(unittest.TestCase):
    """All illegal transitions must raise InvalidStateTransitionError."""

    def test_created_to_running(self):
        fsm = TaskStateMachine()
        with self.assertRaises(InvalidStateTransitionError):
            fsm.transition(TaskStatus.RUNNING)

    def test_created_to_completed(self):
        fsm = TaskStateMachine()
        with self.assertRaises(InvalidStateTransitionError):
            fsm.transition(TaskStatus.COMPLETED)

    def test_created_to_verifying(self):
        fsm = TaskStateMachine()
        with self.assertRaises(InvalidStateTransitionError):
            fsm.transition(TaskStatus.VERIFYING)

    def test_completed_to_anything(self):
        fsm = TaskStateMachine()
        fsm.transition(TaskStatus.QUEUED)
        fsm.transition(TaskStatus.RUNNING)
        fsm.transition(TaskStatus.VERIFYING)
        fsm.transition(TaskStatus.COMPLETED)

        for target in TaskStatus:
            with self.assertRaises(InvalidStateTransitionError):
                fsm.transition(target)

    def test_failed_rejects_all(self):
        fsm = TaskStateMachine()
        fsm.transition(TaskStatus.FAILED)
        with self.assertRaises(InvalidStateTransitionError):
            fsm.transition(TaskStatus.RUNNING)

    def test_cancelled_rejects_all(self):
        fsm = TaskStateMachine()
        fsm.transition(TaskStatus.CANCELLED)
        with self.assertRaises(InvalidStateTransitionError):
            fsm.transition(TaskStatus.QUEUED)

    def test_running_to_queued(self):
        fsm = TaskStateMachine()
        fsm.transition(TaskStatus.QUEUED)
        fsm.transition(TaskStatus.RUNNING)
        with self.assertRaises(InvalidStateTransitionError):
            fsm.transition(TaskStatus.QUEUED)


class TestTransitionHistory(unittest.TestCase):
    """Transition history is recorded correctly."""

    def test_history_records(self):
        fsm = TaskStateMachine(task_id="hist-1")
        fsm.transition(TaskStatus.QUEUED, reason="r1", actor="scheduler")
        fsm.transition(TaskStatus.RUNNING, reason="r2", actor="worker")

        history = fsm.history
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0].from_state, TaskStatus.CREATED)
        self.assertEqual(history[0].to_state, TaskStatus.QUEUED)
        self.assertEqual(history[0].actor, "scheduler")
        self.assertEqual(history[1].reason, "r2")

    def test_history_is_copy(self):
        fsm = TaskStateMachine()
        fsm.transition(TaskStatus.QUEUED)
        h1 = fsm.history
        h1.append(None)  # Mutate copy
        self.assertEqual(len(fsm.history), 1)  # Original unchanged


class TestCanTransition(unittest.TestCase):
    """can_transition checks without side effects."""

    def test_can_transition_true(self):
        fsm = TaskStateMachine()
        self.assertTrue(fsm.can_transition(TaskStatus.PLANNED))
        self.assertTrue(fsm.can_transition(TaskStatus.QUEUED))

    def test_can_transition_false(self):
        fsm = TaskStateMachine()
        self.assertFalse(fsm.can_transition(TaskStatus.RUNNING))
        self.assertFalse(fsm.can_transition(TaskStatus.COMPLETED))


class TestAllowedTransitions(unittest.TestCase):
    """get_allowed_transitions returns correct sets."""

    def test_created_allowed(self):
        fsm = TaskStateMachine()
        allowed = fsm.get_allowed_transitions()
        self.assertIn(TaskStatus.PLANNED, allowed)
        self.assertIn(TaskStatus.QUEUED, allowed)
        self.assertIn(TaskStatus.CANCELLED, allowed)
        self.assertIn(TaskStatus.FAILED, allowed)
        self.assertNotIn(TaskStatus.RUNNING, allowed)

    def test_terminal_allowed_empty(self):
        fsm = TaskStateMachine()
        fsm.transition(TaskStatus.FAILED)
        self.assertEqual(fsm.get_allowed_transitions(), set())


class TestSerialization(unittest.TestCase):
    """to_dict produces valid JSON-serializable output."""

    def test_to_dict(self):
        fsm = TaskStateMachine(task_id="ser-1")
        fsm.transition(TaskStatus.QUEUED)
        d = fsm.to_dict()
        self.assertEqual(d["task_id"], "ser-1")
        self.assertEqual(d["current_state"], "QUEUED")
        self.assertFalse(d["is_terminal"])
        self.assertEqual(len(d["history"]), 1)


class TestThreadSafety(unittest.TestCase):
    """Concurrent transitions must not corrupt state."""

    def test_concurrent_transitions(self):
        fsm = TaskStateMachine()
        fsm.transition(TaskStatus.QUEUED)
        fsm.transition(TaskStatus.RUNNING)

        errors = []
        successes = []

        def try_transition(target, blocked_reason=None):
            try:
                fsm.transition(target, blocked_reason=blocked_reason)
                successes.append(target)
            except InvalidStateTransitionError:
                errors.append(target)

        # Only one of VERIFYING, PAUSED, CANCELLING should succeed from RUNNING
        threads = [
            threading.Thread(target=try_transition, args=(TaskStatus.VERIFYING,)),
            threading.Thread(target=try_transition, args=(TaskStatus.PAUSED,)),
            threading.Thread(target=try_transition, args=(TaskStatus.CANCELLING,)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Exactly one should succeed (the first to acquire the lock)
        self.assertEqual(len(successes), 1)
        self.assertEqual(len(errors), 2)


if __name__ == "__main__":
    unittest.main()
