# MAX OS v1 — State Management Plan

### Every piece of state in the system, where it lives, who owns it,
### and what happens when something goes wrong mid-write.

---

## Design Principle

The TRD (§0, §4) is explicit: **SQLite in WAL mode, single file, no
external state stores.** State management for MAX OS v1 means three
things: (1) the database is the single source of truth, (2) in-memory
state is a cache that the DB can always reconstruct, and (3) nothing
important is only in memory.

---

## 1. State Categories

MAX OS v1 has exactly four categories of state. Each has different
durability requirements and different failure modes.

### 1.1 Durable State (survives crashes, survives restarts)

| State | Table | Owner | Write Pattern |
|-------|-------|-------|---------------|
| Task lifecycle | `tasks` / `task_trace` | Task State Machine | Transactional: one UPDATE per transition |
| Task audit trail | `task_events` | Trace Logger | Append-only: one INSERT per event |
| Calendar entries | `calendar_events` | Calendar Agent | INSERT on create, UPDATE on status change |
| Notes + embeddings | `notes`, `note_embeddings` | Notes Agent | INSERT only (notes are immutable once stored) |
| Coding task metadata | `coding_tasks` | Coding Agent | INSERT on start, UPDATE on completion |
| Deploy task metadata | `deploy_tasks` | Deploy Agent | INSERT on start, UPDATE per DA-stage |
| Build progress | `phases`, `steps`, `sessions` | Build Orchestrator | UPDATE on step completion |
| Error decisions | `decisions_log` | Any session | Append-only |
| Blockers | `blockers` | Any session | INSERT on raise, UPDATE on resolve |
| Circuit breaker | `circuit_breaker_state` | Circuit Breaker | UPDATE per failure/recovery |
| Outcome stats | `outcome_tracker` | Outcome Tracker | Upsert per task completion |
| Dead letters | `dead_letter_queue` | DLQ Manager | INSERT on exhaust, UPDATE on requeue |

**Durability guarantee:** SQLite WAL mode. A crash mid-write loses at
most the current uncommitted transaction — never corrupts the DB file.

### 1.2 Session State (lives as long as the daemon process)

| State | Location | Owner | Reconstructable from DB? |
|-------|----------|-------|--------------------------|
| In-memory priority queue | `heapq` in `task_queue.py` | Task Queue | ✅ Yes — rebuilt from `tasks` WHERE status IN ('queued','lock_wait') on startup |
| Active lock table | `dict` in `lock_manager.py` | Lock Manager | ✅ Yes — all `running` tasks re-acquire on startup (or mark interrupted) |
| Heartbeat timers | `dict` in `watchdog.py` | Watchdog | ✅ Yes — restarted for any task found in `running` on startup |
| Circuit breaker state (cached) | `dict` in `circuit_breaker.py` | Circuit Breaker | ✅ Yes — read from `circuit_breaker_state` table on startup |
| Intent classifier context | ephemeral in-call | Router | ✅ N/A — stateless per-call |

**Key invariant:** Every piece of session state can be reconstructed
from the database. If the daemon crashes and restarts, the only state
loss is "what was happening right this second" — and that's handled by
the crash recovery protocol (see §5).

### 1.3 Ephemeral State (exists only during a single task execution)

| State | Location | Lifetime | Loss = |
|-------|----------|----------|--------|
| Task snapshot (files) | Temp dir, linked to task_id | RUNNING → DONE/ROLLBACK | Rollback still works (no snapshot = mark interrupted) |
| LLM API call context | In-flight HTTP request | Single classify/prompt call | Retry via retry.py |
| Git working tree changes | Local repo clone | Coding/Deploy execution | Snapshot rollback restores pre-execution state |
| Confirmation prompt state | CLI ↔ daemon socket | Until user responds | Daemon re-prompts on reconnect if task still awaits |

### 1.4 External State (owned by third parties, MAX reads/writes but doesn't own)

| State | Location | MAX's Role | Failure Mode |
|-------|----------|------------|--------------|
| GitHub repo contents | GitHub API | Deploy Agent pushes | Reconciliation checks post-push |
| OS Keychain secrets | OS keyring | Vault reads | Fallback to encrypted file |
| Local git repos | Filesystem | Coding Agent writes | Snapshot/rollback |
| Test runner output | Subprocess stdout | Coding/Deploy reads | Timeout + retry |

---

## 2. State Machine: Task Lifecycle

