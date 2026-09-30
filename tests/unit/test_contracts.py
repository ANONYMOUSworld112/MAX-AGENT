"""
Unit tests for core/contracts.py — Data contract schema validation,
serialization round-trips, and required field enforcement.
"""

import json
import unittest
from core.contracts import (
    TaskIntent, Task, ActionRequest, ActionResult, EventEnvelope,
    RoutingDecision, RiskLevel, ChannelTrust, TaskStatus, BlockedReason,
    VerificationOutcome, ErrorClass, IdempotencyClass,
)


class TestEnums(unittest.TestCase):
    """Test enum properties and values."""

    def test_risk_level_values(self):
        self.assertEqual(RiskLevel.LOW.value, "LOW")
        self.assertEqual(RiskLevel.CRITICAL.label, "CRITICAL")

    def test_task_status_terminal(self):
        terminal = {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED, TaskStatus.EXPIRED}
        non_terminal = set(TaskStatus) - terminal
        for s in terminal:
            self.assertTrue(s.is_terminal, f"{s} should be terminal")
        for s in non_terminal:
            self.assertFalse(s.is_terminal, f"{s} should NOT be terminal")

    def test_all_14_states_exist(self):
        self.assertEqual(len(TaskStatus), 14)

    def test_verification_outcome_values(self):
        self.assertEqual(VerificationOutcome.SUCCESS.value, "SUCCESS")
        self.assertEqual(VerificationOutcome.FAILURE.value, "FAILURE")
        self.assertEqual(VerificationOutcome.UNKNOWN.value, "UNKNOWN")


class TestTaskIntent(unittest.TestCase):
    """Test TaskIntent creation and serialization."""

    def test_creation_with_defaults(self):
        intent = TaskIntent(raw_input="Open Chrome", action="open_app", target="chrome")
        self.assertEqual(intent.raw_input, "Open Chrome")
        self.assertEqual(intent.action, "open_app")
        self.assertEqual(intent.channel, ChannelTrust.UNTRUSTED)
        self.assertFalse(intent.is_compound)
        self.assertTrue(len(intent.id) > 0)
        self.assertTrue(len(intent.timestamp) > 0)

    def test_immutability(self):
        intent = TaskIntent()
        with self.assertRaises(AttributeError):
            intent.action = "modified"

    def test_json_round_trip(self):
        intent = TaskIntent(
            raw_input="Play music",
            action="play_music",
            target="Believer",
            channel=ChannelTrust.SEMI_TRUSTED,
            origin="voice",
            parameters={"artist": "Imagine Dragons"},
        )
        d = intent.to_dict()
        json_str = json.dumps(d)
        restored = TaskIntent.from_dict(json.loads(json_str))
        self.assertEqual(restored.action, intent.action)
        self.assertEqual(restored.channel, intent.channel)
        self.assertEqual(restored.parameters, intent.parameters)


class TestTask(unittest.TestCase):
    """Test Task creation and serialization."""

    def test_creation_defaults(self):
        task = Task(action="open_app", target="chrome")
        self.assertEqual(task.status, TaskStatus.CREATED)
        self.assertEqual(task.risk_level, RiskLevel.LOW)
        self.assertIsNone(task.blocked_reason)
        self.assertEqual(task.retry_count, 0)

    def test_mutable_status(self):
        task = Task()
        task.status = TaskStatus.RUNNING
        self.assertEqual(task.status, TaskStatus.RUNNING)

    def test_json_round_trip(self):
        task = Task(
            action="delete_file",
            target="/tmp/test.txt",
            status=TaskStatus.BLOCKED,
            blocked_reason=BlockedReason.CONFIRMATION,
            risk_level=RiskLevel.HIGH,
            verification_outcome=VerificationOutcome.UNKNOWN,
            error_class=ErrorClass.TRANSIENT,
        )
        d = task.to_dict()
        json_str = json.dumps(d)
        restored = Task.from_dict(json.loads(json_str))
        self.assertEqual(restored.status, TaskStatus.BLOCKED)
        self.assertEqual(restored.blocked_reason, BlockedReason.CONFIRMATION)
        self.assertEqual(restored.risk_level, RiskLevel.HIGH)

    def test_required_fields(self):
        task = Task()
        self.assertTrue(len(task.id) > 0)
        self.assertTrue(len(task.created_at) > 0)


