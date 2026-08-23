# MAX — Computer-Use Upgrade
## REPO_AUDIT.md (Phase 0 — Repo Ground Truth Audit)

| | |
|---|---|
| **Purpose** | Satisfy the "do not break existing MAX" constraint by documenting what already exists before extending it |
| **Status** | **COMPLETED** — Audited against the live MAX repository. |
| **Audit Date** | 2026-08-17 |

---

## Executive Summary

The MAX repository possesses a mature multi-agent architecture with a 24-table SQLite state database (`max_state.db`), a 5-layer Bayesian memory subsystem, a dual orchestrator architecture (`core/orchestrator.py` and `src/core/main_agent.py`), a comprehensive tool abstraction system, and native platform adapters for Windows, Linux, and macOS.

The new Computer-Use Layer upgrade (PRD, TRD, ARCHITECTURE, AGENTS, API_CONTRACT, DECISIONS, IMPLEMENTATION_PLAN) is **100% architecturally compatible** with the existing codebase. It acts as the specialized Level 4 execution engine and Level 7 perception layer without disrupting existing workflows.

---

## 1. Current Agents

- **Existing Agent Implementation**:
  - **Core Agents (`src/agents/`, `agents/`)**: `MainAgent` (`src/core/main_agent.py`), `CodingAgent` (`src/agents/coding_agent.py`, `agents/coding.py`), `DeployAgent` (`src/agents/deploy_agent.py`, `agents/deploy.py`), `CalendarAgent` (`src/agents/calendar_agent.py`, `agents/calendar.py`), `NotesAgent` (`src/agents/notes_agent.py`, `agents/notes.py`), `ResearchAgent` (`src/agents/research_agent.py`, `agents/research.py`), `DocumentAgent` (`agents/document.py`), `ApplicationAssistAgent` (`agents/application_assist.py`), `ApplicationAgent` (`agents/application_agent.py`), `BrowserAgent` (`agents/browser_agent.py`), `DesktopAgent` (`agents/desktop_agent.py`), `InputControlAgent` (`agents/input_control.py`), `WebSearchAgent` (`agents/websearch.py`), `NovaVoiceOperator` (`agents/nova_voice_operator.py`).
  - **Database Registry (`agent_registry` table)**: 28 agents registered across 6 operational tiers.
- **Orchestrator Integration**:
  - `core/orchestrator.py` provides the central execution loop, DAG task scheduler, and permission firewall.
  - `src/core/main_agent.py` provides user-facing conversational intent understanding and delegation.
  - The new **Computer-Use Orchestrator** plugs directly into `core/orchestrator.py` as the specialized subsystem that manages Observe→Think→Act→Verify (OTAV) execution loops.
- **Agent Roster Reconciliation**:
  - The 17-agent roster defined in `AGENTS.md` (Main Agent, Planner, Computer-Use Orchestrator, Vision Agent, OCR Agent, UIA/Windows Agent, Browser Agent, File Agent, Form Agent, Shopping Agent, System Agent, Application Agent, Research Agent, Coding Agent, Communication Agent, Verification Agent, Recovery Agent, Security Agent) cleanly maps onto the existing specialized agent classes while enforcing the 3-tier Tony AI autonomy model (JARVIS / FRIDAY / Ultron-lockout).

---

## 2. Current Tools

- **Tool Definitions**:
  - `tools/interfaces.py` defines `Tool`, `ToolExecutionResult`, `ToolContext`.
  - `core/computer_control/tool_registry.py` defines registered tools and contracts.
  - `tools/backends/` contains `browser_tool.py`, `computer_control.py`, `filesystem_local.py`, `terminal_subprocess.py`, `windows_terminal.py`.
- **Contract Compatibility**:
  - Existing tool outputs return structured execution result objects with `success`, `output`, `error`, and `metadata`.
  - The `ToolResult` contract in `TRD.md` §3.2 extends this with explicit `verification`, `risk_tier`, `confidence`, `before_state_ref`, and `after_state_ref` fields.
  - Tool adapters in `tools/backends/` wrap and emit the standard `ToolResult` shape without breaking existing consumers.

---

## 3. Backend & API

- **Task Queue**:
  - In-process priority queue with thread-safe locking and cancellation in `tasks/task_system.py`, `src/core/task_queue.py`, and `core/event_bus.py`.
  - Async execution loop in `core/execution_loop.py` and `core/task_state.py`.
- **Server Topology**:
  - FastAPI server in `server/app.py` and `src/api/server.py`.
  - Cross-platform architecture: Core engine runs cross-platform (Linux/macOS/Windows) with platform detection in `core/platform/detector.py`.
- **API Surface**:
  - Existing routes: `/health`, `/task`, `/status`, `/chat`.
  - `API_CONTRACT.md` routes (`/v1/tasks`, `/v1/tasks/{id}`, `/v1/tasks/{id}/control`, `/v1/tasks/{id}/confirm`, `/v1/tasks/{id}/observability`, `/v1/health`) extend the existing FastAPI application with standard REST endpoints.

