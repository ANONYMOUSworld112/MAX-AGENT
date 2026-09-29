import time
import pytest
from core.max_infra.kill_switch import KillSwitch, KillSwitchTrippedError

def test_kill_switch_lifecycle():
    ks = KillSwitch.get_instance()
    ks.reset()
    assert ks.is_armed() is True
    assert ks.is_tripped() is False

    # Guard should not raise when normal
    ks.guard()

    # Add a callback listener
    tripped_reasons = []
    ks.add_listener(lambda r: tripped_reasons.append(r))

    # Trip the switch
    ks.trip("Emergency test abort")
    assert ks.is_tripped() is True
    assert len(tripped_reasons) == 1
    assert tripped_reasons[0] == "Emergency test abort"

    # Guard must now raise
    with pytest.raises(KillSwitchTrippedError):
        ks.guard()

def test_kill_switch_process_registration():
    ks = KillSwitch.get_instance()
    ks.reset()
    ks.register_process(999999)
    assert 999999 in ks.registered_pids
    ks.unregister_process(999999)
    assert 999999 not in ks.registered_pids
