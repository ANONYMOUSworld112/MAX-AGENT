# MAX-AGENT: Master Architectural Conflict Log

> **Document Version**: 1.0.0  
> **Status**: PENDING OWNER REVIEW (Phase 0 Gate Deliverable)  
> **Authority**: Governed by Section 0.2 of Master Engineering Specification v2  

---

## 1. Authority Hierarchy
Per Section 0.1 of Master Spec v2, conflicts are resolved in the following priority order:
1. **Safety and security** (Sections 1-S, 5, 13)
2. **Honesty and correctness** (Sections 1-H, 14, 26)
3. **Preservation of working behavior** (Section 1-P)
4. **Feature requirements** (Sections 16-22)
5. **Naming and style**

---

## 2. Catalog of Identified Conflicts

### Conflict CF-01: Ghost Tests vs Empty Test Suite
- **What**: Automated test suite existence and verification status.
- **Where**: `IMPLEMENTATION_PLAN.md` (Lines 75–115) vs Actual Repository File System.
- **Position 1 (IMPLEMENTATION_PLAN.md)**: Claims "All Tests Passing: 74/74 across 15 phases in ~8s", citing `tests/integration/test_dual_lane.py`, `tests/e2e/*.py`, etc.
- **Position 2 (Actual Codebase)**: Prior to Phase 0, the `tests/` directory did not exist in the repository at all. Zero automated tests were committed.
- **Classification**: Honesty & Correctness (Rule 1-H1, 1-H2, 1-H3).
- **Proposed Resolution**: Record that the claim in `IMPLEMENTATION_PLAN.md` was synthetic/copied from an external project (`Mark-LIII`). Establish real Tier 0 characterization tests (completed in `tests/tier0_characterization/` with 21 passing tests and evidence saved in `docs/evidence/p0/tier0_test_run.txt`).

---

### Conflict CF-02: Task Lifecycle State Machine Definitions
- **What**: Task states and transition invariants.
- **Where**: `core/max_infra/task_lifecycle.py` vs Master Spec v2 Section 8.
- **Position 1 (core/max_infra/task_lifecycle.py)**: Defines 9 states: `CREATED`, `QUEUED`, `LOCK_WAIT`, `RUNNING`, `RECONCILING`, `DONE`, `FAILED`, `CANCELLED`, `ROLLED_BACK`.
- **Position 2 (Master Spec v2 Section 8)**: Defines 14 states: `CREATED`, `PLANNED`, `QUEUED`, `BLOCKED`, `RUNNING`, `VERIFYING`, `RETRYING`, `PAUSED`, `CANCELLING`, `INTERRUPTED`, `COMPLETED`, `FAILED`, `CANCELLED`, `EXPIRED`. Mandatory `blocked_reason` (DEPENDENCY, RESOURCE, SCHEDULE, USER_INPUT, CONFIRMATION) and terminal states `COMPLETED`, `FAILED`, `CANCELLED`, `EXPIRED`.
- **Classification**: Structural Conflict (changes component boundaries and data contracts).
- **Proposed Resolution**: Adopt Master Spec v2 Section 8 state machine in Phase 1. The Spec's 14 states represent a true production lifecycle supporting dependency blocking, schedule delays, pause/resume, and crash recovery. Migrate `core/max_infra/task_lifecycle.py` cleanly behind a feature flag.

---

### Conflict CF-03: Dual-Lane Routing Architecture vs Gemini Live WebSocket Bypass
- **What**: Request ingestion, reflex triage, and dispatch mechanism.
- **Where**: `IMPLEMENTATION_PLAN.md` (Section 1 & 3) vs `main.py` (`_listen_audio`, `_execute_tool`).
- **Position 1 (IMPLEMENTATION_PLAN.md)**: All user input immediately enters `ReflexIntentRouter` (<33ms) and branches into Lane A (sync read) or Lane B (TaskQueue).
- **Position 2 (main.py)**: All user audio streams directly to Gemini Live over a cloud WebSocket (`models/gemini-3.1-flash-live-preview`). Gemini decides the tool to invoke. `ReflexIntentRouter` is only called as a fourth fallback in `_execute_tool` when Gemini returns an unrecognized tool name.
- **Classification**: Structural Conflict (orchestration control plane boundary).
- **Proposed Resolution**: In Phase 2, implement the formal `InputGateway` and `IntentEngine`. For fast voice commands, maintain low latency via the fast path (single schema-constrained call or Gemini Live), but route all execution requests through the deterministic `PlanValidator`, `TaskGraph`, `Scheduler`, and `ExecutionGateway`.

