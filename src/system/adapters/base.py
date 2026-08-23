"""
MAX OS — System Adapter ABC (Cross-Platform Abstraction)
═══════════════════════════════════════════════════════════

Every system operation goes through this interface.
Platform-specific subclasses (WindowsAdapter, LinuxAdapter, MacOSAdapter)
implement the actual OS calls.

The high-level MAX commands remain platform-independent.
"""

from __future__ import annotations

import platform
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ProcessInfo:
    """Standardized process information across platforms."""
    pid: int
    name: str
    status: str
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    username: str = ""
    command_line: str = ""
    parent_pid: Optional[int] = None
    created_at: str = ""


@dataclass
class DiskInfo:
    """Standardized disk/partition information."""
    device: str
    mountpoint: str
    filesystem: str
    total_gb: float
    used_gb: float
    free_gb: float
    percent_used: float


@dataclass
class NetworkInterface:
    """Standardized network interface information."""
    name: str
    ip_address: str = ""
    mac_address: str = ""
    is_up: bool = False
    speed_mbps: int = 0
    netmask: str = ""


@dataclass
class BatteryInfo:
    """Standardized battery information."""
    percent: float
    is_charging: bool
    time_remaining_minutes: Optional[int] = None
    power_source: str = "unknown"


@dataclass
class SystemInfo:
    """Standardized system information."""
    os_name: str
    os_version: str
    os_build: str = ""
    hostname: str = ""
    architecture: str = ""
    cpu_model: str = ""
    cpu_cores_physical: int = 0
    cpu_cores_logical: int = 0
    cpu_freq_mhz: float = 0.0
    cpu_percent: float = 0.0
    ram_total_gb: float = 0.0
    ram_used_gb: float = 0.0
    ram_available_gb: float = 0.0
    ram_percent: float = 0.0
    gpu_name: str = ""
    gpu_memory_mb: int = 0
    uptime_seconds: float = 0.0
    username: str = ""


@dataclass
class WindowInfo:
    """Standardized window information."""
    title: str
    pid: int = 0
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    is_active: bool = False
    is_minimized: bool = False
    is_maximized: bool = False
    app_name: str = ""


@dataclass
class ServiceInfo:
    """Standardized system service information."""
    name: str
    display_name: str
    status: str               # 'running' | 'stopped' | 'paused'
    start_type: str = ""      # 'automatic' | 'manual' | 'disabled'
    pid: int = 0


@dataclass
class InstalledApp:
    """Standardized installed application information."""
    name: str
    version: str = ""
    publisher: str = ""
    install_path: str = ""
    install_date: str = ""


