# MAX-AGENT — Task Lifecycle & State Machine Forensics

> **Forensic Audit Date**: 2026-09-30  
> **Source Commit**: `877b913` (branch: `max/p0-baseline`)  
> **Auditor**: Principal AI Systems Architect & Codebase Forensic Engineer  
> **Status**: COMPLETED & VERIFIED AGAINST SOURCE CODE  

---

## 1. Documented vs Real Task Lifecycle

### Documented Architecture (Inactive Kernel)
In `core/max_infra/task_lifecycle.py`, MAX defines a 10-state transactional finite state machine:
```
CREATED ──► QUEUED ──► LOCK_WAIT ──► RUNNING ──► RECONCILING ──► DONE
  │            │           │            │              │
  ▼            ▼           ▼            ▼              ▼
CANCELLED   CANCELLED    FAILED       FAILED         FAILED ──► ROLLED_BACK
```
Features defined in `TaskLifecycleFSM`:
- State transition validation (`_ALLOWED_TRANSITIONS`).
- Transactional recording in `StateDB` SQLite database.
- Transition timing and latency tracking.

### Actual Executed Reality (`main.py`)
In the active production runtime, **the TaskLifecycleFSM is completely bypassed.**
The actual lifecycle of a user request is completely ephemeral and stateless:

```
Gemini emits response.tool_call
 ↓
fc = response.tool_call.function_calls[0]
 ↓
Transient ID created on the fly: task_id = f"task_{int(time.time())}"
 ↓
AgentInput instantiated in RAM (main.py:935)
 ↓
agent.run(agent_input) runs synchronously in executor thread
 ↓
AgentOutput returned
 ↓
types.FunctionResponse sent back over WebSocket
 ↓
Task state garbage-collected. No record in any database.
```

---

## 2. Comparison of Lifecycle Properties

| Lifecycle Property | Documented Specification | Actual Production Runtime | Evaluation / Impact |
|---|---|---|---|
| **State Tracking** | Explicit FSM states (`CREATED`, `RUNNING`, etc.) | None. Stateless execution within a single coroutine. | **HIGH RISK**: Cannot inspect running tasks, pause, or resume. |
| **Persistence** | SQLite WAL database (`StateDB: tasks` table) | RAM only. No persistence. | **CRITICAL**: If MAX crashes or is closed, all task history is lost. |
| **Restart Recovery** | Startup recovery reconciling orphaned tasks | None. No startup recovery exists. | **CRITICAL**: Stale child processes or orphaned locks are never reaped. |
| **Cancellation** | Cooperative cancellation via token | None. Hard process interrupt only. | **HIGH RISK**: Mid-flight file writes or subprocesses cannot be cancelled cleanly. |
| **Retry Semantics** | Bounded exponential backoff with circuit breaker | None. No retries in `main.py`. Fails on first exception. | **FRAGILE**: Transient errors immediately crash the user turn. |
| **Decomposition** | Multi-task DAG with dependency edges | Atomic single-step function calls only. | **MISSING**: Complex requests ("Build X and test it") cannot be decomposed. |

---

## 3. Task Decomposition Forensics

### The Question
Can MAX turn *"Build an application, run tests, and open it in VS Code"* into independent, dependency-ordered tasks?

### Source Code Findings
1. In `agents/core/planner.py`, `DecompositionPlanner._execute()` contains a static template returning a 4-step dictionary:
   ```python
   subtasks = [
       {"id": "step_1_spec", "agent": "SpecAuthor", "desc": f"Write spec for {desc}"},
       {"id": "step_2_dev", "agent": "PolyglotDeveloper", "desc": f"Implement changes for {desc}"},
       {"id": "step_3_review", "agent": "CodeReviewer", "desc": "Audit code quality and security"},
       {"id": "step_4_test", "agent": "QATestEngineer", "desc": "Execute test suite"},
   ]
   ```
2. In `main.py`, nothing ever calls `DecompositionPlanner` during normal user requests.
3. If Gemini Live receives a complex prompt, it either attempts to call a single tool (e.g. `dev_agent`) or calls multiple tools sequentially in an arbitrary single turn without dependency checks.
4. If one tool in a multi-tool sequence fails, MAX does not abort dependent tools, perform rollbacks, or report a structured partial completion report.

---

## 4. Required Evolution (Master Spec Sections 7, 8, 9)

1. **Adopt Master Spec 14-State Machine**:
   `CREATED`, `PLANNED`, `QUEUED`, `BLOCKED(blocked_reason)`, `RUNNING`, `VERIFYING`, `RETRYING`, `PAUSED`, `CANCELLING`, `INTERRUPTED`, `COMPLETED`, `FAILED`, `CANCELLED`, `EXPIRED`.
2. **Canonical Data Contracts**: Formally implement `TaskIntent` and `Task` with persistent schemas.
3. **TaskGraph Engine**: Support `ACTION`, `CONDITION`, `CONFIRMATION_GATE`, and `SUBGRAPH` nodes with `on_success`, `on_failure`, and `always` edges.
4. **Crash Recovery Procedure**: On daemon startup, query `StateDB` for non-terminal tasks, mark them `INTERRUPTED`, reap orphan PIDs, and resolve based on capability idempotency class.
