# MAX OS v1 — Backend Wiring Order

### The build sequence. Every module has exactly one "ready when" condition.
### No module starts until its predecessor passes its gate.

---

## Guiding Constraint

The TRD (§0) says it plainly: **correctness and recoverability over throughput.**
The wiring order below optimizes for the same thing — each layer must be
*provably correct* before the next layer trusts it. No "build it all, then
integrate." Each wire-up has a test that proves it works before the next
module plugs into it.

---

## Layer 0 — The Floor (nothing else exists without these)

These three modules have zero runtime dependencies. They are the
foundation every other component imports from.

```
┌─────────────────────────────────────────────────────────┐
│  0A. state_db.py — Single SQLite connection factory     │
│      Wire: get_connection() → WAL mode, foreign keys ON │
│      Gate: SELECT 1 returns, WAL pragma verified         │
├─────────────────────────────────────────────────────────┤
│  0B. max_state_schema.sql → create all 11 tables        │
│      Wire: schema applied via state_db connection        │
│      Gate: all 11 tables exist, all indices present      │
├─────────────────────────────────────────────────────────┤
│  0C. kill_switch.py — Signal handler, top priority       │
│      Wire: registered BEFORE any other import            │
│      Gate: dummy long-running task killed in <1s          │
└─────────────────────────────────────────────────────────┘
```

**Why this order:** `state_db` must exist for the schema to be applied.
The kill switch must be armed before anything can run — this is
ARCHITECTURE.md Principle #1, non-negotiable. If anything below crashes
during development, the kill switch is already there to stop it.

### Wiring Diagram

```
state_db.py ──creates──► max_state.db
     │                        │
     │                        ▼
     │               11 tables + indices
     │
kill_switch.py ──registers──► signal handler (SIGTERM/SIGINT)
     │
     ▼
  GATE 0: both pass → proceed to Layer 1
```

---

## Layer 1 — Security Envelope (before any external call)

```
┌─────────────────────────────────────────────────────────┐
│  1A. vault.py — Secrets vault adapter                   │
│      Wire: get_secret(name) → OS keychain first,        │
│            encrypted-file fallback second                │
│      Imports: (none from our code — OS keychain API)     │
│      Gate: store a test secret, retrieve it, grep repo   │
│            for the literal value — must find nothing      │
├─────────────────────────────────────────────────────────┤
│  1B. data_boundary.py — Outbound payload sanitizer      │
│      Wire: every_outbound_llm_call.must_pass_through()  │
│      Imports: vault.py (to know what patterns to mask)   │
│      Gate: planted fake API key in an out-of-scope file  │
│            never appears in the outbound payload          │
└─────────────────────────────────────────────────────────┘
```

**Why before anything else:** The TRD's data-boundary requirement (§9)
and zero-plaintext-secrets requirement are *preconditions*, not features.
Every module that touches external APIs (Router, Agents) will import
`data_boundary` — it must exist and be tested first.

### Wiring Diagram

```
vault.py ──backs──► OS Keychain / Encrypted file
     │
     ▼
data_boundary.py ──wraps──► all future LLM API calls
     │
     ▼
  GATE 1: both pass → proceed to Layer 2
```

---

## Layer 2 — Task Infrastructure (the state machine and queue)

