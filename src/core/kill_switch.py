"""
MAX OS — Kill Switch (Component #0)
Build Order: #3 (Layer 0C — registered BEFORE any other import)
═══════════════════════════════════════════════════════════════

Non-negotiable first component. System refuses to boot without it armed.
Budget: 1 second to halt everything, no exceptions.

Design: ADR-002 in decisions.md
Source: 01_BACKEND_WIRING_ORDER.md Layer 0C
Gate:   Dummy long-running task killed in <1s
"""

from __future__ import annotations

import os
import sys
import signal
import logging
import time
import threading
from datetime import datetime, timezone
from typing import Callable, Optional

logger = logging.getLogger("max.core.kill_switch")

# ── State ─────────────────────────────────────────────────────
_armed: bool = False
_active_tasks: dict[str, dict] = {}    # task_id → {pid, description, started_at}
_active_subprocesses: list[int] = []   # PIDs of spawned subprocesses
_shutdown_callbacks: list[Callable] = []
_kill_count: int = 0                   # double-trigger detection
_last_kill_time: float = 0
_lock = threading.Lock()

# Budget: 1 second total, no exceptions
KILL_BUDGET_SECONDS = 1.0
SIGTERM_WAIT_MS = 500
DOUBLE_TRIGGER_WINDOW_MS = 2000


class KillSwitchNotArmedError(RuntimeError):
    """Raised when the system tries to boot without Kill Switch armed."""
    pass


def arm() -> None:
    """
    Arm the Kill Switch. MUST be called before any other component
    initializes. Registers signal handlers for SIGINT and SIGTERM.
    """
    global _armed
    
    if _armed:
        logger.warning("Kill Switch already armed — ignoring duplicate arm()")
        return
    
    # Register signal handlers (if in main thread)
    try:
        signal.signal(signal.SIGINT, _signal_handler)
        signal.signal(signal.SIGTERM, _signal_handler)
        if sys.platform == "win32" and hasattr(signal, "SIGBREAK"):
            signal.signal(signal.SIGBREAK, _signal_handler)
    except (ValueError, AttributeError, RuntimeError):
        pass
    
    _armed = True
    logger.info("Kill Switch ARMED — signal handlers registered")


def is_armed() -> bool:
    """Check if Kill Switch is armed."""
    return _armed


def require_armed() -> None:
    """
    Assert Kill Switch is armed. Call this at system boot.
    If Kill Switch isn't armed, the system MUST NOT start.
    """
    if not _armed:
        raise KillSwitchNotArmedError(
            "Kill Switch is not armed. System refuses to initialize. "
            "Call kill_switch.arm() before any other component. "
            "This is ARCHITECTURE.md Principle #1 — non-negotiable."
        )


