-- =====================================================================
-- MAX OS — Memory Context Heap Schema
-- File: applied to max_state.db alongside max_state_schema.sql
-- 
-- Purpose: 5-layer persistent memory system that lets MAX know the user,
-- remember preferences, learn behavioral patterns, maintain per-project
-- context, and manage conversational working memory with promotion.
--
-- Design: On-device only. No cloud storage. Explicit preferences have
-- confidence=1.0; inferred patterns start low and grow with evidence.
-- Memory intake is deterministic (no LLM) for pattern detection.
--
-- Decision: ADR-018 in decisions.md
-- =====================================================================

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------
-- LAYER 1 — IDENTITY MEMORY (who the user is)
-- Permanent unless user explicitly changes. Smallest layer.
-- Examples: name, role, timezone, language, skill_level
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS memory_identity (
    key           TEXT PRIMARY KEY,              -- e.g. 'name', 'role', 'timezone', 'language'
    value         TEXT NOT NULL,
    source        TEXT NOT NULL DEFAULT 'explicit'
                    CHECK (source IN ('explicit', 'inferred')),
    confidence    REAL NOT NULL DEFAULT 1.0      -- explicit=1.0, inferred starts lower
                    CHECK (confidence >= 0.0 AND confidence <= 1.0),
    set_at        TEXT NOT NULL,                 -- ISO 8601 timestamp
    updated_at    TEXT NOT NULL
);

-- ---------------------------------------------------------------------
-- LAYER 2 — PREFERENCE MEMORY (what the user wants)
-- Explicit: "I prefer Python" → confidence=1.0
-- Inferred: user always picks Python → confidence grows with evidence
-- Categories scope which agents/modules read this preference
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS memory_preferences (
    pref_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    category      TEXT NOT NULL                  -- 'coding', 'deploy', 'communication',
                    CHECK (category IN (         --  'scheduling', 'general', 'ui',
                        'coding', 'deploy',      --  'workflow'
                        'communication',
                        'scheduling', 'general',
                        'ui', 'workflow'
                    )),
    key           TEXT NOT NULL,                 -- e.g. 'language', 'framework', 'response_style'
    value         TEXT NOT NULL,                 -- the preference value
    source        TEXT NOT NULL DEFAULT 'explicit'
                    CHECK (source IN ('explicit', 'inferred')),
    confidence    REAL NOT NULL DEFAULT 1.0
                    CHECK (confidence >= 0.0 AND confidence <= 1.0),
    context       TEXT,                          -- what triggered this preference being stored
    set_at        TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    UNIQUE(category, key)                        -- one preference per category+key pair
);

-- ---------------------------------------------------------------------
-- LAYER 3 — BEHAVIORAL MEMORY (learned patterns from observation)
-- These are NOT explicit preferences — they're detected habits.
-- Confidence starts at 0.3 and grows with repeated observations.
-- Patterns that haven't repeated in 30 days become dormant (active=0).
-- Dormant patterns are NOT deleted — they can reactivate.
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS memory_behavioral (
    pattern_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern_type      TEXT NOT NULL               -- what kind of pattern
                        CHECK (pattern_type IN (
                            'schedule',           -- time-of-day habits (meetings at 10am)
                            'workflow',           -- common task sequences (build→test→deploy)
                            'tool_usage',         -- preferred tools/backends
                            'time_pattern',       -- when they work, peak hours
                            'command_pattern',    -- frequently used phrases/commands
                            'project_switch'      -- context switching patterns
                        )),
    description       TEXT NOT NULL,              -- human-readable: "User typically deploys on Fridays"
    evidence          TEXT NOT NULL,              -- JSON array of observations: timestamps, task_ids
    observation_count INTEGER NOT NULL DEFAULT 1,
    confidence        REAL NOT NULL DEFAULT 0.3   -- starts low, grows with bayesian update
                        CHECK (confidence >= 0.0 AND confidence <= 1.0),
    first_seen        TEXT NOT NULL,              -- when this pattern was first detected
    last_seen         TEXT NOT NULL,              -- most recent observation
    decay_after_days  INTEGER NOT NULL DEFAULT 30,-- how many days without observation before dormancy
    active            INTEGER NOT NULL DEFAULT 1  -- 1=active, 0=dormant
                        CHECK (active IN (0, 1))
);