```
┌─────────────────────────────────────────────────────────┐
│  2A. errors.py — Error taxonomy enum                    │
│      Wire: 5 classes (transient/validation/permission/  │
│            destructive_risk/systemic), classify()        │
│      Imports: (none)                                     │
│      Gate: throw one of each, confirm correct class      │
├─────────────────────────────────────────────────────────┤
│  2B. task_lifecycle.py — State machine                   │
│      Wire: CREATED→QUEUED→LOCK_WAIT→RUNNING→            │
│            RECONCILING→DONE (+ error branches)           │
│      Imports: state_db, errors                           │
│      Gate: illegal transition raises, not silently allows│
├─────────────────────────────────────────────────────────┤
│  2C. task_queue.py — Priority queue + idempotency keys   │
│      Wire: heapq-backed, priority bands 0-4, aging,     │
│            backpressure at MAX_QUEUE_DEPTH=500            │
│      Imports: state_db, task_lifecycle                    │
│      Gate: tasks dequeue in priority order; a waited     │
│            task ages up; queue rejects at capacity         │
├─────────────────────────────────────────────────────────┤
│  2D. snapshot.py — Task-scoped snapshot/rollback         │
│      Wire: auto-snapshot on entering RUNNING;            │
│            full restore on any failure                    │
│      Imports: state_db, task_lifecycle                    │
│      Gate: partial-write task killed mid-execution       │
│            leaves zero artifacts after rollback            │
├─────────────────────────────────────────────────────────┤
│  2E. retry.py — Backoff + full jitter, per error class   │
│      Wire: reads RETRY_POLICY per ErrorClass;            │
│            only TRANSIENT and SYSTEMIC ever retry         │
│      Imports: errors, task_lifecycle                      │
│      Gate: 5 simultaneous transient failures retry at    │
│            spread-out times, never synchronized           │
└─────────────────────────────────────────────────────────┘
```

**Why this sequence:** Errors must be classifiable (2A) before the state
machine can branch on them (2B). The queue (2C) needs the lifecycle to
know which states are terminal. Snapshot (2D) hooks into the RUNNING
transition. Retry (2E) reads the error class and the lifecycle state.

### Wiring Diagram

```
errors.py ◄──classifies── every failure
     │
     ▼
task_lifecycle.py ──records──► task_trace table
     │                              │
     ├──────────────────────────────┤
     ▼                              ▼
task_queue.py                 snapshot.py
     │                              │
     └──────────┬───────────────────┘
                ▼
           retry.py
                │
                ▼
          GATE 2: all pass → proceed to Layer 3
```

---

## Layer 3 — Synchronization Primitives

```
┌─────────────────────────────────────────────────────────┐
│  3A. lock_manager.py — Sorted-order, all-or-nothing     │
│      Wire: acquire_all(resource_ids, timeout)            │
│            shared vs exclusive lock types                 │
│      Imports: state_db (for lock state persistence)      │
│      Gate: reversed-order two-lock test completes        │
│            without hanging (timeout-bounded)              │
├─────────────────────────────────────────────────────────┤
│  3B. watchdog.py — Heartbeat monitor                    │
│      Wire: 15s heartbeat interval, 3 misses = killed    │
│      Imports: task_lifecycle, snapshot, lock_manager      │
│      Gate: deliberately-hung agent killed at 45s,        │
│            snapshot rolled back, locks released            │
├─────────────────────────────────────────────────────────┤
│  3C. reconciliation.py — Post-execution verification    │
│      Wire: queries real state vs agent self-report       │
│      Imports: task_lifecycle, errors (SYSTEMIC on miss)  │
│      Gate: agent that lies about success is caught        │
├─────────────────────────────────────────────────────────┤
│  3D. circuit_breaker.py — Per-agent failure isolation    │
│      Wire: 5 consecutive failures → OPEN; half-open     │
│            test after cooldown                            │
│      Imports: state_db (circuit_breaker_state table)     │
│      Gate: 6th request rejected instantly, other agents  │
│            unaffected                                     │
├─────────────────────────────────────────────────────────┤
│  3E. dlq.py — Dead Letter Queue                         │
│      Wire: exhausted-retry tasks land here with full     │
│            attempt history; requeueable via CLI           │
│      Imports: state_db, task_lifecycle                    │
│      Gate: max dlq --list shows dead task with history   │
└─────────────────────────────────────────────────────────┘
```

### Wiring Diagram

```
lock_manager.py ◄──acquires──  task entering RUNNING
     │
     ├──releases-on──► DONE, WATCHDOG_KILLED, ROLLBACK
     │
     ▼
watchdog.py ──monitors──► heartbeat() calls from agents
     │
     ├──kills──► snapshot.py rollback
     │
     ▼
reconciliation.py ──verifies──► real system state
     │
     ├──mismatch──► errors.py (SYSTEMIC)
     │
     ▼
circuit_breaker.py ──gates──► task_queue (reject if OPEN)
     │
     ▼
dlq.py ──captures──► exhausted tasks
     │
     ▼
  GATE 3: all pass → proceed to Layer 4
```

