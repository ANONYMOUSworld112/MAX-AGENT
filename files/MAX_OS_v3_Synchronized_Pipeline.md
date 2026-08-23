# MAX OS v3 — The Synchronized, Fault-Tolerant Pipeline
### Reviewed and rebuilt as: Staff Engineer who has to run this at 2am · CEO who has to explain it to a board · Tony Stark, who does not accept "JARVIS just kind of got confused"

---

## 0. The Honest Diagnosis First

Before adding anything, here's what's actually wrong with the queue and
error handling in the v2 design, said plainly instead of politely:

| What v2 has | Why it's not enough |
|---|---|
| `asyncio.Queue`, first-in-first-out | No priority. A "remind me in 5 min" and a "deploy to prod NOW" wait in the same line. |
| "Resource Lock Manager" — named, not designed | Doesn't say *how* locks are acquired, what happens on timeout, or how deadlock is prevented when a task needs two resources at once. |
| "retry (max 3, exponential backoff)" | One policy for every error. A typo in user input and a network blip are not the same failure and should not be retried the same way — or at all, in the typo's case. |
| Heartbeat Watchdog — kills and rolls back | Rolls back *what*, exactly? A task that already wrote 3 of 4 files needs a defined unit of rollback, not "undo something." |
| No dead-letter concept | A task that fails 3 times just... stops. Where does it go? Who sees it? |
| No idempotency | If a retried task re-runs a deploy that half-succeeded the first time, does it deploy twice? Nothing says it won't. |

None of this was wrong as a v1 sketch — it was intentionally left thin
because the correct call at the time was to prove the loop first. This
document is the "prove the loop" phase graduating into "now make it not
fall over when three things happen at once," which is exactly the
question a real production system has to answer before it earns the word
"OS" in its name.

**One scope correction up front:** the earlier verdict deferred the Event
Bus, Lock Manager, Watchdog, and Reconciliation Check to "v1.5+" because
*agent breadth* was the thing to cut. That advice still holds — don't add
agent #5 yet. But queueing, locking, and error handling aren't a 5th
agent. They're the floor the 4 agents you already have stand on. Getting
this layer right on day one is cheaper than retrofitting it after you've
shipped bugs on top of a queue that silently drops things. Stark doesn't
bolt the arc reactor on after the suit's built — it's the thing everything
else plugs into.

---

## 1. Task Lifecycle — One State Machine for Every Task, Every Agent

Every task in MAX, regardless of which agent handles it, moves through
exactly these states. No agent gets to invent its own lifecycle.

```
CREATED
   │  (validated, has an idempotency key)
   ▼
QUEUED ───────────────────────────────────────────┐
   │  (priority + dependencies satisfied,           │
   │   queue not over capacity)                      │
   ▼                                                 │
LOCK_WAIT ◄──── resource busy ────────────────────┤
   │  (all required locks acquired, in sorted order) │
   ▼                                                 │
RUNNING ──── heartbeat missed N times ────► WATCHDOG_KILLED
   │                                                 │
   │  agent reports completion                       ▼
   ▼                                          ROLLBACK (unit-scoped,
RECONCILING                                    see §4.4)
   │  (real system state checked against            │
   │   what the agent reported)                      ▼
   ├── MATCH ──────────► DONE ─► locks released   RETRY_QUEUED
   │                        │                         │
   │                        ▼                    (policy allows?)
   │                  response to user            │        │
   │                                              YES      NO
   └── MISMATCH ──────► ROLLBACK ─────────────────┘        ▼
                                                          DEAD
                                                    (Dead Letter Queue)
```

**Every arrow is named.** Nothing transitions silently, and nothing sits
in an undefined state waiting for someone to notice.

---

## 2. Upgrade #1 — The Queue Actually Does Its Job

### 2.1 Priority isn't a suggestion, it's a number with rules

```
Priority bands (highest to lowest):
  0  — Kill Switch / safety actions           (never queues, executes immediately)
  1  — User-initiated, interactive            ("do this now" — user is watching)
  2  — Deploy / production-impacting          (time-sensitive, but always gated anyway)
  3  — Background agent work                  (build steps, scans, non-blocking)
  4  — Scheduled / recurring                  (daily brief, backups)
```

### 2.2 Starvation prevention — aging

A low-priority task that's waited more than 60 seconds gets its effective
priority boosted by one band. This is the fix for the obvious failure
mode: someone spamming "deploy" requests should never permanently starve
a background scan that's been waiting politely. Aging is recalculated
every time the queue is read, not on a separate timer — one less moving
part to get out of sync.

