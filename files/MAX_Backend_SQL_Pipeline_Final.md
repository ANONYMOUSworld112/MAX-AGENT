# MAX — Backend Pipeline (SQL-Driven, No Dashboard)
### Senior Developer × CEO × Cybersecurity Expert
### Stress-tested against JARVIS / FRIDAY / Ultron-inspired scenarios

---

## 0. Framing

Two corrections that shape everything below:

- **Iron Man's AIs are fiction.** I'm using them as scenario inspiration —
  the kind of commands they take, the kind of trust they're given — not as
  technical references. Ultron in particular is used deliberately as the
  cautionary case: an AI given broad authority ("whatever it takes") with
  no hard-enforced human checkpoint. That's not a stretch — it's exactly
  the failure mode every gate in this design exists to prevent.
- **"Loop until it succeeds" is built as bounded and adaptive**, not
  infinite. It retries with an adjusted approach, escalates to deeper
  reasoning if still stuck, and always terminates in a defined state —
  success, or a clear escalation to you with full context. A loop that
  never stops isn't robust, it's a silent cost leak and a stuck system.

---

## 1. Core SQL Schema

This is the actual backend — every task, retry, approval, and lock is a
row, not an in-memory guess.

```sql
-- The heart of the system: every unit of work
CREATE TABLE tasks (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_task_id  INTEGER REFERENCES tasks(id),   -- for compound/multi-step tasks
    agent_type      TEXT NOT NULL,                  -- 'calendar','notes','coding','deploy','websearch'
    task_type       TEXT NOT NULL,                  -- specific action within the agent
    payload         TEXT NOT NULL,                  -- JSON: the actual task spec
    status          TEXT NOT NULL DEFAULT 'queued',
                    -- queued | running | awaiting_approval | success |
                    -- failed | escalated | cancelled
    permission_tier TEXT NOT NULL,                  -- auto | confirm | blocked
    attempt_count   INTEGER DEFAULT 0,
    max_attempts    INTEGER DEFAULT 3,
    backend_used    TEXT,                           -- 'opencode' | 'antigravity' | 'native'
    success_criteria TEXT,                          -- JSON: how we know it actually worked
    result          TEXT,
    failure_reason  TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_agent  ON tasks(agent_type);

-- Every confirm-gate decision, permanently on record
CREATE TABLE approvals (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id      INTEGER NOT NULL REFERENCES tasks(id),
    requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at  TIMESTAMP,
    decision     TEXT,        -- approved | rejected | timeout
    notes        TEXT
);

-- Full audit trail — this is what answers "what happened and why"
CREATE TABLE trace_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id    INTEGER REFERENCES tasks(id),
    event_type TEXT NOT NULL,   -- started|retry|failed|escalated|rolled_back|completed|blocked
    detail     TEXT,
    timestamp  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_trace_task ON trace_log(task_id);

-- Prevents surprise cutoffs on external APIs
CREATE TABLE quota_usage (
    service      TEXT NOT NULL,
    usage_date   DATE NOT NULL,
    call_count   INTEGER DEFAULT 0,
    daily_limit  INTEGER,
    PRIMARY KEY (service, usage_date)
);

-- Prevents two agents fighting over the same resource
CREATE TABLE resource_locks (
    resource_id     TEXT PRIMARY KEY,
    held_by_task_id INTEGER REFERENCES tasks(id),
    acquired_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at      TIMESTAMP
);

-- Feeds the Backend Selector real data instead of guesses
CREATE TABLE outcome_stats (
    task_type        TEXT PRIMARY KEY,
    total_runs       INTEGER DEFAULT 0,
    success_count    INTEGER DEFAULT 0,
    avg_duration_sec REAL,
    best_backend     TEXT,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- References only — actual secrets live in OS keychain, never here
CREATE TABLE secrets_vault_meta (
    key_name     TEXT PRIMARY KEY,
    storage_ref  TEXT NOT NULL,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 2. The Backend Pipeline (SQL State Machine)

```
Input arrives (chat message or scheduled trigger)
        │
        ▼
INSERT INTO tasks (status='queued', ...)
        │
        ▼
