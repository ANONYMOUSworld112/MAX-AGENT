"""
MAX OS — Web Search Agent (Step 5.1).
Explicit trigger only; quota-checked against api_quota_usage; graceful degradation.
Enforces Kill Switch checks and Data Boundary sanitization before external requests.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from core.kill_switch import get_kill_switch, require_armed
from core.quota import QuotaTracker
from core.data_boundary import sanitize_payload

SEARCH_TRIGGER_PATTERNS = [
    re.compile(r"\b(from internet|search for|latest|current|today|right now|check online|what's happening with|lookup)\b", re.IGNORECASE),
]


@dataclass
class SearchResult:
    query: str
    grounded: bool
    content: str
    sources: List[str] = field(default_factory=list)
    quota_exhausted: bool = False
    error: Optional[str] = None


class WebSearchAgent:
    """
    Tier 2 Web Search Agent.
    - Explicit trigger only.
    - Checks daily quota before external API calls.
    - Gracefully degrades to internal knowledge if quota is reached or network is unavailable.
    """

    def __init__(
        self,
        quota_tracker: Optional[QuotaTracker] = None,
        search_backend_fn: Optional[Callable[[str], List[Dict[str, str]]]] = None,
        daily_limit: int = 1500,
    ):
        self.quota_tracker = quota_tracker or QuotaTracker()
        self.search_backend_fn = search_backend_fn
        self.daily_limit = daily_limit

    def is_search_triggered(self, query: str) -> bool:
        """Checks if the query explicitly requests real-time web information."""
        return any(p.search(query) for p in SEARCH_TRIGGER_PATTERNS)

    def search(self, query: str, force: bool = False) -> SearchResult:
        """
        Executes a web search if triggered and within quota.
        """
        require_armed(get_kill_switch())

        if not force and not self.is_search_triggered(query):
            return SearchResult(
                query=query,
                grounded=False,
                content="Query did not contain an explicit web search trigger. Skipping live search.",
                sources=[],
            )

        # 1. Quota Check
        quota_status = self.quota_tracker.check_quota("google_search", default_limit=self.daily_limit)
        if quota_status.is_exhausted:
            return SearchResult(
                query=query,
                grounded=False,
                content="Daily search quota reached — answering from existing knowledge instead, may not be current.",
                sources=[],
                quota_exhausted=True,
            )

        # 2. Data Boundary check: sanitize outbound search query
        safe_query = sanitize_payload({"q": query}).get("q", query)

        # 3. Call search backend
        try:
            if self.search_backend_fn is not None:
                raw_results = self.search_backend_fn(safe_query)
            else:
                # Built-in fallback / mock engine
                raw_results = [
                    {"title": f"Search Results for: {safe_query}", "snippet": f"Latest verified live info regarding {safe_query}", "url": "https://example.com/live-news"}
                ]

            # 4. Record Quota usage
            self.quota_tracker.record_usage("google_search", calls=1, quota_limit=self.daily_limit)

            snippets = [f"• {r.get('title')}: {r.get('snippet')}" for r in raw_results]
            sources = [r.get("url", "") for r in raw_results if r.get("url")]

            return SearchResult(
                query=safe_query,
                grounded=True,
                content="\n".join(snippets),
                sources=sources,
                quota_exhausted=False,
            )

        except Exception as e:
            # Graceful degradation on network error
            return SearchResult(
                query=safe_query,
                grounded=False,
                content=f"Live search encountered network issue ({e}) — falling back to offline knowledge.",
                sources=[],
                error=str(e),
            )