### 2.3 Dependency-aware, not just FIFO-within-priority

A task can declare `depends_on: [task_id, ...]`. The queue will not hand
a task to a worker until every dependency is in a terminal success state.
This is what makes "build it, then deploy it, then tell me" work
correctly without a human wiring the sequence by hand — the Planner
declares the dependency graph once, and the queue enforces it forever
after.

### 2.4 Backpressure — the queue can say no

```
MAX_QUEUE_DEPTH = 500

if queue.depth() >= MAX_QUEUE_DEPTH:
    reject_with_message(
        "I've got too much queued right now — this one's on hold. "
        "Want me to drop something lower priority to make room, or wait?"
    )
```

A full queue rejects *loudly*, with a message the user actually sees and
can act on. The one thing it's never allowed to do is drop a task
silently to make room — that's how "I asked it to do X three hours ago
and it just... didn't" happens, which is the single fastest way to lose
trust in an assistant.

### 2.5 Idempotency — retries can't duplicate side effects

Every task gets a UUID idempotency key at creation. Agents with real-world
side effects (Deploy, Calendar, Inbox) are required to check "have I
already done this exact idempotency key?" before acting — not just before
the whole task, but before each side-effecting sub-step. This is the fix
for "the watchdog killed it after the deploy actually succeeded, so the
retry deployed it a second time." Concretely: the Deploy Agent's `DA-8`
production-deploy step checks the target's currently-live commit SHA
before deploying — if it already matches, it reports success without
re-running.

---

## 3. Upgrade #2 — Synchronization That Actually Prevents Deadlock

### 3.1 The real problem with "just add a lock manager"

Naming a Resource Lock Manager doesn't prevent deadlock. Deadlock happens
when Task A holds lock 1 and wants lock 2, while Task B holds lock 2 and
wants lock 1 — both wait forever. This is the classic failure mode of any
system with more than one lockable resource, and it's exactly the
situation MAX creates the moment a compound task needs, say, both the
`database` resource and the `deploy` resource at once.

### 3.2 The fix — global lock ordering + timeout, not just "acquire and hope"

```python
class ResourceLockManager:
    """
    Two independent deadlock defenses, not one:
      1. Every caller acquires locks in the SAME sorted order, always.
         Circular wait is mathematically impossible if every task
         requests resource A before resource B, never the reverse.
      2. A timeout backstop in case anything still gets stuck for a
         reason ordering doesn't cover (e.g. a lock holder crashed
         without releasing).
    """
    def __init__(self):
        self._locks: dict[str, threading.Lock] = {}
        self._registry_lock = threading.Lock()

    def _get(self, resource_id: str) -> threading.Lock:
        with self._registry_lock:
            return self._locks.setdefault(resource_id, threading.Lock())

    def acquire_all(self, resource_ids: list[str], timeout: float = 10.0):
        acquired = []
        for rid in sorted(resource_ids):          # global ordering — the actual fix
            lock = self._get(rid)
            if lock.acquire(timeout=timeout):
                acquired.append(lock)
            else:
                for held in acquired:              # all-or-nothing acquisition
                    held.release()
                return False                        # caller goes back to LOCK_WAIT, queues
        return True
```

**Why "all-or-nothing" matters as much as ordering:** a task either gets
every lock it needs or none of them. There's no partial-acquisition state
where a task is quietly sitting on one resource waiting for another —
that half-locked state is where most real-world lock bugs live.

### 3.3 Lock types — not everything needs exclusivity

| Lock type | Used for | Behavior |
|---|---|---|
| Exclusive | Deploy, DB write/migration, file write, keyboard/mouse | One holder, everyone else queues |
| Shared (read) | DB read, file read, screenshot | Many simultaneous holders, blocks only against an exclusive request |

Making read operations shared-lockable instead of exclusive-lockable is a
small change that removes most of the artificial queueing — two agents
reading the database at once is fine and shouldn't wait on each other.

### 3.4 Heartbeat Watchdog — now with a defined rollback unit

The watchdog doesn't just "kill and roll back" — it rolls back to the
**snapshot taken when the task entered `RUNNING`**, which is task-scoped,
not agent-scoped or project-scoped. A stuck task never takes down more
than the unit of work it owns.

