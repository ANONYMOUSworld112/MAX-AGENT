"""Central Agent Registry and Router.

Registers and coordinates all 33 specialized agents across 5 clusters:
- Cluster 1: Core Reasoning & Orchestration (5)
- Cluster 2: Software Delivery (8)
- Cluster 3: Founder Productivity (8)
- Cluster 4: High-Risk Input Control (6)
- Cluster 5: Infrastructure & System Health (6)

Also provides the deterministic AgentRouter implementing the 5-step routing algorithm:
1. Capability Match
2. Circuit Breaker Filter
3. Priority Ranking
4. Resource Check
5. Audit Record Generation (RoutingDecision)
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from agents.base import BaseAgent
from core.capability_registry import CapabilityRegistry
from core.contracts import (
    EventEnvelope,
    RoutingDecision,
    Task,
    TaskIntent,
    _new_id,
    _now_utc,
)
from core.events import AuditWriter, EventBus
from core.max_infra.circuit_breaker import CircuitBreaker, CircuitState

logger = logging.getLogger("max.agents.router")


class AgentRegistry:
    """Central registry for the 33-agent swarm."""

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


# ---------------------------------------------------------------------------
# Default Candidate Mapping Table for Deterministic Routing
# ---------------------------------------------------------------------------

DEFAULT_ACTION_CANDIDATES: Dict[str, List[Tuple[str, float, int]]] = {
    # Desktop and App Management
    "open_app": [("desktopagent", 1.0, 100), ("computeruseagent", 0.85, 80)],
    "launch_app": [("desktopagent", 1.0, 100), ("computeruseagent", 0.85, 80)],
    "window_control": [("desktopagent", 1.0, 100), ("computeruseagent", 0.85, 80)],
    "desktopagent": [("desktopagent", 1.0, 100)],
    "computeruseagent": [("computeruseagent", 1.0, 100)],

    # Media & Browser Automation
    "youtube_video": [("browseragent", 1.0, 95), ("desktopagent", 0.8, 70)],
    "play_media": [("browseragent", 1.0, 95), ("desktopagent", 0.8, 70)],
    "web_search": [("researchagent", 1.0, 95), ("browseragent", 0.85, 80)],
    "browseragent": [("browseragent", 1.0, 100)],
    "researchagent": [("researchagent", 1.0, 100)],

    # Reminders and Tasks
    "reminder": [("tasktracker", 1.0, 90), ("calendaragent", 0.8, 70)],
    "set_reminder": [("tasktracker", 1.0, 90), ("calendaragent", 0.8, 70)],
    "tasktracker": [("tasktracker", 1.0, 100)],
    "notesagent": [("notesagent", 1.0, 100)],

    # Calendar
    "calendaragent": [("calendaragent", 1.0, 100), ("meetingprep", 0.7, 50)],
    "meeting": [("calendaragent", 1.0, 100), ("meetingprep", 0.7, 50)],
    "meetingprep": [("meetingprep", 1.0, 100)],

    # Coding and Development
    "dev_agent": [("codingagent", 1.0, 100), ("devopsagent", 0.7, 60)],
    "codingagent": [("codingagent", 1.0, 100), ("devopsagent", 0.7, 60)],
    "polyglotdeveloper": [("codingagent", 1.0, 100)],
    "fix_test": [("testwriter", 1.0, 95), ("codingagent", 0.9, 90)],
    "testwriter": [("testwriter", 1.0, 100)],
    "codereviewer": [("codereviewer", 1.0, 100), ("codingagent", 0.7, 60)],
    "apidesigner": [("apidesigner", 1.0, 100)],
    "systemarchitect": [("apidesigner", 1.0, 100)],
    "docwriter": [("docwriter", 1.0, 100)],
    "dependencymgr": [("dependencymgr", 1.0, 100)],
    "devopsagent": [("devopsagent", 1.0, 100)],
    "dbagent": [("dbagent", 1.0, 100)],

    # Productivity & Communication
    "emailagent": [("emailagent", 1.0, 100), ("commsagent", 0.7, 60)],
    "inboxagent": [("emailagent", 1.0, 100)],
    "commsagent": [("commsagent", 1.0, 100)],
    "fileorganizer": [("fileorganizer", 1.0, 100)],
    "file_controller": [("fileorganizer", 1.0, 100)],

    # Control, Guardrails, Safety
    "securitygate": [("securitygate", 1.0, 100)],
    "security_gate": [("securitygate", 1.0, 100)],
    "reflexguardrails": [("securitygate", 1.0, 100)],
    "emergencyinterrupter": [("securitygate", 1.0, 100)],
    "killswitch": [("securitygate", 1.0, 100)],
    "kill_switch": [("securitygate", 1.0, 100)],
    "recoveryengine": [("recoveryengine", 1.0, 100)],
    "undo": [("recoveryengine", 1.0, 100)],
    "inputarbiter": [("inputarbiter", 1.0, 100)],

    # Health & System
    "systemmonitoragent": [("systemmonitoragent", 1.0, 100), ("performanceagent", 0.8, 70)],
    "systemmonitor": [("systemmonitoragent", 1.0, 100)],
    "system_status": [("systemmonitoragent", 1.0, 100), ("performanceagent", 0.8, 70)],
    "get_system_status": [("systemmonitoragent", 1.0, 100), ("performanceagent", 0.8, 70)],
    "networkagent": [("networkagent", 1.0, 100)],
    "backupagent": [("backupagent", 1.0, 100)],
    "updateagent": [("updateagent", 1.0, 100)],
    "performanceagent": [("performanceagent", 1.0, 100)],
    "healthcheck": [("healthcheck", 1.0, 100)],

    # Core Reasoning & Task Planning
    "taskgraph": [("decompositionplanner", 1.0, 100), ("masterorchestrator", 0.8, 50)],
    "decompositionplanner": [("decompositionplanner", 1.0, 100), ("masterorchestrator", 0.8, 50)],
    "masterorchestrator": [("masterorchestrator", 1.0, 100)],
    "validationverifier": [("validationverifier", 1.0, 100)],
    "modelrouter": [("modelrouter", 1.0, 100)],
    "adversarialcritic": [("adversarialcritic", 1.0, 100)],
}


class AgentRouter:
    """Deterministic Agent and Worker Router (Master Spec Section 10).

    Routes tasks to specialized agents through a deterministic 5-step pipeline:
    1. Capability match: Identifies qualified candidate agents and calculates match scores.
    2. Circuit breaker check: Disqualifies agents currently in OPEN state.
    3. Priority ranking: Ranks surviving candidates by capability score, priority, and deterministic tie-breaking.
    4. Resource check: Verifies required OS and hardware resources are available.
    5. Audit logging: Constructs an immutable RoutingDecision record and writes to the audit chain.
    """

    def __init__(
        self,
        registry: Optional[AgentRegistry] = None,
        capability_registry: Optional[CapabilityRegistry] = None,
        audit_writer: Optional[AuditWriter] = None,
        event_bus: Optional[EventBus] = None,
        resource_checker: Optional[Callable[[str], bool]] = None,
    ) -> None:
        self.registry = registry or AgentRegistry.get_instance()
        self.capability_registry = capability_registry or CapabilityRegistry.get_instance()
        self.audit_writer = audit_writer
        self.event_bus = event_bus
        self.resource_checker = resource_checker or (lambda res: True)
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}

    def set_circuit_breaker(self, agent_name: str, cb: CircuitBreaker) -> None:
        """Inject or override circuit breaker for a specific agent (e.g. for testing)."""
        self._circuit_breakers[agent_name.lower().strip()] = cb

    def get_circuit_breaker(self, agent_name: str) -> Optional[CircuitBreaker]:
        """Retrieve circuit breaker for an agent."""
        key = agent_name.lower().strip()
        if key in self._circuit_breakers:
            return self._circuit_breakers[key]
        agent = self.registry.get(key)
        if agent and hasattr(agent, "circuit_breaker"):
            return agent.circuit_breaker
        return None

    def get_agent(self, name: str) -> Optional[BaseAgent]:
        """Retrieve agent instance from registry."""
        return self.registry.get(name)

    def route_and_get(
        self,
        intent_or_task: Union[TaskIntent, Task, str],
        task_id: Optional[str] = None,
        required_resources: Optional[List[str]] = None,
    ) -> Tuple[RoutingDecision, Optional[BaseAgent]]:
        """Route to an agent and return both the decision and the instance."""
        decision = self.route(intent_or_task, task_id, required_resources)
        agent = self.get_agent(decision.selected) if decision.selected else None
        return decision, agent

    def _find_candidates(self, action: str) -> List[Dict[str, Any]]:
        """Step 1: Match action/capability to candidate agents."""
        candidates: List[Dict[str, Any]] = []
        norm = action.lower().strip()

        if norm in DEFAULT_ACTION_CANDIDATES:
            for canon, score, priority in DEFAULT_ACTION_CANDIDATES[norm]:
                ag = self.registry.get(canon)
                display_name = ag.name if ag else canon
                candidates.append({
                    "name": display_name,
                    "canonical": canon,
                    "match_score": score,
                    "priority": priority,
                })
            return candidates

        # Check direct agent registry match (canonical name or alias)
        direct_ag = self.registry.get(norm)
        if direct_ag:
            return [{
                "name": direct_ag.name,
                "canonical": direct_ag.name.lower().strip(),
                "match_score": 1.0,
                "priority": 100,
            }]

        # Check CapabilityRegistry entry
        if self.capability_registry:
            cap = self.capability_registry.get(norm)
            if cap and cap.agent_class:
                cap_ag = self.registry.get(cap.agent_class)
                display_name = cap_ag.name if cap_ag else cap.agent_class
                return [{
                    "name": display_name,
                    "canonical": display_name.lower().strip(),
                    "match_score": 1.0,
                    "priority": 100,
                }]

        # Fallback candidate: MasterOrchestrator
        orch = self.registry.get("masterorchestrator")
        orch_name = orch.name if orch else "MasterOrchestrator"
        return [{
            "name": orch_name,
            "canonical": "masterorchestrator",
            "match_score": 0.3,
            "priority": 10,
        }]

    def route(
        self,
        intent_or_task: Union[TaskIntent, Task, str],
        task_id: Optional[str] = None,
        required_resources: Optional[List[str]] = None,
    ) -> RoutingDecision:
        """Deterministic 5-Step Routing Algorithm.

        1. Capability Match: Identifies qualified candidate agents.
        2. Circuit Breaker Check: Disqualifies agents currently OPEN.
        3. Priority Ranking: Deterministic sort (score desc, priority desc, name asc).
        4. Resource Check: Verifies needed system resources are available.
        5. Audit Logging: Constructs and writes immutable RoutingDecision.
        """
        # Input normalization
        if isinstance(intent_or_task, Task):
            tid = intent_or_task.id
            action = intent_or_task.action
            res = list(intent_or_task.resources_required) if intent_or_task.resources_required else (required_resources or [])
        elif isinstance(intent_or_task, TaskIntent):
            tid = task_id or _new_id()
            action = intent_or_task.action
            res = list(required_resources or [])
        else:
            tid = task_id or _new_id()
            action = str(intent_or_task)
            res = list(required_resources or [])

        norm_action = action.lower().strip()

        # Step 1: Capability Match
        raw_candidates = self._find_candidates(norm_action)

        # Step 2: Circuit Breaker Filter
        cb_status: Dict[str, str] = {}
        viable_candidates = []
        for cand in raw_candidates:
            cb = self.get_circuit_breaker(cand["canonical"])
            if cb:
                st = cb.state.value if hasattr(cb.state, "value") else str(cb.state)
                allowed = cb.is_allowed(cand["canonical"])
            else:
                st = "CLOSED"
                allowed = True
            cb_status[cand["name"]] = st
            if allowed:
                viable_candidates.append(cand)

        # Step 3: Priority Ranking & Stable Tie-Breaking
        ranked_candidates = sorted(
            viable_candidates,
            key=lambda c: (-c["match_score"], -c["priority"], c["name"]),
        )

        # Step 4: Resource Check
        if not res and self.capability_registry:
            cap_entry = self.capability_registry.get(norm_action)
            if cap_entry and cap_entry.declared_resources:
                res = list(cap_entry.declared_resources)

        res_availability: Dict[str, bool] = {}
        for r in res:
            res_availability[r] = self.resource_checker(r)

        selected_name = ""
        selected_score = 0.0
        reason = ""

        if not raw_candidates:
            selected_name = ""
            selected_score = 0.0
            reason = f"No candidate agents found for action '{action}'"
        elif not viable_candidates:
            selected_name = ""
            selected_score = 0.0
            all_cands_str = ", ".join([c["name"] for c in raw_candidates])
            reason = f"All candidate agents [{all_cands_str}] circuit broken (OPEN)"
        else:
            all_res_ok = all(res_availability.values()) if res_availability else True
            if all_res_ok:
                chosen = ranked_candidates[0]
                selected_name = chosen["name"]
                selected_score = chosen["match_score"]

                if len(ranked_candidates) == 1 and len(raw_candidates) == 1:
                    reason = f"Matched capability '{action}' to agent '{selected_name}' (score: {selected_score:.2f}, priority: {chosen['priority']})"
                elif len(raw_candidates) > len(viable_candidates):
                    broken = [c["name"] for c in raw_candidates if c not in viable_candidates]
                    reason = f"Selected '{selected_name}' (score: {selected_score:.2f}) because higher candidate(s) circuit-broken: {broken}"
                else:
                    competitors = [
                        c["name"] for c in ranked_candidates[1:]
                        if c["match_score"] == chosen["match_score"] and c["priority"] == chosen["priority"]
                    ]
                    if competitors:
                        reason = f"Selected '{selected_name}' via deterministic tie-breaking over {competitors}"
                    else:
                        reason = f"Matched capability '{action}' to highest ranked agent '{selected_name}' (score: {selected_score:.2f}, priority: {chosen['priority']})"
            else:
                missing = [r for r, ok in res_availability.items() if not ok]
                selected_name = ""
                selected_score = 0.0
                reason = f"Required resource(s) unavailable: {missing} for candidates {[c['name'] for c in ranked_candidates]}"

        # Step 5: RoutingDecision Record & Audit Log
        decision = RoutingDecision(
            id=_new_id(),
            task_id=tid,
            intent_action=action,
            candidates=[c["name"] for c in raw_candidates],
            selected=selected_name,
            reason=reason,
            capability_match_score=selected_score,
            circuit_breaker_status=cb_status,
            resource_availability=res_availability,
            timestamp=_now_utc(),
        )

        if self.audit_writer:
            self.audit_writer.write(
                event_type="routing.decision",
                correlation_id=tid,
                actor="AgentRouter",
                payload=decision.to_dict(),
            )
        if self.event_bus:
            self.event_bus.publish(
                EventEnvelope(
                    event_type="routing.decision",
                    correlation_id=tid,
                    actor="AgentRouter",
                    payload=decision.to_dict(),
                )
            )

        return decision
