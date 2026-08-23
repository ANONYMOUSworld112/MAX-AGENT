"""
MAX OS — API Quota Usage Tracker (Step 5.1).
Records and enforces per-service API quota limits in SQLite api_quota_usage table.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DEFAULT_DB_PATH = Path(__file__).parent.parent / "max_state.db"


@dataclass
class QuotaStatus:
    service: str
    period: str
    calls_made: int
    tokens_used: int
    cost_usd: float
    quota_limit: Optional[int]
    is_exhausted: bool


class QuotaTracker:
    """
    Tracks and checks per-service API quota usage (e.g. google_search, anthropic, google_tts).
    """

    def __init__(self, db_path: Optional[Path | str] = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.row_factory = sqlite3.Row
        return conn

    def check_quota(self, service: str, period: Optional[str] = None, default_limit: int = 1500) -> QuotaStatus:
        """Checks whether service has reached its quota limit for period."""
        p = period or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        conn = self._get_conn()
        try:
            cur = conn.execute("SELECT * FROM api_quota_usage WHERE service = ? AND period = ?", (service, p))
            row = cur.fetchone()
            if not row:
                return QuotaStatus(
                    service=service,
                    period=p,
                    calls_made=0,
                    tokens_used=0,
                    cost_usd=0.0,
                    quota_limit=default_limit,
                    is_exhausted=False,
                )

            limit = row["quota_limit"] if row["quota_limit"] is not None else default_limit
            calls = row["calls_made"]
            exhausted = bool(limit and calls >= limit)
            return QuotaStatus(
                service=service,
                period=p,
                calls_made=calls,
                tokens_used=row["tokens_used"],
                cost_usd=row["cost_usd"],
                quota_limit=limit,
                is_exhausted=exhausted,
            )
        finally:
            conn.close()

    def record_usage(
        self,
        service: str,
        calls: int = 1,
        tokens: int = 0,
        cost_usd: float = 0.0,
        period: Optional[str] = None,
        quota_limit: Optional[int] = 1500,
    ) -> QuotaStatus:
        """Records API usage and updates api_quota_usage table."""
        p = period or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        now = datetime.now(timezone.utc).isoformat()
        conn = self._get_conn()
        try:
            conn.execute(
                """
                INSERT INTO api_quota_usage (service, period, calls_made, tokens_used, cost_usd, quota_limit, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(service, period) DO UPDATE SET
                    calls_made = calls_made + excluded.calls_made,
                    tokens_used = tokens_used + excluded.tokens_used,
                    cost_usd = cost_usd + excluded.cost_usd,
                    last_updated = excluded.last_updated;
                """,
                (service, p, calls, tokens, cost_usd, quota_limit, now),
            )
            conn.commit()
            return self.check_quota(service, period=p, default_limit=quota_limit or 1500)
        finally:
            conn.close()
