"""
Application Registry & Process Signature Catalog
=================================================

Pre-resolved application signatures for guarded, deterministic launches
and post-launch L3 state verification (process tables + window handles).
"""

from __future__ import annotations

import os
import json
import platform
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class AppSignature:
    """Pre-resolved metadata for a desktop application."""
    name: str
    aliases: List[str] = field(default_factory=list)
    executables: List[str] = field(default_factory=list)
    process_names: List[str] = field(default_factory=list)
    window_title_patterns: List[str] = field(default_factory=list)
    launch_args: List[str] = field(default_factory=list)
    is_uwp_uri: bool = False
    uwp_uri: str = ""

    def matches(self, query: str) -> bool:
        q = query.lower().strip()
        if q == self.name.lower():
            return True
        for a in self.aliases:
            if q == a.lower():
                return True
        for ex in self.executables:
            if q == ex.lower() or q == ex.lower().replace(".exe", ""):
                return True
        return False


_KNOWN_APPS: List[AppSignature] = [
    AppSignature(
        name="vscode",
        aliases=["vs code", "vscode", "visual studio code", "code"],
        executables=["code.cmd", "code.exe", "code"],
        process_names=["code.exe", "Code.exe"],
        window_title_patterns=["Visual Studio Code"],
    ),
    AppSignature(
        name="chrome",
        aliases=["google chrome", "chrome"],
        executables=["chrome.exe", "chrome", "google-chrome"],
        process_names=["chrome.exe", "google-chrome"],
        window_title_patterns=["Google Chrome", "Chrome"],
    ),
    AppSignature(
        name="calculator",
        aliases=["calc", "calculator"],
        executables=["calc.exe", "calc"],
        process_names=["CalculatorApp.exe", "calc.exe", "Calculator.exe"],
        window_title_patterns=["Calculator"],
        is_uwp_uri=True,
        uwp_uri="calculator:",
    ),
    AppSignature(
        name="notepad",
        aliases=["notepad", "text editor"],
        executables=["notepad.exe", "notepad"],
        process_names=["notepad.exe", "Notepad.exe"],
        window_title_patterns=["Notepad"],
    ),
    AppSignature(
        name="edge",
        aliases=["msedge", "edge", "microsoft edge"],
        executables=["msedge.exe", "msedge"],
        process_names=["msedge.exe"],
        window_title_patterns=["Microsoft Edge"],
    ),
    AppSignature(
        name="terminal",
        aliases=["wt", "windows terminal", "terminal"],
        executables=["wt.exe", "wt"],
        process_names=["WindowsTerminal.exe", "wt.exe"],
        window_title_patterns=["Windows Terminal"],
    ),
    AppSignature(
        name="explorer",
        aliases=["file explorer", "explorer", "files"],
        executables=["explorer.exe"],
        process_names=["explorer.exe"],
        window_title_patterns=["File Explorer", "This PC"],
    ),
    AppSignature(
        name="taskmgr",
        aliases=["task manager", "taskmgr"],
        executables=["taskmgr.exe"],
        process_names=["Taskmgr.exe", "taskmgr.exe"],
        window_title_patterns=["Task Manager"],
    ),
    AppSignature(
        name="spotify",
        aliases=["spotify"],
        executables=["spotify.exe", "spotify"],
        process_names=["Spotify.exe"],
        window_title_patterns=["Spotify"],
    ),
    AppSignature(
        name="discord",
        aliases=["discord"],
        executables=["discord.exe", "discord"],
        process_names=["Discord.exe"],
        window_title_patterns=["Discord"],
    ),
    AppSignature(
        name="slack",
        aliases=["slack"],
        executables=["slack.exe", "slack"],
        process_names=["slack.exe", "Slack.exe"],
        window_title_patterns=["Slack"],
    ),
    AppSignature(
        name="firefox",
        aliases=["firefox", "mozilla firefox"],
        executables=["firefox.exe", "firefox"],
        process_names=["firefox.exe"],
        window_title_patterns=["Mozilla Firefox", "Firefox"],
    ),
]


