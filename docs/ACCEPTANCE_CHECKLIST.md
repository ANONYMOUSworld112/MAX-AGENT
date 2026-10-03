# MAX-AGENT v2.0 Production Acceptance Checklist & Telemetry Audit

This document certifies that MAX-AGENT v2.0 meets all production acceptance gates specified in [MAX_AGENT_MASTER_IMPLEMENTATION_PLAN.md](file:///f:/MAX-AGENT/MAX_AGENT_MASTER_IMPLEMENTATION_PLAN.md) and [docs/MAX_REPAIR_PLAN.md](file:///f:/MAX-AGENT/docs/MAX_REPAIR_PLAN.md).

---

## 1. 10 Core Production Telemetry Questions

Rule 1-H1 Honesty dictates that MAX-AGENT must never claim completion or status without auditable, authoritative proof. MAX answers all operational state questions via deterministic queries to SQLite `StateDB` (WAL mode) and its tamper-evident cryptographically chained `audit_log`.

### Question 1: What am I doing?
- **Operational Meaning**: Identifies the currently active subtask, action, and lifecycle state.
- **Data Source**: `tasks` table and `task_traces` table.
- **SQL Audit Query**:
```sql
SELECT 
    t.task_id, 
    t.status, 
    t.agent_name, 
    json_extract(t.payload_json, '$.action') AS active_action,
    tt.step AS current_step, 
    tt.details AS step_details,
    tt.timestamp AS last_activity
FROM tasks t
LEFT JOIN task_traces tt ON t.task_id = tt.task_id
WHERE t.task_id = :task_id
ORDER BY tt.id DESC 
LIMIT 1;
```
- **Evidence Schema**: `tasks.status IN ('CREATED', 'DISPATCHED', 'EXECUTING', 'VERIFYING', 'COMPLETED', 'FAILED')`.

---

### Question 2: Why am I doing it?
- **Operational Meaning**: Traces user intent decomposition, high-level plan goals, and causal parentage.
- **Data Source**: `tasks.metadata_json` (parent task linkage and parsed intent) and `audit_log.details`.
- **SQL Audit Query**:
```sql
SELECT 
    t.task_id,
    json_extract(t.metadata_json, '$.parent_task_id') AS parent_task_id,
    json_extract(t.metadata_json, '$.intent') AS parsed_intent,
    json_extract(t.payload_json, '$.goal') AS goal,
    json_extract(t.metadata_json, '$.prompt') AS raw_user_prompt
FROM tasks t 
WHERE t.task_id = :task_id;
```
- **Evidence Schema**: Deterministic task graph linkage ensuring every subtask traces to a root intent node.

---

### Question 3: Who is doing it?
- **Operational Meaning**: Identifies the specific actor, worker process, or subagent instance executing the step.
- **Data Source**: `tasks.agent_name` and `audit_log.actor`.
- **SQL Audit Query**:
```sql
SELECT 
    id, 
    timestamp, 
    actor, 
    event_type,
    json_extract(details, '$.worker_pid') AS worker_pid
FROM audit_log
WHERE json_extract(details, '$.task_id') = :task_id
ORDER BY id DESC;
```
- **Evidence Schema**: Concrete worker identities (`LocalDevWorker`, `ReminderWorker`, `MediaWorker`, `DesktopWorker`, `ApplicationRegistry`).

---

### Question 4: What tool is being used?
- **Operational Meaning**: Identifies the exact capability or tool invoked from the single execution choke point.
- **Data Source**: `audit_log.details` (choke-point tool execution record).
- **SQL Audit Query**:
```sql
SELECT 
    id, 
    timestamp, 
    actor,
    json_extract(details, '$.tool_name') AS tool_name,
    json_extract(details, '$.parameters') AS parameters
FROM audit_log
WHERE json_extract(details, '$.task_id') = :task_id
  AND json_extract(details, '$.tool_name') IS NOT NULL
ORDER BY id DESC;
```
- **Evidence Schema**: Tools registered in `core.capability_registry.CapabilityRegistry` validated prior to invocation.

---

### Question 5: What resource is being accessed or locked?
- **Operational Meaning**: Guarantees mutually exclusive resource access (files, ports, display, processes) without deadlock.
- **Data Source**: `resource_locks` table.
- **SQL Audit Query**:
```sql
SELECT 
    rl.resource_id, 
    rl.task_id, 
    rl.acquired_at, 
    rl.expires_at,
    (strftime('%s', rl.expires_at) - strftime('%s', 'now')) AS lease_remaining_seconds
FROM resource_locks rl
WHERE rl.task_id = :task_id;
```
- **Evidence Schema**: Dijkstra-ordered hierarchical leases managed by `core.scheduler.TaskScheduler`.

---

### Question 6: What failed?
- **Operational Meaning**: Authoritative failure capture, root cause error message, and exception stack trace.
- **Data Source**: `audit_log` error events and `circuit_breakers` table.
- **SQL Audit Query**:
```sql
SELECT 
    id, 
    timestamp, 
    event_type,
    actor,
    json_extract(details, '$.error_message') AS error_message,
    json_extract(details, '$.traceback') AS traceback,
    json_extract(details, '$.failure_phase') AS failure_phase
FROM audit_log
WHERE json_extract(details, '$.task_id') = :task_id
  AND event_type IN ('TASK_FAILED', 'VERIFICATION_FAILED', 'CIRCUIT_TRIPPED')
ORDER BY id DESC;
```
- **Evidence Schema**: Structural failures recorded before any fallback or self-correction attempt.

---

### Question 7: What was retried?
- **Operational Meaning**: Complete audit trail of retry attempts, self-correction strategies, and recovery actions.
- **Data Source**: `audit_log` retry events and `task_traces`.
- **SQL Audit Query**:
```sql
SELECT 
    id, 
    timestamp,
    json_extract(details, '$.retry_attempt') AS retry_attempt,
    json_extract(details, '$.correction_strategy') AS strategy,
    json_extract(details, '$.previous_failure') AS previous_failure,
    json_extract(details, '$.rollback_snapshot_id') AS rollback_snapshot_id
FROM audit_log
WHERE json_extract(details, '$.task_id') = :task_id
  AND event_type = 'TASK_RETRY'
ORDER BY id ASC;
```
- **Evidence Schema**: Monotonically increasing attempt counters bounded by retry budgets.

---

### Question 8: What was verified?
- **Operational Meaning**: Multi-tier authoritative evidence proving task success (L0 Syntax, L1 Execution, L2 State Diff, L3 OS/Process).
- **Data Source**: `audit_log` verification events and `snapshots` table.
- **SQL Audit Query**:
```sql
SELECT 
    id, 
    timestamp,
    json_extract(details, '$.verification_tier') AS tier,
    json_extract(details, '$.verifier_name') AS verifier,
    json_extract(details, '$.evidence') AS authoritative_evidence,
    json_extract(details, '$.evidence_hash') AS evidence_hash
FROM audit_log
WHERE json_extract(details, '$.task_id') = :task_id
  AND event_type = 'VERIFICATION_SUCCESS'
ORDER BY id DESC;
```
- **Evidence Schema**: Deterministic verification artifacts (test runner exit code 0, SHA-256 state diffs, or OS window/process matching).

---

### Question 9: What remains to be done?
- **Operational Meaning**: Query remaining steps in compound task graphs or batch executions.
- **Data Source**: `tasks` table with parent-child task graph relationships.
- **SQL Audit Query**:
```sql
SELECT 
    task_id, 
    agent_name, 
    status, 
    priority_band,
    json_extract(payload_json, '$.action') AS pending_action
FROM tasks
WHERE json_extract(metadata_json, '$.parent_task_id') = :parent_id
  AND status NOT IN ('COMPLETED', 'VERIFIED')
ORDER BY priority_band ASC, created_at ASC;
```
- **Evidence Schema**: Pending DAG nodes filtered by status `CREATED` or `DISPATCHED`.

---

### Question 10: Why did I say the task was complete?
- **Operational Meaning**: Absolute truthfulness guarantee. No task is marked completed without immutable cryptographic evidence.
- **Data Source**: `audit_log` record with event `TASK_VERIFIED_COMPLETE` and SHA-256 hash chaining.
- **SQL Audit Query**:
```sql
SELECT 
    a.id, 
    a.timestamp, 
    a.prev_hash,
    a.hash,
    json_extract(a.details, '$.verification_tier') AS verified_tier,
    json_extract(a.details, '$.verifier_name') AS verifier_used,
    json_extract(a.details, '$.evidence_hash') AS evidence_hash,
    json_extract(a.details, '$.authoritative_proof') AS proof_summary
FROM audit_log a
WHERE json_extract(a.details, '$.task_id') = :task_id
  AND a.event_type = 'TASK_VERIFIED_COMPLETE';
```
- **Evidence Schema**: The presence of this row in the tamper-evident hash chain is the single condition required for declaring success.

---

## 2. 25 Golden Tasks Forensic Benchmark (Phase 0 vs Phase 12)

| Metric | Phase 0 Baseline (Legacy) | Phase 12 Acceptance (Target) | Phase 12 Verified (Actual) | Status |
|:---|:---:|:---:|:---:|:---:|
| **Route Accuracy** | 84.0% | ≥ 95.0% | **100.0%** | PASS |
| **Verified Success Rate** | 16.0% | ≥ 80.0% | **100.0%** | PASS |
| **False Success Rate** | 56.0% | < 5.0% | **0.0%** | PASS |
| **Safety Catch Rate** | 0.0% (Bypassed in runtime) | 100.0% | **100.0%** | PASS |
| **Multi-Task Support** | 0.0% (No TaskGraph) | 100.0% | **100.0%** | PASS |
| **Automated Test Count** | 21 passing (Tier 0) | ≥ 250 passing | **297 passing** | PASS |

- **Phase 0 Baseline Evidence**: [docs/evidence/p0/evals_baseline.json](file:///f:/MAX-AGENT/docs/evidence/p0/evals_baseline.json)
- **Phase 12 Acceptance Evidence**: [docs/evidence/p12/evals_e2e.json](file:///f:/MAX-AGENT/docs/evidence/p12/evals_e2e.json)

---

## 3. Production Readiness Verification Sign-Off

- [x] **Tier 0 Characterization Tests**: All 21 original baseline tests remain 100% passing.
- [x] **Single Execution Choke Point**: All actions routed through `CapabilityRegistry` with deterministic validation.
- [x] **RCE Elimination**: Removed `exec()` and `eval()` in favor of AST verification and typed executors.
- [x] **Desktop Automation Reliability**: Applications verified with L3 process & window tracking; zero blind sleeps.
- [x] **Sandboxed Coding**: Git worktree isolation with independent test verification and auto-rollback.
- [x] **Deterministic Scheduling**: SQLite WAL persistence, RFC 5545 RRULE recurrence, and Dijkstra resource leases.
- [x] **Memory Hardening**: Provenance-gated memory (TRUSTED/UNTRUSTED) and SQLite StateDB layer architecture.
- [x] **Process Safety & Windows Job Objects**: Reliable process tree termination and kill-switch integration.
- [x] **Verification Hierarchy**: L0 (Syntax), L1 (Execution), L2 (State Diff), L3 (OS Integration) with self-correction.
- [x] **Provider Abstraction & Offline Fallback**: Unified Gemini, Ollama, and Mock providers with zero vendor lock-in.
- [x] **Modular Domain Workers**: Real implementations for Calendar, Reminder, Media, and LocalDev.
- [x] **Observability & HUD Dashboard API**: Authenticated (`X-MAX-Token`), rate-limited, local-only API with real-time Qt progress widget.
- [x] **Golden Benchmark E2E**: 100% verified success rate, 0% false success rate across 25 golden tasks.
- [x] **Release Tag**: Prepared for `v2.0.0-rc1`.
