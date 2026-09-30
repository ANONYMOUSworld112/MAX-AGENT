# MAX-AGENT — Real Architecture Audit

> **Forensic Audit Date**: 2026-09-30  
> **Source Commit**: `877b913` (branch: `max/p0-baseline`)  
> **Auditor**: Principal AI Systems Architect & Codebase Forensic Engineer  
> **Status**: COMPLETED & VERIFIED AGAINST SOURCE CODE  

---

## 1. Executive Forensic Discovery: The Dual-Architecture Reality

A deep-level static and dynamic code inspection of repository `ANONYMOUSworld112/MAX-AGENT` reveals a stark divergence between **Documented Architecture** (in `readme.md`, `IMPLEMENTATION_PLAN.md`, and `memory/long_term.json`) and **Actual Executed Architecture** in production (`main.py`, `ui.py`, `actions/`).

The codebase is effectively split into two disconnected universes:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      ACTIVE EXECUTED ARCHITECTURE                           │
│  (What actually runs when a user speaks or types into MAX)                  │
│                                                                             │
│  User Speech / Text / Dashboard Web                                         │
│         │                                                                   │
│         ▼                                                                   │
│  main.py (MaxLive) ──► WebSocket ──► Gemini 3.1 Live Preview Model          │
│         ▲                                    │                              │
│         │                                    ▼ Function Call (fc.name)      │
│         └──────────── main.py:_execute_tool()                               │
│                              │                                              │
│         ┌────────────────────┼────────────────────┐                         │
│         ▼                    ▼                    ▼                         │
│   Inline Tools         actions/*.py         agents/*.py (33 Stubs)          │
│  (screen_process,    (open_app, desktop,    (BaseAgent.run wrapper          │
│   save_memory, etc)   dev_agent, etc)        calls stub _execute())         │
└─────────────────────────────────────────────────────────────────────────────┘

                                     VS

┌─────────────────────────────────────────────────────────────────────────────┐
│                    INACTIVE / DORMANT ARCHITECTURE                          │
│  (Sophisticated kernel modules built in isolation, never wired to main loop)│
│                                                                             │
│  • core/max_infra/task_queue.py     ──► Instantiated in main.py, never used │
│  • core/max_infra/state_db.py       ──► SQLite WAL database, zero calls     │
│  • core/max_infra/task_lifecycle.py ──► 10-state FSM, zero active tasks     │
│  • core/max_infra/watchdog.py       ──► Background watchdog, never spawned  │
│  • core/max_infra/vault.py          ──► AES-256 Vault, api_keys.json plain  │
│  • core/perception/*                ──► Accessibility & DOM, never imported │
│  • core/verification/*              ──► VerificationEngine, never imported  │
│  • core/reflex/triage.py            ──► ReflexTriage, zero calls            │
│  • core/reflex/guardrails.py        ──► Bypassed on all normal requests     │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Component-by-Component Forensic Audit

| Subsystem | Documented Claim | Source File & Class | Actual Implementation Status | Actual Execution Role |
|---|---|---|---|---|
| **Entry Point** | Unified autonomous agent launcher | `main.py:main()` | [EXISTS] [ACTIVE] | Starts PyQt6 UI thread and an asyncio background thread running `MaxLive.run()`. |
| **User Interface** | Cybernetic Stark HUD with live waveform | `ui.py:MAXUI` | [EXISTS] [ACTIVE] | PyQt6 window rendering face animations, waveform audio levels, chat logs, settings drawer, and wake toggles. |
| **Model Connection** | Multi-model router with local/cloud fallback | `main.py:MaxLive._build_config()` | [EXISTS] [ACTIVE] | Hardcoded bidirectional WebSocket to Google Gemini Live API: `models/gemini-3.1-flash-live-preview`. |
| **Input Ingestion** | Multimodal ingestion gateway with provenance | `main.py:_listen_audio()`, `_on_text_command()` | [EXISTS] [ACTIVE] | Raw 16kHz PCM audio or text strings forwarded directly into Gemini WebSocket. No provenance tracking. |
| **Intent Detection** | Sub-33ms LAYA System 1 Reflex Engine | `core/reflex/intent_router.py:ReflexIntentRouter` | [EXISTS] [DORMANT] | **Bypassed.** Intent is determined entirely by Google's Gemini model server-side. Reflex router is only called as a fallback if Gemini returns an unknown tool name. |
| **Guardrails & Risk** | 4-tier security gate blocking dangerous actions | `core/reflex/guardrails.py:ReflexGuardrails` | [EXISTS] [DORMANT] | **Bypassed.** `ReflexGuardrails` is never invoked during tool execution. Tools execute immediately without risk tier evaluation. |
| **Task Queue** | Priority heapq with anti-starvation aging | `core/max_infra/task_queue.py:TaskQueue` | [EXISTS] [UNUSED] | Instantiated on line 472 of `main.py` (`self._task_queue = TaskQueue()`), but never enqueued or dequeued anywhere in `main.py`. |
| **Task State Machine** | 10-state transactional lifecycle FSM | `core/max_infra/task_lifecycle.py:TaskLifecycleFSM` | [EXISTS] [UNUSED] | Exists with clean state transition logic, but never instantiated or bound to incoming user requests. |
| **State Database** | SQLite WAL engine with audit chaining | `core/max_infra/state_db.py:StateDB` | [EXISTS] [UNUSED] | Complete SQLite schema with 7 tables, but no production module opens or writes to `max_state.db`. |
| **Agent Registry** | 33-agent specialized autonomous swarm | `agents/router.py:AgentRegistry` | [EXISTS] [EXPOSED AS TOOLS] | Registers 33 agent classes. Exposes all 33 schemas directly to Gemini's function calling list. |
| **Agent Logic** | Domain specialists (coding, calendar, email, etc.) | `agents/*/*.py` | [EXISTS] [MOCKED] | All 33 agents are shallow stubs returning mock dictionaries and simulated success messages (`AgentOutput(success=True)`). |
| **Action Tools** | 19 modular action handlers | `actions/*.py` | [EXISTS] [ACTIVE] | Auto-discovered by `core/action_loader.py`. These perform the actual real work on the machine (launching apps, searching web, capturing screen). |
| **Desktop Automation** | Computer Use Agent with UIA / Vision | `actions/desktop.py` | [EXISTS] [ACTIVE / UNSAFE] | Generates raw Python code via Gemini Flash and executes it via `exec()` with `pyautogui` and `ctypes`. |
| **Application Launch** | Verified app launcher with process tracking | `actions/open_app.py:open_app()` | [EXISTS] [ACTIVE / FRAGILE] | Checks `shutil.which` -> `subprocess.Popen(shell=True)` -> Blind Windows Search keypress simulation. No window or process verification. |
| **Perception Engine** | UIA accessibility tree + DOM + OCR | `core/perception/*` | [EXISTS] [UNUSED] | Complete perception modules exist on disk but are never imported by `main.py` or any active action. Vision uses basic `mss` JPEG capture. |
| **Verification Engine** | Multi-level verifier (L0-L3) | `core/verification/*` | [EXISTS] [UNUSED] | Verifier classes exist on disk but are never called. Tool success is assumed if no Python exception is raised. |
| **Secret Storage** | AES-256 encrypted credential vault | `core/max_infra/vault.py:MaxVault` | [EXISTS] [UNUSED] | API keys are read from plaintext JSON file at `config/api_keys.json`. |
| **Dashboard / Remote** | Local web control surface | `dashboard/server.py:DashboardServer` | [EXISTS] [ACTIVE / RISKY] | FastAPI server binding to `0.0.0.0:8000`. Attempts automatic Windows Firewall elevation via temporary batch script. |

---

## 3. Real Process and Concurrency Model

MAX operates as a single Python process with a multi-threaded architecture:

1. **Thread 1 (Main Thread - GUI)**: Runs the PyQt6 `QApplication.exec()` event loop, managing UI rendering, waveform visualizer, and user window interactions.
2. **Thread 2 (Background Daemon - MAX Runtime)**: Runs `asyncio.run(MaxLive.run())` inside an asyncio event loop.
3. **Asyncio TaskGroup**: Manages concurrent network and audio coroutines:
   - `_listen_audio`: Reads PCM input from `sounddevice.InputStream` callback.
   - `_send_realtime`: Sends audio PCM chunks over Gemini WebSocket.
   - `_receive_audio`: Consumes server responses, text transcriptions, audio bytes, and tool calls.
   - `_play_audio`: Writes server audio chunks to `sounddevice.RawOutputStream`.
   - `_run_system_monitor`: Periodic 10s CPU/RAM threshold checks.
   - `_run_background_monitor`: Periodic 30m news topic checks.
   - `_run_proactive_mode`: Periodic 60s silence check-in.
   - `_run_sleep_watch`: Periodic 5s wake-word sleep check.
   - `_process_dashboard_commands`: Polls remote command queue.
4. **Thread Pool Executor**: Used via `loop.run_in_executor(None, ...)` to run blocking action handlers (`open_app`, `desktop`, `web_search`) so they do not freeze the asyncio event loop.
5. **Detector Thread**: `WakeWordDetector` runs `openwakeword` inference in its own dedicated thread when wake word mode is active.

---

## 4. Key Architectural Flaws Identified

1. **Bypassed Control Plane**: The control plane promised in the architecture diagrams does not control execution. Gemini directly decides which tool to call.
2. **Mock Agent Layer**: All 33 agents in `agents/` are cosmetic stubs. When Gemini invokes an agent tool (e.g. `codingagent`), it receives a synthetic confirmation without any real work performed.
3. **Unchoked Side Effects**: 37 execution call sites across 16 files bypass any centralized security gateway, executing `subprocess.Popen`, `os.system`, `pyautogui`, and `open("w")` directly.
4. **Arbitrary Code Execution**: `actions/desktop.py` passes LLM-generated code directly to `exec()`, creating an extreme remote code execution (RCE) risk.
5. **Unsandboxed Pip Installs**: `actions/dev_agent.py` installs unpinned packages directly into the host Python environment via `sys.executable -m pip install`.
6. **False Success Verification**: Actions return "Done" or "Opened [app]" without verifying that target processes exist or windows are focused.