---

## Layer 4 — Intent Classification & Routing

```
┌─────────────────────────────────────────────────────────┐
│  4A. intent_classifier.py — Keyword-first, LLM fallback │
│      Wire: classify(text) → {agent, intent, confidence}  │
│      Imports: data_boundary (to scope LLM call)          │
│      Gate: 10 sample messages classified correctly;      │
│            <70% confidence returns 'clarify'              │
├─────────────────────────────────────────────────────────┤
│  4B. permissions.py — Tier enforcement                   │
│      Wire: auto/confirm/production_gate per task         │
│            metadata, never by phrasing                    │
│      Imports: (config file: production_targets.yaml)     │
│      Gate: 5 phrasings of "skip approval" all fail       │
├─────────────────────────────────────────────────────────┤
│  4C. planner.py — Dependency graph decomposition         │
│      Wire: compound request → ordered sub-tasks with     │
│            depends_on edges                               │
│      Imports: intent_classifier, task_queue               │
│      Gate: "build, deploy, remind me" → 3 tasks in       │
│            correct sequence                               │
├─────────────────────────────────────────────────────────┤
│  4D. prompt_agent.py — Agent-specific prompt builder     │
│      Wire: raw input + context → structured prompt       │
│      Imports: data_boundary, intent_classifier            │
│      Gate: credential-pattern strings never in output     │
└─────────────────────────────────────────────────────────┘
```

### Wiring Diagram

```
User input (raw text)
     │
     ▼
intent_classifier.py ──{agent, intent, confidence}──► planner.py
     │                                                      │
     │                                                      ▼
     │                                              task_queue.py
     │                                              (with depends_on)
     │
     ▼
permissions.py ──tier──► confirm gate / production gate / auto
     │
     ▼
prompt_agent.py ──structured prompt──► Agent modules
     │
     ▼
  GATE 4: all pass → proceed to Layer 5
```

---

## Layer 5 — Agent Modules (the business logic)

Build in this order — each one adds complexity incrementally.

```
┌─────────────────────────────────────────────────────────┐
│  5A. Agent base interface                                │
│      Wire: classify(), tier_for(intent), execute(task),  │
│            report() — shared by all 4 agents             │
│      Gate: interface contract enforced by ABC              │
├─────────────────────────────────────────────────────────┤
│  5B. Calendar Agent — simplest, auto-tier only           │
│      Wire: schedule/remind, conflict detection           │
│      Imports: agent base, state_db, task_lifecycle        │
│      Gate: creates event; conflicting time flagged        │
├─────────────────────────────────────────────────────────┤
│  5C. Notes Agent — auto-tier, adds semantic search       │
│      Wire: store note, embed, cosine similarity search   │
│      Imports: agent base, state_db, local embedding model│
│      Gate: store + retrieve by natural language query     │
├─────────────────────────────────────────────────────────┤
│  5D. Coding Agent — confirm-tier, real complexity        │
│      Wire: wraps opencode/external tool; file writes     │
│            require snapshot + rollback                    │
│      Imports: agent base, snapshot, prompt_agent,         │
│               data_boundary                               │
│      Gate: produces working code; forced-failure test     │
│            proves rollback                                │
├─────────────────────────────────────────────────────────┤
│  5E. Deploy Agent — production_gate, highest risk        │
│      Wire: repo-push mode; DA-1→DA-9 pipeline;          │
│            production approval gate enforced inside       │
│            deploy_prod() itself                           │
│      Imports: agent base, vault (GitHub PAT), permissions,│
│               snapshot, reconciliation                     │
│      Gate: gate unbypassable; direct call without token   │
│            fails; idempotent redeploy verified             │
└─────────────────────────────────────────────────────────┘
```

### Wiring Diagram

```
Agent Base Interface (ABC)
     │
     ├──► Calendar Agent ──► calendar_events table
     │         └──► auto-tier only
     │
     ├──► Notes Agent ──► notes table + note_embeddings
     │         └──► auto-tier, local embedding model
     │
     ├──► Coding Agent ──► coding_tasks table, local repos
     │         ├──► confirm-tier (per-task default)
     │         └──► snapshot/rollback on every execution
     │
     └──► Deploy Agent ──► deploy_tasks table, GitHub API
               ├──► production_gate-tier
               ├──► vault.get_secret("github_pat")
               └──► reconciliation (health check post-deploy)
```

