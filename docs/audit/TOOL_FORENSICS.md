# MAX-AGENT — Tool Invocation & Schema Forensics

> **Forensic Audit Date**: 2026-09-30  
> **Source Commit**: `877b913` (branch: `max/p0-baseline`)  
> **Auditor**: Principal AI Systems Architect & Codebase Forensic Engineer  
> **Status**: COMPLETED & VERIFIED AGAINST SOURCE CODE  

---

## 1. Tool Population Overview

At startup, MAX exposes **60+ tool definitions** to the Google Gemini Live session (`main.py:770`):
1. **8 Inline Tools** (`TOOL_DECLARATIONS` in `main.py`)
2. **19 Action Tools** (`actions/*.py` discovered by `core/action_loader.py`)
3. **33 Agent Tools** (`agents/*/*.py` registered in `AgentRegistry`)
4. **Plugin Tools** (`plugins/` discovered by `core/plugin_loader.py`)

---

## 2. Inline Tools (`main.py`)

| Tool Name | Owner | Declared Parameters | Real Side Effects | Timeout | Verification Level | Security / Risk Assessment |
|---|---|---|---|---|---|---|
| `system_status` | `main.py:881` | None | Reads CPU, RAM, GPU, temps via `psutil` | None | L3 (Local OS read) | LOW. Safe read-only telemetry. |
| `screen_process` | `main.py:846` | `angle` (screen/camera), `text` | Captures display screenshot or webcam frame | 4s cooldown | L1 (Vision prompt injection) | MEDIUM. Captures sensitive screen content/credentials. |
| `close_camera` | `main.py:877` | None | Stops UI camera stream | None | L0 (UI state flag) | LOW. UI state update. |
| `manage_monitor`| `main.py:885` | `action` (add/remove/list), `topic` | Modifies `~/.MAX/monitored_topics.json` | None | L3 (JSON file write) | LOW. User-configured news monitoring. |
| `shutdown_max` | `main.py:898` | None | Saves session summary, terminates process (`os._exit(0)`) | 1.5s sleep | L0 (Process termination) | HIGH. Kills running assistant. |
| `save_memory` | `main.py:812` | `category`, `key`, `value` | Modifies `memory/long_term.json` | None | L3 (JSON file write) | MEDIUM. Unsanitized memory write. |
| `recall_memory`| `main.py:830` | `query` | Reads `memory/long_term.json` | None | L3 (JSON file read) | LOW. Local dictionary scan. |
| `undo` | `main.py:837` | `action` (undo/list) | Pops `core/undo.py` stack, reverses file ops / settings | None | L2 (Rollback execution) | MEDIUM. Modifies files / system settings. |

---

## 3. Discovered Actions (`actions/*.py`)

| Tool Name | Source File | Handler Function | Real Side Effects | Verification | Forensic Status |
|---|---|---|---|---|---|
| `open_app` | `actions/open_app.py` | `open_app()` | `subprocess.Popen(shell=True)`, `pyautogui.press("win")` | None (fixed sleep) | ACTIVE / UNVERIFIED |
| `desktop` | `actions/desktop.py` | `desktop()` | `exec()` with LLM code, `ctypes`, `pyautogui` | None | ACTIVE / EXTREMELY UNSAFE |
| `dev_agent` | `actions/dev_agent.py` | `dev_agent()` | File generation, host `pip install`, `subprocess.run` | Traceback parse | ACTIVE / UNSANDBOXED |
| `reminder` | `actions/reminder.py` | `reminder()` | Creates Windows Scheduled Task via `schtasks.exe` | None | ACTIVE / UNCHOKED |
| `youtube_video` | `actions/youtube_video.py` | `youtube_video()` | HTTP scrape, `cmd /c start`, Notepad popup | None | ACTIVE / INDIRECT INJECTION |
| `browser_control` | `actions/browser_control.py` | `browser_control()` | Spawns browser or simulates hotkeys | None | ACTIVE / UNVERIFIED |
| `file_controller` | `actions/file_controller.py` | `file_controller()` | File create, move, copy, delete (`os.remove`) | None | ACTIVE / UNCHOKED WRITE/DELETE |
| `file_processor` | `actions/file_processor.py` | `file_processor()` | Reads PDF, DOCX, TXT, CSV, image OCR | None | ACTIVE (Read-only) |
| `web_search` | `actions/web_search.py` | `web_search()` | DuckDuckGo search, scrapes top pages | None | ACTIVE (Read-only) |
| `weather_report` | `actions/weather_report.py` | `weather_report()` | HTTP request to wttr.in | None | ACTIVE (Read-only) |
| `flight_finder` | `actions/flight_finder.py` | `flight_finder()` | HTTP scrape | None | ACTIVE (Read-only) |
| `game_updater` | `actions/game_updater.py` | `game_updater()` | Subprocess / Steam check | None | ACTIVE / UNVERIFIED |
| `computer_settings` | `actions/computer_settings.py` | `computer_settings()` | Volume, brightness, wifi, power | UI Confirm for power | ACTIVE / PARTIAL GATE |
| `computer_control` | `actions/computer_control.py` | `computer_control()` | Keystroke / click simulation via `pyautogui` | None | ACTIVE / UNCHOKED |
| `send_message` | `actions/send_message.py` | `send_message()` | Webhook / message trigger | None | ACTIVE / UNCHOKED |
| `code_helper` | `actions/code_helper.py` | `code_helper()` | Syntax checking | None | ACTIVE (Read-only) |
| `system_monitor` | `actions/system_monitor.py` | `system_monitor()` | `psutil` telemetry | L3 (Local metrics) | ACTIVE (Read-only) |
| `background_monitor` | `actions/background_monitor.py` | `manage_monitor()` | Topic persistence | L3 (File read/write) | ACTIVE |
| `proactive` | `actions/proactive.py` | Engine class | Background check-in prompt builder | None | ACTIVE (Background) |

---

## 4. Agent Tools (`agents/*/*.py` — 33 Registered)

All 33 agent tools expose a generic schema:
```json
{
  "name": "<agent_name_lowercase>",
  "description": "<Agent Description>",
  "parameters": {
    "type": "object",
    "properties": {
      "task_description": {"type": "string"},
      "parameters": {"type": "object"}
    },
    "required": ["task_description"]
  }
}
```
**Forensic Reality**: When called, all 33 agents execute a stub method returning synthetic output.  
**Result**: 33 duplicate, misleading tools that confuse model routing and produce false-positive success reports.

---

## 5. Critical Tool Architecture Vulnerabilities

1. **Tool Namespace Pollution**: Flooding the LLM context with 60+ tool declarations exceeds the effective tool-routing capacity of small/fast models, degrading selection accuracy.
2. **Missing Input Schema Validation**: Action handlers accept loose `dict` arguments without Pydantic schema validation.
3. **No Central Side-Effect Choke Point**: Actions execute raw `subprocess`, `os.remove`, and `winreg` calls directly without passing through an `ExecutionGateway`.
4. **Zero Pre-Execution Confirmation on Dangerous Actions**:
   - `file_controller` can delete arbitrary files with `action="delete"` without a confirmation dialog.
   - `dev_agent` can run `pip install` on the host machine without confirmation.
5. **No Verification of Effect**: Almost zero tools verify that the real physical effect occurred before reporting success.
