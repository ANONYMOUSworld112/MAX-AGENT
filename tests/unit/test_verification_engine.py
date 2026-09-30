"""
Unit tests for VerificationEngine & ExecutionGateway Integration (Task 8.1)
==========================================================================

Covers:
- Verification levels L0 (Execution), L1 (Observation), L2 (Semantic), L3 (Probe)
- poll_until polling with timeout and error handling
- Process and File verification checks
- Rule 1-H1: UNKNOWN is never treated as SUCCESS
- Gateway integration: post-execution verification failure marks ActionResult as failed
"""

import os
import sys
import tempfile
import pytest

from core.contracts import ActionRequest, ActionResult, ErrorClass, VerificationOutcome
from core.events import EventBus
from core.gateway import ExecutionGateway
from core.verification.engine import (
    VerificationEngine,
    VerificationLevel,
    VerificationReport,
    poll_until,
)
from core.verification.file_verifier import FileVerifier
from core.verification.process_verifier import ProcessVerifier


def test_rule_1_h1_unknown_is_not_verified():
    report = VerificationReport(outcome=VerificationOutcome.UNKNOWN)
    assert report.is_verified is False

    engine = VerificationEngine()
    aggregated = engine.evaluate([
        VerificationReport(outcome=VerificationOutcome.SUCCESS),
        VerificationReport(outcome=VerificationOutcome.UNKNOWN),
    ])
    assert aggregated.outcome == VerificationOutcome.UNKNOWN
    assert aggregated.is_verified is False


def test_poll_until_success():
    counter = {"calls": 0}

    def flaky_until_3():
        counter["calls"] += 1
        if counter["calls"] >= 3:
            return VerificationReport(outcome=VerificationOutcome.SUCCESS)
        return VerificationReport(outcome=VerificationOutcome.FAILURE, errors=["not ready yet"])

    rep = poll_until(flaky_until_3, timeout=1.0, interval=0.05)
    assert rep.outcome == VerificationOutcome.SUCCESS
    assert counter["calls"] == 3


def test_poll_until_timeout():
    def always_fail():
        return VerificationReport(outcome=VerificationOutcome.FAILURE, errors=["always down"])

    rep = poll_until(always_fail, timeout=0.15, interval=0.05)
    assert rep.outcome == VerificationOutcome.FAILURE
    assert rep.is_verified is False


def test_file_verification_levels(tmp_path):
    f = tmp_path / "test_artifact.txt"
    f.write_text("Hello MAX-AGENT Verification Engine!", encoding="utf-8")

    engine = VerificationEngine()

    # L1: File exists
    req_l1 = ActionRequest(
        action="write_file",
        parameters={"verify_file": str(f)},
    )
    rep_l1 = engine.verify_action(req_l1, output={"path": str(f)})
    assert rep_l1.outcome == VerificationOutcome.SUCCESS

    # L2: File content matches snippet
    req_l2 = ActionRequest(
        action="write_file",
        parameters={"verify_file": str(f), "verify_content": "MAX-AGENT Verification"},
    )
    rep_l2 = engine.verify_action(req_l2, output={"path": str(f)})
    assert rep_l2.outcome == VerificationOutcome.SUCCESS

    # L2: Missing snippet fails
    req_l2_fail = ActionRequest(
        action="write_file",
        parameters={"verify_file": str(f), "verify_content": "NonExistentString12345"},
    )
    rep_l2_fail = engine.verify_action(req_l2_fail, output={"path": str(f)})
    assert rep_l2_fail.outcome == VerificationOutcome.FAILURE


def test_process_exit_code_verification():
    engine = VerificationEngine()

    req = ActionRequest(action="run_command", parameters={"cmd": "pytest"})
    rep_ok = engine.verify_action(req, output={"exit_code": 0})
    assert rep_ok.outcome == VerificationOutcome.SUCCESS

    rep_err = engine.verify_action(req, output={"exit_code": 1})
    assert rep_err.outcome == VerificationOutcome.FAILURE


def test_gateway_post_execution_verification_integration(tmp_path):
    bus = EventBus()
    events = []
    bus.subscribe("*", lambda env: events.append(env))

    gw = ExecutionGateway(event_bus=bus)

    # Register an action that creates a file
    target_file = tmp_path / "gateway_created.txt"

    def write_handler(action, params):
        target_file.write_text("Created by gateway handler", encoding="utf-8")
        return {"file": str(target_file)}

    gw.register_handler("create_file", write_handler)

    from core.contracts import ChannelTrust

    # 1. Action with verification that passes
    req_success = ActionRequest(
        action="create_file",
        channel_trust=ChannelTrust.TRUSTED,
        parameters={"verify_file": str(target_file), "verify_content": "Created by gateway"},
    )
    res_success = gw.execute(req_success)
    assert res_success.success is True
    assert res_success.verification_outcome == VerificationOutcome.SUCCESS

    # 2. Action with verification that fails
    req_fail = ActionRequest(
        action="create_file",
        channel_trust=ChannelTrust.TRUSTED,
        parameters={"verify_file": str(target_file), "verify_content": "WrongContentExpected"},
    )
    res_fail = gw.execute(req_fail)
    assert res_fail.success is False
    assert res_fail.verification_outcome == VerificationOutcome.FAILURE
    assert res_fail.error_class == ErrorClass.LOGIC
    assert "Post-execution verification failed" in res_fail.error_message

    # Verify event emitted
    v_fail_events = [e for e in events if e.event_type == "action.verification_failed"]
    assert len(v_fail_events) >= 1
