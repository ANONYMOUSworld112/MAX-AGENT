"""
MAX OS — Multi-Dimensional Benchmarking Framework (Step 7.4).
Tracks Accuracy, Energy (Joules), FLOPs estimates, Latency, and Cost (USD) per model/task.
Stores results in benchmark_results table.
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

DEFAULT_DB_PATH = Path(__file__).parent.parent / "max_state.db"


@dataclass
class BenchmarkMetric:
    benchmark_id: str
    suite_name: str
    model_name: str
    accuracy: float
    energy_joules: float
    flops_est: float
    duration_ms: int
    cost_usd: float
    created_at: str


class BenchmarkRunner:
    """
    Evaluates models and pipelines on multiple operational dimensions.
    """

    def __init__(self, db_path: Optional[Path | str] = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.row_factory = sqlite3.Row
        return conn

    def run_benchmark(
        self,
        suite_name: str,
        model_name: str,
        test_fn: Callable[[], bool],
        est_power_watts: float = 45.0,  # e.g., M-series chip or GPU avg wattage
        est_tokens_per_call: int = 1000,
        cost_per_million_tokens: float = 3.0,
    ) -> BenchmarkMetric:
        import uuid

        bench_id = f"bench-{uuid.uuid4().hex[:8]}"
        start = time.monotonic()

        # Run evaluated function
        success = False
        try:
            success = bool(test_fn())
        except Exception:
            success = False

        duration_s = time.monotonic() - start
        duration_ms = int(duration_s * 1000)

        # Multi-dimensional calculation
        accuracy = 1.0 if success else 0.0
        energy_joules = max(0.0001, round(est_power_watts * max(0.0001, duration_s), 4))
        flops_est = round(est_tokens_per_call * 2 * 1e9, 2)  # parameter FLOPs estimate
        cost_usd = round((est_tokens_per_call / 1_000_000) * cost_per_million_tokens, 6)
        now = datetime.now(timezone.utc).isoformat()

        conn = self._get_conn()
        try:
            conn.execute(
                """
                INSERT INTO benchmark_results (benchmark_id, suite_name, model_name, accuracy, energy_joules, flops_est, duration_ms, cost_usd, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (bench_id, suite_name, model_name, accuracy, energy_joules, flops_est, duration_ms, cost_usd, now),
            )
            conn.commit()
        finally:
            conn.close()

        return BenchmarkMetric(
            benchmark_id=bench_id,
            suite_name=suite_name,
            model_name=model_name,
            accuracy=accuracy,
            energy_joules=energy_joules,
            flops_est=flops_est,
            duration_ms=duration_ms,
            cost_usd=cost_usd,
            created_at=now,
        )

    def list_benchmarks(self, suite_name: Optional[str] = None) -> List[BenchmarkMetric]:
        conn = self._get_conn()
        try:
            query = "SELECT * FROM benchmark_results"
            params = ()
            if suite_name:
                query += " WHERE suite_name = ?"
                params = (suite_name,)
            query += " ORDER BY created_at DESC;"

            rows = conn.execute(query, params).fetchall()
            return [
                BenchmarkMetric(
                    benchmark_id=r["benchmark_id"],
                    suite_name=r["suite_name"],
                    model_name=r["model_name"],
                    accuracy=r["accuracy"],
                    energy_joules=r["energy_joules"],
                    flops_est=r["flops_est"],
                    duration_ms=r["duration_ms"],
                    cost_usd=r["cost_usd"],
                    created_at=r["created_at"],
                )
                for r in rows
            ]
        finally:
            conn.close()
