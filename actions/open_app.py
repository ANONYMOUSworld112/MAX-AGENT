"""
MAX-AGENT Application Launcher with L3 State Verification
==========================================================

Guarded application launch using ApplicationRegistry and L3 verification
(process table + window handle verification). Rejects non-existent applications
honestly without false-positive claims.
"""

import logging
import os
import platform
import shutil
import subprocess
import time

from core.adapters import get_desktop_adapter
from core.app_registry import ApplicationRegistry, AppSignature

logger = logging.getLogger("max.actions.open_app")

_SYSTEM = platform.system()
_REGISTRY = ApplicationRegistry()

_APP_ALIASES: dict[str, dict[str, str]] = {
    "chrome":             {"Windows": "chrome",                  "Darwin": "Google Chrome",        "Linux": "google-chrome"},
    "google chrome":      {"Windows": "chrome",                  "Darwin": "Google Chrome",        "Linux": "google-chrome"},
    "firefox":            {"Windows": "firefox",                 "Darwin": "Firefox",              "Linux": "firefox"},
    "edge":               {"Windows": "msedge",                  "Darwin": "Microsoft Edge",       "Linux": "microsoft-edge"},
    "brave":              {"Windows": "brave",                   "Darwin": "Brave Browser",        "Linux": "brave-browser"},
    "safari":             {"Windows": "msedge",                  "Darwin": "Safari",               "Linux": "firefox"},
    "opera":              {"Windows": "opera",                   "Darwin": "Opera",                "Linux": "opera"},
    "whatsapp":           {"Windows": "WhatsApp",                "Darwin": "WhatsApp",             "Linux": "whatsapp"},
    "telegram":           {"Windows": "Telegram",                "Darwin": "Telegram",             "Linux": "telegram"},
    "discord":            {"Windows": "Discord",                 "Darwin": "Discord",              "Linux": "discord"},
    "slack":              {"Windows": "Slack",                   "Darwin": "Slack",                "Linux": "slack"},
    "zoom":               {"Windows": "Zoom",                    "Darwin": "zoom.us",              "Linux": "zoom"},
    "teams":              {"Windows": "msteams",                 "Darwin": "Microsoft Teams",      "Linux": "teams"},
    "skype":              {"Windows": "skype",                   "Darwin": "Skype",                "Linux": "skype"},
    "signal":             {"Windows": "signal",                  "Darwin": "Signal",               "Linux": "signal"},
    "spotify":            {"Windows": "Spotify",                 "Darwin": "Spotify",              "Linux": "spotify"},
    "vlc":                {"Windows": "vlc",                     "Darwin": "VLC",                  "Linux": "vlc"},
    "netflix":            {"Windows": "Netflix",                 "Darwin": "Netflix",              "Linux": "firefox"},
    "vscode":             {"Windows": "code",                    "Darwin": "Visual Studio Code",   "Linux": "code"},
    "visual studio code": {"Windows": "code",                    "Darwin": "Visual Studio Code",   "Linux": "code"},
    "code":               {"Windows": "code",                    "Darwin": "Visual Studio Code",   "Linux": "code"},
    "terminal":           {"Windows": "wt",                      "Darwin": "Terminal",             "Linux": "x-terminal-emulator"},
    "cmd":                {"Windows": "cmd.exe",                 "Darwin": "Terminal",             "Linux": "bash"},
    "powershell":         {"Windows": "powershell.exe",          "Darwin": "Terminal",             "Linux": "bash"},
    "postman":            {"Windows": "Postman",                 "Darwin": "Postman",              "Linux": "postman"},
    "git":                {"Windows": "git-bash",                "Darwin": "Terminal",             "Linux": "bash"},
    "figma":              {"Windows": "Figma",                   "Darwin": "Figma",                "Linux": "figma"},
    "blender":            {"Windows": "blender",                 "Darwin": "Blender",              "Linux": "blender"},
    "word":               {"Windows": "winword",                 "Darwin": "Microsoft Word",       "Linux": "libreoffice --writer"},
    "excel":              {"Windows": "excel",                   "Darwin": "Microsoft Excel",      "Linux": "libreoffice --calc"},
    "powerpoint":         {"Windows": "powerpnt",                "Darwin": "Microsoft PowerPoint", "Linux": "libreoffice --impress"},
    "libreoffice":        {"Windows": "soffice",                 "Darwin": "LibreOffice",          "Linux": "libreoffice"},
    "notepad":            {"Windows": "notepad.exe",             "Darwin": "TextEdit",             "Linux": "gedit"},
    "textedit":           {"Windows": "notepad.exe",             "Darwin": "TextEdit",             "Linux": "gedit"},
    "explorer":           {"Windows": "explorer.exe",            "Darwin": "Finder",               "Linux": "nautilus"},
    "file explorer":      {"Windows": "explorer.exe",            "Darwin": "Finder",               "Linux": "nautilus"},
    "finder":             {"Windows": "explorer.exe",            "Darwin": "Finder",               "Linux": "nautilus"},
    "task manager":       {"Windows": "taskmgr.exe",             "Darwin": "Activity Monitor",     "Linux": "gnome-system-monitor"},
    "settings":           {"Windows": "ms-settings:",            "Darwin": "System Preferences",   "Linux": "gnome-control-center"},
    "calculator":         {"Windows": "calc.exe",                "Darwin": "Calculator",           "Linux": "gnome-calculator"},
    "paint":              {"Windows": "mspaint.exe",             "Darwin": "Preview",              "Linux": "gimp"},
    "instagram":          {"Windows": "Instagram",               "Darwin": "Instagram",            "Linux": "firefox"},
    "tiktok":             {"Windows": "TikTok",                  "Darwin": "TikTok",               "Linux": "firefox"},
    "notion":             {"Windows": "Notion",                  "Darwin": "Notion",               "Linux": "notion"},
    "obsidian":           {"Windows": "Obsidian",                "Darwin": "Obsidian",             "Linux": "obsidian"},
    "capcut":             {"Windows": "CapCut",                  "Darwin": "CapCut",               "Linux": "capcut"},
    "steam":              {"Windows": "steam",                   "Darwin": "Steam",                "Linux": "steam"},
    "epic":               {"Windows": "EpicGamesLauncher",       "Darwin": "Epic Games Launcher",  "Linux": "legendary"},
    "epic games":         {"Windows": "EpicGamesLauncher",       "Darwin": "Epic Games Launcher",  "Linux": "legendary"},
}