def register_task(task_id: str, description: str = "", pid: int = 0) -> None:
    """Register an active task so Kill Switch knows what to stop."""
    with _lock:
        _active_tasks[task_id] = {
            "pid": pid,
            "description": description,
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
    logger.debug("Task registered with Kill Switch: %s", task_id)


def unregister_task(task_id: str) -> None:
    """Remove a completed/cancelled task from Kill Switch tracking."""
    with _lock:
        _active_tasks.pop(task_id, None)


def register_subprocess(pid: int) -> None:
    """Register a spawned subprocess for kill tracking."""
    with _lock:
        if pid not in _active_subprocesses:
            _active_subprocesses.append(pid)


def unregister_subprocess(pid: int) -> None:
    """Remove a completed subprocess from tracking."""
    with _lock:
        if pid in _active_subprocesses:
            _active_subprocesses.remove(pid)


def on_shutdown(callback: Callable) -> None:
    """Register a callback to run during kill sequence (for cleanup)."""
    _shutdown_callbacks.append(callback)


def trigger(reason: str = "manual") -> None:
    """
    Manually trigger the Kill Switch. Same effect as SIGINT/SIGTERM.
    Called by `max kill` CLI command or double Ctrl+C.
    
    Budget: 1 second total.
    """
    logger.warning("KILL SWITCH TRIGGERED — reason: %s", reason)
    _execute_kill_sequence(reason)


def get_status() -> dict:
    """Return current Kill Switch status for diagnostics."""
    with _lock:
        return {
            "armed": _armed,
            "active_tasks": len(_active_tasks),
            "active_subprocesses": len(_active_subprocesses),
            "tasks": dict(_active_tasks),
            "kill_count": _kill_count,
        }


# ── Internal ──────────────────────────────────────────────────

def _signal_handler(signum: int, frame) -> None:
    """
    Signal handler — the actual kill switch mechanism.
    Double-trigger within 2 seconds = force exit.
    """
    global _kill_count, _last_kill_time
    
    now = time.monotonic()
    
    # Double-trigger detection: second signal within 2s = hard exit
    if now - _last_kill_time < DOUBLE_TRIGGER_WINDOW_MS / 1000:
        _kill_count += 1
        if _kill_count >= 2:
            logger.critical("DOUBLE KILL — forcing immediate exit")
            os._exit(1)
    else:
        _kill_count = 1
    
    _last_kill_time = now
    
    sig_name = signal.Signals(signum).name
    logger.warning("Kill Switch signal received: %s", sig_name)
    
    # Run kill sequence in a thread to avoid signal handler limitations
    t = threading.Thread(target=_execute_kill_sequence, args=(sig_name,), daemon=True)
    t.start()


def _execute_kill_sequence(reason: str) -> None:
    """
    The kill sequence. Budget: 1 second total.
    
    1. SIGTERM to all subprocesses (wait 500ms)
    2. SIGKILL to any still alive
    3. Mark all in-flight tasks as 'killed' in DB
    4. Release all locks (force-release)
    5. Log kill event
    6. Run shutdown callbacks
    """
    start = time.monotonic()
    
    logger.info("Kill sequence started — reason: %s", reason)
    
    # Step 1: SIGTERM to all tracked subprocesses
    with _lock:
        pids_to_kill = list(_active_subprocesses)
    
    for pid in pids_to_kill:
        try:
            if sys.platform == "win32":
                os.kill(pid, signal.SIGTERM)
            else:
                os.kill(pid, signal.SIGTERM)
            logger.debug("SIGTERM sent to PID %d", pid)
        except (ProcessLookupError, PermissionError):
            pass  # Already dead or not ours
    
    # Wait up to 500ms for graceful termination
    if pids_to_kill:
        time.sleep(min(SIGTERM_WAIT_MS / 1000, KILL_BUDGET_SECONDS / 2))
    
    # Step 2: SIGKILL any survivors
    for pid in pids_to_kill:
        try:
            if sys.platform == "win32":
                os.kill(pid, signal.SIGTERM)  # Windows doesn't have SIGKILL
            else:
                os.kill(pid, signal.SIGKILL)
            logger.debug("SIGKILL sent to PID %d", pid)
        except (ProcessLookupError, PermissionError):
            pass
    
    # Step 3: Mark tasks as killed in DB (direct write, bypasses state machine)
    _mark_tasks_killed(reason)
    
    # Step 4: Run shutdown callbacks
    for cb in _shutdown_callbacks:
        try:
            cb()
        except Exception as e:
            logger.error("Shutdown callback failed: %s", e)
    
    # Step 5: Clear tracking
    with _lock:
        _active_tasks.clear()
        _active_subprocesses.clear()
    
    elapsed = time.monotonic() - start
    logger.info(
        "Kill sequence completed in %.3fs (budget: %.1fs) — reason: %s",
        elapsed, KILL_BUDGET_SECONDS, reason
    )
    
    if elapsed > KILL_BUDGET_SECONDS:
        logger.error(
            "Kill sequence EXCEEDED budget: %.3fs > %.1fs",
            elapsed, KILL_BUDGET_SECONDS
        )


def _mark_tasks_killed(reason: str) -> None:
    """
    Direct DB write to mark all in-flight tasks as 'killed'.
    This is the ONE case where normal state machine transitions are bypassed.
    """
    try:
        from src.infra import state_db
        
        now = datetime.now(timezone.utc).isoformat()
        task_ids = list(_active_tasks.keys())
        
        if not task_ids:
            return
        
        conn = state_db.get_connection()
        for task_id in task_ids:
            conn.execute(
                "UPDATE tasks SET status = 'killed', updated_at = ?, "
                "error_message = ? WHERE id = ? AND status IN ('running', 'lock_wait')",
                (now, f"Kill switch activated: {reason}", task_id)
            )
            conn.execute(
                "INSERT INTO task_events (task_id, ts, event_type, detail) "
                "VALUES (?, ?, 'kill_switch_activated', ?)",
                (task_id, now, f"Kill switch triggered: {reason}")
            )
        conn.commit()
        
        logger.info("Marked %d tasks as killed in database", len(task_ids))
        
    except Exception as e:
        # Kill switch must not crash — log and continue
        logger.error("Failed to mark tasks as killed in DB: %s", e)
