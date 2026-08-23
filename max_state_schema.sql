-- =====================================================================
-- MAX OS — Unified State Database
-- File: max_state.db (SQLite)
-- Two jobs, one file:
--   1. BUILD PROGRESS  — lets any coding agent resume this project from
--      exactly where a previous session left off, even with zero memory
--      of that session (quota ran out, context reset, new machine, etc.)
--   2. RUNTIME TRACE    — once MAX itself is running, this is the same
--      Trace Log / Outcome Tracker / Dead Letter Queue designed earlier.
-- One schema, two lifecycles — build-time rows and runtime rows never
-- collide because they live in different tables.
-- =====================================================================

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------
-- BUILD PROGRESS TABLES
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS phases (
    phase_id      INTEGER PRIMARY KEY,
    name          TEXT NOT NULL,
    goal          TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'not_started'
                    CHECK (status IN ('not_started','in_progress','done','blocked')),
    started_at    TEXT,
    completed_at  TEXT
);

CREATE TABLE IF NOT EXISTS steps (
    step_id               TEXT PRIMARY KEY,        -- e.g. '1.3', '2.7'
    phase_id              INTEGER NOT NULL REFERENCES phases(phase_id),
    title                 TEXT NOT NULL,
    description           TEXT NOT NULL,
    depends_on            TEXT,                     -- comma-separated step_ids, '' if none
    acceptance_criteria   TEXT NOT NULL,             -- how the agent proves this step is actually done
    files_touched         TEXT,                      -- comma-separated relative paths
    status                TEXT NOT NULL DEFAULT 'not_started'
                            CHECK (status IN ('not_started','in_progress','blocked','done')),
    attempt_count         INTEGER NOT NULL DEFAULT 0,
    last_updated          TEXT,
    notes                 TEXT                       -- free text: what was tried, what's left
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id     TEXT PRIMARY KEY,                 -- uuid4
    started_at     TEXT NOT NULL,
    ended_at       TEXT,
    ended_reason   TEXT
                    CHECK (ended_reason IN ('quota_exhausted','completed_step','user_stopped','error') OR ended_reason IS NULL),
    steps_touched  TEXT,                              -- comma-separated step_ids worked this session
    summary        TEXT                               -- plain-English handoff note for the NEXT session
);

CREATE TABLE IF NOT EXISTS decisions_log (
    decision_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   TEXT REFERENCES sessions(session_id),
    step_id      TEXT REFERENCES steps(step_id),
    timestamp    TEXT NOT NULL,
    decision     TEXT NOT NULL,                       -- what was decided, in one sentence
    reasoning    TEXT NOT NULL                         -- why — so a future session doesn't re-litigate it
);

CREATE TABLE IF NOT EXISTS blockers (
    blocker_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    step_id       TEXT REFERENCES steps(step_id),
    raised_at     TEXT NOT NULL,
    description   TEXT NOT NULL,
    resolved      INTEGER NOT NULL DEFAULT 0,          -- 0/1
    resolved_at   TEXT,
    resolution    TEXT
);

-- ---------------------------------------------------------------------
-- RUNTIME TABLES (MAX's own operation, once built — see MAX_OS_v3 doc)
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS task_trace (
    task_id           TEXT PRIMARY KEY,
    idempotency_key    TEXT NOT NULL,
    agent              TEXT NOT NULL,
    intent             TEXT NOT NULL,
    input_summary      TEXT NOT NULL,
    priority_band      INTEGER NOT NULL,
    state              TEXT NOT NULL,                  -- see task lifecycle state machine
    error_class        TEXT,                            -- transient/validation/permission/destructive_risk/systemic
    attempt_count      INTEGER NOT NULL DEFAULT 0,
    created_at         TEXT NOT NULL,
    completed_at       TEXT,
    duration_ms        INTEGER,
    result_summary     TEXT
);

CREATE TABLE IF NOT EXISTS outcome_tracker (
    task_type        TEXT PRIMARY KEY,
    avg_duration_ms  INTEGER,
    success_rate     REAL,
    sample_count     INTEGER NOT NULL DEFAULT 0,
    last_updated     TEXT
);

CREATE TABLE IF NOT EXISTS dead_letter_queue (
    task_id          TEXT PRIMARY KEY,
    agent            TEXT NOT NULL,
    original_input   TEXT NOT NULL,
    attempts_json    TEXT NOT NULL,                    -- full history: every attempt, every error
    died_at          TEXT NOT NULL,
    requeued         INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS circuit_breaker_state (
    agent           TEXT PRIMARY KEY,
    state           TEXT NOT NULL DEFAULT 'closed'
                     CHECK (state IN ('closed','open','half_open')),
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    opened_at       TEXT
);

-- ---------------------------------------------------------------------
-- API QUOTA TRACKING
-- Referenced in ARCHITECTURE.md (step 5.1) but was missing from the
-- original schema. One shared table, keyed by service — see Decision D11.
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS api_quota_usage (
    service         TEXT NOT NULL,                     -- e.g. 'anthropic', 'google_tts', 'google_search'
    period          TEXT NOT NULL,                     -- e.g. '2026-08-14', '2026-08'
    calls_made      INTEGER NOT NULL DEFAULT 0,
    tokens_used     INTEGER NOT NULL DEFAULT 0,
    cost_usd        REAL NOT NULL DEFAULT 0.0,
    quota_limit     INTEGER,                          -- NULL = unlimited
    last_updated    TEXT NOT NULL,
    PRIMARY KEY (service, period)
);

-- ---------------------------------------------------------------------
-- AGENT REGISTRY
-- Formalizes AGENTS.md into queryable SQL. Adds OpenJarvis's 3-mode
-- execution taxonomy (on_demand / scheduled / continuous) as a real
-- column alongside MAX's existing tier + permission system.
-- These are complementary axes, not competing ones — see
-- MAX_OpenJarvis_Unified_Features.md §5.
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS agent_registry (
    agent_name         TEXT PRIMARY KEY,
    tier               INTEGER NOT NULL,              -- build priority (1=built, 2=next, etc.)
    execution_mode     TEXT NOT NULL
                        CHECK (execution_mode IN ('on_demand','scheduled','continuous')),
    status             TEXT NOT NULL
                        CHECK (status IN ('built','next','deferred')),
    default_permission TEXT NOT NULL
                        CHECK (default_permission IN ('auto','confirm','blocked')),
    description        TEXT,                          -- what this agent does
    backend            TEXT,                          -- e.g. 'Native', 'opencode', 'Git CLI/API'
    category           TEXT                           -- e.g. 'worker', 'orchestration', 'infra'
);

-- ---------------------------------------------------------------------
-- Helpful indexes — cheap now, expensive to forget once the trace table
-- has months of rows in it
-- ---------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_steps_status        ON steps(status);
CREATE INDEX IF NOT EXISTS idx_task_trace_agent     ON task_trace(agent);
CREATE INDEX IF NOT EXISTS idx_task_trace_state     ON task_trace(state);
CREATE INDEX IF NOT EXISTS idx_task_trace_created   ON task_trace(created_at);
CREATE INDEX IF NOT EXISTS idx_agent_registry_tier  ON agent_registry(tier);
CREATE INDEX IF NOT EXISTS idx_api_quota_service    ON api_quota_usage(service);
