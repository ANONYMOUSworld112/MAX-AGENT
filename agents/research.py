"""
MAX OS — Research Agent (Deep Research Tier 2).
Executes multi-query research with source citations and quota warnings before heavy requests.
Integrates with WebSearchAgent and QuotaTracker.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.kill_switch import get_kill_switch, require_armed
from core.quota import QuotaTracker
from agents.websearch import WebSearchAgent, SearchResult


@dataclass
class ResearchFinding:
    sub_topic: str
    summary: str
    sources: List[str] = field(default_factory=list)


@dataclass
class ResearchReport:
    topic: str
    summary: str
    findings: List[ResearchFinding] = field(default_factory=list)
    citations: List[str] = field(default_factory=list)
    quota_warned: bool = False
    warning_message: Optional[str] = None


class ResearchAgent:
    """
    Tier 2 Research Agent.
    Decomposes research topics into targeted sub-queries, checks quota limits,
    synthesizes multi-source findings, and formats citations.
    """

    def __init__(
        self,
        web_search_agent: Optional[WebSearchAgent] = None,
        quota_tracker: Optional[QuotaTracker] = None,
        warning_threshold_queries: int = 4,
    ):
        self.quota_tracker = quota_tracker or QuotaTracker()
        self.web_search = web_search_agent or WebSearchAgent(quota_tracker=self.quota_tracker)
        self.warning_threshold_queries = warning_threshold_queries

    def conduct_research(
        self,
        topic: str,
        sub_topics: Optional[List[str]] = None,
        depth: str = "standard",
    ) -> ResearchReport:
        """Conducts multi-query deep research on a topic."""
        require_armed(get_kill_switch())

        # 1. Determine sub-queries
        queries = sub_topics or [
            f"{topic} overview and fundamentals",
            f"{topic} key developments and state of the art",
            f"{topic} challenges, risks and future outlook",
        ]

        # 2. Check quota warning before heavy requests
        quota_status = self.quota_tracker.check_quota("google_search")
        remaining_quota = (quota_status.quota_limit or 1500) - quota_status.calls_made

        quota_warned = False
        warning_msg = None
        if len(queries) >= self.warning_threshold_queries or remaining_quota < len(queries):
            quota_warned = True
            warning_msg = (
                f"Quota Warning: Research request requires {len(queries)} queries. "
                f"Current calls today: {quota_status.calls_made}, remaining quota: {remaining_quota}."
            )

        # 3. Execute sub-queries and gather citations
        findings: List[ResearchFinding] = []
        all_citations: List[str] = []

        for q in queries:
            search_res = self.web_search.search(q, force=True)
            finding = ResearchFinding(
                sub_topic=q,
                summary=search_res.content,
                sources=search_res.sources,
            )
            findings.append(finding)
            all_citations.extend(search_res.sources)

        # Deduplicate citations
        dedup_citations = list(dict.fromkeys(all_citations))

        # 4. Synthesize executive summary
        summary_lines = [
            f"### Comprehensive Research Report: {topic}",
            f"**Depth:** {depth.upper()} | **Sub-queries analyzed:** {len(queries)}",
            "",
            "#### Key Findings:",
        ]
        for idx, f in enumerate(findings, 1):
            summary_lines.append(f"{idx}. **{f.sub_topic}**\n   {f.summary}")

        if dedup_citations:
            summary_lines.append("\n#### Citations & Sources:")
            for c in dedup_citations:
                summary_lines.append(f"- {c}")

        return ResearchReport(
            topic=topic,
            summary="\n".join(summary_lines),
            findings=findings,
            citations=dedup_citations,
            quota_warned=quota_warned,
            warning_message=warning_msg,
        )