---

## 4. Frontend & Observability Dashboard

- **Surfaces**:
  - `ui/live_desktop/` (`index.html`, `viewer.js`, `style.css`) — live desktop visual stream and element inspector.
  - `jarvis_hud_live.html` — real-time HUD showing agent status, CPU/memory telemetry, and live activity.
  - `gui/app.py` — native desktop GUI interface.
- **Integration**:
  - Computer-Use observability (`ARCHITECTURE.md` §8) feeds `/v1/tasks/{id}/observability` directly to both `ui/live_desktop/` and `jarvis_hud_live.html`.

---

## 5. Database & Audit Trail

- **SQLite WAL Mode**:
  - Configured with `PRAGMA journal_mode = WAL;` and foreign keys enabled across `max_state.db`.
- **Table Structure**:
  - 24 active tables: `agent_registry`, `api_quota_usage`, `blockers`, `calendar_events`, `circuit_breaker_state`, `dead_letter_queue`, `decisions_log`, `memory_access_log`, `memory_behavioral`, `memory_conversational`, `memory_identity`, `memory_preferences`, `memory_project`, `outcome_tracker`, `owner_habits`, `owner_profile`, `owner_project_memory`, `phases`, `reminders`, `self_evolution_metrics`, `sessions`, `sqlite_sequence`, `steps`, `task_trace`.
- **Audit Extension**:
  - `task_trace` and `audit_events` store execution timelines.
  - The new fields (`risk_tier`, `confidence`, `recovery_attempts`, `before_state_ref`, `after_state_ref`) are supported directly via migration or JSON payload storage, ensuring 100% backward compatibility.

---

## 6. Existing Computer-Control Code

- **Existing Implementations**:
  - `core/computer_control/` (`environment.py`, `permission_firewall.py`, `screen_diff.py`, `tool_registry.py`, `turbo_executor.py`, `vision_fallback.py`, `windows_input.py`, `checkpoint_manager.py`).
  - `core/controllers/` (`keyboard_controller.py`, `mouse_controller.py`).
  - `core/win32_interactive_session.py` (Win32 SendInput, mouse_event, keybd_event, desktop attachment).
  - `src/system/adapters/windows.py` and `src/system/adapters/linux.py`.
- **Alignment**:
  - Primitives in `TRD.md` §3.1 directly utilize the existing controllers and drivers, adding strict `Element`-derived target resolution and pre-action focus verification.

---

## 7. Voice System

- **Voice Pipeline**:
  - Audio capture and VAD in `voice/audio_capture.py` and `voice/vad.py`.
  - Wakeword engine in `voice/wakeword.py` and STT in `voice/stt.py`.
  - TTS in `voice/tts.py`, `core/voice_output.py`, and `core/single_tts_queue.py`.
  - ElevenLabs integration in `src/infra/elevenlabs_voice.py`.
  - Confirmation mode in `voice/confirmation_mode.py` and intent bridge in `voice/intent_bridge.py`.
- **Handoff**:
  - The Main Agent ↔ Computer-Use handoff seamlessly supports both turn-based voice commands and real-time streaming audio feedback.

---

## 8. Task Queue & State Schema

- **Schema Mapping**:
  - Existing `TaskState` in `core/task_state.py` and `Task` in `tasks/task_system.py` support task lifecycle, status flags, and step tracking.
  - The unified `Task` schema in `TRD.md` §6 directly aligns with the existing task lifecycle: `QUEUED`, `PLANNING`, `RUNNING`, `WAITING_FOR_USER`, `BLOCKED`, `FAILED`, `VERIFYING`, `COMPLETED`, `CANCELLED`.

---

## 9. Existing APIs & Collisions

- **Audit Findings**:
  - Existing endpoints: `/health`, `/task`, `/status`, `/chat`.
  - No route collisions exist with `/v1/tasks`, `/v1/tasks/{id}/control`, `/v1/tasks/{id}/confirm`, `/v1/tasks/{id}/observability`.

---

## 10. Existing Tests & Verification

- **Test Suite Status**:
  - `pytest`: **7 passed** in `test_files_foundation_integration.py`.
  - `smoke_test.py`: **PASS** (exit code 0).
  - `audit_all_phases.py`: **PASS** (database integrity verified).
  - `demo_jarvis_supreme_live.py`: **PASS** (ambient presence & 5-layer memory nominal).

---

## 11. Platform Reality Check

- **Platform Finding**:
  - MAX is designed as a hybrid platform architecture:
    - Orchestrator, planning, 5-layer memory, and API server run cross-platform (Linux / Windows / macOS).
    - Native desktop automation drivers exist for Windows (UIA, Win32) and Linux (X11 / Wayland / AT-SPI).
  - The Computer-Use Upgrade can run either directly co-located on a Windows host or as a dedicated Windows execution node connected over loopback/LAN API to the MAX orchestrator.
  - `ADR-001` in `DECISIONS.md` is confirmed and refined to reflect this hybrid deployment architecture.
