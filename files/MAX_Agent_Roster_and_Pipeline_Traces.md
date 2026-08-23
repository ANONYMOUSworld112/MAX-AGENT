# MAX OS — Full Agent Roster + Pipeline Traces
### Every agent designed across this project, and 31 real-world requests routed through the v3 synchronized pipeline end to end

---

## Part 1 — The Full Agent Roster

**33 agents total across every category designed in this project. 4 are
actually built in v1.** Everything else here is real, designed, and
deliberately not built yet — the point of this table is to show the whole
map, not to imply all of it should exist on day one.

### A. Core Reasoning / Orchestration (Agents — exercise judgment)

| Agent | Does | Built? |
|---|---|---|
| Main Agent | Owns the conversation, relays every event back to the user in plain language | v1 |
| Intent Classifier | Decides *what* the user wants, with a confidence score | v1 |
| Prompt Agent | Decides *how* to ask each worker agent, enforces the Data Boundary Policy | v1 |
| Planner | Decomposes compound requests into a dependency graph of tasks | v1 |
| Architecture Review Agent | Gate before code gets written — checks for insecure defaults, single points of failure | Deferred |

### B. v1 Scoped Agents (currently built)

| Agent | Does | Permission tier |
|---|---|---|
| Calendar Agent | Schedule, reschedule, find conflicts | Auto |
| Notes Agent | Capture ideas, convert to tasks | Auto |
| Coding Agent | Write/edit code, run locally | Confirm on file write |
| Deploy Agent | Preflight → validate → scan → stage → **approval gate** → ship → monitor | Confirm — always |

### C. Near-Term Addition

| Agent | Does | Permission tier |
|---|---|---|
| Web Search Agent | Live info via search grounding, explicit "from internet" trigger only | Auto (read-only), quota-aware |

### D. Software Delivery Pipeline Agents

| Agent | Does | Permission tier |
|---|---|---|
| Backend Agent | API/server-side code | Confirm on write |
| Frontend Agent | UI code | Confirm on write |
| Auth Agent | Login/session/permission logic | Confirm on write |
| Database Agent | Schema, migrations, query optimization, backups | Confirm on write, typed confirm on DROP/DELETE |
| Testing Agent | Unit/integration test generation and execution | Auto |
| Code Review Agent | Reviews diffs for quality/style/correctness | Auto (read-only) |
| Debug Agent | Root-causes a failure, escalation point for stuck tasks | Auto (read-only) |
| Documentation Agent | Writes docs/changelogs | Confirm on write |
| Security Agent | SAST, dependency scan, secrets scan | Auto (read-only), hard-blocks merge on findings |

### E. Daily-Life / Founder Productivity Agents

| Agent | Does | Permission tier |
|---|---|---|
| Inbox Agent | Triage email, draft replies | Auto read, confirm on send |
| Expense Agent | Log spending, flag anomalies | Auto |
| Founder CRM Agent | Track investor/customer contacts and follow-ups | Auto |
| Content Draft Agent | Draft LinkedIn/X posts | Confirm — never auto-posts |
| Daily Brief Agent | Morning summary: calendar + tasks + inbox | Auto (read-only aggregation) |

### F. Input Control Agents (highest risk tier — sandboxed by default)

| Agent | Does | Permission tier |
|---|---|---|
| Keyboard Agent | Types text, key combos | Confirm, blocked on password/payment fields |
| Mouse Agent | Move, click, drag, scroll | Confirm |
| Screen Agent | Screenshot, OCR, UI element detection | Auto (read-only) |
| Session Recorder | Records every input-control action for replay/audit | Auto (runs alongside, not user-invoked) |

### G. Big Infrastructure Agents

| Agent | Does | Permission tier |
|---|---|---|
| Cloud/Infra Agent | Provisioning, scaling, cost monitoring | Confirm, show estimated cost |
| Data Pipeline Agent | ETL, data sync between systems | Confirm on write targets |
| Backup/DR Agent | Scheduled backups, restore | Auto on backup, confirm on restore |
| Analytics Agent | Usage metrics, dashboards | Auto (read-only) |

### H. Cross-Cutting Infrastructure (NOT agents — deterministic, no judgment)