---

### Conflict CF-04: Mock Agent Implementations vs Real Swarm
- **What**: Implementation status of the 33 registered agents.
- **Where**: `agents/*/*.py` vs Rule 1-H1 (No fake implementations).
- **Position 1 (IMPLEMENTATION_PLAN.md)**: Declares all 33 agents implemented, tested, and passing across 5 clusters.
- **Position 2 (Actual Codebase)**: Forensics reveal agents (e.g., `CodingAgent`, `CalendarAgent`, `ComputerUseAgent`, `EmailAgent`) return synthetic `success=True` with hardcoded strings and zero actual side effects or tool calls.
- **Classification**: Honesty & Correctness (Rule 1-H1).
- **Proposed Resolution**: Per Rule 1-H1, stubs must raise `NotImplementedError` or return `UNSUPPORTED`, never return fake `success=True`. In Phase 0/1, tag all stub agents as `[NOT IMPLEMENTED]` in the component map. In subsequent domain phases (P4 desktop, P5 app launch, P6 media, P7 calendar/reminder, P9 OpenCode), replace stubs with real capability handlers.

---

### Conflict CF-05: Direct Execution vs ExecutionGateway Choke Point
- **What**: Execution of side effects (subprocesses, file writes, input injection, registry access).
- **Where**: `actions/*.py` vs Master Spec v2 Section 1-S2 & Section 13.
- **Position 1 (Current actions/*.py)**: Actions directly invoke `subprocess.run`, `subprocess.Popen(shell=True)`, `pyautogui`, `ctypes.windll`, `send2trash`, and `exec()` without passing through any security gate or risk check.
- **Position 2 (Master Spec v2 Section 13)**: Single choke point: Every side effect must pass through `ExecutionGateway.execute(ActionRequest)`. No agent, worker, or plugin performs side effects directly. Automated AST tests ban OS-level imports outside adapters.
- **Classification**: Safety and Security (Top Priority, Authority Order 1).
- **Proposed Resolution**: In Phase 1, build `ExecutionGateway` and `PolicyEngine`. Migrate existing actions through the gateway using the strangler-fig pattern, moving low-level OS calls into platform adapters (`core/platform/windows/`, etc.).

---

### Conflict CF-06: Arbitrary Code Execution in Desktop Action
- **What**: Desktop automation logic in `actions/desktop.py`.
- **Where**: `actions/desktop.py:97` (`_execute_generated_code`) vs Rule 1-S1 & Section 16.
- **Position 1 (actions/desktop.py)**: Prompts Gemini to generate Python code based on user prompt, then compiles and executes it via `exec(compile(code, "<max_desktop>", "exec"), sandbox)`.
- **Position 2 (Master Spec v2 Rule 1-S1 & Section 16)**: "The LLM proposes; deterministic MAX code decides and executes." The interaction hierarchy requires direct APIs, accessibility/UIA semantic targeting, and grounded actions—never arbitrary runtime `exec()` of LLM-generated code.
- **Classification**: Safety and Security (Top Priority, Authority Order 1).
- **Proposed Resolution**: Flag `actions/desktop.py:exec()` as a critical vulnerability. In Phase 4 (Platform Adapters) and Phase 16 (Desktop Interaction), replace `exec()` with deterministic UIA/accessibility and input injection adapters managed by the Desktop Actor.

---

### Conflict CF-07: Dashboard Network Binding and Firewall Configuration
- **What**: HTTP / WebSocket network interface binding and firewall behavior.
- **Where**: `dashboard/server.py` vs Master Spec v2 Section 5.
- **Position 1 (dashboard/server.py)**: Binds to `0.0.0.0` (all network interfaces, including public/LAN) and executes scripts to punch holes through the Windows Firewall for remote LAN access.
- **Position 2 (Master Spec v2 Section 5)**: "Dashboard/API: bind to 127.0.0.1 only; per-install random token; validate Origin and Host; no state changes on GET; WebSocket authenticated; rate limited."
- **Classification**: Safety and Security (Top Priority, Authority Order 1).
- **Proposed Resolution**: In Phase 11, reconfigure dashboard server to bind strictly to `127.0.0.1`. Disable firewall hole-punching by default. Enforce token validation and `Origin`/`Host` header validation on all endpoints.

---

### Conflict CF-08: Reminder Scheduling via schtasks.exe vs Daemon Scheduler
- **What**: Reminder persistence and scheduling architecture.
- **Where**: `actions/reminder.py` vs Master Spec v2 Section 11 & Section 19.
- **Position 1 (actions/reminder.py)**: Writes standalone Python scripts into `~/.MAX/reminders/{task_name}.py` and invokes Windows `schtasks.exe` via subprocess.
- **Position 2 (Master Spec v2 Section 11 & 19)**: One unified scheduler running in the MAX daemon, backed by transactional SQLite WAL store, with injectable `Clock`, RFC 5545 RRULE recurrence, DST fold/gap handling, and misfire policies.
- **Classification**: Structural Conflict.
- **Proposed Resolution**: In Phase 7 (Time, Reminders, Calendar), implement the daemon-hosted scheduler backed by `StateDB`. Retain `schtasks.exe` only as an optional OS wake-up hook if MAX daemon is configured to start on boot.

---

### Conflict CF-09: Watchdog Implementation (Thread vs Separate Process)
- **What**: Watchdog architecture and emergency stop reliability.
- **Where**: `core/max_infra/watchdog.py` vs Master Spec v2 Section 6.1 & Section 13.
- **Position 1 (core/max_infra/watchdog.py)**: Runs as an in-process daemon `threading.Thread` in Python.
- **Position 2 (Master Spec v2 Section 13)**: The Watchdog must be a separate watchdog process (not the orchestrator loop) handling global hotkeys and monitoring orchestrator heartbeats so emergency stop functions even when the orchestrator is hung or blocked.
- **Classification**: Safety and Security (Authority Order 1).
- **Proposed Resolution**: In Phase 3, build an independent Watchdog process that registers the owner-selected global emergency stop hotkey and monitors orchestrator heartbeats via shared memory or local IPC.

---

## 3. Summary of Escalations for Human Owner Approval

| Conflict ID | Summary | Proposed Action | Owner Approval Status |
|---|---|---|---|
| **CF-01** | Replace false 74/74 test claims with real Tier 0 characterization tests | Approve real tests and baseline evidence | **AWAITING APPROVAL** |
| **CF-02** | Upgrade 9-state machine to 14-state machine per Spec Section 8 | Adopt 14-state machine in Phase 1 | **AWAITING APPROVAL** |
| **CF-03** | Reconcile Gemini Live fast-path with deterministic PlanValidator/Gateway | Implement dual-mode gateway | **AWAITING APPROVAL** |
| **CF-04** | Formalize stub agents as [NOT IMPLEMENTED] until real implementations exist | Enforce Rule 1-H1 honesty rule | **AWAITING APPROVAL** |
| **CF-05** | Route all unchoked side-effects in `actions/` through `ExecutionGateway` | Enforce single choke point | **AWAITING APPROVAL** |
| **CF-06** | Remove `exec()` in `actions/desktop.py` and replace with deterministic UIA | Eliminate LLM arbitrary code exec | **AWAITING APPROVAL** |
| **CF-07** | Restrict dashboard binding from `0.0.0.0` to `127.0.0.1` only | Harden dashboard network boundary | **AWAITING APPROVAL** |
| **CF-08** | Migrate `actions/reminder.py` from `schtasks.exe` to SQLite daemon scheduler | Adopt StateDB persistent scheduler | **AWAITING APPROVAL** |
| **CF-09** | Upgrade Watchdog from in-process thread to separate watchdog process | Build dedicated watchdog process | **AWAITING APPROVAL** |