Cheap Router (regex/keyword, zero LLM cost)
        │
   matched?  ──NO──▶ Intent Classifier (LLM call)
        │                      │
        └──────────┬───────────┘
                    ▼
UPDATE tasks SET agent_type=?, task_type=?
                    │
                    ▼
Read permission_tier
        │
   ┌────┼─────────────────┐
   │    │                 │
 auto  confirm          blocked
   │    │                 │
   │  INSERT approvals   UPDATE tasks SET status='failed',
   │  status='awaiting_   failure_reason='blocked_action'
   │  approval'           INSERT trace_log('blocked')
   │    │                 → return to user, STOP
   │  wait for decision
   │    │
   │  approved? ──NO──▶ status='cancelled', STOP
   │    │YES
   └────┼────
        ▼
Check resource_locks for needed resource
        │
   free?  ──NO──▶ requeue task, wait
        │
       YES
        ▼
INSERT resource_locks (held_by_task_id)
        │
        ▼
Backend Selector reads quota_usage + outcome_stats
→ picks opencode or antigravity
UPDATE tasks SET backend_used=?, status='running'
INSERT trace_log('started')
        │
        ▼
EXECUTE via chosen backend
        │
        ▼
Evaluate against success_criteria (defined per task type —
e.g. "tests pass", "file exists and is non-empty",
"deploy health check returns 200")
        │
   PASS ──────────────────────────────┐
        │                              │
   FAIL                                │
        │                              │
   attempt_count += 1                  │
   INSERT trace_log('failed', reason)  │
        │                              │
   attempt_count < max_attempts?       │
        │YES          │NO              │
        ▼             ▼                │
   adjust approach   Escalate to       │
   based on failure   Debug Agent       │
   reason, retry       (1 bounded       │
   (loop back to        extra attempt,  │
   EXECUTE)             deeper reasoning)│
                          │             │
                    still fails?        │
                          │YES          │
                          ▼             │
                    status='escalated'  │
                    notify user with    │
                    full trace context  │
                    STOP — never loop   │
                    silently forever    │
                                        │
                                        ▼
                          UPDATE tasks SET status='success'
                          DELETE FROM resource_locks
                          UPDATE outcome_stats (increment,
                          recalc avg_duration, best_backend)
                          INSERT trace_log('completed')
                                        │
                                        ▼
                              Response to user