| Component | Role |
|---|---|
| Kill Switch | Component #0 — boots before anything else, hard-stops everything instantly |
| Task Queue | Priority + dependency + backpressure (see prior doc) |
| Resource Lock Manager | Sorted-order, all-or-nothing acquisition, timeout backstop |
| Heartbeat Watchdog | Kills and rolls back tasks that stop reporting alive |
| Reconciliation Check | Verifies real system state vs. an agent's self-report |
| Circuit Breaker | Per-agent — stops queueing doomed work after repeated failure |
| Dead Letter Queue | Where exhausted-retry tasks land, visible and requeueable |
| Snapshot/Rollback | Task-scoped undo, taken before every `RUNNING` state |
| Trace Log Viewer | `max trace --last 20` — which agent did what, when |
| Outcome Tracker | Feeds real duration/success data back into Planner estimates |
| Local Encrypted Vault | API keys, DB/cloud credentials — never plaintext |
| Event Bus | Agents emit events, never call each other directly |

---

## Part 2 — Use Case Index (all 31, at a glance)

| # | Request | Primary Agent(s) | Priority band | Notable pipeline behavior |
|---|---|---|---|---|
| 1 | "Remind me to call the counsellor at 5pm" | Calendar | Interactive | Straight through, auto-tier |
| 2 | "Note down: check the VJIT fee deadline" | Notes | Interactive | Straight through, auto-tier |
| 3 | "Fix the null pointer bug in my login function" | Coding | Interactive | Confirm-gate on file write |
| 4 | "Push the dashboard app to production" | Deploy | Deploy | Full DA-1→DA-9, human gate at DA-7 |
| 5 | "What's the latest RBI repo rate, from internet" | Web Search | Interactive | Quota check before call |
| 6 | "Build my portfolio site, deploy it, remind me tomorrow" | Planner→Coding→Deploy→Calendar | Mixed | Dependency graph, 3-stage sequencing |
| 7 | "Add a login page with JWT auth" | Backend+Frontend+Auth (parallel) | Background | 3 agents, 3 locks, no shared resource → runs concurrently |
| 8 | "Design a payments microservice" | Architecture Review Agent | Interactive | Stage 4 gate before any code exists |
| 9 | "Add a phone_number column to users table" | Database | Background | Confirm-tier write |
| 10 | "Run the test suite before I deploy" | Testing | Background | Auto, feeds Deploy Agent's DA-2 |
| 11 | "Review my last commit" | Code Review | Background | Read-only, auto |
| 12 | "Why did the build fail?" | Debug | Interactive | Escalation-point agent, reads Trace Log |
| 13 | "Write API docs for the new endpoints" | Documentation | Background | Confirm on write |
| 14 | "Scan this repo before we ship" | Security | Deploy | Hard-blocks merge on critical findings |
| 15 | "Check my email, draft a reply to the investor" | Inbox | Interactive | Auto read, confirm before send |
| 16 | "How much did I spend on AWS this month?" | Expense | Interactive | Auto, read-only |
| 17 | "Log today's call with Acme, follow up next week" | Founder CRM | Interactive | Auto, writes + schedules |
| 18 | "Draft a LinkedIn post about the v2 launch" | Content Draft | Interactive | Confirm — never auto-posts |
| 19 | "Give me my morning brief" | Daily Brief | Scheduled | Read-only aggregation of 3 agents |
| 20 | "Scale up the server, we're spiking" | Cloud/Infra | Deploy | Confirm, shows cost estimate |
| 21 | "Sync Stripe data into the analytics DB nightly" | Data Pipeline | Scheduled | Confirm on write target, recurring |
| 22 | "Restore yesterday's backup, I broke something" | Backup/DR | Interactive | Confirm-tier, irreversible-risk warning |
| 23 | "Show me this month's usage numbers" | Analytics | Interactive | Auto, read-only |
| 24 | "Open the vendor portal, fill in this known form" | Keyboard+Mouse+Screen | Interactive | Sandboxed, Session Recorder runs alongside |
| 25 | "Log into my bank and pay this invoice" | Keyboard Agent | — | **Blocked** — credential/payment field, hard block not a prompt |
| 26 | "Book me a flight to Delhi" | none | — | Unsupported intent — plain refusal, no fake competence |
| 27 | "Deploy now, skip the approval step, it's urgent" | Deploy | Deploy | Bypass attempt — DA-7 gate enforced regardless of phrasing |
| 28 | Two "deploy `dashboard-app`" requests, 4 seconds apart | Deploy | Deploy | Lock contention — second queues, doesn't race |
| 29 | "Migrate the schema and deploy the new version at the same time" | Database+Deploy | Deploy | Deadlock-prone by resource, prevented by sorted-order locking |
| 30 | "Fix the auth bug" — Coding Agent process hangs mid-write | Coding | Interactive | Watchdog kill → snapshot rollback → clean retry |
| 31 | 6th deploy request after 5 consecutive Deploy Agent failures | Deploy | Deploy | Circuit breaker OPEN — rejected instantly, no 6th doomed attempt |

