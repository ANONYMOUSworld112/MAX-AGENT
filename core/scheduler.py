"""
MAX-AGENT TaskScheduler Engine
==============================

Deterministic, transactional scheduler backed by SQLite WAL with:
- Injectable Clock for time-travel and deterministic testing
- Priority queue with priority aging to prevent task starvation
- RFC 5545 RRULE recurrence engine (DAILY, WEEKLY, HOURLY, BYDAY, COUNT, UNTIL)
- DST fold/gap handling with ZoneInfo
- Misfire policies (fire_immediately, skip, run_once) and deadline enforcement
- Crash recovery on startup (reset stuck RUNNING jobs)
- Concurrent TaskGraph dispatch subject to Dijkstra-ordered Resource Leases

Master Spec references:
- Section 7 (Reminder scheduling, DST)
- Section 8 (Task lifecycle, priority bands, aging, deadlines)
- Section 9 (TaskGraph representation & concurrency)
- Conflict CF-08 (Daemon scheduler replacing schtasks.exe)
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import contextlib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
import time
from enum import Enum
import json
import logging
import os
import re
import sqlite3
import threading
from typing import Any, Callable, Dict, Iterator, List, Optional, Set, Tuple, Union
from zoneinfo import ZoneInfo

from core.clock import Clock, SystemClock
from core.contracts import ActionResult, BlockedReason, EventEnvelope, _new_id, _now_utc
from core.events import EventBus
from core.max_infra.lock_manager import LockManager, LockTimeoutError, ResourceRequest
from core.max_infra.state_db import StateDB
from core.task_graph import EdgeCondition, NodeStatus, TaskGraph, TaskNode

logger = logging.getLogger("max.scheduler")


class JobStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    MISFIRED = "MISFIRED"
    PAUSED = "PAUSED"


class MisfirePolicy(str, Enum):
    FIRE_IMMEDIATELY = "fire_immediately"
    SKIP = "skip"
    RUN_ONCE = "run_once"


DAY_MAP = {
    "MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6
}


@dataclass
class ScheduledJob:
    """A persistent unit of scheduled work."""
    job_id: str
    name: str
    task_type: str
    payload: Dict[str, Any]
    priority: int                                 # 1=CRITICAL, 2=HIGH, 3=DEFAULT, 4=LOW
    next_fire_time: datetime                      # Timezone-aware (UTC)
    rrule: Optional[str] = None                   # RFC 5545 string
    tz_name: str = "UTC"
    misfire_policy: MisfirePolicy = MisfirePolicy.FIRE_IMMEDIATELY
    status: JobStatus = JobStatus.PENDING
    deadline: Optional[datetime] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    run_count: int = 0

    def effective_priority(self, now: datetime, aging_interval_seconds: float = 60.0) -> int:
        """
        Calculates aging priority.
        As a job waits past its next_fire_time, its priority integer decreases (increases urgency).
        """
        if now <= self.next_fire_time:
            return self.priority
        overdue_seconds = (now - self.next_fire_time).total_seconds()
        aging_steps = int(overdue_seconds / aging_interval_seconds)
        return max(1, self.priority - aging_steps)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "name": self.name,
            "task_type": self.task_type,
            "payload": self.payload,
            "priority": self.priority,
            "next_fire_time": self.next_fire_time.isoformat(),
            "rrule": self.rrule,
            "tz_name": self.tz_name,
            "misfire_policy": self.misfire_policy.value,
            "status": self.status.value,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "run_count": self.run_count,
        }

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> ScheduledJob:
        return cls(
            job_id=row["job_id"],
            name=row["name"],
            task_type=row["task_type"],
            payload=json.loads(row["payload_json"]),
            priority=row["priority"],
            next_fire_time=datetime.fromisoformat(row["next_fire_time"]),
            rrule=row["rrule"],
            tz_name=row["tz_name"],
            misfire_policy=MisfirePolicy(row["misfire_policy"]),
            status=JobStatus(row["status"]),
            deadline=datetime.fromisoformat(row["deadline"]) if row["deadline"] else None,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            run_count=row["run_count"] if "run_count" in row.keys() else 0,
        )


# ---------------------------------------------------------------------------
# RFC 5545 Recurrence Engine
# ---------------------------------------------------------------------------

def parse_rrule(rrule_str: str) -> Dict[str, Any]:
    """Parses standard RFC 5545 RRULE parameters."""
    params: Dict[str, Any] = {}
    clean = rrule_str.strip()
    if clean.upper().startswith("RRULE:"):
        clean = clean[6:]

    parts = clean.split(";")
    for part in parts:
        if "=" not in part:
            continue
        key, val = part.split("=", 1)
        k = key.strip().upper()
        v = val.strip().upper()

        if k == "FREQ":
            params["freq"] = v
        elif k == "INTERVAL":
            params["interval"] = max(1, int(v))
        elif k == "COUNT":
            params["count"] = int(v)
        elif k == "UNTIL":
            # UTC format: 20261231T235959Z or ISO
            params["until"] = v
        elif k == "BYDAY":
            params["byday"] = [day.strip() for day in v.split(",") if day.strip() in DAY_MAP]
        elif k == "BYHOUR":
            params["byhour"] = [int(h) for h in v.split(",") if h.isdigit()]
        elif k == "BYMINUTE":
            params["byminute"] = [int(m) for m in v.split(",") if m.isdigit()]

    params.setdefault("interval", 1)
    return params


def compute_next_occurrence(
    rrule_str: str,
    after_dt: datetime,
    tz_name: str = "UTC",
    current_count: int = 0,
) -> Optional[datetime]:
    """
    Computes the next datetime occurrence adhering to RFC 5545 and DST rules.
    Returns UTC timezone-aware datetime or None if rule bounds (COUNT/UNTIL) are exceeded.
    """
    params = parse_rrule(rrule_str)
    freq = params.get("freq")
    interval = params.get("interval", 1)
    max_count = params.get("count")
    until_str = params.get("until")

    if max_count is not None and current_count >= max_count:
        return None

    # Resolve local timezone for correct calendar stepping and DST resolution
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = timezone.utc

    # Convert after_dt to local timezone
    local_dt = after_dt.astimezone(tz)

    next_local = local_dt
    if freq == "MINUTELY":
        next_local = local_dt + timedelta(minutes=interval)
    elif freq == "HOURLY":
        next_local = local_dt + timedelta(hours=interval)
    elif freq == "DAILY":
        next_local = local_dt + timedelta(days=interval)
    elif freq == "WEEKLY":
        byday = params.get("byday")
        if not byday:
            next_local = local_dt + timedelta(weeks=interval)
        else:
            # Advance day by day until matching a day in byday
            target_weekdays = {DAY_MAP[d] for d in byday}
            candidate = local_dt + timedelta(days=1)
            # Find next matching day
            while candidate.weekday() not in target_weekdays:
                candidate += timedelta(days=1)
            next_local = candidate
    elif freq == "MONTHLY":
        # Advance by interval months, clamping day of month if needed
        year = local_dt.year
        month = local_dt.month + interval
        year += (month - 1) // 12
        month = ((month - 1) % 12) + 1
        day = min(local_dt.day, 28)  # Safe clamping for monthly recurring
        next_local = local_dt.replace(year=year, month=month, day=day)
    elif freq == "YEARLY":
        next_local = local_dt.replace(year=local_dt.year + interval)
    else:
        # Default fallback 1 day
        next_local = local_dt + timedelta(days=1)

    # Disambiguate DST fold and gaps
    # Python 3.9+ ZoneInfo handles fold naturally; ensure localized datetime is valid
    try:
        # Replace fold=0 by default for consistent earliest occurrence
        next_local = next_local.replace(fold=0)
    except Exception:
        pass

    next_utc = next_local.astimezone(timezone.utc)

    # Check UNTIL boundary if specified
    if until_str:
        try:
            # Match 20261231T235959Z
            m = re.match(r"^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z?$", until_str)
            if m:
                until_dt = datetime(
                    int(m.group(1)), int(m.group(2)), int(m.group(3)),
                    int(m.group(4)), int(m.group(5)), int(m.group(6)),
                    tzinfo=timezone.utc
                )
            else:
                until_dt = datetime.fromisoformat(until_str).astimezone(timezone.utc)

            if next_utc > until_dt:
                return None
        except Exception as e:
            logger.warning("Error parsing UNTIL datetime '%s': %s", until_str, e)

    return next_utc


# ---------------------------------------------------------------------------
# TaskScheduler Class
# ---------------------------------------------------------------------------

class TaskScheduler:
    """
    Unified transactional scheduler backed by SQLite WAL.
    """

    def __init__(
        self,
        db_path: str = "max_state.db",
        clock: Optional[Clock] = None,
        event_bus: Optional[EventBus] = None,
        state_db: Optional[StateDB] = None,
        aging_interval_seconds: float = 60.0,
        misfire_grace_seconds: float = 300.0,
    ) -> None:
        self.db_path = db_path
        self.clock = clock or SystemClock()
        self.event_bus = event_bus or EventBus()
        self.state_db = state_db
        self.aging_interval_seconds = aging_interval_seconds
        self.misfire_grace_seconds = misfire_grace_seconds
        self._lock = threading.RLock()
        self._conn: Optional[sqlite3.Connection] = None

        self._init_db()
        self.recover_on_startup()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            parent = os.path.dirname(self.db_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=30.0)
            self._conn.row_factory = sqlite3.Row
            with self._conn:
                self._conn.execute("PRAGMA journal_mode = WAL;")
                self._conn.execute("PRAGMA synchronous = NORMAL;")
        return self._conn

    def _init_db(self) -> None:
        with self._lock:
            conn = self._get_conn()
            with conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS scheduled_jobs (
                        job_id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        task_type TEXT NOT NULL,
                        payload_json TEXT NOT NULL DEFAULT '{}',
                        priority INTEGER NOT NULL DEFAULT 3,
                        next_fire_time TEXT NOT NULL,
                        rrule TEXT,
                        tz_name TEXT NOT NULL DEFAULT 'UTC',
                        misfire_policy TEXT NOT NULL DEFAULT 'fire_immediately',
                        status TEXT NOT NULL DEFAULT 'PENDING',
                        deadline TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        run_count INTEGER NOT NULL DEFAULT 0
                    );
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_jobs_status_fire ON scheduled_jobs(status, next_fire_time);"
                )

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    def recover_on_startup(self) -> int:
        """Resets any jobs left in RUNNING state back to PENDING following crash."""
        with self._lock:
            conn = self._get_conn()
            now_iso = self.clock.now().isoformat()
            with conn:
                cur = conn.execute(
                    """
                    UPDATE scheduled_jobs
                    SET status = 'PENDING', updated_at = ?
                    WHERE status = 'RUNNING'
                    """,
                    (now_iso,)
                )
                count = cur.rowcount
            if count > 0:
                logger.warning("Scheduler startup recovery: reset %d orphaned RUNNING jobs to PENDING", count)
            return count

    def schedule_job(
        self,
        name: str,
        fire_time: datetime,
        task_type: str = "reminder",
        payload: Optional[Dict[str, Any]] = None,
        priority: int = 3,
        rrule: Optional[str] = None,
        tz_name: str = "UTC",
        misfire_policy: MisfirePolicy = MisfirePolicy.FIRE_IMMEDIATELY,
        deadline: Optional[datetime] = None,
        job_id: Optional[str] = None,
    ) -> ScheduledJob:
        """Persists a new scheduled job."""
        with self._lock:
            conn = self._get_conn()
            jid = job_id or _new_id()
            now_utc = self.clock.now()

            # Ensure fire_time is timezone-aware UTC
            if fire_time.tzinfo is None:
                fire_time = fire_time.replace(tzinfo=timezone.utc)
            else:
                fire_time = fire_time.astimezone(timezone.utc)

            dl_utc = None
            if deadline:
                if deadline.tzinfo is None:
                    dl_utc = deadline.replace(tzinfo=timezone.utc)
                else:
                    dl_utc = deadline.astimezone(timezone.utc)

            job = ScheduledJob(
                job_id=jid,
                name=name,
                task_type=task_type,
                payload=payload or {},
                priority=priority,
                next_fire_time=fire_time,
                rrule=rrule,
                tz_name=tz_name,
                misfire_policy=misfire_policy,
                status=JobStatus.PENDING,
                deadline=dl_utc,
                created_at=now_utc,
                updated_at=now_utc,
                run_count=0,
            )

            with conn:
                conn.execute(
                    """
                    INSERT INTO scheduled_jobs (
                        job_id, name, task_type, payload_json, priority,
                        next_fire_time, rrule, tz_name, misfire_policy,
                        status, deadline, created_at, updated_at, run_count
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        job.job_id,
                        job.name,
                        job.task_type,
                        json.dumps(job.payload),
                        job.priority,
                        job.next_fire_time.isoformat(),
                        job.rrule,
                        job.tz_name,
                        job.misfire_policy.value,
                        job.status.value,
                        job.deadline.isoformat() if job.deadline else None,
                        job.created_at.isoformat(),
                        job.updated_at.isoformat(),
                        job.run_count,
                    )
                )

            self.event_bus.publish(EventEnvelope(
                event_type="scheduler.job_scheduled",
                correlation_id=job.job_id,
                actor="scheduler",
                payload={"job_id": job.job_id, "name": job.name, "fire_time": job.next_fire_time.isoformat()},
            ))
            logger.info("Scheduled job '%s' (%s) for %s", job.name, job.job_id, job.next_fire_time.isoformat())
            return job

    def get_job(self, job_id: str) -> Optional[ScheduledJob]:
        with self._lock:
            conn = self._get_conn()
            cur = conn.execute("SELECT * FROM scheduled_jobs WHERE job_id = ?", (job_id,))
            row = cur.fetchone()
            return ScheduledJob.from_row(row) if row else None

    def list_jobs(self, status: Optional[Union[JobStatus, str]] = None) -> List[ScheduledJob]:
        with self._lock:
            conn = self._get_conn()
            if status is not None:
                st_val = status.value if isinstance(status, JobStatus) else status
                cur = conn.execute("SELECT * FROM scheduled_jobs WHERE status = ? ORDER BY next_fire_time", (st_val,))
            else:
                cur = conn.execute("SELECT * FROM scheduled_jobs ORDER BY next_fire_time")
            return [ScheduledJob.from_row(r) for r in cur.fetchall()]

    def cancel_job(self, job_id: str) -> bool:
        with self._lock:
            conn = self._get_conn()
            now_iso = self.clock.now().isoformat()
            with conn:
                cur = conn.execute(
                    "UPDATE scheduled_jobs SET status = 'CANCELLED', updated_at = ? WHERE job_id = ? AND status != 'CANCELLED'",
                    (now_iso, job_id)
                )
                if cur.rowcount > 0:
                    self.event_bus.publish(EventEnvelope(
                        event_type="scheduler.job_cancelled",
                        correlation_id=job_id,
                        actor="scheduler",
                        payload={"job_id": job_id},
                    ))
                    logger.info("Cancelled job '%s'", job_id)
                    return True
                return False

    def snooze_job(self, job_id: str, delta: timedelta) -> ScheduledJob:
        with self._lock:
            job = self.get_job(job_id)
            if not job:
                raise KeyError(f"Job '{job_id}' not found")

            now_utc = self.clock.now()
            new_fire = now_utc + delta
            conn = self._get_conn()
            with conn:
                conn.execute(
                    """
                    UPDATE scheduled_jobs
                    SET next_fire_time = ?, status = 'PENDING', updated_at = ?
                    WHERE job_id = ?
                    """,
                    (new_fire.isoformat(), now_utc.isoformat(), job_id)
                )

            logger.info("Snoozed job '%s' to %s", job_id, new_fire.isoformat())
            return self.get_job(job_id)  # type: ignore

    def poll(self, max_jobs: int = 10) -> List[ScheduledJob]:
        """
        Polls for due jobs, handles misfires and deadlines, applies priority aging,
        marks selected jobs as RUNNING, and returns them for execution.
        """
        with self._lock:
            conn = self._get_conn()
            now_utc = self.clock.now()
            now_iso = now_utc.isoformat()

            cur = conn.execute(
                "SELECT * FROM scheduled_jobs WHERE status = 'PENDING' AND next_fire_time <= ? ORDER BY next_fire_time ASC",
                (now_iso,)
            )
            rows = cur.fetchall()
            if not rows:
                return []

            due_jobs = [ScheduledJob.from_row(r) for r in rows]
            ready_to_run: List[ScheduledJob] = []

            for job in due_jobs:
                # 1. Check Deadline
                if job.deadline and now_utc > job.deadline:
                    with conn:
                        conn.execute(
                            "UPDATE scheduled_jobs SET status = 'MISFIRED', updated_at = ? WHERE job_id = ?",
                            (now_iso, job.job_id)
                        )
                    self.event_bus.publish(EventEnvelope(
                        event_type="scheduler.job_misfired",
                        correlation_id=job.job_id,
                        actor="scheduler",
                        payload={"job_id": job.job_id, "reason": "deadline_exceeded"},
                    ))
                    logger.warning("Job '%s' passed deadline %s without firing -> MISFIRED", job.name, job.deadline.isoformat())
                    continue

                # 2. Check Misfire Policy for overdue recurrence
                overdue = (now_utc - job.next_fire_time).total_seconds()
                if overdue > self.misfire_grace_seconds:
                    if job.misfire_policy == MisfirePolicy.SKIP and job.rrule:
                        # Advance past missed runs to the next future occurrence
                        next_dt = compute_next_occurrence(job.rrule, now_utc, job.tz_name, job.run_count)
                        if next_dt:
                            with conn:
                                conn.execute(
                                    "UPDATE scheduled_jobs SET next_fire_time = ?, updated_at = ? WHERE job_id = ?",
                                    (next_dt.isoformat(), now_iso, job.job_id)
                                )
                            logger.info("Job '%s' missed fire time; misfire_policy=skip advanced to %s", job.name, next_dt.isoformat())
                            continue
                        else:
                            with conn:
                                conn.execute(
                                    "UPDATE scheduled_jobs SET status = 'COMPLETED', updated_at = ? WHERE job_id = ?",
                                    (now_iso, job.job_id)
                                )
                            continue

                ready_to_run.append(job)

            if not ready_to_run:
                return []

            # 3. Sort by priority aging: (effective_priority, next_fire_time, created_at)
            ready_to_run.sort(
                key=lambda j: (
                    j.effective_priority(now_utc, self.aging_interval_seconds),
                    j.next_fire_time,
                    j.created_at,
                )
            )

            selected = ready_to_run[:max_jobs]

            # 4. Mark selected jobs as RUNNING
            with conn:
                for job in selected:
                    conn.execute(
                        "UPDATE scheduled_jobs SET status = 'RUNNING', updated_at = ? WHERE job_id = ?",
                        (now_iso, job.job_id)
                    )
                    job.status = JobStatus.RUNNING
                    self.event_bus.publish(EventEnvelope(
                        event_type="scheduler.job_fired",
                        correlation_id=job.job_id,
                        actor="scheduler",
                        payload={"job_id": job.job_id, "name": job.name},
                    ))

            return selected

    def complete_job(self, job_id: str, success: bool = True) -> Optional[ScheduledJob]:
        """
        Marks a job as complete. If recurring, computes the next occurrence and reschedules.
        """
        with self._lock:
            job = self.get_job(job_id)
            if not job:
                return None

            conn = self._get_conn()
            now_utc = self.clock.now()
            now_iso = now_utc.isoformat()
            new_run_count = job.run_count + 1

            if job.rrule:
                next_fire = compute_next_occurrence(
                    job.rrule,
                    after_dt=job.next_fire_time,
                    tz_name=job.tz_name,
                    current_count=new_run_count,
                )
                if next_fire:
                    with conn:
                        conn.execute(
                            """
                            UPDATE scheduled_jobs
                            SET next_fire_time = ?, status = 'PENDING', run_count = ?, updated_at = ?
                            WHERE job_id = ?
                            """,
                            (next_fire.isoformat(), new_run_count, now_iso, job_id)
                        )
                    self.event_bus.publish(EventEnvelope(
                        event_type="scheduler.job_rescheduled",
                        correlation_id=job_id,
                        actor="scheduler",
                        payload={"job_id": job_id, "next_fire_time": next_fire.isoformat(), "run_count": new_run_count},
                    ))
                    logger.info("Rescheduled recurring job '%s' for %s (run %d)", job.name, next_fire.isoformat(), new_run_count)
                    return self.get_job(job_id)

            # Not recurring or reached limit -> COMPLETED
            with conn:
                conn.execute(
                    """
                    UPDATE scheduled_jobs
                    SET status = 'COMPLETED', run_count = ?, updated_at = ?
                    WHERE job_id = ?
                    """,
                    (new_run_count, now_iso, job_id)
                )

            self.event_bus.publish(EventEnvelope(
                event_type="scheduler.job_completed",
                correlation_id=job_id,
                actor="scheduler",
                payload={"job_id": job_id, "success": success},
            ))
            logger.info("Job '%s' completed successfully", job.name)
            return self.get_job(job_id)


