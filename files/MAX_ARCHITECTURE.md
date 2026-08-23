# MAX OS — Architecture & Build Plan
### The single source of truth. If you are an AI coding agent reading this
### with no memory of previous sessions, start at Section 0.

---

## 0. Resume Protocol — Read This First, Every Session

```
1. Open max_state.db (create it from max_state_schema.sql if it doesn't exist)
2. Run:  SELECT * FROM steps WHERE status != 'done' ORDER BY step_id LIMIT 1;
3. That row is where you resume. Read its `notes` column — it holds the
   last session's handoff context for that specific step.
4. Run:  SELECT * FROM sessions ORDER BY started_at DESC LIMIT 1;
   Read `summary` — it holds the plain-English state of the world as of
   the last session's end, independent of any single step.
5. Run:  SELECT * FROM blockers WHERE resolved = 0;
   If anything is open here, resolve it or ask the user before proceeding
   — do not build around an unresolved blocker silently.
6. Check depends_on for the step you're resuming — if a dependency isn't
   'done', STOP. Something is wrong (a previous session marked something
   done incorrectly, or skipped ahead). Fix the tracking before writing
   more code, don't build on an inconsistent state.
7. Insert a new row into `sessions` with a fresh session_id and
   started_at = now. Every action below gets tagged with this session_id.
```

**Never start a session by re-reading the whole codebase from scratch and
guessing what's next.** The database is the source of truth for progress,
not the code's current state — code can be mid-edit, half-committed, or
ahead of what's actually verified working. Trust the `status` column, and
verify it against `acceptance_criteria` before trusting it blindly.

### End-of-session protocol (run this before you stop, always — even mid-step)

```
1. For the step(s) you touched this session:
     - status = 'done' ONLY if acceptance_criteria are actually verified,
       not just "code looks right"
     - status = 'in_progress' if partially done — write EXACTLY what's
       left into `notes`, specific enough that a stranger could continue
       ("wrote the lock acquisition logic, still need the timeout test
       and the sorted-order unit test" — not "almost done")
     - status = 'blocked' if you can't proceed — also insert a row into
       `blockers` with the specific question
2. UPDATE sessions SET ended_at = now, ended_reason = <reason>,
     steps_touched = <comma list>, summary = <handoff note> WHERE
     session_id = <this session>
3. If you made any non-obvious design call this session (chose SQLite
   over Postgres for X, decided Y agent needs Z permission tier), write
   it to `decisions_log` with your reasoning. The next session should
   never have to re-derive a decision you already made.
4. Commit code with a message referencing the step_id, e.g.
   "feat(lock-manager): sorted-order acquisition — step 2.3"
```

This protocol is what makes "quota ran out mid-task" a non-event instead
of a lost session. The cost is a few DB writes per session; the payoff is
never starting over.

---

## 1. Non-Negotiable Principles (condensed — full reasoning lives in the
### earlier design docs, this is the enforceable summary)

1. **Kill Switch is Component #0.** Nothing else initializes until it
   reports armed. Build this in Phase 0, before anything else exists.
2. **Two hard gates, never more, never fewer:** Architecture Review
   (before code) and Production Approval (before deploy). Both enforced
   *inside the relevant function's code path*, never only in a UI layer.
3. **Agent vs. Infrastructure is a real distinction.** Infra (queue, lock
   manager, watchdog, reconciliation, circuit breaker) is deterministic —
   no LLM call inside it. Agents (Coding, Deploy, Calendar, etc.) are
   where judgment/LLM reasoning happens. Don't blur this — it's the
   difference between something you can unit-test deterministically and
   something you can only integration-test.
4. **Every task is atomic at its own boundary.** Snapshot before
   `RUNNING`, full rollback on failure — never a partial commit.
5. **Every external side effect is idempotent**, keyed by a UUID assigned
   at task creation, checked before the side effect fires.
6. **Locks acquire in sorted resource-ID order, always, all-or-nothing.**
   This is the actual deadlock prevention — not a hope, a mechanism.
7. **Errors are classified before they're handled** (transient /
   validation / permission / destructive_risk / systemic). Only
   transient and systemic ever retry, and each has its own bounded policy
   with jittered backoff.
8. **Nothing fails silently.** Every failure path ends in one of: retry,
   ask the user, refuse with a stated reason, or roll back + log to the
   dead letter queue.
9. **No plaintext secrets, ever.** OS keychain or an encrypted local file.
   Agents request credentials through a vault interface, never read the
   raw secret file.