```
Heartbeat contract:
  agent must call heartbeat() at least every 15s while RUNNING
  3 missed heartbeats (45s) → WATCHDOG_KILLED
  → snapshot restored → locks released → task → RETRY_QUEUED or DEAD
```

### 3.5 Reconciliation — never trust the agent's self-report

```
agent reports: { "status": "success", "result": {...} }
        │
        ▼
Reconciliation Check queries REAL state:
  - Deploy Agent said "deployed" → does the health endpoint actually
    return the new version?
  - Coding Agent said "file written" → does the file exist with the
    expected content hash?
  - Calendar Agent said "event created" → does a GET on the calendar
    API actually show it?
        │
   MATCH ──► DONE          MISMATCH ──► treat as a SYSTEMIC error
                                        (see §4), not a success
```

This single check is what turns "looks synchronized" into "is actually
synchronized" — an agent hallucinating success is a real failure mode for
LLM-driven agents specifically, more than for traditional software, and
it's the one v2 didn't have a concrete check for.

---

## 4. Upgrade #3 — Error Handling With an Actual Taxonomy

### 4.1 Every error gets classified before anything decides what to do with it

| Class | Example | Retry? | Who decides what happens next |
|---|---|---|---|
| **Transient** | Network timeout, API rate limit, temporary lock contention | Yes — bounded | System, automatically |
| **Validation** | Malformed input, file doesn't exist, bad syntax in generated code | No | System fails fast, tells user exactly what was wrong |
| **Permission** | Blocked-tier action attempted (e.g. typing into a password field) | No | System refuses, explains why, logs the attempt |
| **Destructive-risk** | Action needs a confirm-gate that hasn't been passed | No | System escalates to the gate, does not proceed or retry around it |
| **Systemic** | Agent crashed, reconciliation mismatch, repeated failure of the same task | Limited (2x) then escalate | Circuit breaker + Debug Agent, then user with full context |

**The rule that actually matters:** retrying is the *exception*, not the
default. v2's "retry max 3" applied to everything, which means a bad user
input would get retried three times before failing — wasted time and a
worse error message. Under this taxonomy, a `VALIDATION` error fails
immediately with a clear reason; only `TRANSIENT` and `SYSTEMIC` errors
ever see a retry loop at all.

### 4.2 Retry policy — exponential backoff with full jitter, per class

```python
RETRY_POLICY = {
    ErrorClass.TRANSIENT: dict(max_retries=3, base=1.0,  cap=30.0),
    ErrorClass.SYSTEMIC:  dict(max_retries=2, base=5.0,  cap=60.0),
    # VALIDATION, PERMISSION, DESTRUCTIVE_RISK: max_retries=0, no policy needed
}

def backoff_delay(attempt: int, base: float, cap: float) -> float:
    # FULL jitter, not just "add some randomness" — this is the version
    # that actually prevents synchronized retry storms when several
    # tasks fail at once (e.g. an LLM API outage hits 5 agents simultaneously).
    return random.uniform(0, min(cap, base * (2 ** attempt)))
```

**Why jitter matters at all:** without it, five agents that all fail at
the same moment (say, the LLM API blips) all retry at exactly 1s, 2s, 4s
— synchronized, hammering the API in unison right when it's already
struggling. Full jitter spreads retries out so a transient outage doesn't
turn into a self-inflicted thundering herd.

### 4.3 Circuit breaker — per agent, not global

If Deploy Agent fails 5 times in a row (not 5 different tasks — 5
consecutive), the circuit **opens**: every new deploy task is rejected
immediately with "Deploy Agent is unhealthy right now, not attempting
further deploys until this is investigated" instead of queueing more
doomed attempts. After a cooldown, one test task is allowed through
(**half-open**) — if it succeeds, the circuit closes; if not, it reopens
for a longer cooldown.

```
CLOSED ──(5 consecutive failures)──► OPEN ──(cooldown elapses)──► HALF_OPEN
   ▲                                                                  │
   └──────────────── one test task succeeds ◄────────────────────────┘
                              │
                    test task fails → back to OPEN, longer cooldown
```

This is scoped **per agent type**, not globally — Deploy Agent tripping
its breaker shouldn't stop Calendar Agent from working. Independent
failure domains, same as the "agent isolation" principle from the
original design, just actually enforced now.

### 4.4 Rollback — atomic at the task boundary, honest about what can't roll back

