"""Monthly API spend ledger based on provider-reported token usage."""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path


class BudgetLedger:
    """Track estimated spend; prices are explicitly configured per million tokens."""

    def __init__(self, path: str | Path, *, monthly_cap_usd: float = 0,
                 input_usd_per_million: float = 0, output_usd_per_million: float = 0):
        self.path = Path(path)
        self.cap = max(0.0, float(monthly_cap_usd))
        self.input_rate = max(0.0, float(input_usd_per_million))
        self.output_rate = max(0.0, float(output_usd_per_million))
        self._lock = threading.RLock()
        self._data = self._load()

    def _month(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m")

    def _load(self) -> dict:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        if data.get("month") != self._month():
            return {"month": self._month(), "input_tokens": 0, "output_tokens": 0, "estimated_usd": 0.0}
        return data

    @property
    def spent_usd(self) -> float:
        with self._lock:
            return float(self._data.get("estimated_usd", 0.0))

    @property
    def enabled(self) -> bool:
        return self.cap > 0

    @property
    def exhausted(self) -> bool:
        return self.enabled and self.spent_usd >= self.cap

    def record(self, input_tokens: int = 0, output_tokens: int = 0) -> float:
        """Record API-reported usage and return current month estimate."""
        with self._lock:
            if self._data.get("month") != self._month():
                self._data = {"month": self._month(), "input_tokens": 0,
                              "output_tokens": 0, "estimated_usd": 0.0}
            input_tokens = max(0, int(input_tokens))
            output_tokens = max(0, int(output_tokens))
            self._data["input_tokens"] = int(self._data.get("input_tokens", 0)) + input_tokens
            self._data["output_tokens"] = int(self._data.get("output_tokens", 0)) + output_tokens
            self._data["estimated_usd"] = (
                self._data["input_tokens"] * self.input_rate
                + self._data["output_tokens"] * self.output_rate
            ) / 1_000_000
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
            return float(self._data["estimated_usd"])

    def status(self) -> dict:
        return {"month": self._data.get("month", self._month()), "enabled": self.enabled,
                "cap_usd": self.cap, "estimated_usd": self.spent_usd,
                "remaining_usd": max(0.0, self.cap - self.spent_usd) if self.enabled else None,
                "input_tokens": self._data.get("input_tokens", 0),
                "output_tokens": self._data.get("output_tokens", 0)}