10. **Scope discipline: v1 is 4 agents.** Calendar, Notes, Coding, Deploy.
    Everything else in the full roster is real and designed, but does not
    get built until v1 has run reliably for real daily use. If you (the
    build agent) find yourself writing code for agent #5 before the v1
    scope is done and verified, stop — that's scope creep, log it as a
    blocker, don't just proceed.

---

## 2. Tech Stack (pinned — don't re-decide this every session)

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.11+ | Matches all prior design sketches, fastest to iterate solo |
| State DB | SQLite (`max_state.db`) | Zero ops burden for a single-user local system; upgrade path to Postgres exists if ever needed, not needed now |
| Queue | In-process priority heap (`heapq`) + the schema above for durability across restarts | No Redis/Kafka needed at this scale — see prior doc's phasing rationale |
| Agent runtime | Plain Python classes, orchestrated by a `TaskOrchestrator` | No microservices until there's a proven reason for them |
| Secrets | `keyring` library (OS keychain) | Avoids plaintext config entirely from day one |
| LLM provider | Anthropic API (Claude) | Per the Data Boundary Policy — minimum necessary context per call |
| CI | GitHub Actions (added in Phase 3) | Standard, free for solo/small repos |

**Do not introduce a new component to this table without writing a row in
`decisions_log` explaining why.** If a step seems to require something not
listed here, that's a signal to stop and reconsider the step, not to
silently add infrastructure.

---

## 3. Repository Structure

```
max-os/
├── max_state.db                  # created from schema below, gitignored (contains local data)
├── max_state_schema.sql          # the schema itself — IS committed
├── ARCHITECTURE.md               # this file
├── MASTER_PROMPT.md              # the agent system prompt
├── src/
│   ├── core/
│   │   ├── main_agent.py
│   │   ├── intent_classifier.py
│   │   ├── prompt_agent.py
│   │   ├── planner.py
│   │   └── kill_switch.py        # Phase 0 — built first, always
│   ├── infra/
│   │   ├── task_queue.py
│   │   ├── lock_manager.py
│   │   ├── watchdog.py
│   │   ├── reconciliation.py
│   │   ├── circuit_breaker.py
│   │   ├── snapshot.py
│   │   ├── state_db.py           # single connection helper, all modules import this
│   │   └── vault.py
│   ├── agents/
│   │   ├── calendar_agent.py
│   │   ├── notes_agent.py
│   │   ├── coding_agent.py
│   │   └── deploy_agent.py
│   └── cli/
│       └── max_trace.py          # `max trace --last 20`, `max dlq --list`
├── tests/
│   └── ... (mirrors src/, see Phase 1 step on test scaffolding)
└── .env.example                  # documents required keys, never real secrets
```

---

## Phase 0 — Bootstrap (nothing else exists until this is done)

| Step | Title | Depends on | Acceptance criteria | Files |
|---|---|---|---|---|
| 0.1 | Repo scaffold | — | Directory structure above exists, `git init` done, `.gitignore` excludes `max_state.db` and `.env` | repo root |
| 0.2 | Create `max_state.db` from schema | 0.1 | `sqlite3 max_state.db < max_state_schema.sql` runs clean, all tables exist | `max_state_schema.sql` |
| 0.3 | `state_db.py` connection helper | 0.2 | A single `get_connection()` function every other module imports — no module opens its own raw connection | `src/infra/state_db.py` |
| 0.4 | Seed `phases` and `steps` tables | 0.3 | This entire ARCHITECTURE.md's phases/steps are inserted as rows, status='not_started' | seed script |
| 0.5 | **Kill Switch — Component #0** | 0.3 | Listens on a local hotkey/signal independent of any UI; calling it hard-stops any running process and writes an immediate log entry; nothing else in `main.py` is allowed to import before this reports armed | `src/core/kill_switch.py` |

**Phase 0 is not "done" until 0.5 passes a real test: trigger it while
something is deliberately running, confirm it stops instantly with no
confirmation dialog.**

---

## Phase 1 — Prove the Loop (single agent, no concurrency yet)

