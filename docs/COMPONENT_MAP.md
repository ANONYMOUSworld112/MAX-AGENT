# MAX-AGENT: Master Component Map (Section 6 Target Components)

> **Document Version**: 1.0.0  
> **Status**: VERIFIED against commit HEAD on branch `max/p0-baseline`  
> **Audience**: Master Implementation Agent & System Owner  
> **Authority**: Governed by Section 1-P3 & Section 6 of Master Engineering Specification v2  

---

## 1. Mapping Policy & Architectural Rules

Per **Rule 1-P3 (No duplicate subsystems)**:
Every target component from Section 6.1 of the Master Specification is cataloged below with its status:
- **`[EXISTING]`**: Reused and extended in-place.
- **`[REPLACE]`**: Replaced with written justification detailing why the existing asset is inadequate or broken.
- **`[NEW]`**: Built new, accompanied by proof that no existing component could be adapted.

---

## 2. Component Mapping Matrix

| # | Section 6 Target Component | Existing Codebase Asset | Status | Written Justification & Action Plan |
|---|---|---|---|---|
| 1 | **InputGateway** | `main.py` (_listen_audio, _on_text_command, _process_dashboard_commands) | **REPLACE** | **Justification**: Current input handling is fragmented across three separate loops in `main.py`, tightly coupled to Gemini Live WebSocket and PyQt6 UI. It lacks canonical timestamping, channel identification, provenance tracking, and trust level tagging. **Plan**: Unify under a single `InputGateway` producing validated `InputEnvelope` objects. |
| 2 | **IntentEngine** | `core/reflex/intent_router.py` (`ReflexIntentRouter`) | **EXISTING (EXTEND)** | **Justification**: `ReflexIntentRouter` and `LayaReflexEngine` already classify Lane A vs Lane B and target agent. **Plan**: Extend to support both fast-path schema decoding (single model call for simple voice) and full multi-step intent extraction. |
| 3 | **ContextManager** | `core/memory/context_heap.py` (`MemoryContextHeap`) & `core/memory/token_budget.py` | **EXISTING (EXTEND)** | **Justification**: 5-layer hierarchy and token budgeting exist in `core/memory/`. **Plan**: Wire into the live execution pipeline and integrate with the persistent store so context is loaded deterministically. |
| 4 | **MemoryManager** | `memory/memory_manager.py` (`load_memory`, `update_memory`, `search_memory`) | **EXISTING (EXTEND)** | **Justification**: Proven JSON storage and prompt formatting work reliably. **Plan**: Wrap in the unified data contract, enforce provenance validation (only TRUSTED-origin writes), and integrate SQLite backing from `StateDB`. |
| 5 | **TaskClassifier** | `core/reflex/triage.py` & `agents/router.py` | **EXISTING (EXTEND)** | **Justification**: Band-based triage and agent routing exist. **Plan**: Standardize category classification across the 17 request categories in Section 6.5. |
| 6 | **TaskPlanner** | `actions/dev_agent.py:_plan_project` & `agents/core/planner.py` | **REPLACE** | **Justification**: `dev_agent._plan_project` is an unconstrained prompt producing ad-hoc project plans, while `agents/core/planner.py` is a mock returning canned text. Neither validates schemas, enforces budgets, or outputs a DAG. **Plan**: Implement deterministic schema-constrained `TaskPlanner` supporting fast-path vs full-path. |
| 7 | **PlanValidator** | None (Previously missing) | **NEW** | **Proof**: No module in the existing repository validates task graphs, cycle prevention, parameter schemas, capability constraints, or untrusted context confirmation gates. |
| 8 | **TaskGraph** | None (Previously missing) | **NEW** | **Proof**: Current execution is strictly sequential or single-tool. No DAG data structure exists for conditional edges (`on_success`, `on_failure`, `always`), bounded expansion loops, or concurrent branch execution. |
| 9 | **CapabilityRegistry** | `core/action_loader.py` (`ActionRegistry`) | **EXISTING (EXTEND)** | **Justification**: `ActionRegistry` already discovers tool schemas dynamically from `actions/*.py`. **Plan**: Extend `ActionRecord` into full `CapabilityEntry` (with params schema, declared resources, idempotency class, postcondition template, base risk, verification method). |
| 10 | **AgentRegistry** | `agents/router.py` (`AgentRegistry`) | **EXISTING (EXTEND)** | **Justification**: Thread-safe singleton registering 33 agent classes with aliases. **Plan**: Retain the registry while replacing mock agent implementations with real domain handlers. |
| 11 | **AgentRouter** | `agents/router.py` & `agents/core/model_router.py` | **REPLACE** | **Justification**: The existing router performs trivial string matching without evaluating capability match, circuit breaker status, agent priority, platform constraints, or writing `RoutingDecision` audit records. **Plan**: Implement deterministic 5-step routing algorithm per Section 10. |
| 12 | **TaskScheduler** | `core/max_infra/task_queue.py` (`TaskQueue`) & `actions/reminder.py` | **REPLACE** | **Justification**: `TaskQueue` is purely in-memory and disconnected. `reminder.py` depends on Windows `schtasks.exe`. Neither supports transactional persistence, priority aging with deadline enforcement, restart recovery, or RFC 5545 RRULE recurring schedules. **Plan**: Build unified `TaskScheduler` backed by `StateDB` (SQLite WAL) with injectable `Clock`. |
| 13 | **ResourceManager** | `core/max_infra/lock_manager.py` (`LockManager`) | **EXISTING (EXTEND)** | **Justification**: `LockManager` already implements Dijkstra's sorted resource ordering and TTL expiration. **Plan**: Extend to support SHARED vs EXCLUSIVE resource leases, heartbeat management, and human user desktop competition guards (`UserActivityMonitor`). |
| 14 | **ExecutionGateway** | `core/confirm.py` & `agents/safety/security_gate.py` | **REPLACE** | **Justification**: Existing security checks are bypassed by all actions. `core/confirm.py` is only manually called by 2 actions and is not tied to actions' canonical hashes. `security_gate.py` is an uncalled agent stub. **Plan**: Build central `ExecutionGateway` single choke point enforcing policy, confirmation binding, risk computation, and sandboxing. |
| 15 | **ObservationEngine** | `core/perception/` (`screen_capture`, `accessibility`, `ui_detection`) | **EXISTING (EXTEND)** | **Justification**: Modules for screen capture (MSS), accessibility (UIA/pywinauto), and UI detection exist. **Plan**: Unify into an `ObservationEngine` producing valid observation handles with cache invalidation and password masking. |
| 16 | **VerificationEngine**| `core/verification/engine.py` (`VerificationEngine`) | **EXISTING (EXTEND)** | **Justification**: Outcome classification into `SUCCESS`, `FAILURE`, `UNKNOWN` is already implemented. **Plan**: Extend with verification levels L0–L3 (OS state, UIA tree, vision, none), wait-until polling, and evidence recording. |
| 17 | **RecoveryEngine** | `core/undo.py` (`undo_stack`), `core/max_infra/snapshot.py`, `core/max_infra/circuit_breaker.py` | **EXISTING (EXTEND)** | **Justification**: Snapshot creation, undo stack, and circuit breakers exist. **Plan**: Integrate into a comprehensive `RecoveryEngine` implementing the Section 15 decision table based on error class and capability idempotency class. |
| 18 | **EventBus + AuditLog**| `core/max_infra/schema.sql` (`audit_log` table) | **EXISTING (EXTEND)** | **Justification**: The SQLite schema already defines an `audit_log` table with `prev_hash` and `hash` fields for cryptographic chaining. **Plan**: Implement in-memory publish-subscribe `EventBus` with backpressure and append-only hash-chained storage in `StateDB`. |
| 19 | **ResponseEngine** | `main.py:speak` / `main.py:speak_error` | **REPLACE** | **Justification**: Current responses are free-form strings generated directly by Gemini or raw exceptions printed to stdout. **Plan**: Implement `ResponseEngine` receiving structured outcomes only, enforcing that success claims strictly match verification levels. |
| 20 | **Watchdog** | `core/max_infra/watchdog.py` | **REPLACE** | **Justification**: Existing `Watchdog` is an in-process thread inside the main Python interpreter. If the Python process or GIL freezes, the watchdog freezes with it. **Plan**: Migrate to an out-of-process Watchdog monitoring orchestrator heartbeats, global emergency hotkeys, and enforcing kill-switch trips. |