class TestActionRequest(unittest.TestCase):
    """Test ActionRequest creation and serialization."""

    def test_creation(self):
        req = ActionRequest(
            task_id="task-1",
            action="open_app",
            parameters={"name": "chrome"},
            risk_level=RiskLevel.MEDIUM,
            channel_trust=ChannelTrust.TRUSTED,
        )
        self.assertEqual(req.action, "open_app")
        self.assertEqual(req.risk_level, RiskLevel.MEDIUM)

    def test_immutability(self):
        req = ActionRequest()
        with self.assertRaises(AttributeError):
            req.action = "modified"

    def test_json_round_trip(self):
        req = ActionRequest(
            action="delete_file",
            risk_level=RiskLevel.HIGH,
            idempotency=IdempotencyClass.NON_IDEMPOTENT,
            channel_trust=ChannelTrust.SEMI_TRUSTED,
        )
        d = req.to_dict()
        restored = ActionRequest.from_dict(d)
        self.assertEqual(restored.risk_level, RiskLevel.HIGH)
        self.assertEqual(restored.idempotency, IdempotencyClass.NON_IDEMPOTENT)


class TestActionResult(unittest.TestCase):
    """Test ActionResult creation and serialization."""

    def test_creation(self):
        result = ActionResult(
            request_id="req-1",
            task_id="task-1",
            success=True,
            output={"message": "Done"},
            verification_outcome=VerificationOutcome.SUCCESS,
            duration_ms=150.0,
        )
        self.assertTrue(result.success)
        self.assertEqual(result.verification_outcome, VerificationOutcome.SUCCESS)

    def test_failure_result(self):
        result = ActionResult(
            success=False,
            error_class=ErrorClass.ENVIRONMENT,
            error_message="Missing dependency",
        )
        self.assertFalse(result.success)
        self.assertEqual(result.error_class, ErrorClass.ENVIRONMENT)

    def test_json_round_trip(self):
        result = ActionResult(
            success=False,
            error_class=ErrorClass.TRANSIENT,
            verification_outcome=VerificationOutcome.FAILURE,
        )
        d = result.to_dict()
        restored = ActionResult.from_dict(d)
        self.assertEqual(restored.error_class, ErrorClass.TRANSIENT)
        self.assertEqual(restored.verification_outcome, VerificationOutcome.FAILURE)


class TestEventEnvelope(unittest.TestCase):
    """Test EventEnvelope creation and JSON serialization."""

    def test_creation(self):
        event = EventEnvelope(
            event_type="task.created",
            correlation_id="task-1",
            actor="system",
            payload={"action": "open_app"},
        )
        self.assertEqual(event.event_type, "task.created")
        self.assertTrue(len(event.id) > 0)

    def test_to_json(self):
        event = EventEnvelope(event_type="test", payload={"key": "value"})
        json_str = event.to_json()
        parsed = json.loads(json_str)
        self.assertEqual(parsed["event_type"], "test")
        self.assertEqual(parsed["payload"]["key"], "value")


class TestRoutingDecision(unittest.TestCase):
    """Test RoutingDecision creation."""

    def test_creation(self):
        rd = RoutingDecision(
            task_id="task-1",
            intent_action="open_app",
            candidates=["ComputerWorker", "AppLauncher"],
            selected="AppLauncher",
            reason="Exact capability match",
            capability_match_score=1.0,
        )
        self.assertEqual(rd.selected, "AppLauncher")
        self.assertEqual(len(rd.candidates), 2)


if __name__ == "__main__":
    unittest.main()