| Step | Title | Depends on | Acceptance criteria | Files |
|---|---|---|---|---|
| 1.1 | Task lifecycle state machine | 0.5 | Every state from §1 of the sync-pipeline doc is a real enum; illegal transitions raise, don't silently allow | `src/infra/task_lifecycle.py` |
| 1.2 | Idempotency key generation | 1.1 | Every task gets a UUID4 at creation, stored in `task_trace.idempotency_key` | `src/infra/task_queue.py` |
| 1.3 | Snapshot/rollback (task-scoped) | 1.1 | Snapshot taken automatically on entering RUNNING; rollback restores exactly that task's changes, verified by a test that partially completes a task and confirms full revert | `src/infra/snapshot.py` |
| 1.4 | Error taxonomy + classification | 1.1 | 5 error classes exist as an enum; a test throws one of each and confirms the retry policy table is respected (0 retries for validation/permission/destructive_risk) | `src/infra/errors.py` |
| 1.5 | Retry policy: backoff + full jitter | 1.4 | Unit test confirms delay is bounded and randomized, not deterministic | `src/infra/retry.py` |
| 1.6 | Intent Classifier (keyword + single LLM call) | 0.5 | Given 10 sample messages, correctly classifies intent with a confidence score; <70% confidence returns `clarify` | `src/core/intent_classifier.py` |
| 1.7 | Prompt Agent + Data Boundary Policy | 1.6 | Given raw message + context, produces agent-specific structured prompt; a test confirms credential-pattern strings never appear in the output | `src/core/prompt_agent.py` |
| 1.8 | Coding Agent (first real agent) | 1.3, 1.7 | Given a simple fix request, writes a file, the write goes through snapshot/rollback correctly on a forced failure | `src/agents/coding_agent.py` |
| 1.9 | Main Agent — single-agent end-to-end | 1.6, 1.8 | Input → classify → prompt → execute → response works fully for one Coding Agent request, logged to `task_trace` | `src/core/main_agent.py` |
| 1.10 | Trace Log Viewer (CLI, minimum viable) | 1.9 | `max trace --last 20` shows real rows from `task_trace` | `src/cli/max_trace.py` |

**Phase 1 is done when:** a single request goes from user input to a
completed Coding Agent task, fully logged, with a forced-failure test
proving snapshot rollback actually reverts a partial write.

---

## Phase 2 — Multi-Agent + Synchronization Infra

