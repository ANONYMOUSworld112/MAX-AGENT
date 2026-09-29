import pytest
from core.reflex.guardrails import ReflexGuardrails, RiskTier
from core.reflex.triage import ReflexTriage

def test_guardrails_tier3_hard_block():
    guard = ReflexGuardrails(fallback_mode=True)
    res = guard.check_safety("rm -rf / --no-preserve-root")
    assert res.is_safe is False
    assert res.risk_tier == RiskTier.TIER_3_HARD_BLOCKED

def test_guardrails_tier2_confirm_write():
    guard = ReflexGuardrails(fallback_mode=True)
    res = guard.check_safety("Update database schema and delete unused customer columns")
    assert res.risk_tier == RiskTier.TIER_2_CONFIRM_ON_WRITE

def test_guardrails_tier0_safe_read():
    guard = ReflexGuardrails(fallback_mode=True)
    res = guard.check_safety("What is the CPU usage?")
    assert res.risk_tier == RiskTier.TIER_0_AUTO
    assert res.is_safe is True

def test_triage_priority_assignment():
    triage = ReflexTriage(fallback_mode=True)
    assert triage.assign_priority("EMERGENCY KILL SWITCH ACTIVATED") == 0
    assert triage.assign_priority("What time is it?") == 1
    assert triage.assign_priority("Refactor auth module and run test suite") == 2
    assert triage.assign_priority("Summarize daily newsletter emails in background") == 3
    assert triage.assign_priority("Clean old temporary cache files and vacuum sqlite") == 4
