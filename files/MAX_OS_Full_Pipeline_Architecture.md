# MAX OS — Full Autonomous Delivery Pipeline
### User Input → Production Deployment, End to End

---

## 0. Design Principle

Every stage below either **executes**, **validates**, or **gates**. Nothing skips
validation, and nothing touches production without passing an explicit gate.
This is the single idea that makes the whole system trustworthy — the rest is
just organizing agents around it.

---

## 1. The Full Pipeline (One Continuous Flow)

```
USER
  │  (voice / text / image / file)
  ▼
┌─────────────────────────────────────────────────────────────┐
│ STAGE 1 — INTAKE                                             │
│  Input Normalizer → Intent Classifier → Context Loader       │
└─────────────────────────────────────────────────────────────┘
  ▼
┌─────────────────────────────────────────────────────────────┐
│ STAGE 2 — UNDERSTANDING                                      │
│  Requirement Extraction → Constraint Analysis →               │
│  Ambiguity Resolution (ask user if underspecified)            │
└─────────────────────────────────────────────────────────────┘
  ▼
┌─────────────────────────────────────────────────────────────┐
│ STAGE 3 — PLANNING                                            │
│  Task Decomposition → Tech Stack Selection →                  │
│  Dependency Graph → Complexity/Risk Estimate                  │
└─────────────────────────────────────────────────────────────┘
  ▼
┌─────────────────────────────────────────────────────────────┐
│ STAGE 4 — ARCHITECTURE REVIEW GATE  ⛔ (human or agent gate)  │
│  Scalability check → Security check → Simplicity check        │
│  FAIL → back to Stage 3   |   PASS → continue                 │
└─────────────────────────────────────────────────────────────┘
  ▼
┌─────────────────────────────────────────────────────────────┐
│ STAGE 5 — SCHEDULING                                          │
│  Priority Queue → Dependency-aware ordering →                 │
│  Worker assignment                                             │
└─────────────────────────────────────────────────────────────┘
  ▼
┌─────────────────────────────────────────────────────────────┐
│ STAGE 6 — EXECUTION (Worker Pool, parallel where possible)    │
│  Database Agent → Backend Agent → Frontend Agent →            │
│  Auth Agent → Docs Agent                                       │
│  (each works off its own snapshot; reports via Event Bus)     │
└─────────────────────────────────────────────────────────────┘
  ▼
┌─────────────────────────────────────────────────────────────┐
│ STAGE 7 — VALIDATION LOOP (per task, before merge)             │
│  Lint → Unit Tests → Type Check → Self-review by agent         │
│  FAIL → Retry (max N) → still fails → Escalate to Debug Agent  │
└─────────────────────────────────────────────────────────────┘
  ▼
┌─────────────────────────────────────────────────────────────┐
│ STAGE 8 — INTEGRATION                                         │
│  Merge branches → Integration Tests → End-to-End Tests        │
│  FAIL → Rollback to last good snapshot → re-plan failing part  │
└─────────────────────────────────────────────────────────────┘
  ▼
┌─────────────────────────────────────────────────────────────┐
│ STAGE 9 — SECURITY & QUALITY SCAN                              │
│  SAST → Dependency vuln scan → Secrets scan →                 │
│  Performance/load check                                        │
│  FAIL → block merge, report to user, do not proceed            │
└─────────────────────────────────────────────────────────────┘
  ▼
┌─────────────────────────────────────────────────────────────┐
│ STAGE 10 — VERSION CONTROL                                    │
│  Git commit → Tag release → Changelog → Backup                │
└─────────────────────────────────────────────────────────────┘
  ▼
┌─────────────────────────────────────────────────────────────┐
│ STAGE 11 — BUILD & PACKAGE                                     │
│  Docker build → Image scan → Push to registry                 │
└─────────────────────────────────────────────────────────────┘
  ▼
┌─────────────────────────────────────────────────────────────┐
│ STAGE 12 — STAGING DEPLOYMENT                                 │
│  Deploy to staging → Smoke tests → Health checks               │
└─────────────────────────────────────────────────────────────┘
  ▼
┌─────────────────────────────────────────────────────────────┐
│ STAGE 13 — PRODUCTION APPROVAL GATE  ⛔ (always human)         │
│  Diff summary + test report + security report shown to user   │
│  User approves → continue   |   User rejects → hold/rollback  │
└─────────────────────────────────────────────────────────────┘
  ▼
┌─────────────────────────────────────────────────────────────┐
│ STAGE 14 — PRODUCTION DEPLOYMENT                               │
│  Blue/green or canary rollout → Health check →                │
│  Auto-rollback if health check fails within window             │
└─────────────────────────────────────────────────────────────┘
  ▼
┌─────────────────────────────────────────────────────────────┐
│ STAGE 15 — MONITORING & FEEDBACK                                │
│  Live metrics → Error tracking → Log aggregation →             │
│  Results written back to Memory (what worked, what failed)     │
└─────────────────────────────────────────────────────────────┘
  ▼
RESPONSE TO USER (status report, links, next steps)
```

