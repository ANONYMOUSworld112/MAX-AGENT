"""
MAX-AGENT Intent Engine
========================

Two-stage intent parsing engine replacing flat-array tool exposure:
  1. Fast Path (80%+ of voice commands):
     Deterministic schema-constrained mapping from raw utterance to
     validated TaskIntent with high confidence.
  2. Full Path (compound requests):
     Multi-step decomposition into a dependency-ordered TaskGraph DAG.

Master Spec references:
  - Section 6 (Intent Engine)
  - Section 8 (Task Planning & Graphs)
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional, Tuple

from core.contracts import ChannelTrust, TaskIntent
from core.plan_validator import PlanValidator
from core.task_graph import EdgeCondition, TaskGraph, TaskNode

logger = logging.getLogger("max.intent_engine")


class IntentEngine:
    """
    Schema-constrained intent parser supporting fast-path extraction
    and full-path DAG decomposition for compound requests.
    """

    def __init__(self, plan_validator: Optional[PlanValidator] = None) -> None:
        self.validator = plan_validator or PlanValidator()

    def parse(
        self,
        utterance: str,
        channel: ChannelTrust = ChannelTrust.UNTRUSTED,
    ) -> TaskIntent | TaskGraph:
        """
        Parse raw utterance into a single TaskIntent or a compound TaskGraph.
        """
        text = utterance.strip()
        if not text:
            return TaskIntent(raw_input="", action="unknown", channel=channel)

        # 1. Check for compound requests first
        if self._is_compound(text):
            graph = self._decompose_compound(text, channel)
            if graph:
                self.validator.assert_valid(graph)
                return graph

        # 2. Fast-path single intent
        return self._parse_single(text, channel)

    def route_name(self, utterance: str) -> str:
        """
        Determine canonical route name for benchmark / routing verification.

        Maps to expected golden benchmark categories:
          - 'open_app'
          - 'youtube_video'
          - 'reminder'
          - 'CalendarAgent'
          - 'dev_agent'
          - 'TaskGraph'
          - 'ReflexGuardrails'
          - 'KillSwitch'
          - 'undo'
        """
        text = utterance.strip()
        lower = text.lower()

        # 1. Emergency stop
        if re.search(r"\b(emergency\s*stop|kill\s*switch|abort\s*all|halt\s*all)\b", lower):
            return "KillSwitch"

        # 2. Security violations / malicious instructions
        if re.search(r"(\bignore\s+all\s+instructions\b|\bdelete\s+system32\b|\bformat\s+(?:drive\s+)?[a-z]:)", lower):
            return "ReflexGuardrails"

        # 3. Undo
        if re.search(r"^\s*undo(\s+last\s+action)?\s*\.?$", lower):
            return "undo"

        # 4. 33-Agent Swarm Inquiries
        if re.search(r"\b(33\s*agents?|agents?\s*swarm|swarm\s*agents?)\b", lower) or (
            "agent" in lower and any(w in lower for w in ["what are", "who are", "list", "tell me about", "explain", "describe", "show"])
        ):
            return "get_swarm_agents"


        # 5. Multi-task / compound requests
        if self._is_compound(text):
            return "TaskGraph"

        # 5. App launching
        if re.match(r"^open\s+", lower):
            return "open_app"

        # 6. Music / Video playback
        if re.match(r"^play\s+", lower):
            return "youtube_video"

        # 7. Reminders
        if re.match(r"^remind\s+", lower):
            return "reminder"

        # 8. Calendar
        if any(w in lower for w in ["meeting", "calendar", "appointment", "free time"]):
            return "CalendarAgent"

        # 9. Coding / Software Development
        if any(w in lower for w in ["python", "project", "fastapi", "test failure", "calculator", "code"]):
            return "dev_agent"

        # 10. System metrics
        if any(w in lower for w in ["cpu", "system status", "health"]):
            return "system_monitor"

        return "unknown"

    def _is_compound(self, text: str) -> bool:
        """Detect whether an utterance is a compound multi-step instruction."""
        lower = text.lower()

        # Obvious compound patterns
        compound_patterns = [
            r"\b(open\s+.+?\s+and\s+(create|search|write|run)\s+.+)\b",
            r"\b(build\s+.+?\s+and\s+(remind|play|notify)\s+.+)\b",
            r"\b(create\s+.+?\s+and\s+(remind|test|commit)\s+.+)\b",
            r"\b(.+?\s+(then|after that|and also)\s+.+)\b",
        ]
        return any(re.search(pat, lower) for pat in compound_patterns)

    def _decompose_compound(self, text: str, channel: ChannelTrust) -> Optional[TaskGraph]:
        """Decompose compound utterance into a TaskGraph DAG."""
        lower = text.lower().strip().rstrip(".")
        graph = TaskGraph()

        # Case A: "Open <App> and search for <Query>"
        m_search = re.match(r"open\s+(.+?)\s+and\s+search(?:\s+for)?\s+(.+)", lower)
        if m_search:
            app_name = m_search.group(1).strip()
            query = m_search.group(2).strip()

            n1 = TaskNode(
                node_id="step_1_open",
                intent=TaskIntent(
                    raw_input=f"Open {app_name}",
                    action="open_app",
                    target=app_name,
                    parameters={"app_name": app_name},
                    channel=channel,
                ),
            )
            n2 = TaskNode(
                node_id="step_2_search",
                intent=TaskIntent(
                    raw_input=f"Search for {query}",
                    action="web_search",
                    target=query,
                    parameters={"query": query},
                    channel=channel,
                ),
            )
            graph.add_node(n1)
            graph.add_node(n2)
            graph.add_edge("step_1_open", "step_2_search", EdgeCondition.ON_SUCCESS)
            return graph

        # Case B: "Open <App> and create a file"
        m_create = re.match(r"open\s+(.+?)\s+and\s+create\s+(?:a\s+)?file", lower)
        if m_create:
            app_name = m_create.group(1).strip()
            n1 = TaskNode(
                node_id="step_1_open",
                intent=TaskIntent(
                    raw_input=f"Open {app_name}",
                    action="open_app",
                    target=app_name,
                    parameters={"app_name": app_name},
                    channel=channel,
                ),
            )
            n2 = TaskNode(
                node_id="step_2_create_file",
                intent=TaskIntent(
                    raw_input="Create file",
                    action="codingagent",
                    parameters={"action": "create_file"},
                    channel=channel,
                ),
            )
            graph.add_node(n1)
            graph.add_node(n2)
            graph.add_edge("step_1_open", "step_2_create_file", EdgeCondition.ON_SUCCESS)
            return graph

        # Case C: Parallel independent tasks: "Build <X> and remind me at <Y>"
        m_build_remind = re.match(r"build\s+(?:my\s+|the\s+)?(.+?)\s+and\s+remind\s+me\s+(.+)", lower)
        if m_build_remind:
            project = m_build_remind.group(1).strip()
            remind_time = m_build_remind.group(2).strip()

            n_build = TaskNode(
                node_id="task_build",
                intent=TaskIntent(
                    raw_input=f"Build {project}",
                    action="codingagent",
                    target=project,
                    parameters={"instruction": f"Build {project}"},
                    channel=channel,
                ),
            )
            n_remind = TaskNode(
                node_id="task_remind",
                intent=TaskIntent(
                    raw_input=f"Remind me {remind_time}",
                    action="set_reminder",
                    parameters={"time": remind_time},
                    channel=channel,
                ),
            )
            # Parallel execution: both added without an edge
            graph.add_node(n_build)
            graph.add_node(n_remind)
            return graph

        # Case D: Parallel tasks: "Build <X> and play music"
        m_build_music = re.match(r"build\s+(?:the\s+|my\s+)?(.+?)\s+and\s+play\s+(.+)", lower)
        if m_build_music:
            project = m_build_music.group(1).strip()
            music = m_build_music.group(2).strip()

            n_build = TaskNode(
                node_id="task_build",
                intent=TaskIntent(
                    raw_input=f"Build {project}",
                    action="codingagent",
                    target=project,
                    parameters={"instruction": f"Build {project}"},
                    channel=channel,
                ),
            )
            n_music = TaskNode(
                node_id="task_music",
                intent=TaskIntent(
                    raw_input=f"Play {music}",
                    action="youtube_video",
                    parameters={"query": music},
                    channel=channel,
                ),
            )
            graph.add_node(n_build)
            graph.add_node(n_music)
            return graph

        return None

    def _parse_single(self, text: str, channel: ChannelTrust) -> TaskIntent:
        """Fast-path schema parsing for single-intent utterances."""
        lower = text.lower().strip().rstrip(".")

        # Emergency Stop
        if re.search(r"\b(emergency\s*stop|kill\s*switch)\b", lower):
            return TaskIntent(
                raw_input=text,
                action="kill_switch",
                target="emergency_stop",
                channel=channel,
            )

        # Prohibited / Malicious
        if re.search(r"(\bignore\s+all\s+instructions\b|\bdelete\s+system32\b|\bformat\s+(?:drive\s+)?[a-z]:)", lower):
            return TaskIntent(
                raw_input=text,
                action="security_gate",
                target="prohibited",
                parameters={"danger": True},
                channel=channel,
            )


        # Open Application
        m_app = re.match(r"^open\s+(.+)", lower)
        if m_app:
            app_name = m_app.group(1).strip()
            return TaskIntent(
                raw_input=text,
                action="open_app",
                target=app_name,
                parameters={"app_name": app_name},
                channel=channel,
            )

        # Music / Video playback
        m_play = re.match(r"^play\s+(.+)", lower)
        if m_play:
            query = m_play.group(1).strip()
            return TaskIntent(
                raw_input=text,
                action="youtube_video",
                target=query,
                parameters={"query": query},
                channel=channel,
            )

        # Reminders
        m_remind = re.match(r"^remind\s+me\s+(.+)", lower)
        if m_remind:
            remind_str = m_remind.group(1).strip()
            return TaskIntent(
                raw_input=text,
                action="set_reminder",
                target=remind_str,
                parameters={"spec": remind_str},
                channel=channel,
            )

        # Calendar operations
        if any(w in lower for w in ["meeting", "calendar", "appointment"]):
            return TaskIntent(
                raw_input=text,
                action="calendaragent",
                parameters={"instruction": text},
                channel=channel,
            )

        # Coding / Software development
        if any(w in lower for w in ["python", "fastapi", "calculator", "fix this test", "build"]):
            return TaskIntent(
                raw_input=text,
                action="codingagent",
                parameters={"instruction": text},
                channel=channel,
            )

        # Undo
        if "undo" in lower:
            return TaskIntent(
                raw_input=text,
                action="undo",
                channel=channel,
            )

        # 33-Agent Swarm Inquiries
        if re.search(r"\b(33\s*agents?|agents?\s*swarm|swarm\s*agents?)\b", lower) or (
            "agent" in lower and any(w in lower for w in ["what are", "who are", "list", "tell me about", "explain", "describe", "show"])
        ):
            cluster = "all"
            for c in ["core", "software", "productivity", "safety", "health"]:
                if c in lower:
                    cluster = c
                    break
            return TaskIntent(
                raw_input=text,
                action="get_swarm_agents",
                target=cluster,
                parameters={"cluster": cluster},
                channel=channel,
            )

        # Generic fallback
        return TaskIntent(
            raw_input=text,
            action="general_assistant",
            parameters={"query": text},
            channel=channel,
        )


if __name__ == "__main__":
    import sys
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Open VS Code"
    engine = IntentEngine()
    parsed = engine.parse(query)
    route = engine.route_name(query)
    print("=" * 60)
    print(f"Utterance: {query}")
    print(f"Canonical Route: {route}")
    if isinstance(parsed, TaskGraph):
        print(f"TaskGraph DAG: {len(parsed.nodes)} nodes, {len(parsed.edges)} edges")
        for node in parsed.topological_sort():
            print(f"  - Node {node.node_id}: action={node.intent.action}, target={node.intent.target}")
    else:
        print(f"TaskIntent: action={parsed.action}, target={parsed.target}, params={parsed.parameters}")
    print("=" * 60)