This is the single most important piece of state in the system. Every
task, regardless of agent, follows this exact machine.

```
                         ┌─── VALIDATION error ───► FAILED (immediate)
                         │
  CREATED ──► QUEUED ────┼─── circuit breaker OPEN ──► REJECTED
                         │
                         └──► LOCK_WAIT ──► RUNNING ──► RECONCILING ──► DONE
                                  │             │              │
                                  │             │              └── MISMATCH ──► ROLLBACK
                                  │             │
                                  │             └── heartbeat timeout ──► WATCHDOG_KILLED
                                  │                                            │
                                  │                                            ▼
                                  │                                        ROLLBACK
                                  │                                            │
                                  └────────────────────────────────────────────┤
                                                                               │
                                                                        ┌──────┤
                                                                        │      │
                                                                 retry? YES    NO
                                                                        │      │
                                                                        ▼      ▼
                                                                  RETRY_QUEUED  DEAD
```

### State Transition Rules (enforced by task_lifecycle.py)

| From | To | Trigger | Side Effects |
|------|----|---------|--------------|
| CREATED | QUEUED | Validation passes, idempotency key assigned | INSERT into task_trace |
| QUEUED | LOCK_WAIT | Dependencies satisfied, circuit breaker closed | Priority band assigned |
| LOCK_WAIT | RUNNING | All locks acquired (sorted order) | Snapshot taken, heartbeat started |
| RUNNING | RECONCILING | Agent reports completion | Heartbeat stopped |
| RECONCILING | DONE | Real state matches report | Locks released, task_events logged |
| RECONCILING | ROLLBACK | Real state mismatches | Error classified as SYSTEMIC |
| RUNNING | WATCHDOG_KILLED | 3 missed heartbeats (45s) | Locks released, snapshot restored |
| WATCHDOG_KILLED | ROLLBACK | Automatic | Snapshot restored |
| ROLLBACK | RETRY_QUEUED | Retry policy allows | retry_count incremented |
| ROLLBACK | DEAD | Retry policy exhausted | Inserted into dead_letter_queue |
| QUEUED | REJECTED | Circuit breaker OPEN for this agent | User notified immediately |
| CREATED | FAILED | Validation error (bad input) | User told exactly what's wrong |

**Illegal transitions:** Any transition not in this table raises
`IllegalStateTransition`, logged to `task_events` with full context.
Silent swallowing of illegal transitions is the single most common
source of "stuck state" bugs — this is how the PRD's 2-week success
metric (§6) gets enforced architecturally.

---

## 3. Concurrency Model

### 3.1 Threading Model

```
max-core daemon (single process)
     │
     ├── Main thread: asyncio event loop
     │       ├── Socket listener (CLI connections)
     │       ├── Task dequeue loop
     │       └── Heartbeat checker (periodic)
     │
     ├── Worker pool: 2-4 concurrent task slots
     │       ├── Each task runs in its own coroutine
     │       ├── CPU-bound work (embedding) offloaded to thread pool
     │       └── Subprocess calls (git, test runners) via asyncio.subprocess
     │
     └── Kill switch: separate signal handler (not in event loop)
```

### 3.2 Lock Granularity

| Resource | Lock Type | Scope |
|----------|-----------|-------|
| `project:<path>` | Exclusive | One deploy/code task per project at a time |
| `calendar` | Shared(read) / Exclusive(write) | Multiple reads, one write at a time |
| `notes_db` | Shared(read) / Exclusive(write) | Multiple searches, one write at a time |
| `github:<repo>` | Exclusive | One push at a time per repo |
| `llm_api` | Semaphore(N) | Rate limiting, not mutual exclusion |

### 3.3 Transaction Boundaries

Every state mutation follows this pattern:

```python
async def execute_task(task):
    # 1. Acquire all locks (sorted order, all-or-nothing)
    if not await lock_manager.acquire_all(task.resources, timeout=10):
        task.transition(LOCK_WAIT)
        return  # re-queued, will retry acquisition

    # 2. Take snapshot
    snapshot_id = await snapshot.capture(task)

    # 3. Start heartbeat
    heartbeat = watchdog.start_monitoring(task.id)

    try:
        # 4. Execute (the agent does its work)
        result = await agent.execute(task)

        # 5. Reconcile (verify real state matches)
        if await reconciliation.verify(task, result):
            task.transition(DONE)
        else:
            raise ReconciliationMismatch(task, result)

    except Exception as e:
        # 6. Classify error, rollback, decide retry
        error_class = errors.classify(e)
        await snapshot.restore(snapshot_id)
        task.transition(ROLLBACK)

        if retry.should_retry(task, error_class):
            task.transition(RETRY_QUEUED)
        else:
            await dlq.insert(task, error_class)
            task.transition(DEAD)

    finally:
        # 7. Always release locks, always stop heartbeat
        heartbeat.stop()
        lock_manager.release_all(task.resources)
```

