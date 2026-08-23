"""
MAX OS — State Database Connection Factory
Build Order: #1 (Layer 0A — the absolute foundation)
═══════════════════════════════════════════════════════

Single SQLite connection factory. Every module imports this.
WAL mode for crash-safe writes. Foreign keys enforced.

Design: ADR-001 in decisions.md
Source: 01_BACKEND_WIRING_ORDER.md Layer 0A
Gate:   SELECT 1 returns, WAL pragma verified
"""

from __future__ import annotations

import sqlite3
import threading
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("max.infra.state_db")

# ── Configuration ─────────────────────────────────────────────
DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "max_state.db"

# Thread-local storage for per-thread connections
_local = threading.local()
_db_path: Path = DEFAULT_DB_PATH
_initialized: bool = False


def set_db_path(path: str | Path) -> None:
    """Override the default database path. Must be called before first connection."""
    global _db_path, _initialized
    if _initialized:
        raise RuntimeError(
            "Cannot change DB path after connections have been opened. "
            "Call close_all() first."
        )
    _db_path = Path(path)


def get_connection() -> sqlite3.Connection:
    """
    Get a SQLite connection for the current thread.
    
    - WAL mode enabled (crash-safe writes, concurrent reads)
    - Foreign keys enforced
    - Row factory set to sqlite3.Row for dict-like access
    - Connection is cached per-thread
    
    Returns:
        sqlite3.Connection configured for MAX OS
    """
    global _initialized
    
    conn = getattr(_local, "connection", None)
    if conn is not None:
        return conn
    
    # Ensure parent directory exists
    _db_path.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(
        str(_db_path),
        timeout=30.0,
        check_same_thread=False,  # We manage thread safety ourselves
    )
    
    # ── Pragmas (set once per connection) ──────────────────
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA synchronous = NORMAL")  # WAL-safe, better perf
    conn.execute("PRAGMA cache_size = -8000")     # 8MB cache
    
    conn.row_factory = sqlite3.Row
    
    _local.connection = conn
    _initialized = True
    
    logger.debug("Database connection opened: %s (WAL mode, FK enforced)", _db_path)
    return conn


def execute(sql: str, params: tuple = ()) -> sqlite3.Cursor:
    """Execute a single SQL statement and return the cursor."""
    return get_connection().execute(sql, params)


def executemany(sql: str, params_seq) -> sqlite3.Cursor:
    """Execute a SQL statement against all parameter sequences."""
    return get_connection().executemany(sql, params_seq)


def fetchone(sql: str, params: tuple = ()) -> Optional[sqlite3.Row]:
    """Execute and fetch one row."""
    return get_connection().execute(sql, params).fetchone()


def fetchall(sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    """Execute and fetch all rows."""
    return get_connection().execute(sql, params).fetchall()


def commit() -> None:
    """Commit the current transaction."""
    conn = getattr(_local, "connection", None)
    if conn:
        conn.commit()


def rollback() -> None:
    """Rollback the current transaction."""
    conn = getattr(_local, "connection", None)
    if conn:
        conn.rollback()


def close() -> None:
    """Close the current thread's connection."""
    conn = getattr(_local, "connection", None)
    if conn:
        conn.close()
        _local.connection = None
        logger.debug("Database connection closed for current thread")


def close_all() -> None:
    """Close all connections and reset initialization state."""
    global _initialized
    close()
    _initialized = False


def apply_schema(schema_path: str | Path) -> None:
    """
    Apply a SQL schema file to the database.
    Safe to call multiple times (uses IF NOT EXISTS).
    """
    schema_path = Path(schema_path)
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")
    
    sql = schema_path.read_text(encoding="utf-8")
    conn = get_connection()
    conn.executescript(sql)
    conn.commit()
    logger.info("Schema applied from: %s", schema_path)


def verify() -> bool:
    """
    Gate check: verify the database is operational.
    Returns True if WAL mode active and basic query works.
    """
    try:
        conn = get_connection()
        
        # Check basic connectivity
        result = conn.execute("SELECT 1").fetchone()
        assert result[0] == 1, "SELECT 1 failed"
        
        # Verify WAL mode
        mode = conn.execute("PRAGMA journal_mode").fetchone()
        assert mode[0].lower() == "wal", f"Expected WAL mode, got: {mode[0]}"
        
        # Verify foreign keys
        fk = conn.execute("PRAGMA foreign_keys").fetchone()
        assert fk[0] == 1, "Foreign keys not enabled"
        
        logger.info("Database verification passed: WAL mode, FK enabled")
        return True
        
    except Exception as e:
        logger.error("Database verification FAILED: %s", e)
        return False


def get_table_list() -> list[str]:
    """Return list of all table names in the database."""
    rows = fetchall(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    return [row["name"] for row in rows]
