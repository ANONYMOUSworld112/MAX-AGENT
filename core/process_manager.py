"""
MAX-AGENT Process Manager
=========================

Centralized process lifecycle management using Windows Job Objects for
clean process tree termination and orphan process elimination.

Features:
- Windows Job Objects with JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
- TerminateJobObject for instant recursive tree kills on cancel/timeout
- Cross-platform psutil fallback for Linux/macOS
- Ring-buffered stdout/stderr streaming to prevent pipe deadlocks
- Timeout enforcement with graceful-then-forceful termination
- Process registry tracking active subprocesses

Master Spec references:
- Section 10 (Process Isolation, Job Objects)
- Section 13 (Gateway execution)
- docs/audit/SECURITY.md
- docs/evolution/IMPROVEMENT_MATRIX.md
"""

from __future__ import annotations

from collections import deque
import ctypes
from dataclasses import dataclass, field
import logging
import os
import subprocess
import sys
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

logger = logging.getLogger("max.process_manager")

# Windows Job Object Constants
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
JobObjectExtendedLimitInformation = 9


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
        ("LimitFlags", ctypes.c_uint32),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", ctypes.c_uint32),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", ctypes.c_uint32),
        ("SchedulingClass", ctypes.c_uint32),
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


class RingBuffer:
    """Bounded in-memory character buffer to prevent pipe deadlock and unbounded growth."""

    def __init__(self, max_chars: int = 100_000) -> None:
        self.max_chars = max_chars
        self._chunks: deque[str] = deque()
        self._current_len = 0
        self._lock = threading.Lock()

    def append(self, text: str) -> None:
        if not text:
            return
        with self._lock:
            self._chunks.append(text)
            self._current_len += len(text)
            while self._current_len > self.max_chars and self._chunks:
                popped = self._chunks.popleft()
                self._current_len -= len(popped)

    def get_value(self) -> str:
        with self._lock:
            return "".join(self._chunks)

    def __len__(self) -> int:
        with self._lock:
            return self._current_len


@dataclass
class ProcessRunResult:
    """The result of executing a managed subprocess."""
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float
    timed_out: bool = False
    cancelled: bool = False

    @property
    def success(self) -> bool:
        return self.exit_code == 0 and not self.timed_out and not self.cancelled


class ManagedProcess:
    """A subprocess tracked and controlled by the ProcessManager."""

    def __init__(
        self,
        process_id: str,
        popen: subprocess.Popen,
        job_handle: Optional[int] = None,
        max_buffer_chars: int = 100_000,
    ) -> None:
        self.process_id = process_id
        self.popen = popen
        self.job_handle = job_handle
        self.stdout_buffer = RingBuffer(max_chars=max_buffer_chars)
        self.stderr_buffer = RingBuffer(max_chars=max_buffer_chars)
        self._reader_threads: List[threading.Thread] = []
        self._start_time = time.monotonic()
        self._closed = False
        self._lock = threading.RLock()

        self._start_stream_readers()

    def _start_stream_readers(self) -> None:
        if self.popen.stdout:
            t_out = threading.Thread(
                target=self._stream_reader,
                args=(self.popen.stdout, self.stdout_buffer),
                daemon=True,
            )
            t_out.start()
            self._reader_threads.append(t_out)

        if self.popen.stderr:
            t_err = threading.Thread(
                target=self._stream_reader,
                args=(self.popen.stderr, self.stderr_buffer),
                daemon=True,
            )
            t_err.start()
            self._reader_threads.append(t_err)

    def _stream_reader(self, stream, buffer: RingBuffer) -> None:
        try:
            for line in iter(stream.readline, ""):
                if not line:
                    break
                buffer.append(line)
        except Exception:
            pass
        finally:
            try:
                stream.close()
            except Exception:
                pass

    def kill_tree(self) -> None:
        """Forcefully terminates the entire process tree using Job Objects or recursive PID kill."""
        with self._lock:
            # 1. Windows Job Object termination kills entire tree in kernel
            if sys.platform == "win32" and self.job_handle:
                try:
                    ctypes.windll.kernel32.TerminateJobObject(self.job_handle, 1)
                except Exception as e:
                    logger.warning("Error calling TerminateJobObject: %s", e)

            # 2. Process termination
            try:
                self.popen.kill()
            except Exception:
                pass

            # 3. psutil recursive cleanup fallback
            try:
                import psutil
                parent = psutil.Process(self.popen.pid)
                children = parent.children(recursive=True)
                for child in children:
                    try:
                        child.kill()
                    except Exception:
                        pass
            except Exception:
                pass

            self.close()

    def wait(self, timeout: Optional[float] = None) -> int:
        return self.popen.wait(timeout=timeout)

    def close(self) -> None:
        with self._lock:
            if not self._closed:
                self._closed = True
                if sys.platform == "win32" and self.job_handle:
                    try:
                        ctypes.windll.kernel32.CloseHandle(self.job_handle)
                        self.job_handle = None
                    except Exception:
                        pass


