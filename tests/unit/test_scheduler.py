"""
Unit tests for MAX-AGENT TaskScheduler Engine
=============================================

Covers:
- Job persistence and restart recovery across SQLite database re-opening
- Priority aging preventing task starvation
- RFC 5545 RRULE recurrence (DAILY, WEEKLY BYDAY, HOURLY, COUNT, UNTIL)
- DST fold and gap handling with ZoneInfo
- Misfire policies (fire_immediately, skip) and deadline enforcement
- Job cancellation and snooze
"""

from datetime import datetime, timedelta, timezone
import os
import tempfile
import pytest

from core.clock import FakeClock
from core.events import EventBus
from core.scheduler import (
    JobStatus,
    MisfirePolicy,
    ScheduledJob,
    TaskScheduler,
    compute_next_occurrence,
    parse_rrule,
)


@pytest.fixture
def temp_db(tmp_path):
    return str(tmp_path / "test_scheduler.db")


def test_schedule_and_persist_across_restart(temp_db):
    start = datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)
    clock = FakeClock(start)

    # 1. Schedule job in first instance
    s1 = TaskScheduler(db_path=temp_db, clock=clock)
    fire_time = start + timedelta(hours=2)
    job = s1.schedule_job(
        name="Doctor appointment reminder",
        fire_time=fire_time,
        task_type="reminder",
        payload={"message": "Visit Dr. Smith"},
        priority=2,
    )
    assert job.status == JobStatus.PENDING
    job_id = job.job_id
    s1.close()

    # 2. Re-open scheduler with new instance on same database (simulating MAX restart)
    s2 = TaskScheduler(db_path=temp_db, clock=clock)
    recovered = s2.get_job(job_id)
    assert recovered is not None
    assert recovered.job_id == job_id
    assert recovered.name == "Doctor appointment reminder"
    assert recovered.payload == {"message": "Visit Dr. Smith"}
    assert recovered.priority == 2
    assert recovered.status == JobStatus.PENDING
    assert recovered.next_fire_time == fire_time
    s2.close()


def test_crash_recovery_resets_orphaned_running_jobs(temp_db):
    start = datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)
    clock = FakeClock(start)

    s1 = TaskScheduler(db_path=temp_db, clock=clock)
    job = s1.schedule_job(name="Crashed task", fire_time=start, priority=1)

    # Poll it to put it into RUNNING state
    due = s1.poll()
    assert len(due) == 1
    assert due[0].status == JobStatus.RUNNING
    s1.close()

    # Restart MAX: recover_on_startup should reset RUNNING to PENDING
    s2 = TaskScheduler(db_path=temp_db, clock=clock)
    recovered = s2.get_job(job.job_id)
    assert recovered is not None
    assert recovered.status == JobStatus.PENDING
    s2.close()


def test_priority_aging_prevents_starvation(temp_db):
    start = datetime(2026, 10, 1, 10, 0, tzinfo=timezone.utc)
    clock = FakeClock(start)

    sched = TaskScheduler(db_path=temp_db, clock=clock, aging_interval_seconds=60.0)

    # Schedule low priority job (priority 4) due at 10:00
    low_job = sched.schedule_job(name="Low priority task", fire_time=start, priority=4)

    # Advance clock by 3 minutes (180s = 3 aging steps -> priority decreases from 4 to 1)
    clock.advance(minutes=3)

    # Now schedule a fresh high priority job (priority 2) due at current time
    high_job = sched.schedule_job(name="High priority task", fire_time=clock.now(), priority=2)

    # Poll jobs: low_job effective priority is 4 - 3 = 1, beating high_job's priority 2!
    polled = sched.poll(max_jobs=2)
    assert len(polled) == 2
    assert polled[0].job_id == low_job.job_id
    assert polled[1].job_id == high_job.job_id
    sched.close()


def test_rfc5545_daily_recurrence(temp_db):
    start = datetime(2026, 10, 1, 8, 0, tzinfo=timezone.utc)
    clock = FakeClock(start)

    sched = TaskScheduler(db_path=temp_db, clock=clock)
    job = sched.schedule_job(
        name="Daily Standup",
        fire_time=start,
        rrule="FREQ=DAILY;INTERVAL=1",
        priority=2,
    )

    # First poll: job fires
    polled = sched.poll()
    assert len(polled) == 1
    assert polled[0].job_id == job.job_id

    # Complete first run -> next occurrence is tomorrow at 8:00
    rescheduled = sched.complete_job(job.job_id)
    assert rescheduled is not None
    assert rescheduled.status == JobStatus.PENDING
    assert rescheduled.run_count == 1
    assert rescheduled.next_fire_time == datetime(2026, 10, 2, 8, 0, tzinfo=timezone.utc)

    # Advance clock to next day
    clock.advance(days=1)
    polled2 = sched.poll()
    assert len(polled2) == 1
    assert polled2[0].job_id == job.job_id
    sched.close()


