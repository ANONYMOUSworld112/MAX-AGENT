"""
Session and Step Management Helper for MAX OS build protocol.
"""
import sqlite3
import uuid
import datetime
import sys
import io
from pathlib import Path

# Ensure UTF-8 output on Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

DB_PATH = Path(__file__).parent / "max_state.db"

def get_connection():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def start_session(summary="Executing build steps"):
    conn = get_connection()
    c = conn.cursor()
    
    # 2. Check next step
    c.execute("SELECT * FROM steps WHERE status != 'done' ORDER BY step_id LIMIT 1")
    next_step = c.fetchone()
    print("Next Step:", dict(next_step) if next_step else "None")
    
    # 3. Last session
    c.execute("SELECT * FROM sessions ORDER BY started_at DESC LIMIT 1")
    last_sess = c.fetchone()
    print("Last Session:", dict(last_sess) if last_sess else "None")
    
    # 4. Blockers
    c.execute("SELECT * FROM blockers WHERE resolved = 0")
    blockers = c.fetchall()
    print("Open Blockers:", [dict(b) for b in blockers])
    
    # 5. Check dependencies
    if next_step and next_step["depends_on"]:
        deps = [d.strip() for d in next_step["depends_on"].split(",") if d.strip()]
        for d in deps:
            c.execute("SELECT status FROM steps WHERE step_id = ?", (d,))
            r = c.fetchone()
            print(f"Dependency {d} status: {r['status'] if r else 'NOT FOUND'}")
            
    # 6. Insert new session
    sess_id = str(uuid.uuid4())
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    c.execute("INSERT INTO sessions (session_id, started_at, summary) VALUES (?, ?, ?)",
              (sess_id, now, summary))
    conn.commit()
    print(f"Started Session: {sess_id}")
    return sess_id

def set_step_status(step_id, status, notes=None):
    conn = get_connection()
    c = conn.cursor()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    if notes is not None:
        c.execute("""
            UPDATE steps 
            SET status = ?, last_updated = ?, notes = ?, attempt_count = attempt_count + 1
            WHERE step_id = ?
        """, (status, now, notes, step_id))
    else:
        c.execute("""
            UPDATE steps 
            SET status = ?, last_updated = ?, attempt_count = attempt_count + 1
            WHERE step_id = ?
        """, (status, now, step_id))
    
    # Also update phase status if needed
    c.execute("SELECT phase_id FROM steps WHERE step_id = ?", (step_id,))
    row = c.fetchone()
    if row:
        phase_id = row["phase_id"]
        # Check if all steps in phase are done
        c.execute("SELECT COUNT(*) as remaining FROM steps WHERE phase_id = ? AND status != 'done'", (phase_id,))
        rem = c.fetchone()["remaining"]
        if rem == 0:
            c.execute("UPDATE phases SET status = 'done', completed_at = ? WHERE phase_id = ?", (now, phase_id))
        else:
            c.execute("UPDATE phases SET status = 'in_progress', started_at = coalesce(started_at, ?) WHERE phase_id = ?", (now, phase_id))
            
    conn.commit()
    print(f"Updated Step {step_id} to {status}")

def log_decision(session_id, step_id, decision, reasoning):
    conn = get_connection()
    c = conn.cursor()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    c.execute("""
        INSERT INTO decisions_log (session_id, step_id, timestamp, decision, reasoning)
        VALUES (?, ?, ?, ?, ?)
    """, (session_id, step_id, now, decision, reasoning))
    conn.commit()
    print(f"Logged decision for Step {step_id}: {decision}")

def end_session(session_id, reason, steps_touched, summary):
    conn = get_connection()
    c = conn.cursor()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    c.execute("""
        UPDATE sessions 
        SET ended_at = ?, ended_reason = ?, steps_touched = ?, summary = ?
        WHERE session_id = ?
    """, (now, reason, steps_touched, summary, session_id))
    conn.commit()
    print(f"Ended session {session_id} with reason {reason}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "start":
        start_session()
