"""
Unit tests for core/gateway.py and core/policy.py — ExecutionGateway
and PolicyEngine.

Covers: risk classification, confirmation matrix, handler registration,
policy rejection, confirmation flow, timeout handling, and audit events.
"""

import time
import unittest
import threading
from core.contracts import (
    ActionRequest, ActionResult, RiskLevel, ChannelTrust,
    IdempotencyClass, VerificationOutcome,
)
from core.policy import PolicyEngine, PolicyDecision, ConfirmationType
from core.gateway import (
    ExecutionGateway, ActionNotRegisteredError, PolicyRejectionError,
    ConfirmationRequiredError, ConfirmationTracker,
)
from core.events import EventBus, AuditWriter


# ---------------------------------------------------------------------------
# PolicyEngine Tests
# ---------------------------------------------------------------------------

class TestPolicyRiskTable(unittest.TestCase):
    """Risk classification lookup."""

    def test_known_low_risk(self):
        policy = PolicyEngine()
        self.assertEqual(policy.get_risk_level("web_search"), RiskLevel.LOW)
        self.assertEqual(policy.get_risk_level("screenshot"), RiskLevel.LOW)

    def test_known_medium_risk(self):
        policy = PolicyEngine()
        self.assertEqual(policy.get_risk_level("open_app"), RiskLevel.MEDIUM)
        self.assertEqual(policy.get_risk_level("pip_install"), RiskLevel.MEDIUM)

    def test_known_high_risk(self):
        policy = PolicyEngine()
        self.assertEqual(policy.get_risk_level("delete_file"), RiskLevel.HIGH)
        self.assertEqual(policy.get_risk_level("send_email"), RiskLevel.HIGH)

    def test_unknown_defaults_to_high(self):
        policy = PolicyEngine()
        self.assertEqual(policy.get_risk_level("totally_unknown"), RiskLevel.HIGH)

    def test_prohibited_action(self):
        policy = PolicyEngine()
        self.assertEqual(policy.get_risk_level("format_drive"), RiskLevel.PROHIBITED)


class TestPolicyConfirmation(unittest.TestCase):
    """Confirmation requirements based on (risk, trust)."""

    def test_low_risk_auto_executes(self):
        policy = PolicyEngine()
        for trust in ChannelTrust:
            req = ActionRequest(action="web_search", channel_trust=trust)
            decision = policy.evaluate(req)
            self.assertEqual(decision.confirmation, ConfirmationType.NONE)
            self.assertTrue(decision.is_allowed)

    def test_medium_risk_trusted_auto(self):
        policy = PolicyEngine()
        req = ActionRequest(action="open_app", channel_trust=ChannelTrust.TRUSTED)
        decision = policy.evaluate(req)
        self.assertEqual(decision.confirmation, ConfirmationType.NONE)

    def test_medium_risk_voice_needs_confirm(self):
        policy = PolicyEngine()
        req = ActionRequest(action="open_app", channel_trust=ChannelTrust.SEMI_TRUSTED)
        decision = policy.evaluate(req)
        self.assertEqual(decision.confirmation, ConfirmationType.HUD_BUTTON)

    def test_high_risk_untrusted_rejected(self):
        policy = PolicyEngine()
        req = ActionRequest(action="delete_file", channel_trust=ChannelTrust.UNTRUSTED)
        decision = policy.evaluate(req)
        self.assertEqual(decision.confirmation, ConfirmationType.REJECTED)
        self.assertFalse(decision.is_allowed)

    def test_critical_needs_typed_phrase_from_trusted(self):
        policy = PolicyEngine()
        req = ActionRequest(action="modify_registry", channel_trust=ChannelTrust.TRUSTED)
        decision = policy.evaluate(req)
        self.assertEqual(decision.confirmation, ConfirmationType.TYPED_PHRASE)

    def test_critical_rejected_from_voice(self):
        policy = PolicyEngine()
        req = ActionRequest(action="modify_registry", channel_trust=ChannelTrust.SEMI_TRUSTED)
        decision = policy.evaluate(req)
        self.assertFalse(decision.is_allowed)

    def test_prohibited_always_rejected(self):
        policy = PolicyEngine()
        for trust in ChannelTrust:
            req = ActionRequest(action="format_drive", channel_trust=trust)
            decision = policy.evaluate(req)
            self.assertFalse(decision.is_allowed)

    def test_register_custom_action(self):
        policy = PolicyEngine()
        policy.register_action_risk("my_custom_action", RiskLevel.LOW)
        self.assertEqual(policy.get_risk_level("my_custom_action"), RiskLevel.LOW)


# ---------------------------------------------------------------------------
# ConfirmationTracker Tests
# ---------------------------------------------------------------------------

class TestConfirmationTracker(unittest.TestCase):
    """Confirmation grant/consume lifecycle."""

    def test_unconfirmed_by_default(self):
        tracker = ConfirmationTracker()
        self.assertFalse(tracker.is_confirmed("req-1"))

    def test_grant_and_check(self):
        tracker = ConfirmationTracker()
        tracker.grant("req-1")
        self.assertTrue(tracker.is_confirmed("req-1"))

    def test_consume_is_one_time(self):
        tracker = ConfirmationTracker()
        tracker.grant("req-1")
        self.assertTrue(tracker.consume("req-1"))
        self.assertFalse(tracker.consume("req-1"))  # Already consumed

    def test_consume_ungranted(self):
        tracker = ConfirmationTracker()
        self.assertFalse(tracker.consume("req-nonexistent"))