---

## 4. Data Persistence Strategy

### 4.1 Write Patterns by Frequency

| Pattern | Frequency | Method |
|---------|-----------|--------|
| Task state transitions | ~5-10 per task | Individual UPDATEs within transactions |
| Task events (audit trail) | ~10-20 per task | Batch INSERT at task completion |
| Note storage | User-driven, sporadic | Single INSERT per note |
| Embedding writes | One per note | INSERT with BLOB |
| Calendar entries | User-driven, sporadic | Single INSERT per event |
| Circuit breaker updates | On failure only | UPDATE single row |
| Outcome tracker | On task completion | UPSERT (INSERT OR REPLACE) |

### 4.2 Read Patterns

| Pattern | Frequency | Optimization |
|---------|-----------|-------------|
| Queue reconstruction on startup | Once per daemon start | Index on `tasks.status` |
| Trace log streaming | Continuous polling | Index on `task_events.task_id` + `ts` |
| Notes semantic search | User-driven | In-memory cosine similarity (small dataset) |
| Calendar conflict check | Per calendar write | Index on `calendar_events.start_time` |
| Circuit breaker check | Per task dispatch | Cached in memory, DB is fallback |

### 4.3 Backup Strategy

```
Daily: cp max_state.db max_state.db.backup.$(date +%Y%m%d)
       (safe during operation because WAL mode)

On schema migration: full backup before, test on copy first
```

---

## 5. Crash Recovery Protocol

When the daemon restarts after an unexpected shutdown:

```
STARTUP SEQUENCE:
     │
     ├─ 1. Kill switch armed (ALWAYS first)
     │
     ├─ 2. Open max_state.db (WAL recovery automatic)
     │
     ├─ 3. Scan tasks WHERE status = 'running'
     │      │
     │      ├── For each: was it auto-tier AND idempotent?
     │      │       YES → mark RETRY_QUEUED, auto-resume
     │      │       NO  → mark 'interrupted — needs review'
     │      │              surface in trace log for user
     │      │
     │      └── Release any locks these tasks held
     │
     ├─ 4. Scan tasks WHERE status = 'lock_wait'
     │      └── Re-queue for lock acquisition
     │
     ├─ 5. Rebuild in-memory priority queue from DB
     │
     ├─ 6. Rebuild circuit breaker state from DB
     │
     ├─ 7. Resume normal operation
     │
     └─ 8. Log startup event to task_events
```

**Critical constraint from TRD §8:** interrupted Coding/Deploy tasks
are NEVER auto-resumed — they may have partially completed (opened a PR,
written half the files). Only side-effect-free, idempotent tasks get
auto-resumed. Everything else waits for human review.

---

## 6. State Ownership Matrix

Who is allowed to read and write each state category:

| State | Write Access | Read Access |
|-------|-------------|-------------|
| `tasks` / `task_trace` | Task State Machine ONLY | Queue, Agents, CLI, Watchdog |
| `task_events` | Trace Logger ONLY (append) | CLI, Main Agent |
| `calendar_events` | Calendar Agent ONLY | Planner (conflict check) |
| `notes` / `note_embeddings` | Notes Agent ONLY | Notes Agent (search) |
| `coding_tasks` | Coding Agent ONLY | CLI (trace), Planner |
| `deploy_tasks` | Deploy Agent ONLY | CLI (trace), Planner |
| `circuit_breaker_state` | Circuit Breaker ONLY | Task Queue (dispatch check) |
| `dead_letter_queue` | DLQ Manager ONLY | CLI (dlq --list), Main Agent |
| Lock table (in-memory) | Lock Manager ONLY | Watchdog (to release on kill) |

**No module reaches into another module's tables.** If the Planner needs
to know a task's state, it reads `tasks` through the state machine's
public interface — never a raw SQL query against another module's table.
This is what makes future schema changes safe: only one module knows a
table's internal structure.
