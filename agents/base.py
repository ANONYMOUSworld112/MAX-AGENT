"""BaseAgent Abstraction for the 33-Agent Swarm.

Provides strict lifecycle guarantees:
- Input / Output Pydantic contract validation
- Pre-execution Kill Switch guard check
- Circuit Breaker availability check
- Deadlock-free sorted resource lock acquisition
- Pre-execution atomic snapshot capture for touched files
- Context isolation (own dedicated prompt/memory)
- Post-execution OS state reconciliation
- Dynamic Gemini/CyberBlack AI-agent MAX tool definition generation
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from core.max_infra.kill_switch import KillSwitch
from core.max_infra.circuit_breaker import CircuitBreaker
from core.max_infra.lock_manager import LockManager
from core.max_infra.snapshot import SnapshotEngine
from core.max_infra.reconciliation import ReconciliationEngine

logger = logging.getLogger("max.agents.base")


class AgentInput(BaseModel):
    task_id: str
    task_description: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    target_files: List[str] = Field(default_factory=list)
    required_resources: List[str] = Field(default_factory=list)


class AgentOutput(BaseModel):
    success: bool
    result: str = ""
    artifacts: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class BaseAgent(ABC):
    name: str = "BaseAgent"
    description: str = "Abstract agent"
    permission_tier: int = 0  # 0=Auto, 1=Safe Write, 2=Confirm, 3=Hard Blocked

    def __init__(
        self,
        lock_manager: Optional[LockManager] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
        snapshot_engine: Optional[SnapshotEngine] = None,
        reconciliation_engine: Optional[ReconciliationEngine] = None,
    ) -> None:
        self.lock_manager = lock_manager or LockManager()
        self.circuit_breaker = circuit_breaker or CircuitBreaker()
        self.snapshot_engine = snapshot_engine or SnapshotEngine()
        self.reconciliation_engine = reconciliation_engine or ReconciliationEngine()

    @abstractmethod
    def _execute(self, input_data: AgentInput) -> AgentOutput:
        """Core specialized domain logic implemented by subclass."""
        raise NotImplementedError

    def run(self, input_data: AgentInput) -> AgentOutput:
        """Lifecycle envelope wrapping domain execution in deterministic guarantees."""
        # 1. Kill Switch Guard
        KillSwitch.get_instance().guard()

        # 2. Circuit Breaker Check
        if not self.circuit_breaker.is_allowed(self.name):
            logger.error("Execution blocked: Circuit breaker for '%s' is OPEN", self.name)
            return AgentOutput(
                success=False,
                error=f"Circuit breaker for agent '{self.name}' is OPEN. Task rejected.",
            )

        # 3. Snapshot Capture
        snap_id: Optional[str] = None
        if input_data.target_files:
            snap_id = self.snapshot_engine.capture_snapshot(
                task_id=input_data.task_id,
                file_paths=input_data.target_files,
            )

        # 4. Sorted Resource Locks & Execution
        resources = list(input_data.required_resources)
        for tf in input_data.target_files:
            resources.append(f"file:{tf}")

        try:
            with self.lock_manager.acquire(resources, task_id=input_data.task_id, timeout=10.0):
                logger.info("Agent '%s' running task '%s'", self.name, input_data.task_id)
                output = self._execute(input_data)

                # 5. Reconciliation (if modifying files)
                if input_data.target_files and output.success:
                    recon_rep = self.reconciliation_engine.verify_files_exist(input_data.target_files)
                    if not recon_rep.is_verified:
                        raise RuntimeError(f"State reconciliation failed: {recon_rep.details}")

                self.circuit_breaker.record_success(self.name)
                return output

        except Exception as exc:
            logger.critical("Error during agent '%s' execution: %s", self.name, exc)
            self.circuit_breaker.record_failure(self.name)
            # Automatic rollback on failure if snapshot was captured
            if snap_id:
                logger.warning("Rolling back snapshot '%s' due to failure", snap_id)
                self.snapshot_engine.rollback(snap_id)

            return AgentOutput(
                success=False,
                error=str(exc),
            )

    def get_tool_definition(self) -> Dict[str, Any]:
        """Generates tool schema formatted for action_loader and Gemini Live."""
        return {
            "name": self.name.lower(),
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "task_description": {
                        "type": "string",
                        "description": "Natural language instruction for the agent",
                    },
                    "parameters": {
                        "type": "object",
                        "description": "Optional domain parameters",
                    },
                },
                "required": ["task_description"],
            },
        }
