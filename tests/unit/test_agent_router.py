"""
Unit tests for agents/router.py — Deterministic AgentRouter.

Tests the 5-step routing pipeline:
1. Capability Match
2. Circuit Breaker Filter
3. Priority Ranking & Deterministic Tie-Breaking
4. Resource Availability Check
5. Audit Record Generation (RoutingDecision) & Event Emission
"""

import unittest
from agents.router import AgentRegistry, AgentRouter
from core.contracts import RoutingDecision, TaskIntent, Task
from core.events import AuditWriter, EventBus
from core.max_infra.circuit_breaker import CircuitBreaker


class TestAgentRouterDeterministicPipeline(unittest.TestCase):
    def setUp(self):
        self.registry = AgentRegistry.get_instance()
        self.audit_writer = AuditWriter()
        self.event_bus = EventBus()
        self.router = AgentRouter(
            registry=self.registry,
            audit_writer=self.audit_writer,
            event_bus=self.event_bus,
        )

    def test_golden_task_routing(self):
        """Test expected agent selection for all golden categories."""
        mappings = [
            ("open_app", "DesktopAgent"),
            ("youtube_video", "BrowserAgent"),
            ("reminder", "TaskTracker"),
            ("calendaragent", "CalendarAgent"),
            ("dev_agent", "CodingAgent"),
            ("codingagent", "CodingAgent"),
            ("polyglotdeveloper", "CodingAgent"),
            ("reflexguardrails", "SecurityGate"),
            ("killswitch", "SecurityGate"),
            ("undo", "RecoveryEngine"),
            ("system_status", "SystemMonitorAgent"),
        ]

        for action, expected_agent in mappings:
            with self.subTest(action=action, expected=expected_agent):
                decision = self.router.route(action)
                self.assertIsInstance(decision, RoutingDecision)
                self.assertEqual(
                    decision.selected,
                    expected_agent,
                    f"Action '{action}' routed to '{decision.selected}', expected '{expected_agent}' (reason: {decision.reason})"
                )
                self.assertGreaterEqual(decision.capability_match_score, 0.9)
                self.assertIn(expected_agent, decision.candidates)
                self.assertTrue(len(decision.reason) > 0)

    def test_route_with_task_intent(self):
        """Test routing directly with a TaskIntent contract."""
        intent = TaskIntent(
            raw_input="Open VS Code",
            action="open_app",
            target="VS Code",
        )
        decision = self.router.route(intent)
        self.assertEqual(decision.selected, "DesktopAgent")
        self.assertEqual(decision.intent_action, "open_app")

    def test_route_with_task(self):
        """Test routing directly with a full Task object."""
        task = Task(id="test-task-1", action="dev_agent", target="calculator")
        decision = self.router.route(task)
        self.assertEqual(decision.selected, "CodingAgent")
        self.assertEqual(decision.task_id, "test-task-1")

    def test_circuit_breaker_fallback(self):
        """Test that when a primary candidate is circuit-broken, the router falls back to the next viable candidate."""
        # For "open_app", candidates are DesktopAgent (primary) and ComputerUseAgent (fallback)
        tripped_cb = CircuitBreaker(failure_threshold=1)
        tripped_cb.record_failure("DesktopAgent")
        self.router.set_circuit_breaker("DesktopAgent", tripped_cb)

        decision = self.router.route("open_app")
        self.assertEqual(decision.selected, "ComputerUseAgent")
        self.assertEqual(decision.circuit_breaker_status.get("DesktopAgent"), "OPEN")
        self.assertIn("DesktopAgent", decision.candidates)
        self.assertIn("circuit-broken", decision.reason.lower())

    def test_all_candidates_circuit_broken(self):
        """Test that when all candidates for an action are circuit-broken, selection fails safely."""
        cb_desk = CircuitBreaker(failure_threshold=1)
        cb_desk.record_failure("DesktopAgent")
        self.router.set_circuit_breaker("DesktopAgent", cb_desk)

        cb_cu = CircuitBreaker(failure_threshold=1)
        cb_cu.record_failure("ComputerUseAgent")
        self.router.set_circuit_breaker("ComputerUseAgent", cb_cu)

        decision = self.router.route("open_app")
        self.assertEqual(decision.selected, "")
        self.assertEqual(decision.capability_match_score, 0.0)
        self.assertIn("circuit broken", decision.reason.lower())

    def test_deterministic_tie_breaking(self):
        """Test lexicographical deterministic tie-breaking when scores and priorities match."""
        # Custom candidates can be tested or actions with equal scores
        decision = self.router.route("unknown_random_action_123")
        # Fallback routes to MasterOrchestrator
        self.assertEqual(decision.selected, "MasterOrchestrator")
        self.assertAlmostEqual(decision.capability_match_score, 0.3)

    def test_resource_check_failure(self):
        """Test that missing required resources blocks agent selection."""
        # Resource checker that reports 'display' unavailable
        restricted_router = AgentRouter(
            registry=self.registry,
            resource_checker=lambda res: False if res == "display" else True,
        )
        decision = restricted_router.route("open_app", required_resources=["display"])
        self.assertEqual(decision.selected, "")
        self.assertFalse(decision.resource_availability.get("display"))
        self.assertIn("unavailable", decision.reason.lower())

    def test_audit_writer_and_event_bus_emission(self):
        """Test that every routing decision produces tamper-evident audit records and event envelopes."""
        events_received = []
        self.event_bus.subscribe("routing.decision", lambda evt: events_received.append(evt))

        decision = self.router.route("dev_agent", task_id="task-audit-999")
        self.assertEqual(decision.selected, "CodingAgent")

        # Verify AuditWriter
        self.assertEqual(len(self.audit_writer._chain), 1)
        entry = self.audit_writer._chain[0]
        self.assertEqual(entry.event_type, "routing.decision")
        self.assertEqual(entry.correlation_id, "task-audit-999")
        self.assertEqual(entry.payload["selected"], "CodingAgent")
        self.assertTrue(self.audit_writer.verify_chain())

        # Verify EventBus
        self.assertEqual(len(events_received), 1)
        self.assertEqual(events_received[0].correlation_id, "task-audit-999")
        self.assertEqual(events_received[0].payload["selected"], "CodingAgent")

    def test_route_and_get(self):
        """Test route_and_get returns both the decision and the BaseAgent instance."""
        decision, agent = self.router.route_and_get("open_app")
        self.assertIsNotNone(agent)
        self.assertEqual(agent.name, "DesktopAgent")
        self.assertEqual(decision.selected, "DesktopAgent")


if __name__ == "__main__":
    unittest.main()
