# MAX-AGENT — Target Future Architecture: MAX vNext

> **Forensic Audit Date**: 2026-09-30  
> **Source Commit**: `877b913` (branch: `max/p0-baseline`)  
> **Auditor**: Principal AI Systems Architect & Codebase Forensic Engineer  
> **Status**: COMPLETED & VERIFIED AGAINST SOURCE CODE  

---

## 1. Architectural Philosophy: The Five Evolution Pillars

MAX vNext shifts MAX from an unconstrained prompt-to-tool client to a **governed personal AI operating system**.  
The architecture is anchored on five non-negotiable engineering pillars:

1. **Determinism over Hallucination**: The LLM proposes actions and plans; deterministic, machine-checked MAX code validates, authorizes, and executes them.
2. **Single Choke Point Execution**: 100% of physical and operating system side effects pass through `ExecutionGateway.execute(ActionRequest)`. No worker or tool executes raw side effects directly.
3. **Verification-Driven Completion**: A task is never marked complete because an LLM or worker claims it is done. It is complete only when deterministic system evidence (L2/L3) satisfies the declared postconditions.
4. **Focused Workers over Chaotic Swarms**: Replace the 33 uncoordinated mock stubs with dedicated, single-responsibility workers (`ComputerWorker`, `CodingWorker`, `ProductivityWorker`) operating under strict resource and scope constraints.
5. **Durable, Auditable State**: All intents, task graphs, state transitions, resource leases, and side-effect hashes are transactionally persisted in an append-only, cryptographic audit log backed by SQLite WAL.

---

## 2. Target Conceptual Architecture Diagram

```
                                  USER
                        (Voice / Text / Web HUD)
                                    │
                                    ▼
                         [ INPUT LAYER / GATEWAY ]
                 (Normalize, Audio Pre-filter, Attach Origin)
                                    │
                                    ▼
                             [ INTENT ENGINE ]
               (Fast-Path Single Action vs Full Planning Path)
                                    │
                                    ▼
                            [ CONTEXT ENGINE ]
             (Scoped Task Spec + Relevant Memory + Token Budget)
                                    │
                                    ▼
                             [ TASK PLANNER ]
             (Schema-Constrained Decomposer with PlanValidator)
                                    │
                                    ▼
                           [ TASK GRAPH ENGINE ]
               (DAG of Subtasks: Edges, Conditions, Replans)
                                    │
                                    ▼
                            [ AGENT ROUTER ]
          (Deterministic Capability Match + Circuit Breaker Filter)
                                    │
                                    ▼
                       [ POLICY & SECURITY GATEWAY ]
          (Risk Tiering, Workspace Boundaries, Confirmation Gate)
                                    │
                                    ▼
                          [ RESOURCE MANAGER ]
          (Dijkstra Sorted Leases: desktop-input, project, vram)
                                    │
                                    ▼
                        [ EXECUTION CONTROLLER ]
                                    │
         ┌──────────────────────────┼──────────────────────────┐
         ▼                          ▼                          ▼
 [ COMPUTER WORKER ]        [ CODING WORKER ]        [ PRODUCTIVITY WORKER ]
 (WindowsDesktopAdapter,   (CodingExecutor:          (Calendar, Reminders,
  UIA Semantic Targeting,   OpenCode / Codex /        Local SQLite Provider,
  Process / Window Trees)   Claude / Local Sandbox)   RFC 5545 RRULE Engine)
         │                          │                          │
         └──────────────────────────┼──────────────────────────┘
                                    │
                                    ▼
                          [ OBSERVATION ENGINE ]
               (Process Query, Window State, UIA Tree, OCR)
                                    │
                                    ▼
                         [ VERIFICATION ENGINE ]
         (L3 Deterministic OS State / L2 App State / L1 Vision)
                                    │
                       ┌────────────┴────────────┐
                       ▼                         ▼
                  [ SUCCESS ]               [ FAILURE ]
                       │                         │
                       │                         ▼
                       │                 [ RECOVERY ENGINE ]
                       │              (Classify, Retry, Rollback)
                       │                         │
                       └────────────┬────────────┘
                                    │
                                    ▼
                          [ EVENT BUS & AUDIT ]
             (Append-Only Cryptographic Hash Chain in StateDB)
                                    │
                                    ▼
                         [ TRACE & MEMORY STORE ]
             (Provenance-Gated Updates to Long-Term Memory)
                                    │
                                    ▼
                           [ RESPONSE ENGINE ]
            (Truthful Natural Language Phrased from Verified State)
                                    │
                                    ▼
                                  USER
                       (Spoken TTS / Visual HUD)
```

---

## 3. Subsystem Breakdown & Design Contracts

### 1. Input Layer & Intent Engine
- Fast Path: 80% of voice commands ("Open Chrome", "Play Believer", "Remind me in 10 minutes") bypass the multi-step planner. A single schema-constrained model call maps utterance directly to a validated single-task intent.
- Full Path: Complex, multi-step requests ("Build an expense tracker and open it in VS Code") invoke the decomposer to produce a multi-node `TaskGraph`.

### 2. Execution Gateway & Policy Engine
- The sole choke point for all I/O.
- Enforces risk classification:
  - `LOW`: Read-only queries, telemetry, status inspection.
  - `MEDIUM`: Package installs, project modifications, git commits. Requires standard HUD confirmation.
  - `HIGH`: File deletion, process termination, system modifications. Requires explicit confirmation on a trusted channel.
  - `CRITICAL`: Irreversible OS modifications. Requires explicit typed confirmation phrase.

### 3. Execution Workers
- **ComputerWorker**: Replaces `actions/desktop.py` and `actions/open_app.py`. Built on top of `WindowsDesktopAdapter` utilizing the Windows UI Automation (UIA) tree. Zero `exec()` calls.
- **CodingWorker**: Implements `CodingExecutor`. Spawns workers (such as OpenCode or internal agents) strictly inside a dedicated git worktree with an isolated virtual environment. Enforces test integrity and scope checks before committing.
- **ProductivityWorker**: Replaces mock calendar and reminder stubs. Backed by `StateDB` SQLite storage with RFC 5545 recurrence rules and half-open conflict intervals `[start, end)`.

### 4. Verification Engine
- Evaluates declared postconditions before a task can transition to `COMPLETED`.
- Outcomes: `SUCCESS`, `FAILURE`, or `UNKNOWN`.
- An `UNKNOWN` outcome is **never treated as success**; it triggers re-observation or escalates to the user.