def _normalize(raw: str) -> str:
    key = raw.lower().strip()
    if key in _APP_ALIASES:
        return _APP_ALIASES[key].get(_SYSTEM, raw)
    for alias_key, os_map in _APP_ALIASES.items():
        if alias_key in key or key in alias_key:
            return os_map.get(_SYSTEM, raw)
    return raw


def _is_app_window_open(signature: AppSignature) -> bool:
    """Require a visible window match before reporting that an app opened."""
    adapter = get_desktop_adapter()
    windows = adapter.list_windows()
    for win in windows:
        if win.get("is_visible") is False:
            continue
        w_title = win.get("title", "").lower()
        w_proc = win.get("process_name", "").lower()
        if signature.process_names and w_proc:
            if any(expected.lower() == w_proc for expected in signature.process_names):
                return True
            continue
        for pat in signature.window_title_patterns:
            if pat.lower() in w_title:
                return True

    return False


def _launch_signature(signature: AppSignature) -> bool:
    """Launch an installed app through Windows Search or a native executable."""
    if _SYSTEM == "Windows":
        adapter = get_desktop_adapter()
        if not adapter.hotkey("win", "s"):
            return False
        time.sleep(0.6)
        if not adapter.hotkey("ctrl", "a"):
            return False
        if not adapter.type_text(signature.name):
            return False
        time.sleep(0.4)
        return adapter.hotkey("enter")

    # 1. Check UWP URI (e.g. calculator:)
    if signature.is_uwp_uri:
        try:
            os.startfile(signature.uwp_uri)
            return True
        except Exception as exc:
            logger.debug("os.startfile failed for UWP URI %s: %s", signature.uwp_uri, exc)

    # 2. Check executables on PATH
    for exe in signature.executables:
        bin_path = shutil.which(exe) or (exe if os.path.isabs(exe) and os.path.exists(exe) else None)
        if bin_path:
            try:
                subprocess.Popen(
                    [bin_path] + signature.launch_args,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    shell=(_SYSTEM == "Windows"),
                )
                return True
            except Exception as exc:
                logger.error("Failed to spawn %s: %s", bin_path, exc)

    return False


def open_app(
    parameters=None,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    app_name = (parameters or {}).get("app_name", "").strip()

    if not app_name:
        return "No application name provided."

    sig = _REGISTRY.resolve(app_name)
    if sig is None:
        if _REGISTRY.resolution_issue:
            return f"I found more than one app matching '{app_name}'. {_REGISTRY.resolution_issue}. Please name the app more specifically."
        if not _REGISTRY.inventory_available:
            return (
                f"I couldn't check whether '{app_name}' is installed because the Windows app "
                f"inventory failed. {_REGISTRY.inventory_error}"
            )
        return f"Application '{app_name}' is not present in the installed apps found on this system."

    logger.info("Resolved '%s' to application signature '%s'", app_name, sig.name)
    if player:
        player.write_log(f"[open_app] Launching {sig.name}...")

    # Check if already running
    if _is_app_window_open(sig):
        return f"Application '{app_name}' is already running."

    # Launch application
    launched = _launch_signature(sig)
    if not launched:
        return f"I couldn't send the Windows Search launch input for '{app_name}'. It was not opened."

    # L3 Verification Loop. Cold app startups can take several seconds.
    start_t = time.time()
    while time.time() - start_t < 8.0:
        if _is_app_window_open(sig):
            return f"Opened {app_name} (verified: visible app window)."
        time.sleep(0.3)

    return (
        f"I sent the launch request for '{app_name}', but could not verify that it opened. "
        "I can't confirm it launched."
    )


# ── Tool declaration (auto-discovered by core/action_loader.py) ──────────────
TOOL = {
    "name": "open_app",
    "description": "Whenever asked to open, launch, or start an app, always use this action. On Windows, check the current Search inventory and launch through Windows Search. Report success only after a matching visible app window is observed; otherwise say it could not be verified and may not have opened. If the inventory cannot be read, report that instead of guessing.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "app_name": {
                "type": "STRING",
                "description": "Application name as shown in Windows Search (e.g. 'VS Code', 'Chrome', 'Calculator')",
            }
        },
        "required": [
            "app_name"
        ]
    },
    "handler": open_app,
}
