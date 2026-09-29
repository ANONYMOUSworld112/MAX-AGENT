"""Central Agent Registry and Router.

Registers and coordinates all 33 specialized agents across 5 clusters:
- Cluster 1: Core Reasoning & Orchestration (5)
- Cluster 2: Software Delivery (8)
- Cluster 3: Founder Productivity (8)
- Cluster 4: High-Risk Input Control (6)
- Cluster 5: Infrastructure & System Health (6)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from agents.base import BaseAgent

logger = logging.getLogger("max.agents.router")


class AgentRegistry:
    _instance: Optional[AgentRegistry] = None

    def __init__(self) -> None:
        self._agents: Dict[str, BaseAgent] = {}

    @classmethod
    def get_instance(cls) -> AgentRegistry:
        with cls._get_lock():
            if cls._instance is None:
                cls._instance = cls()
                cls._instance.register_defaults()
            return cls._instance

    @classmethod
    def _get_lock(cls):
        import threading
        if not hasattr(cls, "_cls_lock"):
            cls._cls_lock = threading.Lock()
        return cls._cls_lock

    ALIASES: Dict[str, str] = {
        "polyglotdeveloper": "codingagent",
        "inboxagent": "emailagent",
        "systemmonitor": "systemmonitoragent",
        "emergencyinterrupter": "securitygate",
        "systemarchitect": "apidesigner",
    }

    def register(self, agent: BaseAgent) -> None:
        canonical = agent.name.lower().strip()
        self._agents[canonical] = agent
        logger.debug("Registered agent: %s (%s)", agent.name, canonical)

    def get(self, name: str) -> Optional[BaseAgent]:
        key = name.lower().strip()
        if key in self._agents:
            return self._agents[key]
        if key in self.ALIASES and self.ALIASES[key] in self._agents:
            return self._agents[self.ALIASES[key]]
        return None

    def list_all(self) -> List[BaseAgent]:
        return list(self._agents.values())

    def list_agents(self) -> List[BaseAgent]:
        """Alias for list_all."""
        return self.list_all()

    def get_all_tool_definitions(self) -> List[Dict[str, Any]]:
        return [agent.get_tool_definition() for agent in self._agents.values()]

    def register_defaults(self) -> None:
        """Registers all 33 default agents across the 5 MAX OS clusters."""
        # Cluster 1: Core Reasoning (5)
        from agents.core.orchestrator import MasterOrchestrator
        from agents.core.planner import DecompositionPlanner
        from agents.core.verifier import ValidationVerifier
        from agents.core.model_router import ModelRouter
        from agents.core.critic import AdversarialCritic

        # Cluster 2: Software Delivery (8)
        from agents.software import (
            CodingAgent,
            CodeReviewer,
            TestWriter,
            DevOpsAgent,
            DBAgent,
            APIDesigner,
            DocWriter,
            DependencyMgr,
        )

        # Cluster 3: Founder Productivity (8)
        from agents.productivity import (
            EmailAgent,
            CalendarAgent,
            CommsAgent,
            ResearchAgent,
            FileOrganizer,
            NotesAgent,
            TaskTracker,
            MeetingPrep,
        )

        # Cluster 4: Safety & Input Control (6)
        from agents.safety import (
            ComputerUseAgent,
            DesktopAgent,
            BrowserAgent,
            InputArbiter,
            SecurityGate,
            RecoveryEngine,
        )

        # Cluster 5: Infrastructure & Health (6)
        from agents.health import (
            SystemMonitorAgent,
            NetworkAgent,
            BackupAgent,
            UpdateAgent,
            PerformanceAgent,
            HealthCheck,
        )

        default_agents: List[BaseAgent] = [
            # Cluster 1
            MasterOrchestrator(),
            DecompositionPlanner(),
            ValidationVerifier(),
            ModelRouter(),
            AdversarialCritic(),
            # Cluster 2
            CodingAgent(),
            CodeReviewer(),
            TestWriter(),
            DevOpsAgent(),
            DBAgent(),
            APIDesigner(),
            DocWriter(),
            DependencyMgr(),
            # Cluster 3
            EmailAgent(),
            CalendarAgent(),
            CommsAgent(),
            ResearchAgent(),
            FileOrganizer(),
            NotesAgent(),
            TaskTracker(),
            MeetingPrep(),
            # Cluster 4
            ComputerUseAgent(),
            DesktopAgent(),
            BrowserAgent(),
            InputArbiter(),
            SecurityGate(),
            RecoveryEngine(),
            # Cluster 5
            SystemMonitorAgent(),
            NetworkAgent(),
            BackupAgent(),
            UpdateAgent(),
            PerformanceAgent(),
            HealthCheck(),
        ]

        for ag in default_agents:
            self.register(ag)

        logger.info("AgentRegistry initialized with %d default agents.", len(default_agents))

