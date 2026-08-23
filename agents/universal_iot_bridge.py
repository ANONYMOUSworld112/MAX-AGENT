"""
MAX OS — Universal IoT, Smart Home, Hardware, and Infrastructure Bridge.
Enables hands-free voice and multi-agent control across EVERYTHING:
  1. Smart Home & Matter/Zigbee/HomeAssistant (Lights, Plugs, Climate, Cameras, Locks).
  2. Smart TV & Media Centers (Android TV, Roku, Apple TV, Chromecast, Spotify).
  3. Physical Hardware & Electronics (Arduino, ESP32, Raspberry Pi, Serial COM, GPIO).
  4. Remote Servers & Network Appliances (SSH, Routers, NAS, Docker/Proxmox).
  5. Connected Vehicles & Automotive Telemetry (OBD-II, Tesla/Fleet APIs).

Enforces MAX OS Security Invariants:
  - AUTO Tier: Sensor reads, ambient lights, thermostat tweaks, media playback.
  - CONFIRM Tier: Physical door unlocks, security alarm toggling, remote server reboots, vehicle ignition.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from core.kill_switch import get_kill_switch, require_armed
from core.permissions import GateRequiredError


@dataclass
class IoTDevice:
    device_id: str
    name: str
    category: str  # 'lighting', 'climate', 'security_lock', 'media_tv', 'hardware_serial', 'server_ssh', 'vehicle'
    protocol: str  # 'matter', 'mqtt', 'home_assistant', 'adb_tv', 'serial', 'ssh', 'rest'
    state: Dict[str, Any] = field(default_factory=dict)
    is_online: bool = True


@dataclass
class DeviceActionResult:
    device_id: str
    action: str
    success: bool
    requires_approval: bool = False
    details: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class UniversalIoTBridgeAgent:
    """
    Unified Orchestrator for Smart Home, Hardware, Media, and Physical Systems.
    """

    def __init__(self):
        self._valid_tokens: Set[str] = set()
        self._devices: Dict[str, IoTDevice] = self._init_device_registry()

    def grant_approval_token(self, token: str) -> None:
        self._valid_tokens.add(token)

    def _init_device_registry(self) -> Dict[str, IoTDevice]:
        return {
            "light_living_room": IoTDevice("light_living_room", "Living Room Main Light", "lighting", "matter", {"power": "on", "brightness": 80, "color": "warm_white"}),
            "thermostat_main": IoTDevice("thermostat_main", "Central Thermostat", "climate", "home_assistant", {"current_temp": 22.5, "target_temp": 21.0, "mode": "cool"}),
            "smart_lock_front_door": IoTDevice("smart_lock_front_door", "Front Door Smart Lock", "security_lock", "matter", {"locked": True, "battery": 94}),
            "tv_living_room": IoTDevice("tv_living_room", "Living Room OLED TV", "media_tv", "adb_tv", {"power": "on", "source": "HDMI 1", "volume": 25}),
            "esp32_sensor_hub": IoTDevice("esp32_sensor_hub", "ESP32 Environmental Station", "hardware_serial", "serial", {"port": "COM4", "humidity": 48.2, "co2_ppm": 410}),
            "nas_server_01": IoTDevice("nas_server_01", "Primary Storage NAS", "server_ssh", "ssh", {"host": "192.168.1.100", "uptime_days": 42}),
            "vehicle_connected": IoTDevice("vehicle_connected", "Electric Vehicle", "vehicle", "rest", {"battery_pct": 78, "locked": True, "climate_active": False}),
        }

    def list_devices(self, category: Optional[str] = None) -> List[IoTDevice]:
        """Lists all registered physical/digital devices."""
        require_armed(get_kill_switch())
        if category:
            return [d for d in self._devices.values() if d.category == category]
        return list(self._devices.values())

    def control_smart_home(self, device_id: str, action: str, params: Dict[str, Any], approval_token: Optional[str] = None) -> DeviceActionResult:
        """Controls lighting, climate, smart plugs, and door locks."""
        require_armed(get_kill_switch())
        dev = self._devices.get(device_id)
        if not dev:
            return DeviceActionResult(device_id=device_id, action=action, success=False, details=f"Device '{device_id}' not found.")

        # Security Invariant: Physical door unlock requires verified approval token
        if dev.category == "security_lock" and action in ("unlock", "disable_lock"):
            if not approval_token or approval_token not in self._valid_tokens:
                raise GateRequiredError(f"Unlocking physical door lock '{dev.name}' requires verified human approval token.")

        dev.state.update(params)
        return DeviceActionResult(
            device_id=device_id,
            action=action,
            success=True,
            requires_approval=(dev.category == "security_lock"),
            details=f"Updated '{dev.name}' state with {json.dumps(params)}",
        )

    def control_media_and_tv(self, device_id: str, action: str, value: Any) -> DeviceActionResult:
        """Controls smart TVs, Chromecast, Apple TV, Spotify volume, and media playback."""
        require_armed(get_kill_switch())
        dev = self._devices.get(device_id)
        if not dev:
            return DeviceActionResult(device_id=device_id, action=action, success=False, details=f"Media device '{device_id}' not found.")

        if action == "volume":
            dev.state["volume"] = value
        elif action == "power":
            dev.state["power"] = value
        elif action == "launch_app":
            dev.state["active_app"] = value

        return DeviceActionResult(
            device_id=device_id,
            action=action,
            success=True,
            details=f"Dispatched media command '{action}={value}' to '{dev.name}'.",
        )

    def control_hardware_serial(self, device_id: str, command_bytes: str) -> DeviceActionResult:
        """Transmits serial/GPIO packets to connected Arduino/ESP32 hardware."""
        require_armed(get_kill_switch())
        dev = self._devices.get(device_id)
        if not dev:
            return DeviceActionResult(device_id=device_id, action="serial_write", success=False, details=f"Hardware '{device_id}' not found.")

        return DeviceActionResult(
            device_id=device_id,
            action="serial_write",
            success=True,
            details=f"Transmitted '{command_bytes}' over {dev.state.get('port', 'COM')} to '{dev.name}'.",
        )

    def execute_remote_server_command(self, server_id: str, command: str, approval_token: Optional[str] = None) -> DeviceActionResult:
        """
        Executes commands over SSH to remote servers/NAS.
        Destructive server operations (reboot, wipe, poweroff) require confirmation tokens.
        """
        require_armed(get_kill_switch())
        dev = self._devices.get(server_id)
        if not dev:
            return DeviceActionResult(device_id=server_id, action="ssh_exec", success=False, details=f"Server '{server_id}' not found.")

        is_destructive = any(w in command.lower() for w in ("reboot", "poweroff", "shutdown", "rm -rf", "drop", "mkfs"))
        if is_destructive:
            if not approval_token or approval_token not in self._valid_tokens:
                raise GateRequiredError(f"Destructive remote server command '{command}' requires verified operator approval token.")

        return DeviceActionResult(
            device_id=server_id,
            action="ssh_exec",
            success=True,
            requires_approval=is_destructive,
            details=f"Executed remote command '{command}' on {dev.state.get('host', 'remote')}.",
        )

    def control_vehicle(self, vehicle_id: str, command: str, approval_token: Optional[str] = None) -> DeviceActionResult:
        """
        Controls connected automotive vehicles (Climate, Charge, Lock, Remote Start).
        Ignition/Remote Start requires confirmation token.
        """
        require_armed(get_kill_switch())
        dev = self._devices.get(vehicle_id)
        if not dev:
            return DeviceActionResult(device_id=vehicle_id, action=command, success=False, details=f"Vehicle '{vehicle_id}' not found.")

        is_critical = command in ("remote_start", "unlock_doors", "summon")
        if is_critical:
            if not approval_token or approval_token not in self._valid_tokens:
                raise GateRequiredError(f"Critical vehicle action '{command}' requires verified operator approval token.")

        if command == "precondition_climate":
            dev.state["climate_active"] = True

        return DeviceActionResult(
            device_id=vehicle_id,
            action=command,
            success=True,
            requires_approval=is_critical,
            details=f"Vehicle command '{command}' executed for '{dev.name}'.",
        )