---

## Layer 6 — Orchestrator + CLI

```
┌─────────────────────────────────────────────────────────┐
│  6A. main_agent.py — The daemon orchestrator             │
│      Wire: binds to Unix domain socket (or named pipe    │
│            on Windows); routes requests through the full  │
│            pipeline: classify → plan → queue → execute    │
│      Imports: ALL of the above                            │
│      Gate: end-to-end request completes, logged to trace  │
├─────────────────────────────────────────────────────────┤
│  6B. CLI client — Thin, no business logic                │
│      Wire: sends raw text to daemon; renders trace log;  │
│            forwards confirmation/approval responses       │
│      Imports: (none from core — HTTP/socket client only)  │
│      Gate: max trace --last 20 shows real data;           │
│            max kill stops everything in <1s                │
├─────────────────────────────────────────────────────────┤
│  6C. Trace log viewer (CLI subcommand)                   │
│      Wire: max trace --agent X --failures-only            │
│      Gate: filters against real data correctly             │
├─────────────────────────────────────────────────────────┤
│  6D. DLQ viewer (CLI subcommand)                         │
│      Wire: max dlq --list, max dlq --requeue <id>        │
│      Gate: shows dead tasks, requeue works                │
├─────────────────────────────────────────────────────────┤
│  6E. systemd user service unit (or NSSM on Windows)      │
│      Wire: keeps max-core alive across reboots            │
│      Gate: daemon survives a simulated crash + reboot     │
└─────────────────────────────────────────────────────────┘
```

---

## Layer 7 — Crash Recovery & Startup Reconciliation

```
┌─────────────────────────────────────────────────────────┐
│  7A. Startup recovery logic (inside main_agent.py)       │
│      Wire: on daemon start, scan tasks table:            │
│            - status='running' → mark 'interrupted'        │
│            - auto-tier + idempotent → auto-resume          │
│            - confirm/gate-tier → surface for user review   │
│      Gate: simulated crash mid-task → restart → no        │
│            duplicate side effects, user informed            │
└─────────────────────────────────────────────────────────┘
```

---

## Summary: Total Build Order (26 modules, strict sequence)

| Order | Module | Layer | Depends On |
|-------|--------|-------|------------|
| 1 | `state_db.py` | 0 | — |
| 2 | `max_state_schema.sql` | 0 | 1 |
| 3 | `kill_switch.py` | 0 | 1 |
| 4 | `vault.py` | 1 | — |
| 5 | `data_boundary.py` | 1 | 4 |
| 6 | `errors.py` | 2 | — |
| 7 | `task_lifecycle.py` | 2 | 1, 6 |
| 8 | `task_queue.py` | 2 | 1, 7 |
| 9 | `snapshot.py` | 2 | 1, 7 |
| 10 | `retry.py` | 2 | 6, 7 |
| 11 | `lock_manager.py` | 3 | 1 |
| 12 | `watchdog.py` | 3 | 7, 9, 11 |
| 13 | `reconciliation.py` | 3 | 7, 6 |
| 14 | `circuit_breaker.py` | 3 | 1 |
| 15 | `dlq.py` | 3 | 1, 7 |
| 16 | `intent_classifier.py` | 4 | 5 |
| 17 | `permissions.py` | 4 | — |
| 18 | `planner.py` | 4 | 16, 8 |
| 19 | `prompt_agent.py` | 4 | 5, 16 |
| 20 | Agent base interface | 5 | — |
| 21 | Calendar Agent | 5 | 20, 1, 7 |
| 22 | Notes Agent | 5 | 20, 1 |
| 23 | Coding Agent | 5 | 20, 9, 19, 5 |
| 24 | Deploy Agent | 5 | 20, 4, 17, 9, 13 |
| 25 | `main_agent.py` | 6 | ALL above |
| 26 | CLI client | 6 | — (talks to daemon only) |
