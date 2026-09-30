"""Tier 0 Characterization Test: Confirmation Gate & Undo Stack.

Tests core.confirm and core.undo baseline behaviors.
"""
import time
import core.confirm as confirm_gate
import core.undo as undo_stack


def test_confirm_gate_flow():
    shown = []
    hidden = []
    logs = []

    def fake_show(title, detail):
        shown.append((title, detail))

    def fake_hide():
        hidden.append(True)

    def fake_log(msg):
        logs.append(msg)

    confirm_gate.bind(fake_show, fake_hide, fake_log)

    executed = []
    def do_action():
        executed.append("done")
        return "Action succeeded"

    # Request confirmation
    prompt_instruction = confirm_gate.request("test_op", "Reboot Machine", "Restarting now", do_action)
    assert "[CONFIRMATION_PENDING]" in prompt_instruction
    assert len(shown) == 1
    assert shown[0][0] == "Reboot Machine"
    assert confirm_gate.pending_title() == "Reboot Machine"

    # Resolve with accept
    confirm_gate.resolve(accepted=True)
    assert len(hidden) == 1
    assert confirm_gate.pending_title() == ""

    # Allow worker thread to execute
    time.sleep(0.1)
    assert "done" in executed


def test_confirm_gate_cancel():
    shown = []
    hidden = []
    confirm_gate.bind(lambda t, d: shown.append((t, d)), lambda: hidden.append(True))

    executed = []
    confirm_gate.request("cancel_op", "Delete File", "Deleting file", lambda: executed.append("run"))
    confirm_gate.resolve(accepted=False)

    time.sleep(0.05)
    assert len(executed) == 0


def test_undo_stack_operations():
    # Clear undo stack
    while undo_stack.can_undo():
        undo_stack.undo_last()

    assert not undo_stack.can_undo()
    assert undo_stack.peek() == ""
    assert undo_stack.history() == []

    log = []
    undo_stack.push_undo("volume -> 50%", lambda: log.append("volume restored") or "Volume restored")
    undo_stack.push_undo("file moved", lambda: log.append("file restored") or "File restored")

    assert undo_stack.can_undo()
    assert undo_stack.peek() == "file moved"
    assert undo_stack.history() == ["file moved", "volume -> 50%"]

    # Undo last (actual implementation prepends "Undone: <label>. ")
    res1 = undo_stack.undo_last()
    assert res1 == "Undone: file moved. File restored"
    assert "file restored" in log

    assert undo_stack.peek() == "volume -> 50%"

    res2 = undo_stack.undo_last()
    assert res2 == "Undone: volume -> 50%. Volume restored"
    assert "volume restored" in log

    assert not undo_stack.can_undo()
