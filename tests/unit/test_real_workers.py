"""
Unit tests for Real Domain Workers (Task 10.3)
==============================================

Covers:
- CalendarWorker RFC 5545 events & half-open interval [start, end) conflict detection
- ReminderWorker persistence, due time queries, priority, and snoozing
- MediaWorker session states (IDLE, PLAYING, PAUSED, STOPPED) and volume control
"""

import time
import pytest

from workers.calendar_worker import CalendarWorker
from workers.reminder_worker import ReminderWorker
from workers.media_worker import MediaWorker, MediaState


def test_calendar_half_open_interval_conflicts():
    cw = CalendarWorker()

    # Event 1: 10:00 to 11:00 (1000 to 1100)
    e1 = cw.create_event("Sprint Planning", 1000.0, 1100.0)
    assert e1.summary == "Sprint Planning"

    # Adjacent event: 11:00 to 12:00 (1100 to 1200) should NOT conflict with [1000, 1100)
    e2 = cw.create_event("Architecture Review", 1100.0, 1200.0)
    assert e2.summary == "Architecture Review"

    # Overlapping event: 10:30 to 11:30 (1030 to 1130) overlaps BOTH [1000, 1100) and [1100, 1200)
    conflicts = cw.check_conflicts(1030.0, 1130.0)
    assert len(conflicts) == 2

    # Attempting to create overlapping event without allow_conflicts raises ValueError
    with pytest.raises(ValueError, match="Conflicting event"):
        cw.create_event("Conflicting Meeting", 1030.0, 1130.0, allow_conflicts=False)

    # With allow_conflicts=True, it succeeds
    e3 = cw.create_event("Forced Overlap", 1030.0, 1130.0, allow_conflicts=True)
    assert e3.id is not None

    # List events in range 1050 to 1150
    range_events = cw.list_events(start_range=1050.0, end_range=1150.0)
    assert len(range_events) >= 2


def test_reminder_worker_lifecycle():
    rw = ReminderWorker()

    now = 1000.0
    r1 = rw.create_reminder("Submit tax report", due_time=now - 50.0, priority="HIGH")
    r2 = rw.create_reminder("Buy groceries", due_time=now + 500.0, priority="NORMAL")

    # Due reminders should only return r1
    due = rw.get_due_reminders(now=now)
    assert len(due) == 1
    assert due[0].id == r1.id
    assert due[0].priority == "HIGH"

    # Snooze r1 for 10 minutes (600 seconds)
    rw.snooze(r1.id, minutes=10.0, now=now)
    # Right now, r1 should no longer be due
    due_after_snooze = rw.get_due_reminders(now=now)
    assert len(due_after_snooze) == 0

    # Fast forward 15 minutes
    due_later = rw.get_due_reminders(now=now + 900.0)
    assert len(due_later) >= 1

    # Complete r1
    rw.complete(r1.id)
    active = rw.list_reminders(status="PENDING")
    assert len(active) == 1
    assert active[0].id == r2.id


def test_media_worker_playback_and_volume():
    mw = MediaWorker()
    assert mw.state == MediaState.IDLE

    # Play track
    track = mw.play("CyberBlack Theme", artist="MAX AI", duration_ms=210000)
    assert mw.state == MediaState.PLAYING
    assert track.title == "CyberBlack Theme"

    # Pause & Resume
    assert mw.pause() is True
    assert mw.state == MediaState.PAUSED
    assert mw.resume() is True
    assert mw.state == MediaState.PLAYING

    # Stop
    assert mw.stop() is True
    assert mw.state == MediaState.STOPPED

    # Volume clamping
    assert mw.set_volume(85) == 85
    assert mw.set_volume(150) == 100
    assert mw.set_volume(-20) == 0

    status = mw.get_playback_status()
    assert status["state"] == "STOPPED"
    assert status["track"]["title"] == "CyberBlack Theme"
    assert status["volume"] == 0
