"""
Unit tests for Lifecycle Hooks System (Task 10.2)
=================================================

Covers:
- Priority ordering of registered hooks
- Exception isolation (faulty hook does not interrupt lifecycle)
- Built-in MetricsCollectorHook telemetry
"""

import pytest
from core.contracts import ActionRequest, ActionResult, Task, VerificationOutcome
from core.hooks import HookPoint, HookRegistry, MetricsCollectorHook
from core.verification.engine import VerificationReport


def test_hook_priority_ordering():
    registry = HookRegistry()
    execution_order = []

    def hook_low_prio(task):
        execution_order.append("low")

    def hook_high_prio(task):
        execution_order.append("high")

    registry.register(HookPoint.BEFORE_TASK, hook_low_prio, priority=100, name="low")
    registry.register(HookPoint.BEFORE_TASK, hook_high_prio, priority=10, name="high")

    registry.trigger(HookPoint.BEFORE_TASK, Task(action="test_action"))

    assert execution_order == ["high", "low"]


def test_hook_exception_isolation():
    registry = HookRegistry()
    called = []

    def failing_hook(task):
        raise RuntimeError("Simulated crash in hook")

    def healthy_hook(task):
        called.append(True)

    registry.register(HookPoint.BEFORE_TASK, failing_hook, priority=10, name="fail")
    registry.register(HookPoint.BEFORE_TASK, healthy_hook, priority=20, name="healthy")

    # Should not raise exception
    registry.trigger(HookPoint.BEFORE_TASK, Task(action="test_action"))

    # Healthy hook still executed
    assert called == [True]


def test_metrics_collector_hook():
    registry = HookRegistry()
    metrics = MetricsCollectorHook()
    metrics.register(registry)

    t = Task(action="metrics_task")
    req = ActionRequest(action="sample_action")
    res_ok = ActionResult(success=True)
    res_err = ActionResult(success=False)
    rep_fail = VerificationReport(outcome=VerificationOutcome.FAILURE)

    registry.trigger(HookPoint.BEFORE_TASK, t)
    registry.trigger(HookPoint.BEFORE_TOOL, req)
    registry.trigger(HookPoint.AFTER_TOOL, req, res_ok)

    registry.trigger(HookPoint.BEFORE_TOOL, req)
    registry.trigger(HookPoint.AFTER_TOOL, req, res_err)

    registry.trigger(HookPoint.ON_VERIFICATION, t, rep_fail)
    registry.trigger(HookPoint.AFTER_TASK, t, res_ok)

    assert metrics.task_starts == 1
    assert metrics.task_completions == 1
    assert metrics.tool_calls == 2
    assert metrics.tool_failures == 1
    assert metrics.verification_failures == 1