class SystemAdapter(ABC):
    """
    Cross-platform system abstraction.
    
    Every method either returns structured data or raises an
    appropriate exception that gets classified by errors.py.
    
    Platform detection happens once at instantiation.
    """
    
    @property
    def platform(self) -> str:
        """Return current platform: 'windows', 'linux', 'darwin'."""
        return platform.system().lower()
    
    # ── System Information (Level 0 — INFORMATIONAL) ─────────
    
    @abstractmethod
    def get_system_info(self) -> SystemInfo:
        """Get comprehensive system information (CPU, RAM, GPU, OS)."""
    
    @abstractmethod
    def get_cpu_usage(self) -> dict:
        """Get current CPU usage per-core and total."""
    
    @abstractmethod
    def get_memory_usage(self) -> dict:
        """Get current RAM usage breakdown."""
    
    @abstractmethod
    def get_gpu_info(self) -> list[dict]:
        """Get GPU information (name, memory, usage)."""
    
    @abstractmethod
    def get_battery_info(self) -> Optional[BatteryInfo]:
        """Get battery status. Returns None for desktops."""
    
    @abstractmethod
    def get_disk_usage(self) -> list[DiskInfo]:
        """Get disk usage for all mounted partitions."""
    
    @abstractmethod
    def get_network_interfaces(self) -> list[NetworkInterface]:
        """Get all network interfaces and their status."""
    
    @abstractmethod
    def get_active_connections(self) -> list[dict]:
        """Get active network connections."""
    
    @abstractmethod
    def get_uptime(self) -> float:
        """Get system uptime in seconds."""
    
    @abstractmethod
    def get_user_info(self) -> dict:
        """Get current user session information."""
    
    # ── Process Management (Level 0-2) ───────────────────────
    
    @abstractmethod
    def list_processes(self, sort_by: str = "cpu") -> list[ProcessInfo]:
        """List all running processes, sorted by specified metric."""
    
    @abstractmethod
    def get_process_info(self, pid: int) -> Optional[ProcessInfo]:
        """Get detailed information about a specific process."""
    
    @abstractmethod
    def find_process_by_name(self, name: str) -> list[ProcessInfo]:
        """Find processes matching a name pattern."""
    
    @abstractmethod
    def kill_process(self, pid: int, force: bool = False) -> bool:
        """Terminate a process by PID. Force=True for SIGKILL."""
    
    @abstractmethod
    def start_process(self, command: str, args: list[str] = None,
                      cwd: str = None, env: dict = None) -> int:
        """Start a new process. Returns PID."""
    
    # ── Application Management (Level 1-2) ───────────────────
    
    @abstractmethod
    def list_installed_apps(self) -> list[InstalledApp]:
        """List installed applications."""
    
    @abstractmethod
    def open_application(self, name_or_path: str) -> bool:
        """Launch an application by name or path."""
    
    @abstractmethod
    def close_application(self, name: str) -> bool:
        """Close an application by name (graceful)."""
    
    @abstractmethod
    def is_app_running(self, name: str) -> bool:
        """Check if an application is currently running."""
    
    # ── Filesystem (Level 0-3) ───────────────────────────────
    
    @abstractmethod
    def list_directory(self, path: str, recursive: bool = False) -> list[dict]:
        """List contents of a directory."""
    
    @abstractmethod
    def get_file_info(self, path: str) -> dict:
        """Get metadata about a file/directory."""
    
    @abstractmethod
    def search_files(self, path: str, pattern: str,
                     recursive: bool = True) -> list[str]:
        """Search for files matching a pattern."""
    
    @abstractmethod
    def create_directory(self, path: str) -> bool:
        """Create a directory (with parents)."""
    
    @abstractmethod
    def copy_path(self, source: str, destination: str) -> bool:
        """Copy a file or directory."""
    
    @abstractmethod
    def move_path(self, source: str, destination: str) -> bool:
        """Move a file or directory."""
    
    @abstractmethod
    def delete_path(self, path: str, recursive: bool = False) -> bool:
        """Delete a file or directory."""
    
    @abstractmethod
    def read_file(self, path: str, max_bytes: int = 1_000_000) -> str:
        """Read file contents (text, with size limit)."""
    
    @abstractmethod
    def write_file(self, path: str, content: str) -> bool:
        """Write content to a file."""
    
    @abstractmethod
    def get_directory_size(self, path: str) -> int:
        """Get total size of a directory in bytes."""
    
    # ── Window Management (Level 1-2) ────────────────────────
    
    @abstractmethod
    def list_windows(self) -> list[WindowInfo]:
        """List all visible windows."""
    
    @abstractmethod
    def get_active_window(self) -> Optional[WindowInfo]:
        """Get the currently focused window."""
    
    @abstractmethod
    def focus_window(self, title: str) -> bool:
        """Bring a window to the foreground by title."""
    
    @abstractmethod
    def minimize_window(self, title: str) -> bool:
        """Minimize a window."""
    
    @abstractmethod
    def maximize_window(self, title: str) -> bool:
        """Maximize a window."""
    
    @abstractmethod
    def close_window(self, title: str) -> bool:
        """Close a window."""
    
    # ── Keyboard / Mouse (Level 2-3 — Tier 6 agents) ────────
    
    @abstractmethod
    def key_press(self, key: str) -> bool:
        """Simulate a single key press."""
    
    @abstractmethod
    def hotkey(self, *keys: str) -> bool:
        """Simulate a hotkey combination (e.g. 'ctrl', 'c')."""
    
    @abstractmethod
    def type_text(self, text: str, interval: float = 0.02) -> bool:
        """Type text character by character."""
    
    @abstractmethod
    def mouse_move(self, x: int, y: int) -> bool:
        """Move mouse to absolute position."""
    
    @abstractmethod
    def mouse_click(self, x: int = None, y: int = None,
                    button: str = "left", clicks: int = 1) -> bool:
        """Click at position (or current position if not specified)."""
    
    @abstractmethod
    def mouse_scroll(self, amount: int) -> bool:
        """Scroll mouse wheel. Positive=up, negative=down."""
    
    @abstractmethod
    def get_mouse_position(self) -> tuple[int, int]:
        """Get current mouse cursor position."""
    
    @abstractmethod
    def get_screen_size(self) -> tuple[int, int]:
        """Get screen dimensions (width, height)."""
    
    # ── Clipboard (Level 1) ──────────────────────────────────
    
    @abstractmethod
    def clipboard_get(self) -> str:
        """Get clipboard text content."""
    
    @abstractmethod
    def clipboard_set(self, text: str) -> bool:
        """Set clipboard text content."""
    
    # ── Services (Level 2-3) ─────────────────────────────────
    
    @abstractmethod
    def list_services(self) -> list[ServiceInfo]:
        """List system services."""
    
    @abstractmethod
    def get_service_status(self, name: str) -> Optional[ServiceInfo]:
        """Get status of a specific service."""
    
    @abstractmethod
    def start_service(self, name: str) -> bool:
        """Start a system service."""
    
    @abstractmethod
    def stop_service(self, name: str) -> bool:
        """Stop a system service."""
    
    @abstractmethod
    def restart_service(self, name: str) -> bool:
        """Restart a system service."""
    
    # ── Terminal / Command Execution (Level 2-3) ─────────────
    
    @abstractmethod
    def execute_command(self, command: str, cwd: str = None,
                        timeout: int = 30, env: dict = None) -> dict:
        """
        Execute a shell command safely.
        Returns: {stdout, stderr, exit_code, duration_ms}
        """
    
    # ── Environment Variables (Level 1-2) ────────────────────
    
    @abstractmethod
    def get_env_var(self, name: str) -> Optional[str]:
        """Get an environment variable value."""
    
    @abstractmethod
    def set_env_var(self, name: str, value: str, persistent: bool = False) -> bool:
        """Set an environment variable."""
    
    @abstractmethod
    def list_env_vars(self) -> dict[str, str]:
        """List all environment variables."""
    
    # ── Audio (Level 1-2) ────────────────────────────────────
    
    @abstractmethod
    def get_volume(self) -> int:
        """Get current audio volume (0-100)."""
    
    @abstractmethod
    def set_volume(self, level: int) -> bool:
        """Set audio volume (0-100)."""
    
    @abstractmethod
    def mute(self) -> bool:
        """Mute audio."""
    
    @abstractmethod
    def unmute(self) -> bool:
        """Unmute audio."""
    
    # ── Display (Level 0) ────────────────────────────────────
    
    @abstractmethod
    def get_display_info(self) -> list[dict]:
        """Get display/monitor information."""
    
    @abstractmethod
    def screenshot(self, path: str, region: tuple = None) -> str:
        """Take a screenshot. Returns the saved file path."""


def get_adapter() -> SystemAdapter:
    """
    Factory: return the correct adapter for the current OS.
    Auto-detects platform at runtime.
    """
    system = platform.system().lower()
    
    if system == "windows":
        from src.system.adapters.windows import WindowsAdapter
        return WindowsAdapter()
    elif system == "linux":
        from src.system.adapters.linux import LinuxAdapter
        return LinuxAdapter()
    elif system == "darwin":
        from src.system.adapters.macos import MacOSAdapter
        return MacOSAdapter()
    else:
        raise RuntimeError(f"Unsupported platform: {system}")
