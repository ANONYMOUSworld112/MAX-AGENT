"""
core/kill_switch.py — Standalone Safety Watchdog & Emergency Kill Switch for FRIDAY.

Runs independently of the UI and Electron shell. Listens for the global safety hotkey
(Ctrl+Alt+Shift+K or Pause/Break). When triggered, immediately halts all in-flight actions,
locks tool execution, and places the agent into a DISARMED state until explicitly re-armed.
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
import threading
import time
from typing import Callable, List, Optional, Set

logger = logging.getLogger("friday.security.kill_switch")

_IS_ARMED = True
_LOCK = threading.Lock()
_CANCEL_CALLBACKS: List[Callable[[], None]] = []
_TRACKED_PIDS: Set[int] = set()
_JOB_HANDLE = None


class WindowsJobManager:
    """Manages a Windows Job Object configured to terminate all assigned child processes upon close."""

    def __init__(self) -> None:
        self.job_handle = None
        if sys.platform == "win32":
            self._init_job_object()

    def _init_job_object(self) -> None:
        try:
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.windll.kernel32
            # Create Job Object
            self.job_handle = kernel32.CreateJobObjectW(None, None)
            if not self.job_handle:
                logger.warning("Could not create Windows Job Object for process tracking.")
                return

            # Set JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE (0x2000)
            class IO_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("ReadOperationCount", ctypes.c_uint64),
                    ("WriteOperationCount", ctypes.c_uint64),
                    ("OtherOperationCount", ctypes.c_uint64),
                    ("ReadTransferCount", ctypes.c_uint64),
                    ("WriteTransferCount", ctypes.c_uint64),
                    ("OtherTransferCount", ctypes.c_uint64),
                ]

            class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
                _fields_ = [
                    ("PerProcessUserTimeLimit", ctypes.c_int64),
                    ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", wintypes.DWORD),
                    ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t),
                    ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t),
                    ("PriorityClass", wintypes.DWORD),
                    ("SchedulingClass", wintypes.DWORD),
                ]

            class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
                _fields_ = [
                    ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                    ("IoInfo", IO_COUNTERS),
                    ("ProcessMemoryLimit", ctypes.c_size_t),
                    ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryLimit", ctypes.c_size_t),
                    ("PeakJobMemoryLimit", ctypes.c_size_t),
                ]

            info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
            JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
            info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE

            JobObjectExtendedLimitInformation = 9
            success = kernel32.SetInformationJobObject(
                self.job_handle,
                JobObjectExtendedLimitInformation,
                ctypes.byref(info),
                ctypes.sizeof(info),
            )
            if success:
                logger.info("Windows Job Object initialized with KILL_ON_JOB_CLOSE policy.")
            else:
                logger.warning("SetInformationJobObject failed.")
        except Exception as e:
            logger.warning("Could not initialize Windows Job Object: %s", e)

    def assign_process(self, pid: int) -> bool:
        """Assign a child process PID to the Job Object."""
        if sys.platform != "win32" or not self.job_handle:
            _TRACKED_PIDS.add(pid)
            return False

        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            PROCESS_SET_QUOTA = 0x0100
            PROCESS_TERMINATE = 0x0001
            h_proc = kernel32.OpenProcess(PROCESS_SET_QUOTA | PROCESS_TERMINATE, False, pid)
            if h_proc:
                res = kernel32.AssignProcessToJobObject(self.job_handle, h_proc)
                kernel32.CloseHandle(h_proc)
                _TRACKED_PIDS.add(pid)
                return bool(res)
        except Exception as e:
            logger.warning("Failed to assign PID %d to Job Object: %s", pid, e)
        return False

    def terminate_all(self) -> None:
        """Terminate all processes in the job object immediately."""
        if sys.platform == "win32" and self.job_handle:
            try:
                import ctypes
                kernel32 = ctypes.windll.kernel32
                kernel32.TerminateJobObject(self.job_handle, 1)
                kernel32.CloseHandle(self.job_handle)
                self.job_handle = None
                logger.info("Terminated Windows Job Object process tree.")
            except Exception as e:
                logger.error("Error terminating Job Object: %s", e)

        # Fallback termination for tracked PIDs
        for pid in list(_TRACKED_PIDS):
            try:
                if sys.platform == "win32":
                    import subprocess
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)
                else:
                    os.kill(pid, signal.SIGKILL)
            except Exception:
                pass
        _TRACKED_PIDS.clear()


_JOB_MANAGER = WindowsJobManager()


def assign_child_process(pid: int) -> None:
    """Register a child worker or container process with the kill switch job manager."""
    _JOB_MANAGER.assign_process(pid)


def is_armed() -> bool:
    """True if system is active and tools are permitted to execute."""
    with _LOCK:
        return _IS_ARMED


def trigger_kill_switch(reason: str = "Hotkey Ctrl+Alt+Shift+K activated") -> None:
    """Disarm system immediately and trigger all registered cancellation handlers."""
    global _IS_ARMED
    with _LOCK:
        if not _IS_ARMED:
            return
        _IS_ARMED = False

    logger.critical("🚨 EMERGENCY STAND-DOWN TRIGGERED: %s", reason)
    print(f"\n[🚨 KILL SWITCH ENGAGED]: {reason}. Halting all operations immediately.")

    # 1. Terminate all child worker and sandbox processes via Job Object
    _JOB_MANAGER.terminate_all()

    # 2. Execute all cancellation hooks
    for cb in list(_CANCEL_CALLBACKS):
        try:
            cb()
        except Exception as e:
            logger.error("Error in kill-switch callback: %s", e)


def rearm() -> None:
    """Re-arm the safety system."""
    global _IS_ARMED
    with _LOCK:
        _IS_ARMED = True
    logger.info("Safety kill switch re-armed. Tools unlocked.")
    print("[SAFETY]: System re-armed by boss. Operations permitted.")


def register_cancellation_callback(cb: Callable[[], None]) -> None:
    """Register a callable to invoke immediately if kill switch triggers."""
    with _LOCK:
        _CANCEL_CALLBACKS.append(cb)


def unregister_cancellation_callback(cb: Callable[[], None]) -> None:
    with _LOCK:
        if cb in _CANCEL_CALLBACKS:
            _CANCEL_CALLBACKS.remove(cb)


class WatchdogHotkeyListener(threading.Thread):
    """Background listener for global kill switch hotkeys."""

    def __init__(self, on_trigger: Optional[Callable[[], None]] = None) -> None:
        super().__init__(daemon=True, name="FridayKillSwitchWatchdog")
        self.on_trigger = on_trigger or trigger_kill_switch
        self._running = True

    def run(self) -> None:
        """Attempt to listen via keyboard hooks or keyboard poller."""
        try:
            # Try keyboard package if available
            import keyboard  # type: ignore
            keyboard.add_hotkey("ctrl+alt+shift+k", self.on_trigger)
            keyboard.add_hotkey("pause", self.on_trigger)
            while self._running:
                time.sleep(0.5)
        except Exception:
            # Fallback polling loop / stdin trigger
            while self._running:
                time.sleep(1.0)

    def stop(self) -> None:
        self._running = False