```
Reversible side effects (safe to auto-rollback):
  - File writes within a task           → snapshot restore
  - DB writes wrapped in a transaction   → transaction abort
  - Staging deploys                      → tear down, no user impact

Irreversible / low-risk side effects (don't pretend to roll back — report instead):
  - Calendar event created before a downstream step failed
      → NOT deleted automatically. User told plainly:
        "Event's on your calendar, but the invite email failed to send —
         want me to retry, or you'll send it yourself?"
  - Production deploy that passed health checks, then a LATER step fails
      → deploy stands. Auto-rollback only triggers on a FAILED health
        check within the deploy's own monitoring window (DA-9), never
        because of an unrelated later task failing.

Non-reversible by design (never auto-rollback, always escalate to human):
  - DB migrations without a down-migration defined
      → hard stop, page the user, do not attempt automatic reversal
```

**The principle:** a task either commits as one atomic unit or it
doesn't commit at all — but "roll back" only ever means undoing what's
*actually undoable*. Pretending a sent email or a live migration can be
silently reversed is worse than admitting it can't and telling the user
immediately.

### 4.5 Dead Letter Queue — where things go instead of vanishing

A task that exhausts its retry budget (or hits a `SYSTEMIC` error the
circuit breaker won't let through) moves to `DEAD`, not gone:

```
Dead Letter entry:
  { task_id, agent, original_input, every attempt made,
    every error with full class + message, final state,
    timestamp of first attempt and of death }

CLI: max dlq --list
CLI: max dlq --requeue <task_id>     # after you've fixed whatever broke
```

And critically — the Main Agent doesn't wait for the user to go looking.
It surfaces the death conversationally, the same turn it happens:
*"That deploy failed 3 times, same error each time — dependency install
is timing out. I've stopped retrying and logged it. Here's exactly what
was tried: [...]. Want me to try a different approach, or is this one for
you to look at?"*

---

## 5. The Updated Master Flow

```
USER INPUT
    │
    ▼
INTAKE / NORMALIZE ──(malformed)──► ask to resend, log it
    │
    ▼
INTENT CLASSIFIER ──(<70% confidence)──► CLARIFY, don't guess
    │
    ▼
PLANNER ── builds task(s) + dependency graph + idempotency keys
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  TASK QUEUE                                                │
│  priority band → aging check → depth check (backpressure)  │
│  dependency check → CIRCUIT BREAKER CHECK (per agent)       │
└─────────────────────────────────────────────────────────┘
    │  breaker OPEN? → reject now, explain, do not queue
    ▼
┌─────────────────────────────────────────────────────────┐
│  RESOURCE LOCK MANAGER                                     │
│  sorted-order acquisition, all-or-nothing, timeout          │
└─────────────────────────────────────────────────────────┘
    │  timeout? → back to QUEUE (LOCK_WAIT), not a failure yet
    ▼
┌─────────────────────────────────────────────────────────┐
│  EXECUTION — snapshot taken, heartbeat required every 15s   │
└─────────────────────────────────────────────────────────┘
    │  3 missed heartbeats → WATCHDOG_KILLED → snapshot rollback
    ▼
┌─────────────────────────────────────────────────────────┐
│  RECONCILIATION — real state vs. agent's self-report        │
└─────────────────────────────────────────────────────────┘
    │  mismatch → SYSTEMIC error, into error taxonomy below
    ▼
ERROR TAXONOMY (if anything above failed)
    │
    ├── TRANSIENT        → backoff+jitter retry, bounded
    ├── VALIDATION        → fail fast, explain to user, no retry
    ├── PERMISSION        → refuse, explain, log
    ├── DESTRUCTIVE_RISK   → escalate to confirm-gate
    └── SYSTEMIC          → circuit breaker records failure →
                             retry (2x) → still failing → DEAD LETTER
    │
    ▼
LOCKS RELEASED → RESPONSE TO USER → TRACE LOG + OUTCOME TRACKER
```

---

## 6. Concurrency Scenarios — Proving It Under Load, Not Just on Paper

| Scenario | What the old design would do | What this one does |
|---|---|---|
| Two "deploy" requests for the same project, seconds apart | Unclear — maybe both run, maybe race | Second one hits `LOCK_WAIT` on the deploy resource for that project, queues behind the first, runs after — never concurrent |
| A task needs both `database` and `deploy` locks, another needs `deploy` and `database` in reverse | Classic deadlock | Sorted-order acquisition means both request `database` before `deploy` — no circular wait possible |
| Agent process crashes mid-execution, no heartbeat | Task probably just hangs forever | 45s of missed heartbeats → killed → snapshot rollback → retried or dead-lettered, user never waits indefinitely |
| LLM API has a 90-second outage, 6 tasks fail at once | All 6 retry at the same backoff intervals, hammering the API the moment it's back | Full jitter spreads the 6 retries across a window instead of a synchronized spike |
| A background scan and an interactive "do this now" request arrive together | FIFO — scan might run first, user watches a spinner | Priority band puts interactive requests first; scan ages up if it waits too long, never starves entirely |
| Deploy Agent's last 5 attempts all failed (bad dependency in the repo) | Keeps retrying every new deploy request the same way | Circuit breaker opens after 5 consecutive failures — 6th request rejected instantly with a clear reason instead of joining a doomed queue |
| Task retried after a partial success (2 of 3 files written before the kill) | Retry might re-run from scratch, duplicating writes, or resume incorrectly | Snapshot rollback undid all 3 (atomic task boundary) before retry — retry starts clean, not from a half-done state |
| Queue gets flooded (500+ tasks queued) | Undefined — probably just grows unbounded or crashes | Backpressure ceiling rejects new tasks with a clear message once at capacity, doesn't degrade silently |

---

## 7. Three-Lens Sign-Off

### 🧑‍💻 As the engineer who owns the pager
I would ship this. Every failure mode in the scenarios table above has a
named, testable behavior — which means every one of those rows is also a
test case, not just a design intention. The thing I'd actually build
first isn't the happy path, it's the deadlock test (two tasks, two
resources, reverse order) and the circuit breaker test (force 5 failures,
confirm the 6th is rejected instantly). If those two pass, most of the
rest follows from the same primitives.

### 📋 As the CEO
This is the difference between a demo and a product. Nobody outside
engineering cares about a lock manager — they care that the assistant
never double-deploys, never hangs forever, and tells them clearly when
something's actually broken instead of spinning silently. That's not a
technical nice-to-have, that's the entire trust proposition of a personal
AI system. I'd rather ship 4 agents that never do this wrong than 15
agents that sometimes do.

### 🦾 As Stark
JARVIS never once told Tony "still thinking" for four hours because two
processes were both waiting on each other. The suit doesn't half-fire a
repulsor and hope. Every system in that suit either completes its action
fully or aborts cleanly and says so — that's not a luxury feature, that's
the baseline for anything you're going to trust near production, near
your calendar, or eventually near your keyboard and mouse. Build the
part that fails safely before you build the part that looks impressive.
Nobody remembers the demo where nothing went wrong; everybody remembers
the one where it did and it recovered without you noticing.

---

## 8. What Changes in the Build Plan

This doesn't add a phase — it defines what "done" means for the
infrastructure inside the phases you already have:

- **Phase 1** now explicitly includes: task state machine, idempotency
  keys, and basic snapshot rollback — even with one agent, these cost
  little to build correctly now and a lot to retrofit later.
- **Phase 2** is where the Resource Lock Manager (sorted-order + timeout),
  Heartbeat Watchdog, and Reconciliation Check get built for real — this
  was "deferred" in v2 only in the sense of agent count, not in the sense
  of "skip it." It arrives the moment you have 2+ agents that could ever
  touch the same resource, which is Phase 2 by definition.
- **Phase 3** adds the circuit breaker (per agent) and the Dead Letter
  Queue — by the time you have a real deploy pipeline, you need both.
- **Nothing here requires Kubernetes, Redis, or a message broker.** Every
  primitive above — the lock manager, the circuit breaker, the retry
  policy, the DLQ — is a few hundred lines of plain Python against
  SQLite. Scale the infrastructure when the load actually demands it, not
  before. That's not a compromise; a lock manager that works correctly
  in-process is a better foundation than a distributed one that's never
  been load-tested.

---

## 9. One-Line Summary (interview-ready)

*"Every task moves through one state machine with idempotency keys and
snapshot boundaries. Resources are locked in a fixed global order with a
timeout backstop, so deadlock is prevented by construction, not by luck.
Errors are classified before they're handled — only transient and
systemic failures ever retry, with exponential backoff and full jitter so
recoveries don't synchronize into a second outage. A per-agent circuit
breaker stops the system from queueing more doomed work the moment an
agent is clearly unhealthy, and nothing that exhausts its retries just
disappears — it lands in a dead letter queue and gets surfaced to the
user in the same turn, with the full history of what was tried."*
