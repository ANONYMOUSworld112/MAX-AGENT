"""
MAX OS — Linux System Adapter Implementation
═════════════════════════════════════════════

Concrete implementation of SystemAdapter for Linux using psutil,
subprocess, and standard Linux OS tools.
"""

from __future__ import annotations

import os
import sys
import time
import shutil
import glob
import subprocess
import platform
import logging
from pathlib import Path
from typing import Optional

import psutil

from src.system.adapters.base import (
    SystemAdapter,
    SystemInfo,
    ProcessInfo,
    DiskInfo,
    NetworkInterface,
    BatteryInfo,
    WindowInfo,
    ServiceInfo,
    InstalledApp,
)

logger = logging.getLogger("max.system.adapters.linux")


class LinuxAdapter(SystemAdapter):
    """Linux implementation of SystemAdapter."""

    def get_system_info(self) -> SystemInfo:
        vm = psutil.virtual_memory()
        cpu_freq = psutil.cpu_freq()
        
        # GPU detection via nvidia-smi if present
        gpu_name = ""
        gpu_mem = 0
        if shutil.which("nvidia-smi"):
            try:
                res = subprocess.run(
                    ["nvidia-smi", "--query-gpu=gpu_name,memory.total", "--format=csv,noheader,nounits"],
                    capture_output=True, text=True, timeout=2
                )
                if res.returncode == 0 and res.stdout.strip():
                    parts = res.stdout.strip().split(",")
                    if len(parts) >= 2:
                        gpu_name = parts[0].strip()
                        gpu_mem = int(parts[1].strip())
            except Exception:
                pass

        return SystemInfo(
            os_name="Linux",
            os_version=platform.release(),
            os_build=platform.version(),
            hostname=platform.node(),
            architecture=platform.machine(),
            cpu_model=platform.processor() or "x86_64",
            cpu_cores_physical=psutil.cpu_count(logical=False) or 1,
            cpu_cores_logical=psutil.cpu_count(logical=True) or 1,
            cpu_freq_mhz=cpu_freq.current if cpu_freq else 0.0,
            cpu_percent=psutil.cpu_percent(interval=0.1),
            ram_total_gb=round(vm.total / (1024**3), 2),
            ram_used_gb=round(vm.used / (1024**3), 2),
            ram_available_gb=round(vm.available / (1024**3), 2),
            ram_percent=vm.percent,
            gpu_name=gpu_name,
            gpu_memory_mb=gpu_mem,
            uptime_seconds=time.time() - psutil.boot_time(),
            username=os.getlogin() if hasattr(os, "getlogin") else os.environ.get("USER", "anonymous"),
        )

    def get_cpu_usage(self) -> dict:
        per_cpu = psutil.cpu_percent(interval=0.1, percpu=True)
        return {
            "total_percent": psutil.cpu_percent(interval=0.0),
            "per_cpu_percent": per_cpu,
            "logical_count": psutil.cpu_count(logical=True),
            "physical_count": psutil.cpu_count(logical=False),
        }

    def get_memory_usage(self) -> dict:
        vm = psutil.virtual_memory()
        swap = psutil.swap_memory()
        return {
            "total_gb": round(vm.total / (1024**3), 2),
            "used_gb": round(vm.used / (1024**3), 2),
            "available_gb": round(vm.available / (1024**3), 2),
            "percent": vm.percent,
            "swap_total_gb": round(swap.total / (1024**3), 2),
            "swap_used_gb": round(swap.used / (1024**3), 2),
            "swap_percent": swap.percent,
        }

    def get_gpu_info(self) -> list[dict]:
        gpus = []
        if shutil.which("nvidia-smi"):
            try:
                res = subprocess.run(
                    ["nvidia-smi", "--query-gpu=index,gpu_name,memory.total,memory.used,utilization.gpu", "--format=csv,noheader,nounits"],
                    capture_output=True, text=True, timeout=2
                )
                if res.returncode == 0:
                    for line in res.stdout.strip().splitlines():
                        parts = [p.strip() for p in line.split(",")]
                        if len(parts) >= 5:
                            gpus.append({
                                "index": int(parts[0]),
                                "name": parts[1],
                                "memory_total_mb": int(parts[2]),
                                "memory_used_mb": int(parts[3]),
                                "utilization_percent": float(parts[4]),
                            })
            except Exception as e:
                logger.debug("Failed GPU check: %s", e)
        return gpus

    def get_battery_info(self) -> Optional[BatteryInfo]:
        batt = psutil.sensors_battery()
        if batt is None:
            return None
        return BatteryInfo(
            percent=batt.percent,
            is_charging=batt.power_plugged,
            time_remaining_minutes=int(batt.secsleft / 60) if batt.secsleft > 0 else None,
            power_source="ac" if batt.power_plugged else "battery",
        )

    def get_disk_usage(self) -> list[DiskInfo]:
        disks = []
        for part in psutil.disk_partitions(all=False):
            if "snap" in part.mountpoint or "docker" in part.mountpoint:
                continue
            try:
                usage = psutil.disk_usage(part.mountpoint)
                disks.append(DiskInfo(
                    device=part.device,
                    mountpoint=part.mountpoint,
                    filesystem=part.fstype,
                    total_gb=round(usage.total / (1024**3), 2),
                    used_gb=round(usage.used / (1024**3), 2),
                    free_gb=round(usage.free / (1024**3), 2),
                    percent_used=usage.percent,
                ))
            except Exception:
                continue
        return disks

    def get_network_interfaces(self) -> list[NetworkInterface]:
        interfaces = []
        addrs = psutil.net_if_addrs()
        stats = psutil.net_if_stats()
        for name, addr_list in addrs.items():
            ip = ""
            netmask = ""
            mac = ""
            for a in addr_list:
                if a.family == 2:  # AF_INET
                    ip = a.address
                    netmask = a.netmask
                elif a.family == 17 or getattr(a.family, "name", "") in ("AF_LINK", "AF_PACKET"):
                    mac = a.address
            stat = stats.get(name)
            is_up = stat.isup if stat else False
            speed = stat.speed if stat else 0
            interfaces.append(NetworkInterface(
                name=name,
                ip_address=ip,
                mac_address=mac,
                is_up=is_up,
                speed_mbps=speed,
                netmask=netmask,
            ))
        return interfaces

    def get_active_connections(self) -> list[dict]:
        conns = []
        try:
            for c in psutil.net_connections(kind="inet"):
                conns.append({
                    "fd": c.fd,
                    "family": str(c.family),
                    "type": str(c.type),
                    "laddr": f"{c.laddr.ip}:{c.laddr.port}" if c.laddr else "",
                    "raddr": f"{c.raddr.ip}:{c.raddr.port}" if c.raddr else "",
                    "status": c.status,
                    "pid": c.pid,
                })
        except Exception:
            pass
        return conns[:50]  # Limit to 50

    def get_uptime(self) -> float:
        return time.time() - psutil.boot_time()

    def get_user_info(self) -> dict:
        return {
            "username": os.environ.get("USER", "anonymous"),
            "home": os.environ.get("HOME", "/tmp"),
            "shell": os.environ.get("SHELL", "/bin/bash"),
            "desktop": os.environ.get("XDG_CURRENT_DESKTOP", "unknown"),
        }

    def list_processes(self, sort_by: str = "cpu") -> list[ProcessInfo]:
        procs = []
        for p in psutil.process_iter(['pid', 'name', 'status', 'cpu_percent', 'memory_info', 'username', 'cmdline', 'ppid', 'create_time']):
            try:
                info = p.info
                cmdline = " ".join(info['cmdline']) if info.get('cmdline') else info['name']
                mem_mb = (info['memory_info'].rss / (1024*1024)) if info.get('memory_info') else 0.0
                procs.append(ProcessInfo(
                    pid=info['pid'],
                    name=info['name'],
                    status=info['status'],
                    cpu_percent=info['cpu_percent'] or 0.0,
                    memory_mb=round(mem_mb, 2),
                    username=info['username'] or "",
                    command_line=cmdline,
                    parent_pid=info['ppid'],
                    created_at=str(info['create_time']),
                ))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if sort_by == "cpu":
            procs.sort(key=lambda x: x.cpu_percent, reverse=True)
        elif sort_by == "memory":
            procs.sort(key=lambda x: x.memory_mb, reverse=True)
        return procs[:100]

    def get_process_info(self, pid: int) -> Optional[ProcessInfo]:
        try:
            p = psutil.Process(pid)
            info = p.as_dict(attrs=['pid', 'name', 'status', 'cpu_percent', 'memory_info', 'username', 'cmdline', 'ppid', 'create_time'])
            cmdline = " ".join(info['cmdline']) if info.get('cmdline') else info['name']
            mem_mb = (info['memory_info'].rss / (1024*1024)) if info.get('memory_info') else 0.0
            return ProcessInfo(
                pid=info['pid'],
                name=info['name'],
                status=info['status'],
                cpu_percent=info['cpu_percent'] or 0.0,
                memory_mb=round(mem_mb, 2),
                username=info['username'] or "",
                command_line=cmdline,
                parent_pid=info['ppid'],
                created_at=str(info['create_time']),
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return None

    def find_process_by_name(self, name: str) -> list[ProcessInfo]:
        return [p for p in self.list_processes() if name.lower() in p.name.lower() or name.lower() in p.command_line.lower()]

    def kill_process(self, pid: int, force: bool = False) -> bool:
        try:
            p = psutil.Process(pid)
            if force:
                p.kill()
            else:
                p.terminate()
            return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False

    def start_process(self, command: str, args: list[str] = None, cwd: str = None, env: dict = None) -> int:
        full_cmd = [command] + (args or [])
        proc = subprocess.Popen(full_cmd, cwd=cwd, env=env)
        return proc.pid

    def list_installed_apps(self) -> list[InstalledApp]:
        apps = []
        desktop_files = glob.glob("/usr/share/applications/*.desktop") + glob.glob(os.path.expanduser("~/.local/share/applications/*.desktop"))
        for df in desktop_files[:50]:
            name = Path(df).stem
            try:
                with open(df, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if line.startswith("Name="):
                            name = line.split("=", 1)[1].strip()
                            break
            except Exception:
                pass
            apps.append(InstalledApp(name=name, install_path=df))
        return apps

    def open_application(self, name_or_path: str) -> bool:
        try:
            subprocess.Popen(["xdg-open", name_or_path])
            return True
        except Exception:
            return False

    def close_application(self, name: str) -> bool:
        procs = self.find_process_by_name(name)
        success = False
        for p in procs:
            if self.kill_process(p.pid, force=False):
                success = True
        return success

    def is_app_running(self, name: str) -> bool:
        return len(self.find_process_by_name(name)) > 0

    def list_directory(self, path: str, recursive: bool = False) -> list[dict]:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Path not found: {path}")
        results = []
        if recursive:
            for item in p.rglob("*"):
                results.append({"path": str(item), "is_dir": item.is_dir(), "size": item.stat().st_size if item.is_file() else 0})
        else:
            for item in p.iterdir():
                results.append({"path": str(item), "name": item.name, "is_dir": item.is_dir(), "size": item.stat().st_size if item.is_file() else 0})
        return results

    def get_file_info(self, path: str) -> dict:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Path not found: {path}")
        st = p.stat()
        return {
            "name": p.name,
            "path": str(p.absolute()),
            "size": st.st_size,
            "is_dir": p.is_dir(),
            "created_at": st.st_ctime,
            "modified_at": st.st_mtime,
        }

    def search_files(self, path: str, pattern: str, recursive: bool = True) -> list[str]:
        p = Path(path)
        matches = []
        glob_fn = p.rglob if recursive else p.glob
        for match in glob_fn(pattern):
            matches.append(str(match))
        return matches[:200]

    def create_directory(self, path: str) -> bool:
        Path(path).mkdir(parents=True, exist_ok=True)
        return True

    def copy_path(self, source: str, destination: str) -> bool:
        s, d = Path(source), Path(destination)
        if s.is_dir():
            shutil.copytree(s, d, dirs_exist_ok=True)
        else:
            shutil.copy2(s, d)
        return True

    def move_path(self, source: str, destination: str) -> bool:
        shutil.move(source, destination)
        return True

    def delete_path(self, path: str, recursive: bool = False) -> bool:
        p = Path(path)
        if p.is_dir():
            shutil.rmtree(p)
        else:
            p.unlink()
        return True

    def read_file(self, path: str, max_bytes: int = 1_000_000) -> str:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read(max_bytes)

    def write_file(self, path: str, content: str) -> bool:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
        return True

    def get_directory_size(self, path: str) -> int:
        total = 0
        for entry in os.scandir(path):
            if entry.is_file():
                total += entry.stat().st_size
            elif entry.is_dir():
                total += self.get_directory_size(entry.path)
        return total

    def list_windows(self) -> list[WindowInfo]:
        # Fallback implementation via wmctrl or xdotool if available
        windows = []
        if shutil.which("wmctrl"):
            try:
                res = subprocess.run(["wmctrl", "-l"], capture_output=True, text=True, timeout=2)
                for line in res.stdout.splitlines():
                    parts = line.split(maxsplit=3)
                    if len(parts) >= 4:
                        windows.append(WindowInfo(title=parts[3], pid=0))
            except Exception:
                pass
        return windows

    def get_active_window(self) -> Optional[WindowInfo]:
        windows = self.list_windows()
        return windows[0] if windows else None

    def focus_window(self, title: str) -> bool:
        if shutil.which("wmctrl"):
            try:
                subprocess.run(["wmctrl", "-a", title], check=True)
                return True
            except Exception:
                pass
        return False

    def minimize_window(self, title: str) -> bool:
        return False

    def maximize_window(self, title: str) -> bool:
        return False

    def close_window(self, title: str) -> bool:
        if shutil.which("wmctrl"):
            try:
                subprocess.run(["wmctrl", "-c", title], check=True)
                return True
            except Exception:
                pass
        return False

    def key_press(self, key: str) -> bool:
        try:
            import pyautogui
            pyautogui.press(key)
            return True
        except Exception:
            return False

    def hotkey(self, *keys: str) -> bool:
        try:
            import pyautogui
            pyautogui.hotkey(*keys)
            return True
        except Exception:
            return False

    def type_text(self, text: str, interval: float = 0.02) -> bool:
        try:
            import pyautogui
            pyautogui.write(text, interval=interval)
            return True
        except Exception:
            return False

    def mouse_move(self, x: int, y: int) -> bool:
        try:
            import pyautogui
            pyautogui.moveTo(x, y)
            return True
        except Exception:
            return False

    def mouse_click(self, x: int = None, y: int = None, button: str = "left", clicks: int = 1) -> bool:
        try:
            import pyautogui
            if x is not None and y is not None:
                pyautogui.click(x, y, button=button, clicks=clicks)
            else:
                pyautogui.click(button=button, clicks=clicks)
            return True
        except Exception:
            return False

    def mouse_scroll(self, amount: int) -> bool:
        try:
            import pyautogui
            pyautogui.scroll(amount)
            return True
        except Exception:
            return False

    def get_mouse_position(self) -> tuple[int, int]:
        try:
            import pyautogui
            pos = pyautogui.position()
            return pos.x, pos.y
        except Exception:
            return 0, 0

    def get_screen_size(self) -> tuple[int, int]:
        try:
            import pyautogui
            size = pyautogui.size()
            return size.width, size.height
        except Exception:
            return 1920, 1080

    def clipboard_get(self) -> str:
        try:
            import pyperclip
            return pyperclip.paste()
        except Exception:
            return ""

    def clipboard_set(self, text: str) -> bool:
        try:
            import pyperclip
            pyperclip.copy(text)
            return True
        except Exception:
            return False

    def list_services(self) -> list[ServiceInfo]:
        services = []
        if shutil.which("systemctl"):
            try:
                res = subprocess.run(["systemctl", "list-units", "--type=service", "--no-legend", "--no-pager"], capture_output=True, text=True, timeout=3)
                for line in res.stdout.splitlines():
                    parts = line.split(maxsplit=4)
                    if len(parts) >= 4:
                        services.append(ServiceInfo(
                            name=parts[0],
                            display_name=parts[4] if len(parts) > 4 else parts[0],
                            status="running" if parts[3] == "running" else "stopped"
                        ))
            except Exception:
                pass
        return services

    def get_service_status(self, name: str) -> Optional[ServiceInfo]:
        for s in self.list_services():
            if name.lower() in s.name.lower():
                return s
        return None

    def start_service(self, name: str) -> bool:
        try:
            subprocess.run(["systemctl", "start", name], check=True)
            return True
        except Exception:
            return False

    def stop_service(self, name: str) -> bool:
        try:
            subprocess.run(["systemctl", "stop", name], check=True)
            return True
        except Exception:
            return False

    def restart_service(self, name: str) -> bool:
        try:
            subprocess.run(["systemctl", "restart", name], check=True)
            return True
        except Exception:
            return False

    def execute_command(self, command: str, cwd: str = None, timeout: int = 30, env: dict = None) -> dict:
        start = time.monotonic()
        try:
            res = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
            )
            duration_ms = int((time.monotonic() - start) * 1000)
            return {
                "stdout": res.stdout,
                "stderr": res.stderr,
                "exit_code": res.returncode,
                "duration_ms": duration_ms,
            }
        except subprocess.TimeoutExpired as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            return {
                "stdout": e.stdout or "",
                "stderr": f"Command timed out after {timeout} seconds",
                "exit_code": 124,
                "duration_ms": duration_ms,
            }
        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            return {
                "stdout": "",
                "stderr": str(e),
                "exit_code": 1,
                "duration_ms": duration_ms,
            }

    def get_env_var(self, name: str) -> Optional[str]:
        return os.environ.get(name)

    def set_env_var(self, name: str, value: str, persistent: bool = False) -> bool:
        os.environ[name] = value
        return True

    def list_env_vars(self) -> dict[str, str]:
        return dict(os.environ)

    def get_volume(self) -> int:
        return 50

    def set_volume(self, level: int) -> bool:
        return True

    def mute(self) -> bool:
        return True

    def unmute(self) -> bool:
        return True

    def get_display_info(self) -> list[dict]:
        return [{"width": 1920, "height": 1080, "primary": True}]

    def screenshot(self, path: str, region: tuple = None) -> str:
        try:
            import pyautogui
            img = pyautogui.screenshot(region=region)
            img.save(path)
            return path
        except Exception:
            return ""