-- ---------------------------------------------------------------------
-- LAYER 4 — PROJECT MEMORY (per-project context)
-- What MAX knows about each specific project: tech stack, deploy target,
-- test framework, git conventions, recent errors, file patterns.
-- Observed values (from scanning the project) have confidence=0.8.
-- Explicit values (user told us) have confidence=1.0.
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS memory_project (
    project_id    TEXT NOT NULL,                  -- project path or canonical name
    key           TEXT NOT NULL,                  -- 'tech_stack', 'deploy_target', 'test_framework',
                                                 -- 'git_branch_convention', 'last_error', etc.
    value         TEXT NOT NULL,
    source        TEXT NOT NULL DEFAULT 'observed'
                    CHECK (source IN ('explicit', 'observed', 'inferred')),
    confidence    REAL NOT NULL DEFAULT 0.8
                    CHECK (confidence >= 0.0 AND confidence <= 1.0),
    set_at        TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    PRIMARY KEY (project_id, key)
);

-- ---------------------------------------------------------------------
-- LAYER 5 — CONVERSATIONAL MEMORY (working memory with promotion)
-- Captures context from each interaction. High-importance items that
-- repeat across sessions get promoted to Layer 2 (preferences) or
-- Layer 3 (behavioral patterns). Low-importance items expire.
-- This is the "short-term memory" that enables continuity within and
-- across sessions without replaying entire conversation histories.
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS memory_conversational (
    entry_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id    TEXT NOT NULL,                  -- which session this came from
    content       TEXT NOT NULL,                  -- what was captured from this interaction
    content_type  TEXT NOT NULL DEFAULT 'context' -- what kind of memory this is
                    CHECK (content_type IN (
                        'context',               -- general context from interaction
                        'correction',            -- user corrected MAX's behavior
                        'preference_signal',     -- user expressed a preference implicitly
                        'intent_clarification',  -- user clarified what they actually meant
                        'feedback'               -- user gave explicit feedback (good/bad)
                    )),
    importance    REAL NOT NULL DEFAULT 0.5       -- 0.0-1.0, affects promotion threshold
                    CHECK (importance >= 0.0 AND importance <= 1.0),
    promoted_to   TEXT                            -- NULL if not promoted
                    CHECK (promoted_to IN ('preference', 'behavioral', 'project') OR promoted_to IS NULL),
    promoted_at   TEXT,                           -- when it was promoted
    created_at    TEXT NOT NULL,
    expires_at    TEXT                            -- NULL = no auto-expiry
);

-- ---------------------------------------------------------------------
-- CROSS-CUTTING: Memory Access Log (audit trail)
-- Who read what memory, when, and why. Useful for:
-- 1. Debugging why MAX made a specific decision
-- 2. Auditing what memory content was included in LLM prompts
-- 3. Understanding which memories are actually useful (unused = prune)
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS memory_access_log (
    access_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    layer         TEXT NOT NULL                   -- which memory layer was accessed
                    CHECK (layer IN (
                        'identity', 'preference', 'behavioral',
                        'project', 'conversational'
                    )),
    key_accessed  TEXT NOT NULL,                  -- specific key/id that was read
    accessed_by   TEXT NOT NULL,                  -- which module/agent read this
    purpose       TEXT,                           -- why it was accessed (for audit)
    included_in_llm_call INTEGER NOT NULL DEFAULT 0
                    CHECK (included_in_llm_call IN (0, 1)),
    accessed_at   TEXT NOT NULL
);

-- ---------------------------------------------------------------------
-- INDICES — optimized for the actual read patterns
-- ---------------------------------------------------------------------

-- Layer 2: Preferences are filtered by category when building agent prompts
CREATE INDEX IF NOT EXISTS idx_memory_pref_category
    ON memory_preferences(category);

-- Layer 3: Active patterns are loaded at session start; filtered by type per-agent
CREATE INDEX IF NOT EXISTS idx_memory_behavioral_active
    ON memory_behavioral(active, confidence);
CREATE INDEX IF NOT EXISTS idx_memory_behavioral_type
    ON memory_behavioral(pattern_type);
CREATE INDEX IF NOT EXISTS idx_memory_behavioral_last_seen
    ON memory_behavioral(last_seen);

-- Layer 4: Project memory is loaded per project_id
CREATE INDEX IF NOT EXISTS idx_memory_project_id
    ON memory_project(project_id);

-- Layer 5: Conversational memory is queried by session and by importance
CREATE INDEX IF NOT EXISTS idx_memory_conv_session
    ON memory_conversational(session_id);
CREATE INDEX IF NOT EXISTS idx_memory_conv_importance
    ON memory_conversational(importance DESC);
CREATE INDEX IF NOT EXISTS idx_memory_conv_not_promoted
    ON memory_conversational(promoted_to) WHERE promoted_to IS NULL;

-- Access log: queried for audit trails and usage analysis
CREATE INDEX IF NOT EXISTS idx_memory_access_layer
    ON memory_access_log(layer);
CREATE INDEX IF NOT EXISTS idx_memory_access_time
    ON memory_access_log(accessed_at);
