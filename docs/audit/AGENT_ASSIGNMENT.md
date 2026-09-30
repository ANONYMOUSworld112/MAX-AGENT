# MAX-AGENT — Agent Assignment & Routing Forensics

> **Forensic Audit Date**: 2026-09-30  
> **Source Commit**: `877b913` (branch: `max/p0-baseline`)  
> **Auditor**: Principal AI Systems Architect & Codebase Forensic Engineer  
> **Status**: COMPLETED & VERIFIED AGAINST SOURCE CODE  

---

## 1. Executive Summary: What Decides Agent Assignment?

In the current implementation, agent assignment is **HYBRID (PRIMARY: LLM-BASED; FALLBACK: KEYWORD-BASED)**.

1. **Primary Selection Path (99% of requests)**:
   - **Google Gemini 3.1 Flash Live** model decides the tool call directly from its cloud server.
   - All 33 agent schemas are serialized into `tools=[{"function_declarations": [...]}]` during WebSocket handshake (`main.py:770`).
   - If the cloud LLM predicts `fc.name = "codingagent"`, MAX executes `CodingAgent`.
   - MAX has **no local deterministic validation** of whether `CodingAgent` was the appropriate choice.
   - There is **no recorded selection rationale**, no ranking of alternative candidate agents, and no capability matching.

2. **Fallback Selection Path (Only if Gemini emits an unknown tool name)**:
   - In `main.py:953`, if `fc.name` is not found in `_action_registry`, `_agent_registry`, or `_plugin_registry`, control drops into `self._intent_router.route(name, args)`.
   - `core/reflex/intent_router.py:route_input()` applies a hardcoded keyword check:
     - "code", "refactor", "function", "fix bug", "pytest", "python" ──► `PolyglotDeveloper` (alias for `CodingAgent`)
     - "schedule", "meeting", "calendar", "event" ──► `CalendarAgent`
     - "email", "inbox", "mail" ──► `InboxAgent` (alias for `EmailAgent`)
     - "cpu", "ram", "memory", "battery", "gpu", "telemetry" ──► `SystemMonitor` (alias for `SystemMonitorAgent`)
     - "architect", "system design", "adr", "schema" ──► `SystemArchitect` (alias for `APIDesigner`)
     - "kill", "abort", "emergency stop" ──► `EmergencyInterrupter` (alias for `SecurityGate`)
     - Else ──► `MasterOrchestrator`

---

## 2. Representative Task Routing Evaluation

| User Request | Required Capabilities | Available Registered Candidates | Selected Agent / Tool | Actual Selection Mechanism | Selection Reason Recorded? | Resource Check | Safety Gate Check | Final Execution Outcome |
|---|---|---|---|---|---|---|---|---|
| *"Open VS Code."* | `launch_application`, `verify_window` | `open_app`, `DesktopAgent`, `ComputerUseAgent` | `actions/open_app.py` | LLM selected `open_app` action tool | **NO** (Zero trace) | **NONE** | **NONE** | Blind keystroke simulation (`pyautogui.press("win")`). Returns "Opened VS Code". |
| *"Play Believer."* | `search_media`, `play_media`, `verify_audio` | `youtube_video`, `open_app`, `DesktopAgent` | `actions/youtube_video.py` | LLM selected `youtube_video` action tool | **NO** | **NONE** | **NONE** | Scrapes YouTube HTML, launches browser URL via `cmd /c start`. |
| *"Remind me in 10 minutes."* | `parse_temporal`, `schedule_task`, `persist_event` | `reminder`, `CalendarAgent` | `actions/reminder.py` | LLM selected `reminder` action tool | **NO** | **NONE** | **NONE** | Spawns Windows Scheduled Task via `schtasks.exe`. |
| *"Schedule a meeting tomorrow at 4."* | `calendar_availability`, `create_calendar_event` | `CalendarAgent` | `agents/productivity/calendar_agent.py` | LLM selected `calendaragent` tool | **NO** | **NONE** | **NONE** | Stub returns mock event for `2026-10-01T10:00:00`. Fails silently. |
| *"Build a Python calculator."* | `write_code`, `run_tests`, `verify_artifacts` | `dev_agent`, `CodingAgent` | `actions/dev_agent.py` or `CodingAgent` | Non-deterministic (depends on LLM prompt temperature) | **NO** | **NONE** | **NONE** | If `dev_agent`: Gemini Flash prompt loop + unsandboxed host `pip install`. If `CodingAgent`: Returns mock string. |
| *"Delete old backup files."* | `file_delete`, `permission_gate` | `file_controller`, `FileOrganizer` | `actions/file_controller.py` | LLM selected `file_controller` | **NO** | **NONE** | **NONE** | Deletes files directly via `os.remove` without confirmation gate. |

---

## 3. Failure Mode & Edge Case Analysis

### 1. Can two different agents accidentally receive the same task?
**NO.** The dispatch in `main.py:_execute_tool()` iterates through `response.tool_call.function_calls` sequentially and executes each tool call independently. However, Gemini can emit multiple function calls in one turn (e.g. `[open_app, dev_agent]`), which will run sequentially without dependency synchronization.

### 2. Can no agent receive a task?
**YES.** If Gemini hallucinates a tool name not recognized by any registry and the `ReflexIntentRouter` classifies the intent as `LANE_A` (read-only direct answer), the dispatcher returns `f"Unknown tool: {name}"` and no agent is assigned.

### 3. Can an unsuitable agent receive a task?
**YES.** Because tool selection is left entirely to cloud LLM generation across 60+ tool declarations (7 inline + 19 actions + 33 agents + plugins), model confusion is frequent. For example, asking to "check calendar" can trigger `CalendarAgent` (mock stub) instead of a real action, or "organize files" can trigger `FileOrganizer` (mock stub) instead of `file_controller`.

### 4. Can the LLM bypass the router?
**YES.** The LLM *always* bypasses the router in the current architecture. The router does not govern the LLM; the LLM directly calls tools.

### 5. Can a worker call another worker directly?
**NO.** No agent holds a reference to another agent or has the capability to dispatch to other workers.

### 6. Can agents create uncontrolled recursive delegation?
**NO.** Because no agent can invoke another agent, recursion is physically impossible in the current codebase.

---

## 4. Required Evolution (Master Spec Section 10)

To achieve deterministic, auditable, and reliable agent routing:
1. **Remove all 33 mock agents from Gemini's flat tool declarations**.
2. Expose only a single, schema-constrained intent/plan proposal contract to the LLM.
3. Pass the proposed capability to a **Deterministic Capability Router**:
   - Filter agents by declared capability schema.
   - Filter by platform availability, user permissions, and circuit breaker status.
   - Rank by configured priority, current load, and stable tie-breaking.
   - Write a `RoutingDecision` record storing: chosen agent, rejected candidates with specific rejection reasons, and input parameters used.