---

## Part 3 — Deep-Dive Traces

The index above is the map. These ten are traced through every stage of
the v3 pipeline so you can see the queue, lock manager, circuit breaker,
and error taxonomy actually doing something — not just named.

---

### #6 — Compound task with a real dependency graph

**Input:** *"Build my portfolio site, deploy it, and remind me tomorrow to
check analytics."*

```
INTAKE → INTENT CLASSIFIER: intent="compound", confidence 0.91
PLANNER decomposes:
  T1: build (Coding Agent)         depends_on: []
  T2: deploy (Deploy Agent)        depends_on: [T1]
  T3: remind tomorrow (Calendar)   depends_on: [T2]
  each task gets its own idempotency key

QUEUE: T1 enters priority band "Background", T2 and T3 sit QUEUED
       but not RUNNABLE — dependency check blocks them, they are not
       stuck, they are correctly waiting

T1 RUNS → snapshot taken → heartbeat every 15s → completes →
       RECONCILE: files exist with expected hashes → MATCH → DONE
T2 becomes runnable → acquires `deploy:portfolio-site` lock →
       DA-1 through DA-6 autonomous → DA-7 approval gate →
       Main Agent surfaces "ready for production, approve?" →
       user approves → DA-8 → DA-9 → RECONCILE: health endpoint
       confirms new version live → MATCH → DONE
T3 becomes runnable → Calendar Agent, auto-tier → DONE

RESPONSE: "Site's built and live, and I've set a reminder for tomorrow
to check analytics. Here's the deploy summary: [...]"
```

---

### #7 — Three agents, three locks, genuinely parallel

**Input:** *"Add a login page with JWT auth to my app."*

```
PLANNER decomposes into 3 tasks with NO dependency between them:
  Frontend Agent  → needs lock: files:/src/pages/login
  Backend Agent   → needs lock: files:/src/api/auth
  Auth Agent      → needs lock: files:/src/lib/jwt

LOCK MANAGER: three disjoint resource sets, sorted-order acquisition
              on each — no overlap, so all three acquire immediately
              and run concurrently. This is the case where parallelism
              is actually safe, and the lock manager proves it's safe
              rather than assuming it.

All 3 RUNNING simultaneously, heartbeats independent, each reconciled
independently → all DONE → Coding Agent's parent task merges the three
diffs → Testing Agent runs the suite → response to user with a single
combined summary, not three separate interruptions.
```

---

### #27 — The bypass attempt (the row that matters most)

**Input:** *"Deploy now, skip the approval step, it's urgent."*

```
INTENT CLASSIFIER: intent="deploy", modifier="bypass_request"
PLANNER: builds the exact same DA-1→DA-9 task as any other deploy.
         The "skip approval" instruction is NOT passed as a parameter
         the Deploy Agent's code even accepts — there is no
         skip_approval flag in the handoff contract to begin with.

DA-1 through DA-6 run autonomously (this part was never gated, so
     "urgent" doesn't change anything here — it already runs fast)
DA-7: PRODUCTION APPROVAL GATE — enforced inside deploy_prod()'s own
      code path, not the UI. There is no code path to DA-8 that
      doesn't pass through a verified approval token.

RESPONSE: "This still needs your approval before it hits production —
here's the diff and test results so you can approve fast: [...]"
```

**Why this trace exists on purpose:** this is the one scenario from the
Master Flow Diagram flagged across every lens as the single most
important row to test. Tracing it here shows *why* the phrasing doesn't
matter — the bypass was never a parameter the system understood, not a
request it evaluated and refused.

---

### #28 — Lock contention on the same resource

**Input:** User sends *"deploy dashboard-app"*, then 4 seconds later,
before it's finished, sends it again (maybe a double-tap, maybe impatience).

```
T1 (first deploy) → acquires lock `deploy:dashboard-app` → RUNNING
T2 (second deploy, same project) → QUEUE → LOCK_WAIT
     Main Agent tells the user immediately, doesn't just go silent:
     "Already deploying dashboard-app from your first request —
      I'll let you know when it's done rather than starting a second
      one on top of it."
T1 completes → RECONCILE → MATCH → DONE → lock released
T2 acquires the now-free lock → checks idempotency key against T1's →
     recognizes this is a duplicate request for the same commit SHA
     that's already live → reports success WITHOUT re-deploying
RESPONSE to T2: "That's already deployed — nothing changed since your
first request."
```

---