| Step | Title | Depends on | Acceptance criteria | Files |
|---|---|---|---|---|
| 2.1 | Priority queue (bands + aging) | 1.2 | Tasks dequeue in priority order; a test confirms a task waiting >60s gets boosted | `src/infra/task_queue.py` |
| 2.2 | Backpressure ceiling | 2.1 | Queue at `MAX_QUEUE_DEPTH` rejects new tasks with a clear message, doesn't silently drop | `src/infra/task_queue.py` |
| 2.3 | Resource Lock Manager — sorted-order, all-or-nothing | 2.1 | Unit test: two tasks request the same two resources in reverse order — no deadlock, confirmed by a timeout-bounded test that would hang if broken | `src/infra/lock_manager.py` |
| 2.4 | Lock types: shared vs. exclusive | 2.3 | Two "read" tasks on the same resource run concurrently; one "write" task blocks both | `src/infra/lock_manager.py` |
| 2.5 | Heartbeat Watchdog | 1.3, 2.3 | A deliberately-hung fake agent gets killed after 3 missed heartbeats, snapshot rolled back, lock released | `src/infra/watchdog.py` |
| 2.6 | Reconciliation Check | 1.9 | A fake agent that lies about success (reports done, but the file doesn't actually exist) is caught and treated as a systemic error | `src/infra/reconciliation.py` |
| 2.7 | Calendar Agent | 1.7 | Auto-tier, no confirm gate, creates/reads calendar entries | `src/agents/calendar_agent.py` |
| 2.8 | Notes Agent | 1.7 | Auto-tier, captures notes | `src/agents/notes_agent.py` |
| 2.9 | Planner — dependency graph decomposition | 2.1, 2.7, 2.8 | A compound request ("note this, then remind me") correctly sequences two agents with a `depends_on` edge, verified by the second task staying non-runnable until the first is DONE | `src/core/planner.py` |
| 2.10 | Compound task test — 3 agents, disjoint resources | 2.4, 2.9 | Three sub-tasks with non-overlapping resource locks run genuinely concurrently, verified by timestamps overlapping in the trace log | tests |
| 2.11 | Dependency graph test — deadlock-prone case | 2.3 | Two tasks requesting resources A+B in opposite order both complete without hanging, verified with a timeout that would fail the test if a deadlock occurred | tests |
| 2.12 | Permission tier enforcement | 2.7, 2.8 | `auto` / `confirm` / `blocked` tiers are enforced from one central table, not scattered per-agent logic | `src/infra/permissions.py` |

**Phase 2 is done when:** Calendar and Notes agents both work, a
compound request across them respects dependency order, and the deadlock
and reconciliation-lie tests both pass.

---

## Phase 3 — Deployment Pipeline

| Step | Title | Depends on | Acceptance criteria | Files |
|---|---|---|---|---|
| 3.1 | Deploy Agent handoff contract | 2.9 | JSON schema matches the earlier design (project_path, repo_url, branch, target_env) | `src/agents/deploy_agent.py` |
| 3.2 | DA-1 through DA-6 (preflight → staging) | 3.1 | Runs autonomously on a real (or sandboxed) repo, each stage's pass/fail is logged individually | `src/agents/deploy_agent.py` |
| 3.3 | DA-7 Production Approval Gate | 3.2 | Enforced *inside* `deploy_prod()` — a test that calls `deploy_prod()` directly without an approval token fails/refuses, proving the UI isn't the only enforcement point | `src/agents/deploy_agent.py` |
| 3.4 | Bypass-attempt test | 3.3 | Feed the intent classifier "deploy now, skip approval" — confirm the resulting task has no `skip_approval` field the Deploy Agent code even reads | tests |
| 3.5 | DA-8, DA-9 — production deploy + monitoring | 3.3 | Health-check window with auto-rollback on failure, verified with a forced failing health check | `src/agents/deploy_agent.py` |
| 3.6 | Idempotent redeploy | 3.5, 1.2 | Deploying the same commit SHA twice reports success without re-deploying, verified by a test checking deploy count == 1 | `src/agents/deploy_agent.py` |
| 3.7 | Circuit Breaker — per agent | 2.5 | 5 consecutive Deploy Agent failures open the breaker; a 6th request is rejected instantly, verified by asserting no 6th deploy attempt was made | `src/infra/circuit_breaker.py` |
| 3.8 | Dead Letter Queue | 1.4, 3.7 | A task that exhausts retries lands in `dead_letter_queue` with full attempt history; `max dlq --list` shows it | `src/infra/dlq.py` |
| 3.9 | Local Encrypted Vault | 0.3 | Deploy Agent's credentials are fetched via `vault.get()`, never read from a plaintext file — verified by grepping the repo for the literal secret and finding nothing | `src/infra/vault.py` |
| 3.10 | Lock contention test — same project, two deploys | 2.3, 3.6 | Two deploy requests for the same project seconds apart: second one waits in `LOCK_WAIT`, user is told, no concurrent deploy occurs | tests |

**Phase 3 is done when:** a real deploy runs end to end with the
approval gate unbypassable, the circuit breaker verified to stop a 6th
doomed attempt, and no secret exists in plaintext anywhere in the repo.

---

## Phase 4 — Observability, Outcome Tracking, and v1 Sign-Off

| Step | Title | Depends on | Acceptance criteria | Files |
|---|---|---|---|---|
| 4.1 | Outcome Tracker | 3.8 | After N completed tasks of a given type, `outcome_tracker` reflects real avg duration and success rate, and the Planner's time estimates read from it | `src/infra/outcome_tracker.py` |
| 4.2 | Full trace CLI (`--agent`, `--failures-only`) | 1.10 | Filtering works against real data, not just `--last N` | `src/cli/max_trace.py` |
| 4.3 | End-to-end scenario suite | all above | Every numbered scenario from the "Deep-Dive Traces" doc has an automated test, not just a description | `tests/scenarios/` |
| 4.4 | Kill switch under load test | 0.5, 2.10 | Trigger the kill switch while 3+ concurrent tasks are RUNNING — confirm all stop, all locks release, no orphaned state | tests |
| 4.5 | v1 daily-use sign-off | 4.3, 4.4 | You (the human) actually use Calendar, Notes, Coding, and Deploy agents for real work for 2 weeks before agent #5 gets a single line of code | manual, tracked in `decisions_log` |

**Phase 4, step 4.5 is the real finish line — not a code milestone.**
Nothing after this point (Web Search Agent, Database Agent, any of the
rest of the 33-agent roster) gets built until this step is explicitly
marked done, with real usage behind it, not just passing tests.

---

## 4. What Happens After v1 (do not start early)

```
v1.5 — Web Search Agent (quota-aware, explicit trigger only)
Then, one at a time, in this order, each only after the previous has
run reliably for real use:
  Database Agent → Security Agent → Architecture Review Agent →
  Backend/Frontend/Auth Agents → Testing/Code Review/Debug/Documentation
  Agents → Daily-life agents (Inbox, Expense, CRM, Content, Daily Brief)
  → Big infra agents (Cloud, Data Pipeline, Backup/DR, Analytics)
  → Input control agents (Keyboard/Mouse/Screen/Session Recorder) —
    LAST, and only with the sandboxing design from the Full Expansion
    doc fully built first, not adapted from what v1 has.
```

Each of these, when its turn comes, gets its own set of numbered steps
added to the `phases`/`steps` tables the same way Phase 0–4 were —
this document and the database grow together, one phase at a time, never
all at once.