class ApplicationRegistry:
    """Registry for discovering, resolving, and verifying installed application binaries."""

    def __init__(self, apps: Optional[List[AppSignature]] = None) -> None:
        self._apps: List[AppSignature] = list(apps or _KNOWN_APPS)
        self._inventory_available = platform.system() != "Windows"
        self._inventory_error = ""
        self._resolution_issue = ""

    @property
    def inventory_available(self) -> bool:
        return self._inventory_available

    @property
    def inventory_error(self) -> str:
        return self._inventory_error

    @property
    def resolution_issue(self) -> str:
        return self._resolution_issue

    def register(self, app: AppSignature) -> None:
        self._apps.append(app)

    def resolve(self, query: str) -> Optional[AppSignature]:
        """Resolve a raw natural query to a matching AppSignature."""
        q = query.lower().strip()
        if platform.system() == "Windows":
            self._resolution_issue = ""
            # Only resolve apps Windows reports as launchable. The bundled list
            # supplies process signatures and aliases, but is not proof of install.
            matches = []
            for apps in self.list_installed().values():
                for installed in apps:
                    known = next((app for app in self._apps
                                  if app.matches(installed.name.lower())
                                  or any(installed.name.lower() == alias.lower()
                                         for alias in app.aliases)), None)
                    exact_match = installed.matches(q) or bool(known and known.matches(q))
                    partial_match = bool(q and q in installed.name.casefold())
                    if exact_match or partial_match:
                        matches.append((installed, known, exact_match))
            exact_matches = [match for match in matches if match[2]]
            candidates = exact_matches or matches
            if len(candidates) > 1:
                names = sorted({entry[0].name for entry in candidates}, key=str.casefold)
                self._resolution_issue = "Ambiguous app name; matching entries: " + ", ".join(names)
                return None
            if candidates:
                installed, known, _ = candidates[0]
                self._resolution_issue = ""
                if known:
                    return AppSignature(
                        name=installed.name,
                        aliases=list(dict.fromkeys([*known.aliases, *installed.aliases])),
                        executables=known.executables,
                        process_names=list(dict.fromkeys([*known.process_names, *installed.process_names])),
                        window_title_patterns=list(dict.fromkeys(
                            [*known.window_title_patterns, *installed.window_title_patterns]
                        )),
                        launch_args=known.launch_args,
                        is_uwp_uri=known.is_uwp_uri,
                        uwp_uri=known.uwp_uri,
                    )
                return installed
            self._resolution_issue = ""
            return None

        for app in self._apps:
            if app.matches(q):
                return app

        # Fallback check: is query an executable on system PATH?
        exe_path = shutil.which(q) or shutil.which(f"{q}.exe")
        if exe_path:
            base_name = os.path.basename(exe_path)
            return AppSignature(
                name=q,
                aliases=[q],
                executables=[exe_path],
                process_names=[base_name],
                window_title_patterns=[q],
            )

        return None

    def list_installed(self) -> Dict[str, List[AppSignature]]:
        """Return Windows Start-menu apps grouped into readable categories."""
        grouped: Dict[str, List[AppSignature]] = {}
        if platform.system() == "Windows":
            self._inventory_available = False
            self._inventory_error = "Windows app inventory has not been refreshed."
            # Get-StartApps includes classic Start-menu shortcuts and packaged
            # Windows apps, giving Search the same names it can launch.
            command = (
                "Get-StartApps | Select-Object Name, AppID | "
                "ConvertTo-Json -Compress"
            )
            try:
                result = subprocess.run(
                    ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
                    capture_output=True, text=True, timeout=10, check=False,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                if result.returncode == 0:
                    rows = json.loads(result.stdout) if result.stdout.strip() else []
                    if isinstance(rows, dict):
                        rows = [rows]
                    if not isinstance(rows, list):
                        raise ValueError("Windows returned an unexpected app inventory format")
                    for row in rows if isinstance(rows, list) else []:
                        if not isinstance(row, dict):
                            continue
                        name = str(row.get("Name") or "").strip()
                        if not name:
                            continue
                        aliases = [name]
                        app_id = str(row.get("AppID") or "")
                        if app_id:
                            aliases.append(app_id)
                        process_names = []
                        if app_id.casefold().endswith(".exe") and os.path.isfile(app_id):
                            process_names.append(os.path.basename(app_id))
                        signature = AppSignature(
                            name=name, aliases=aliases,
                            process_names=process_names,
                            window_title_patterns=[name],
                        )
                        grouped.setdefault(_category_for(name), []).append(signature)
                    self._inventory_available = True
                    self._inventory_error = ""
                else:
                    detail = (result.stderr or result.stdout or "no output").strip()
                    self._inventory_error = f"Get-StartApps failed: {detail}"
            except (OSError, subprocess.SubprocessError, json.JSONDecodeError, ValueError) as exc:
                self._inventory_error = f"Could not read Windows app inventory: {exc}"

        return {
            category: sorted(apps, key=lambda app: app.name.casefold())
            for category, apps in sorted(grouped.items())
        }

    def list_all(self) -> List[AppSignature]:
        return list(self._apps)


def _category_for(name: str) -> str:
    """Assign a practical category from a Start-menu app's display name."""
    value = name.casefold()
    categories = {
        "Browsers": ("chrome", "firefox", "edge", "brave", "opera", "browser"),
        "Communication": ("teams", "outlook", "zoom", "slack", "discord", "telegram", "whatsapp", "skype"),
        "Development": ("visual studio", "vscode", "vs code", "github", "git", "postman", "android studio", "terminal"),
        "Productivity": ("word", "excel", "powerpoint", "office", "notion", "onenote", "obsidian", "libreoffice"),
        "Media": ("spotify", "vlc", "media player", "music", "photos", "camera"),
        "Graphics and design": ("paint", "figma", "blender", "photoshop", "illustrator", "capcut", "canva"),
        "Games": ("steam", "epic games", "xbox", "minecraft", "roblox"),
        "System tools": ("settings", "task manager", "control panel", "file explorer", "calculator", "notepad", "snipping tool", "security"),
    }
    for category, terms in categories.items():
        if any(term in value for term in terms):
            return category
    return "Other"