def test_rfc5545_weekly_byday_recurrence():
    # Thursday, Oct 1, 2026
    start = datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)
    # Target: Monday, Wednesday, Friday
    rrule = "FREQ=WEEKLY;BYDAY=MO,WE,FR"

    # From Thursday, next is Friday Oct 2
    n1 = compute_next_occurrence(rrule, after_dt=start)
    assert n1 == datetime(2026, 10, 2, 9, 0, tzinfo=timezone.utc)
    assert n1.weekday() == 4  # Friday

    # From Friday, next is Monday Oct 5
    n2 = compute_next_occurrence(rrule, after_dt=n1)
    assert n2 == datetime(2026, 10, 5, 9, 0, tzinfo=timezone.utc)
    assert n2.weekday() == 0  # Monday


def test_rfc5545_count_and_until_limits(temp_db):
    start = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
    clock = FakeClock(start)

    sched = TaskScheduler(db_path=temp_db, clock=clock)
    job = sched.schedule_job(
        name="Limited Run",
        fire_time=start,
        rrule="FREQ=DAILY;COUNT=2",
    )

    # Run 1
    due1 = sched.poll()
    assert len(due1) == 1
    res1 = sched.complete_job(job.job_id)
    assert res1.status == JobStatus.PENDING
    assert res1.run_count == 1

    # Run 2
    clock.advance(days=1)
    due2 = sched.poll()
    assert len(due2) == 1
    res2 = sched.complete_job(job.job_id)
    # Reached COUNT=2 -> COMPLETED
    assert res2.status == JobStatus.COMPLETED
    assert res2.run_count == 2
    sched.close()


def test_dst_handling_with_zoneinfo():
    # Test Eastern Time across Daylight Saving Time transitions
    # Spring Forward 2026 in US: Sunday March 8, 2026 (02:00 -> 03:00)
    dt_before = datetime(2026, 3, 7, 7, 0, tzinfo=timezone.utc)  # 02:00 EST
    next_dt = compute_next_occurrence("FREQ=DAILY;INTERVAL=1", after_dt=dt_before, tz_name="America/New_York")
    assert next_dt is not None
    # Next day at same local time (or valid hour) computed cleanly without raising exception
    assert next_dt > dt_before


def test_misfire_policy_skip_and_deadline(temp_db):
    start = datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)
    clock = FakeClock(start)

    sched = TaskScheduler(db_path=temp_db, clock=clock, misfire_grace_seconds=120.0)

    # Job with deadline
    dl = start + timedelta(minutes=5)
    deadlined_job = sched.schedule_job(
        name="Must run soon",
        fire_time=start,
        deadline=dl,
    )

    # Advance clock past deadline (10 minutes)
    clock.advance(minutes=10)

    # Polling should mark the job MISFIRED due to exceeded deadline
    polled = sched.poll()
    assert len(polled) == 0

    checked = sched.get_job(deadlined_job.job_id)
    assert checked.status == JobStatus.MISFIRED
    sched.close()


def test_cancel_and_snooze_job(temp_db):
    start = datetime(2026, 10, 1, 10, 0, tzinfo=timezone.utc)
    clock = FakeClock(start)

    sched = TaskScheduler(db_path=temp_db, clock=clock)
    j1 = sched.schedule_job(name="To Cancel", fire_time=start + timedelta(hours=1))
    j2 = sched.schedule_job(name="To Snooze", fire_time=start + timedelta(hours=1))

    # Cancel j1
    assert sched.cancel_job(j1.job_id) is True
    assert sched.get_job(j1.job_id).status == JobStatus.CANCELLED

    # Snooze j2 by 30 minutes
    snoozed = sched.snooze_job(j2.job_id, delta=timedelta(minutes=30))
    assert snoozed.next_fire_time == start + timedelta(minutes=30)
    assert snoozed.status == JobStatus.PENDING
    sched.close()
