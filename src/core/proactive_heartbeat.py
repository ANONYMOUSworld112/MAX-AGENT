"""
MAX OS — Proactive Ambient Heartbeat & Autonomous Self-Driving Daemon.
══════════════════════════════════════════════════════════════════════════════
Runs continuously in the background to:
1. Sense real-time environmental metrics (CPU, RAM, Disk, Active Processes).
2. Track owner presence transitions via PresenceObserver.
3. Deliver proactive voice briefings and diagnostics.
4. Auto-evaluate and execute scheduled tasks autonomously.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

import psutil

from src.core.presence_observer import PresenceObserver, PresenceSnapshot, PresenceState
from src.infra.owner_knowledge_graph import OwnerKnowledgeGraph

logger = logging.getLogger("max.core.proactive_heartbeat")


@dataclass
class SystemTelemetrySnapshot:
    cpu_percent: float
    ram_percent: float
    disk_percent: float
    battery_percent: Optional[float]
    battery_plugged: Optional[bool]
    running_processes_count: int
    system_status: str  # NOMINAL, WARNING, CRITICAL
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ProactiveHeartbeatDaemon:
    """
    JARVIS Proactive Ambient Heartbeat Daemon.
    Performs autonomous telemetry sensing, owner presence greeting, and background health checks.
    """

    def __init__(
        self,
        interval_seconds: float = 5.0,
        voice_output_fn: Optional[Callable[[str], None]] = None,
    ):
        self.interval_seconds = interval_seconds
        self.voice_output_fn = voice_output_fn or self._default_voice
        self.owner_kg = OwnerKnowledgeGraph()
        self.presence = PresenceObserver(on_arrival_callback=self._handle_owner_arrival)
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._latest_telemetry: Optional[SystemTelemetrySnapshot] = None
        self._latest_presence: Optional[PresenceSnapshot] = None

    def _default_voice(self, message: str) -> None:
        try:
            from core.single_tts_queue import speak
            speak(message)
        except Exception:
            print(f"🔊 [JARVIS PROACTIVE VOICE]: \"{message}\"")

    def _handle_owner_arrival(self, snapshot: PresenceSnapshot) -> None:
        prof = self.owner_kg.get_profile()
        greeting = self.presence.generate_arrival_briefing(owner_alias=prof.alias)
        telemetry = self.capture_telemetry()
        full_msg = f"{greeting} CPU load at {telemetry.cpu_percent:.0f}%, memory at {telemetry.ram_percent:.0f}%."
        self.voice_output_fn(full_msg)

    def capture_telemetry(self) -> SystemTelemetrySnapshot:
        cpu = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory().percent
        disk = psutil.disk_usage("/").percent
        
        battery = psutil.sensors_battery()
        bat_percent = battery.percent if battery else None
        bat_plugged = battery.power_plugged if battery else None
        proc_count = len(psutil.pids())

        status = "NOMINAL"
        if cpu > 85 or ram > 90 or disk > 95:
            status = "WARNING"

        snap = SystemTelemetrySnapshot(
            cpu_percent=cpu,
            ram_percent=ram,
            disk_percent=disk,
            battery_percent=bat_percent,
            battery_plugged=bat_plugged,
            running_processes_count=proc_count,
            system_status=status,
        )
        self._latest_telemetry = snap
        return snap

    def tick_once(self) -> Dict[str, Any]:
        """Runs a single evaluation tick."""
        telemetry = self.capture_telemetry()
        presence_snap = self.presence.evaluate_presence()
        self._latest_presence = presence_snap

        return {
            "telemetry": telemetry,
            "presence": presence_snap,
            "owner": self.owner_kg.get_profile().full_name,
        }

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="JARVIS-Heartbeat")
        self._thread.start()
        logger.info("Proactive Heartbeat Daemon started.")

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        logger.info("Proactive Heartbeat Daemon stopped.")

    def _loop(self) -> None:
        while self._running:
            try:
                self.tick_once()
            except Exception as e:
                logger.error("Error in heartbeat loop: %s", e)
            time.sleep(self.interval_seconds)
