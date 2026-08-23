"""
Applies memory_schema.sql and OpenJarvis integration tables into max_state.db.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "max_state.db"

STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS memory_identity (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        source TEXT NOT NULL DEFAULT 'explicit',
        confidence REAL NOT NULL DEFAULT 1.0,
        set_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS memory_preferences (
        pref_id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL,
        key TEXT NOT NULL,
        value TEXT NOT NULL,
        source TEXT NOT NULL DEFAULT 'explicit',
        confidence REAL NOT NULL DEFAULT 1.0,
        context TEXT,
        set_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(category, key)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS memory_behavioral (
        pattern_id INTEGER PRIMARY KEY AUTOINCREMENT,
        pattern_type TEXT NOT NULL,
        description TEXT NOT NULL,
        evidence TEXT NOT NULL,
        observation_count INTEGER NOT NULL DEFAULT 1,
        confidence REAL NOT NULL DEFAULT 0.3,
        first_seen TEXT NOT NULL,
        last_seen TEXT NOT NULL,
        decay_after_days INTEGER NOT NULL DEFAULT 30,
        active INTEGER NOT NULL DEFAULT 1
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS memory_project (
        project_id TEXT NOT NULL,
        key TEXT NOT NULL,
        value TEXT NOT NULL,
        source TEXT NOT NULL DEFAULT 'observed',
        confidence REAL NOT NULL DEFAULT 0.8,
        set_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (project_id, key)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS memory_conversational (
        entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        content TEXT NOT NULL,
        content_type TEXT NOT NULL DEFAULT 'context',
        importance REAL NOT NULL DEFAULT 0.5,
        promoted_to TEXT,
        promoted_at TEXT,
        created_at TEXT NOT NULL,
        expires_at TEXT
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS memory_access_log (
        access_id INTEGER PRIMARY KEY AUTOINCREMENT,
        layer TEXT NOT NULL,
        key_accessed TEXT NOT NULL,
        accessed_by TEXT NOT NULL,
        purpose TEXT,
        included_in_llm_call INTEGER NOT NULL DEFAULT 0,
        accessed_at TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS model_registry (
        model_id TEXT PRIMARY KEY,
        provider TEXT NOT NULL,
        model_name TEXT NOT NULL,
        is_local INTEGER NOT NULL DEFAULT 0,
        context_window INTEGER,
        status TEXT NOT NULL DEFAULT 'active',
        last_verified TEXT
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS skill_registry (
        skill_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        version TEXT NOT NULL DEFAULT '1.0.0',
        description TEXT,
        author TEXT,
        sandbox_mode TEXT NOT NULL DEFAULT 'docker',
        permissions TEXT,
        status TEXT NOT NULL DEFAULT 'installed',
        installed_at TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS scheduled_tasks (
        schedule_id TEXT PRIMARY KEY,
        agent TEXT NOT NULL,
        cron_expr TEXT NOT NULL,
        task_spec TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'active',
        last_run_at TEXT,
        next_run_at TEXT,
        created_at TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS channel_registry (
        channel_id TEXT PRIMARY KEY,
        channel_type TEXT NOT NULL,
        config_json TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'active',
        created_at TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS benchmark_results (
        benchmark_id TEXT PRIMARY KEY,
        suite_name TEXT NOT NULL,
        model_name TEXT NOT NULL,
        accuracy REAL,
        energy_joules REAL,
        flops_est REAL,
        duration_ms INTEGER,
        cost_usd REAL,
        created_at TEXT NOT NULL
    );
    """
]
statements = STATEMENTS

def migrate():
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")

    for stmt in STATEMENTS:
        conn.execute(stmt)

    conn.commit()
    conn.close()
    print("All Phase 6-8 tables and 5-layer memory schema successfully migrated into max_state.db!")

if __name__ == "__main__":
    migrate()
