"""
MAX OS — Action Replay Engine (Section 23)
core/audit/replay.py

Replays machine-readable audit traces for post-mortem analysis and debugging.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.audit.event_store import EventStore


class ActionReplayEngine:
    """
    Replays task execution trajectories from stored audit events.
    """

    def __init__(self, event_store: Optional[EventStore] = None):
        self.store = event_store or EventStore()

    def replay_task_trace(self, task_id: str) -> List[Dict[str, Any]]:
        """
        Reconstructs sequential step-by-step action history for a task.
        """
        events = self.store.get_events_for_task(task_id)
        trajectory = []

        for evt in events:
            trajectory.append({
                "step": len(trajectory) + 1,
                "event_type": evt["event_type"],
                "agent_id": evt["agent_id"],
                "action_id": evt["action_id"],
                "risk_level": evt["risk_level"],
                "status": evt["status"],
                "timestamp": evt["timestamp"],
                "details": evt["payload"],
            })

        return trajectory
