import pytest
from core.reflex.guardrails import ReflexGuardrails, RiskTier
from core import confirm as confirm_gate


def test_reflex_guardrails_to_confirm_gate():
    guard = ReflexGuardrails(fallback_mode=True)

    shown_events = []
    hidden_events = []

    def mock_show(title, detail):
        shown_events.append((title, detail))

    def mock_hide():
        hidden_events.append(True)

    confirm_gate.bind(mock_show, mock_hide)

    # 1. Tier 0 (Safe Read)
    read_res = guard.check_safety("What is the current time and battery percentage?")
    assert read_res.is_safe is True
    assert read_res.risk_tier == RiskTier.TIER_0_AUTO

    # 2. Tier 2 (Confirm on Write)
    write_res = guard.check_safety("Update settings and restart network adapter")
    assert write_res.is_safe is True
    assert write_res.risk_tier == RiskTier.TIER_2_CONFIRM_ON_WRITE

    # Dispatch to confirm_gate
    executed_work = []
    confirm_msg = confirm_gate.request(
        key="test_net_restart",
        title="Restart Network Adapter",
        detail="Will restart adapter eth0",
        run=lambda: executed_work.append("RESTARTED"),
    )
    assert "[CONFIRMATION_PENDING]" in confirm_msg
    assert len(shown_events) == 1

    # User accepts confirmation
    confirm_gate.resolve(accepted=True)
    import time
    time.sleep(0.1)
    assert "RESTARTED" in executed_work

    # 3. Tier 3 (Hard Blocked)
    block_res = guard.check_safety("format c: /q and del /f /s /q c:")
    assert block_res.is_safe is False
    assert block_res.risk_tier == RiskTier.TIER_3_HARD_BLOCKED