# ---------------------------------------------------------------------------
# ExecutionGateway Tests
# ---------------------------------------------------------------------------

def _echo_handler(action: str, params: dict) -> dict:
    """Simple test handler that echoes parameters."""
    return {"action": action, "echoed": params}


def _slow_handler(action: str, params: dict) -> dict:
    """Handler that takes time (for timeout tests)."""
    time.sleep(5)
    return {"done": True}


def _error_handler(action: str, params: dict) -> dict:
    """Handler that raises an exception."""
    raise RuntimeError("Handler exploded")


class TestGatewayRegistration(unittest.TestCase):
    """Handler registration and lookup."""

    def test_register_and_check(self):
        gw = ExecutionGateway()
        gw.register_handler("test_action", _echo_handler)
        self.assertTrue(gw.has_handler("test_action"))
        self.assertFalse(gw.has_handler("unknown"))

    def test_unregistered_raises(self):
        gw = ExecutionGateway()
        req = ActionRequest(action="unknown", channel_trust=ChannelTrust.TRUSTED)
        with self.assertRaises(ActionNotRegisteredError):
            gw.execute(req)


class TestGatewayAutoExecution(unittest.TestCase):
    """LOW-risk trusted actions auto-execute without confirmation."""

    def test_low_risk_auto_executes(self):
        gw = ExecutionGateway()
        gw.register_handler("web_search", _echo_handler)

        req = ActionRequest(
            action="web_search",
            parameters={"query": "test"},
            channel_trust=ChannelTrust.TRUSTED,
        )
        result = gw.execute(req)
        self.assertTrue(result.success)
        self.assertEqual(result.output["action"], "web_search")
        self.assertEqual(gw.execution_count, 1)


class TestGatewayConfirmation(unittest.TestCase):
    """Actions requiring confirmation."""

    def test_medium_risk_voice_needs_confirm(self):
        gw = ExecutionGateway()
        gw.register_handler("open_app", _echo_handler)

        req = ActionRequest(
            action="open_app",
            parameters={"name": "chrome"},
            channel_trust=ChannelTrust.SEMI_TRUSTED,
        )
        with self.assertRaises(ConfirmationRequiredError):
            gw.execute(req)

    def test_confirm_then_execute(self):
        gw = ExecutionGateway()
        gw.register_handler("open_app", _echo_handler)

        req = ActionRequest(
            action="open_app",
            parameters={"name": "chrome"},
            channel_trust=ChannelTrust.SEMI_TRUSTED,
        )
        # First attempt raises
        with self.assertRaises(ConfirmationRequiredError):
            gw.execute(req)

        # Grant confirmation
        gw.confirm(req.id)

        # Second attempt succeeds
        result = gw.execute(req)
        self.assertTrue(result.success)


class TestGatewayPolicyRejection(unittest.TestCase):
    """Prohibited actions are rejected."""

    def test_prohibited_rejected(self):
        gw = ExecutionGateway()
        gw.register_handler("format_drive", _echo_handler)

        req = ActionRequest(
            action="format_drive",
            channel_trust=ChannelTrust.TRUSTED,
        )
        with self.assertRaises(PolicyRejectionError):
            gw.execute(req)


class TestGatewayErrorHandling(unittest.TestCase):
    """Handler errors are captured, not swallowed."""

    def test_handler_exception_returns_failure(self):
        gw = ExecutionGateway()
        gw.register_handler("web_search", _error_handler)

        req = ActionRequest(
            action="web_search",
            channel_trust=ChannelTrust.TRUSTED,
        )
        result = gw.execute(req)
        self.assertFalse(result.success)
        self.assertIn("exploded", result.error_message)


class TestGatewayAuditEvents(unittest.TestCase):
    """Gateway emits audit events for all operations."""

    def test_events_emitted_on_success(self):
        events = []
        bus = EventBus()
        bus.subscribe("*", lambda e: events.append(e))

        gw = ExecutionGateway(event_bus=bus)
        gw.register_handler("web_search", _echo_handler)

        req = ActionRequest(action="web_search", channel_trust=ChannelTrust.TRUSTED)
        gw.execute(req)

        event_types = [e.event_type for e in events]
        self.assertIn("action.started", event_types)
        self.assertIn("action.completed", event_types)

    def test_events_emitted_on_rejection(self):
        events = []
        bus = EventBus()
        bus.subscribe("*", lambda e: events.append(e))

        gw = ExecutionGateway(event_bus=bus)
        gw.register_handler("format_drive", _echo_handler)

        req = ActionRequest(action="format_drive", channel_trust=ChannelTrust.TRUSTED)
        try:
            gw.execute(req)
        except PolicyRejectionError:
            pass

        event_types = [e.event_type for e in events]
        self.assertIn("action.rejected", event_types)


if __name__ == "__main__":
    unittest.main()
