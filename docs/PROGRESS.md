# MAX-AGENT: Master Engineering Progress Tracker

> **Current Phase**: Phase 0 — Repository Forensics & Baseline  
> **Active Branch**: `max/p0-baseline`  
> **Base Commit**: `bed949416abcf4fc2d92d2ff089b31438848648e`  
> **Last Updated**: 2026-09-30  

---

## 1. Phase Status Overview

| Phase | Description | Status | Evidence Path | Gate Status |
|---|---|---|---|---|
| **P0** | **Repository Forensics, Real Architecture Docs, Component Map, Conflict Log, Threat Model, Tier 0 Characterization Tests** | **IMPLEMENTED & TESTED** | `docs/evidence/p0/tier0_test_run.txt` | **AWAITING OWNER APPROVAL** (Component Map & Conflict Log) |
| **P1** | Foundations: Data Contracts, State Machine, Clock, Event Envelope, ExecutionGateway & Policy Engine | PLANNED | — | BLOCKED on P0 Gate Approval |
| **P2** | Planning Path: Schema-Validated Intent, Fast Path, Plan Validator, Task Graph, Capability Registry, Agent Router | PLANNED | — | BLOCKED on P1 Gate Approval |
| **P3** | Scheduler, Resource Leases, Worker Pool, Desktop Actor, Cancellation, Timeouts, Emergency Stop + Watchdog | PLANNED | — | BLOCKED on P2 Gate Approval |
| **P4** | Platform Adapters, FakeDesktop, Windows Adapter, Preconditions, Observation, User Activity Guard | PLANNED | — | BLOCKED on P3 Gate Approval |
| **P5** | ApplicationRegistry, Resolution Ladder, Windows Search Flow, Launch Verification | PLANNED | — | BLOCKED on P4 Gate Approval |
| **P6** | Media Workflow & Transport Verification | PLANNED | — | BLOCKED on P5 Gate Approval |
| **P7** | Time Handling, Reminders, Calendar (Persistence, RRULE, DST, Conflicts) | PLANNED | — | BLOCKED on P6 Gate Approval |
| **P8** | ProcessManager & Terminal Mirror | PLANNED | — | BLOCKED on P7 Gate Approval |
| **P9** | OpenCode Integration & Coding Workflow (Sandbox, Scope-Check, Test-Integrity) | PLANNED | — | BLOCKED on P8 Gate Approval |
| **P10** | Concurrency Validation & Background Multi-Tasking | PLANNED | — | BLOCKED on P9 Gate Approval |
| **P11** | HUD Observability & Dashboard API Authentication Hardening | PLANNED | — | BLOCKED on P10 Gate Approval |
| **P12** | Memory Integration, Hardening Pass, Final Acceptance Verification | PLANNED | — | BLOCKED on P11 Gate Approval |

---

## 2. Phase 0 Deliverables & Forensic Accomplishments

### Completed in Phase 0:
- [x] Full forensic inspection of `main.py`, `ui.py`, `agents/`, `core/`, `actions/`, `memory/`, `dashboard/`, `plugins/`, `config/`, `IMPLEMENTATION_PLAN.md`, `requirements.txt`, `setup.py`, `pyproject.toml`, and `readme.md`.
- [x] Uncovered the discrepancy between synthetic claims in `IMPLEMENTATION_PLAN.md` (which claimed 74 tests passing) and repository reality (zero test files existed).
- [x] Discovered direct unchoked side-effect execution across 16 modules, including `exec()` in `actions/desktop.py` and `0.0.0.0` binding in `dashboard/server.py`.
- [x] Authored `docs/ARCHITECTURE_REAL.md` capturing the real dual runtime vs inactive infrastructure.
- [x] Authored `docs/EXECUTION_FLOW.md` tracing 6 input channels across the 13 mandatory lifecycle stages.
- [x] Authored `docs/COMPONENT_MAP.md` mapping all 20 Section 6 target components to existing code ([EXISTING], [REPLACE], [NEW]).
- [x] Authored `docs/CONFLICT_LOG.md` recording 9 structural and architectural conflicts between existing plans/code and Master Spec v2.
- [x] Authored `docs/THREAT_MODEL.md` evaluating the 7 threat classes of Section 5 against the current codebase.
- [x] Authored `docs/UNCHOKED_SIDE_EFFECTS.md` cataloging 37 specific unchoked execution call sites as input to the Phase 1 `ExecutionGateway`.
- [x] Authored and ran Tier 0 Characterization Tests (`tests/tier0_characterization/` with 21 tests) covering action loader, confirm/undo, memory/config, max_infra (lock manager, task queue, state db, kill switch, circuit breaker, data boundary, verification engine), reflex engine, agent registry, app normalization, and dashboard crypto.
- [x] Verified 21/21 tests passing in 1.09s and saved test execution output to `docs/evidence/p0/tier0_test_run.txt`.
- [x] Ensured zero production code changes were made during Phase 0 (pure forensic baseline).