# ---------------------------------------------------------------------------
# Concurrent TaskGraph Dispatcher
# ---------------------------------------------------------------------------

class TaskGraphDispatcher:
    """
    Executes a TaskGraph with parallel workers subject to Dijkstra-ordered resource leases.
    """

    def __init__(
        self,
        lock_manager: LockManager,
        max_workers: int = 4,
        clock: Optional[Clock] = None,
    ) -> None:
        self.lock_manager = lock_manager
        self.max_workers = max_workers
        self.clock = clock or SystemClock()

    def dispatch(
        self,
        graph: TaskGraph,
        worker_fn: Callable[[TaskNode], ActionResult],
        timeout: float = 60.0,
    ) -> Dict[str, ActionResult]:
        """
        Executes ready TaskNodes concurrently.

        Rules:
        - Independent nodes run in parallel.
        - Nodes requiring conflicting resources serialize safely via LockManager.
        - Edge conditions (ON_SUCCESS, ON_FAILURE, ALWAYS) gate downstream steps.
        """
        completed: Set[str] = set()
        failed: Set[str] = set()
        results: Dict[str, ActionResult] = {}

        # Lock to synchronize state across worker threads
        state_lock = threading.Lock()
        active_futures: Dict[Any, Tuple[str, List[str]]] = {}  # future -> (node_id, acquired_resources)
        claimed_resources: Set[str] = set()

        start_time = time.time()

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            while not graph.is_complete():
                if time.time() - start_time > timeout:
                    raise TimeoutError(f"TaskGraph {graph.graph_id} dispatch exceeded timeout of {timeout}s")

                with state_lock:
                    ready_nodes = graph.get_ready_nodes(completed, failed)

                # Attempt to dispatch ready nodes
                dispatched_any = False
                for node in ready_nodes:
                    if node.status != NodeStatus.PENDING:
                        continue

                    # Determine required resources
                    req_res = []
                    if node.task and node.task.resources_required:
                        req_res = list(node.task.resources_required)
                    elif "resources" in node.intent.parameters:
                        req_res = list(node.intent.parameters["resources"])

                    can_run = False
                    with state_lock:
                        if not req_res:
                            can_run = True
                        else:
                            has_conflict = any(
                                self.lock_manager.is_locked(r) or (r in claimed_resources)
                                for r in req_res
                            )
                            if not has_conflict:
                                can_run = True
                                claimed_resources.update(req_res)

                    if can_run:
                        with state_lock:
                            node.status = NodeStatus.RUNNING
                            if node.task:
                                node.task.status = NodeStatus.RUNNING

                        def make_runner(t_node: TaskNode, resources: List[str]):
                            def _run():
                                if resources:
                                    with self.lock_manager.acquire(resources, task_id=t_node.node_id, timeout=5.0):
                                        return worker_fn(t_node)
                                else:
                                    return worker_fn(t_node)
                            return _run

                        future = executor.submit(make_runner(node, req_res))
                        active_futures[future] = (node.node_id, req_res)
                        dispatched_any = True

                # Check completed futures
                done_futures = [f for f in active_futures if f.done()]
                for f in done_futures:
                    node_id, req_res = active_futures.pop(f)
                    node = graph.nodes[node_id]
                    with state_lock:
                        claimed_resources.difference_update(req_res)
                    try:
                        res = f.result()
                        results[node_id] = res
                        with state_lock:
                            node.result = res
                            if res.success:
                                node.status = NodeStatus.COMPLETED
                                completed.add(node_id)
                                if node.task:
                                    node.task.status = NodeStatus.COMPLETED
                            else:
                                node.status = NodeStatus.FAILED
                                failed.add(node_id)
                                if node.task:
                                    node.task.status = NodeStatus.FAILED
                    except Exception as e:
                        err_res = ActionResult(task_id=node.node_id, success=False, error_message=str(e))
                        results[node_id] = err_res
                        with state_lock:
                            node.result = err_res
                            node.status = NodeStatus.FAILED
                            failed.add(node_id)

                if not dispatched_any and not done_futures and active_futures:
                    # Workers are busy executing; sleep briefly to avoid spin
                    time.sleep(0.01)

                # Check if graph is blocked with no active futures and no ready nodes
                with state_lock:
                    if not active_futures and not graph.is_complete():
                        ready = graph.get_ready_nodes(completed, failed)
                        if not ready:
                            # Mark remaining unreachable PENDING nodes as SKIPPED
                            for nid, n in graph.nodes.items():
                                if n.status == NodeStatus.PENDING:
                                    n.status = NodeStatus.SKIPPED
                            break

        return results