---

## 3. Subsystem Conflict & Resolution Summary

1. **State Machine Subsystem**:
   - `core/max_infra/task_lifecycle.py` uses 9 states (`CREATED`, `QUEUED`, `LOCK_WAIT`, `RUNNING`, `RECONCILING`, `DONE`, `FAILED`, `CANCELLED`, `ROLLED_BACK`).
   - Resolution: Replace with the 14-state machine defined in Section 8 (`CREATED`, `PLANNED`, `QUEUED`, `BLOCKED`, `RUNNING`, `VERIFYING`, `RETRYING`, `PAUSED`, `CANCELLING`, `INTERRUPTED`, `COMPLETED`, `FAILED`, `CANCELLED`, `EXPIRED`) with mandatory `blocked_reason`.
2. **Execution Subsystem**:
   - Built-in actions (`actions/*.py`) execute side effects directly.
   - Resolution: All actions migrate behind `ExecutionGateway.execute()`. No OS libraries imported outside adapters.
3. **Storage Subsystem**:
   - Split between `memory/long_term.json`, `~/.MAX/reminders`, and `core/max_infra/state_db.py`.
   - Resolution: Transactional SQLite database (`StateDB` in WAL mode) becomes the single source of truth for tasks, schedules, locks, audit log, and memory layers.
