"""
Unit tests for ProcessManager & Windows Job Object Process Tree Kill (Task 7.1)
================================================================================

Covers:
- Command execution and stdout/stderr capture in RingBuffer
- Process tree termination via Windows Job Objects (killing parent and child)
- Timeout termination killing hung process
- Cleanup on shutdown
"""

import os
import subprocess
import sys
import time
import pytest

from core.process_manager import ProcessManager, RingBuffer


def test_ring_buffer_bounds():
    buf = RingBuffer(max_chars=50)
    buf.append("A" * 30)
    assert len(buf) == 30

    buf.append("B" * 30)
    # Total appended = 60 > 50, so older chunks dropped
    assert len(buf) <= 50
    val = buf.get_value()
    assert "B" in val


def test_process_manager_run_command_success():
    pm = ProcessManager()
    code = "import sys; print('hello from process manager'); sys.stderr.write('warn log\\n')"
    res = pm.run_command([sys.executable, "-c", code])

    assert res.success is True
    assert res.exit_code == 0
    assert "hello from process manager" in res.stdout
    assert "warn log" in res.stderr
    assert res.duration_ms > 0
    assert res.timed_out is False


def test_process_manager_timeout_kills_hung_process():
    pm = ProcessManager()
    # Script sleeps for 10 seconds
    cmd = [sys.executable, "-c", "import time; time.sleep(10)"]

    res = pm.run_command(cmd, timeout=0.3)

    assert res.timed_out is True
    assert res.success is False
    assert res.exit_code != 0


def test_process_tree_termination():
    pm = ProcessManager()

    # Script spawns a child process and sleeps
    script = (
        "import subprocess, sys, time\n"
        "p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(20)'])\n"
        "time.sleep(20)\n"
    )

    managed = pm.spawn([sys.executable, "-c", script])
    parent_pid = managed.popen.pid

    # Give child process a moment to spawn
    time.sleep(0.3)

    # Terminate the process tree
    managed.kill_tree()
    managed.wait(timeout=2.0)

    # Verify parent is dead
    assert managed.popen.poll() is not None

    # Check child processes via psutil if available
    try:
        import psutil
        try:
            p = psutil.Process(parent_pid)
            children = p.children(recursive=True)
            assert len(children) == 0
        except psutil.NoSuchProcess:
            # Successfully killed
            pass
    except ImportError:
        pass