---

## 2. What Makes This "Autonomous" vs Just Automated

Three things, in order of importance:

1. **Self-correcting loops** — Stage 7 and 8 retry and re-plan without
   asking the user every time. Only genuinely stuck or destructive/production
   decisions escalate.
2. **Gates, not guesses** — Stage 4 and Stage 13 are the only two points
   where the system *must* stop and get explicit sign-off. Everything else
   proceeds on its own authority within pre-approved permissions.
3. **Memory feedback** — Stage 15 writes outcomes back into Stage 3's
   planning inputs. Over time the Planner gets better at estimating and
   choosing stacks because it has a record of what actually worked.

---

## 3. Cross-Cutting Systems (touch every stage)

| System | Role |
|---|---|
| **Event Bus** | Agents never call each other directly — they emit `task.started`, `task.failed`, `retry.requested` etc. Keeps everything loosely coupled and gives you a free audit trail. |
| **Permission Manager** | Every action classified `auto-allow / confirm / block` before it runs. This is what Stage 4 and 13 are built on. |
| **Snapshot/Rollback** | Taken before Stage 6 execution and before Stage 14 deploy. Anything that fails validation reverts to the last snapshot instead of leaving a half-done state. |
| **Audit Logger** | Every stage transition, every agent action, every gate decision — timestamped, immutable. |

---

## 4. Realistic Build Phasing

Building all 15 stages at once is how solo projects die. Build in this order —
each phase is a fully working system on its own, just smaller in scope.

### Phase 1 — Prove the loop (2–3 weeks)
Stages 1, 2, 3, 6 (one agent only), 7, 10.
- One agent (Coding Agent), no parallelism.
- SQLite for state, no queue system — a plain in-process task list.
- No staging/production split yet — just "does the generated code pass its own tests."
- **Goal:** input → plan → code → test → commit, fully working end to end.

### Phase 2 — Multi-agent + gates (next 3–4 weeks)
Add Stages 4, 5, 8, 9.
- Add 2nd and 3rd agents (Backend, Frontend).
- Add the Event Bus (can be a simple pub/sub — Redis Streams or even Python's
  `asyncio` queue — not Kafka).
- Add the Architecture Review Gate as a prompt-based check, not a full agent yet.

### Phase 3 — Deployment pipeline (next month)
Add Stages 11, 12, 13, 14.
- Real Docker build + push.
- Staging environment (even a single VPS is fine).
- Production gate is literally a Telegram/CLI prompt asking "deploy? y/n" —
  doesn't need a dashboard yet.

### Phase 4 — Observability + autonomy (ongoing)
Add Stage 15, snapshot/rollback automation, retry/escalation logic,
vector-memory-backed planning improvements.
- This is where it starts to feel genuinely autonomous instead of scripted.

### Explicitly defer until you have a working Phase 3
Kubernetes, RBAC, vector DB, multi-region deploy, canary rollout automation,
full dashboard UI. These are real and worth having eventually — they're just
not what makes the core loop work, and building them early is the most common
way this kind of project stalls.

---

## 5. Minimal Tech Stack for Phase 1–2 (so you actually ship)

| Component | Phase 1–2 choice | Later upgrade |
|---|---|---|
| Task state | SQLite | PostgreSQL |
| Queue | Python `asyncio.Queue` | Redis / Celery |
| Event bus | In-process pub/sub | Redis Streams / NATS |
| Agent runtime | opencode CLI in tmux (what you already have) | same, scaled out |
| CI | GitHub Actions | same |
| Deploy target | Single VPS + Docker | K8s when you actually have multiple services |

---

## 6. One-Line Summary for Interviews

*"MAX plans, executes, and validates software changes through a gated
pipeline — agents work autonomously between two human checkpoints:
architecture review before code is written, and deployment approval before
it reaches production. Everything in between is retried, rolled back, or
escalated automatically, and every outcome feeds back into planning."*
