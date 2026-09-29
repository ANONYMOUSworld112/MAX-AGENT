-- MAX OS State Schema for SQLite (WAL mode)
-- 11 Tables for Tasks, Concurrency, Circuits, Memory, and Audit

CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    agent_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'CREATED',
    priority_band INTEGER NOT NULL DEFAULT 2,
    payload_json TEXT DEFAULT '{}',
    metadata_json TEXT DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    idempotency_key TEXT UNIQUE
);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks(priority_band);
CREATE INDEX IF NOT EXISTS idx_tasks_agent ON tasks(agent_name);

CREATE TABLE IF NOT EXISTS task_traces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    step TEXT NOT NULL,
    details TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_traces_task_id ON task_traces(task_id);

CREATE TABLE IF NOT EXISTS resource_locks (
    resource_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    acquired_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS circuit_breakers (
    target_name TEXT PRIMARY KEY,
    state TEXT NOT NULL DEFAULT 'CLOSED',
    failure_count INTEGER DEFAULT 0,
    last_failure TIMESTAMP,
    trip_time TIMESTAMP,
    cooldown_seconds REAL DEFAULT 60.0
);

CREATE TABLE IF NOT EXISTS memory_layers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    layer INTEGER NOT NULL, -- 1=Identity, 2=Preference, 3=Behavioral, 4=Project, 5=Conversational
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    metadata_json TEXT DEFAULT '{}',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(layer, key)
);

CREATE INDEX IF NOT EXISTS idx_memory_layer_key ON memory_layers(layer, key);

CREATE TABLE IF NOT EXISTS snapshots (
    snapshot_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    file_path TEXT NOT NULL,
    backup_path TEXT NOT NULL,
    original_sha256 TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_snapshots_task ON snapshots(task_id);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL,
    details TEXT,
    prev_hash TEXT,
    hash TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
