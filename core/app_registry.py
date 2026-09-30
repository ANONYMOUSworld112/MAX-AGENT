"""
Application Registry & Process Signature Catalog
=================================================

Pre-resolved application signatures for guarded, deterministic launches
and post-launch L3 state verification (process tables + window handles).
"""

from __future__ import annotations

import os
import shutil
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
        window_title_patterns=["Windows Terminal", "PowerShell", "Command Prompt"],
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

    def register(self, app: AppSignature) -> None:
        self._apps.append(app)

    def resolve(self, query: str) -> Optional[AppSignature]:
        """Resolve a raw natural query to a matching AppSignature."""
        q = query.lower().strip()
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

    def list_all(self) -> List[AppSignature]:
        return list(self._apps)