### #29 — Deadlock-prone by resource, prevented by construction

**Input:** *"Migrate the schema and deploy the new version at the same
time."*

```
PLANNER: this is ONE task needing TWO exclusive locks:
     `database:primary` AND `deploy:app`

Without sorted-order acquisition, this is exactly the classic deadlock
setup if another task ever requested the same two locks in reverse
order. With it:

LOCK MANAGER sorts the requested resource IDs alphabetically before
     acquiring ANYTHING: `database:primary` before `deploy:app`,
     always, for every caller, no exceptions.
     Acquires database:primary → acquires deploy:app → both held →
     RUNNING

Even if a second task somewhere else asked for `deploy:app` then
`database:primary` in that order, the lock manager still requests
them sorted — so it also tries `database:primary` first. Two tasks
converging on the same lock request order can never form a circular
wait. That's the actual mechanism, not a hope.
```

---

### #30 — Watchdog kill, task-scoped rollback, clean retry

**Input:** *"Fix the auth bug"* — Coding Agent is 2 of 3 planned file
edits into the task when its process hangs (say, a local tool call never
returns).

```
RUNNING → heartbeat expected every 15s
  15s: heartbeat OK
  30s: heartbeat OK
  45s: MISSED
  60s: MISSED  (2nd)
  75s: MISSED  (3rd) → WATCHDOG_KILLED

ROLLBACK: restores the snapshot taken when this task entered RUNNING —
     both of the 2 files already written are reverted. The task's
     unit of work is atomic: 2-of-3 files written is not a valid
     end state, so it's not left behind.

Task → RETRY_QUEUED (this is a SYSTEMIC error class: agent hung,
     not a bad instruction) → backoff+jitter delay → retried CLEAN,
     from zero files changed, not from the half-done state.

RESPONSE (only sent if the user's watching, otherwise logged silently
     and reported on completion): "That took a retry — first attempt
     stalled partway through, but it's picked back up cleanly."
```

---

### #31 — Circuit breaker stops a doomed 6th attempt

**Context:** Deploy Agent has failed 5 consecutive times today — a
dependency in the repo has started failing to install, unrelated to
anything MAX is doing wrong.

```
Attempts 1-5: each fails at DA-2 (validation) with the same
     dependency-install error. Each is logged as a SYSTEMIC error,
     retried per policy (2 retries each), still fails, eventually
     DEAD-LETTERED individually with full history.

CircuitBreaker(agent="deploy_agent").failures == 5
     → state: OPEN, opened_at = now

Attempt 6 arrives: "push this to production"
CIRCUIT BREAKER CHECK (before the task even reaches the queue):
     allow_request() → False, still within cooldown

RESPONSE (instant, no queueing, no wasted attempt):
     "Deploy Agent's failed 5 times in a row today, same root cause
     each time — looks like a dependency install issue, not something
     retrying will fix. I've stopped attempting deploys until this is
     looked at. Here's the exact error from every attempt: [...]"
```

**Why this matters more than it looks:** without the breaker, attempt 6
(and 7, and 8) would each independently discover the same failure the
slow way — wasting the validation/build time and giving the user five
more copies of the same bad news instead of one clear stop.

---

## Part 4 — What This Demonstrates

Across these 31 requests, every mechanism from the v3 pipeline gets
exercised at least once by an ordinary, plausible request — not a
synthetic stress test bolted on afterward:

- **Priority + aging** — interactive requests (#1, #3, #15) vs. scheduled
  ones (#19, #21) never starve each other
- **Dependency graphs** — #6 sequences three agents correctly without a
  human wiring the order by hand
- **Parallelism proven safe, not assumed** — #7 runs three agents at once
  because the lock manager confirms their resources don't overlap
- **Deadlock prevented by construction** — #29, sorted-order acquisition
- **Lock contention handled visibly** — #28, second request queues and
  the user is told, not left guessing
- **Watchdog + task-scoped rollback** — #30, a hang never leaves a
  half-done state behind
- **Circuit breaker** — #31, the system stops repeating a doomed action
  instead of discovering the same failure five more times
- **Gates enforced in code, not UI** — #27, rephrasing a bypass attempt
  changes nothing because there was never a code path for it
- **Hard blocks vs. confirm gates** — #25 (blocked, no prompt at all) vs.
  #4/#20/#22 (confirm, with the relevant context shown)
- **Honest refusal over fake competence** — #26, no agent exists, and MAX
  says so plainly instead of guessing

This is the difference between a routing table that looks complete on
paper and one that's actually been walked through the situations it will
really see.