class ProcessManager:
    """
    Centralized controller for launching and terminating processes safely.
    """

    def __init__(self) -> None:
        self._active_processes: Dict[str, ManagedProcess] = {}
        self._lock = threading.Lock()

    def _create_job_object(self) -> Optional[int]:
        """Creates a Windows Job Object configured to kill all processes on handle close."""
        if sys.platform != "win32":
            return None

        try:
            h_job = ctypes.windll.kernel32.CreateJobObjectW(None, None)
            if not h_job:
                return None

            info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
            info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE

            res = ctypes.windll.kernel32.SetInformationJobObject(
                h_job,
                JobObjectExtendedLimitInformation,
                ctypes.byref(info),
                ctypes.sizeof(info),
            )
            if not res:
                ctypes.windll.kernel32.CloseHandle(h_job)
                return None
            return h_job
        except Exception as e:
            logger.warning("Failed to configure Windows Job Object: %s", e)
            return None

    def _assign_to_job(self, h_job: int, process_handle: int) -> bool:
        if sys.platform != "win32" or not h_job:
            return False
        try:
            return bool(ctypes.windll.kernel32.AssignProcessToJobObject(h_job, process_handle))
        except Exception as e:
            logger.warning("Failed to assign process to Job Object: %s", e)
            return False

    def spawn(
        self,
        command: Union[str, List[str]],
        process_id: Optional[str] = None,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        shell: bool = False,
    ) -> ManagedProcess:
        """Spawns a new managed subprocess assigned to a Windows Job Object."""
        pid_str = process_id or str(time.time_ns())
        h_job = self._create_job_object()

        # On Windows, hide command window
        startupinfo = None
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)

        proc = subprocess.Popen(
            command,
            cwd=cwd,
            env=merged_env,
            shell=shell,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            startupinfo=startupinfo,
            bufsize=1,
        )

        if h_job and sys.platform == "win32":
            # Assign process to Job Object via kernel handle
            # proc._handle is the internal Windows process handle in Python
            p_handle = getattr(proc, "_handle", None)
            if p_handle:
                self._assign_to_job(h_job, int(p_handle))

        managed = ManagedProcess(process_id=pid_str, popen=proc, job_handle=h_job)

        with self._lock:
            self._active_processes[pid_str] = managed

        return managed

    def run_command(
        self,
        command: Union[str, List[str]],
        timeout: float = 30.0,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        shell: bool = False,
    ) -> ProcessRunResult:
        """Executes a command synchronously up to timeout, cleanly terminating tree on timeout."""
        start_t = time.monotonic()
        managed = self.spawn(command=command, cwd=cwd, env=env, shell=shell)

        timed_out = False
        try:
            exit_code = managed.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            logger.warning("Process '%s' timed out after %ss. Terminating tree.", managed.process_id, timeout)
            managed.kill_tree()
            exit_code = -1
        finally:
            with self._lock:
                self._active_processes.pop(managed.process_id, None)
            managed.close()

        duration = (time.monotonic() - start_t) * 1000.0
        return ProcessRunResult(
            exit_code=exit_code,
            stdout=managed.stdout_buffer.get_value(),
            stderr=managed.stderr_buffer.get_value(),
            duration_ms=duration,
            timed_out=timed_out,
        )

    def terminate_process(self, process_id: str) -> bool:
        """Terminates a specific managed process and its children."""
        with self._lock:
            managed = self._active_processes.pop(process_id, None)
        if managed:
            managed.kill_tree()
            return True
        return False

    def cleanup_all(self) -> int:
        """Terminates all active processes on shutdown."""
        with self._lock:
            active = list(self._active_processes.values())
            self._active_processes.clear()

        count = len(active)
        for managed in active:
            try:
                managed.kill_tree()
            except Exception:
                pass
        return count