---

## 3. Evidence Paths

- **Tier 0 Test Run Evidence**: [`docs/evidence/p0/tier0_test_run.txt`](file:///f:/MAX-AGENT/docs/evidence/p0/tier0_test_run.txt)
- **Real Architecture**: [`docs/ARCHITECTURE_REAL.md`](file:///f:/MAX-AGENT/docs/ARCHITECTURE_REAL.md)
- **Execution Flow**: [`docs/EXECUTION_FLOW.md`](file:///f:/MAX-AGENT/docs/EXECUTION_FLOW.md)
- **Component Map**: [`docs/COMPONENT_MAP.md`](file:///f:/MAX-AGENT/docs/COMPONENT_MAP.md)
- **Conflict Log**: [`docs/CONFLICT_LOG.md`](file:///f:/MAX-AGENT/docs/CONFLICT_LOG.md)
- **Threat Model**: [`docs/THREAT_MODEL.md`](file:///f:/MAX-AGENT/docs/THREAT_MODEL.md)
- **Unchoked Side Effects**: [`docs/UNCHOKED_SIDE_EFFECTS.md`](file:///f:/MAX-AGENT/docs/UNCHOKED_SIDE_EFFECTS.md)

---

## 4. Open Conflicts Requiring Owner Decision / Approval at Gate 0

1. **Conflict CF-01**: Replace false 74/74 test claims from old plan with real Tier 0 characterization test baseline.
2. **Conflict CF-02**: Upgrade 9-state machine to 14-state machine per Master Spec Section 8 in Phase 1.
3. **Conflict CF-03**: Reconcile Gemini Live fast-path with deterministic PlanValidator / ExecutionGateway choke point.
4. **Conflict CF-04**: Tag mock agents as `[NOT IMPLEMENTED]` under Rule 1-H1 until real implementations are delivered.
5. **Conflict CF-05**: Route all 37 unchoked side-effect paths through `ExecutionGateway`.
6. **Conflict CF-06**: Eliminate `exec()` arbitrary code execution in `actions/desktop.py` and replace with deterministic UIA adapters.
7. **Conflict CF-07**: Rebind dashboard from `0.0.0.0` to `127.0.0.1` and remove firewall hole-punching.
8. **Conflict CF-08**: Replace `actions/reminder.py` `schtasks.exe` scripts with daemon SQLite scheduler.
9. **Conflict CF-09**: Upgrade Watchdog from in-process thread to out-of-process watchdog process with global emergency hotkey.

---

## 5. Next Steps

Upon human owner approval of the **Phase 0 Gate** (Component Map & Conflict Log):
1. Tag Phase 0 commit: `git tag gate-p0-approved`.
2. Create Phase 1 branch: `git checkout -b max/p1-foundations`.
3. Proceed with Phase 1 deliverables (Data contracts, 14-state machine, injectable Clock, event envelope, ExecutionGateway & PolicyEngine, banned-import AST scan).