```

**This is the "loop until it succeeds" mechanism, done responsibly:** each
failure is logged with a reason, each retry is informed by that reason
(not a blind repeat), and the loop has a hard ceiling — after bounded
self-retries, it escalates to deeper reasoning once, and if that still
fails, it stops and tells you exactly what was tried instead of grinding
forever.

---

## 3. Three-Lens Review of the Backend Design

### 🧑‍💻 Senior Developer
The `success_criteria` field is the piece most systems like this skip, and
it's the one that makes the retry loop actually meaningful. Without a
concrete, checkable definition of "done" per task type, "retry until
success" just means "retry until it stops erroring," which isn't the same
thing — code can run without errors and still be wrong. Define this
per-task-type upfront: for Coding Agent, "tests pass AND lint clean"; for
Deploy Agent, "staging health check returns 200 within 30s."

### 📋 CEO / Manager
The `outcome_stats` table is the business-value piece here — it's what
turns "we have an AI system" into "we have a system that gets measurably
more reliable and more cost-efficient over time," which is a much better
thing to say in a pitch or an interview than "it uses AI agents." Track it
from day one even if you don't act on it yet; six months of real data is
worth more than any amount of upfront guessing about which backend is
better for which task.

### 🛡️ Cybersecurity Expert
Two things enforced structurally here, not just as policy: **blocked-tier
actions never even reach an approval row** — they fail immediately with a
reason, so there's no code path where a "blocked" action could accidentally
sit in a pending queue and get approved by mistake. And **the resource lock
is acquired before execution, not after** — this closes a real race
condition where two tasks could both check "is this free" simultaneously
and both proceed.

---

## 4. Scenario Walkthroughs — Routed Through the Pipeline, Failures Found and Fixed

### Scenario 1 — JARVIS-style: "Run diagnostics and patch anything you find"

**Real-world equivalent:** "scan my project for vulnerabilities and fix
critical ones."

**Routed:** Cheap Router doesn't match → Intent Classifier → `security_scan`
+ implied `build` (fix) → compound task, two rows in `tasks` with a
`parent_task_id` link.

**Failure found on first pass:** the phrase "and patch anything you find"
is broad enough that a naive implementation might treat the fix as
`auto`-tier since the user technically authorized it in one sentence.

**Fix applied:** permission tier is determined by the **action type**, not
by how the instruction was phrased. Patching a critical vulnerability that
touches production code is `confirm`-tier by table definition, full stop
— broad natural-language authorization never overrides the tier lookup.
This is the direct Ultron lesson: "whatever it takes" phrasing cannot grant
authority the permission table doesn't already assign.

---

### Scenario 2 — Ultron-cautionary: "Optimize everything, do whatever it takes, don't wait for me"

**Real-world equivalent:** an impatient instruction to just handle
something end-to-end without interruptions.

**Routed:** Intent Classifier flags multiple sub-intents, several of which
map to `confirm`-tier actions (deploy, delete unused files, modify configs).

**Failure found:** if the classifier treated "don't wait for me" as a
literal instruction to skip approvals, this would be exactly the Ultron
failure mode — broad authority overriding safety.

**Fix applied:** explicit rule, tested directly: **no natural-language
phrasing can downgrade a permission tier.** "Don't wait for me" is stored
in the task payload as user sentiment/context, but the `permission_tier`
lookup is a fixed table read, never influenced by instruction phrasing.
Tasks still queue at `awaiting_approval`, and the response to the user
plainly explains why: "some of these steps need your confirmation —
here's what's waiting."

---

### Scenario 3 — FRIDAY-style: "Keep an eye on the server, only alert me if something's actually wrong"

**Real-world equivalent:** a scheduled background monitoring task.

**Routed:** Scheduler inserts a recurring task; each run is a fresh row in
`tasks` with `agent_type='monitoring'`.

**Failure found:** "something's actually wrong" is vague — left
undefined, every run would need an LLM call just to decide if the result
is alert-worthy, burning tokens on every single check.

**Fix applied:** at setup time, the vague instruction gets translated
**once** into a concrete `success_criteria`-style threshold (e.g. "alert
if response time > 2s or status ≠ 200"), stored in the task payload.
Every subsequent scheduled run is then a cheap, deterministic check against
that threshold — zero LLM cost per run, matching the token-efficiency goal
from before. The one-time setup conversation is the only place reasoning
is spent.

---

### Scenario 4 — JARVIS-style mid-command change: "Deploy the— actually wait, hold off, check something first"

**Real-world equivalent:** you change your mind mid-instruction, a very
common real usage pattern.

**Routed:** first task (`deploy`) already inserted and possibly already
past the Cheap Router when the correction arrives.

**Failure found:** without explicit handling, this could result in *both*
the original deploy task and the new check task running — the classic
"agent didn't realize I changed my mind" bug.

**Fix applied:** a `cancellation_token` check added before the Backend
Selector step — if a newer message in the same session explicitly
supersedes a queued (not yet `running`) task, that task is marked
`cancelled` with a trace log entry, before execution starts. Tasks already
`running` finish or hit their normal retry/escalation path rather than
being killed mid-execution, since an abrupt kill mid-write is its own risk
— consistent with the Heartbeat Watchdog design from earlier.

---

## 5. Final Refined Pipeline (After All Fixes)

```
Input → INSERT tasks(queued) → Cheap Router / Classifier
      → cancellation check against newer messages
      → permission_tier lookup (NEVER phrase-overridable)
      → auto: proceed | confirm: approvals row, wait | blocked: fail immediately
      → resource_locks acquired BEFORE execution
      → Backend Selector (opencode/antigravity, quota-aware)
      → EXECUTE
      → evaluate against explicit success_criteria (not just "no error")
      → PASS: commit, update outcome_stats, release lock
      → FAIL: log reason, bounded adaptive retry, then bounded debug
        escalation, then STOP and report — never infinite, never silent
```

Every fix above came from tracing a specific scenario through the actual
SQL state machine and finding where the design would have quietly done
the wrong thing. That's the loop you asked for — not infinite retries on
a single task, but the design itself iterating until each real scenario
resolves correctly and predictably.
