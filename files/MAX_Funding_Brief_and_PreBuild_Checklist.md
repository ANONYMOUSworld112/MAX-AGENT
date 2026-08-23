# MAX OS — Project Brief & Pre-Build Checklist
### Prepared as a senior engineer would present it to a client or funder

---

## PART A — Explaining MAX (for funding / client conversations)

### What MAX Is, In One Paragraph

MAX is a personal AI operating system: a small set of specialized AI
agents — for coding, scheduling, deployment, and eventually research and
daily productivity — coordinated by one synchronized backend, running
entirely on the user's own machine. Instead of one general-purpose
chatbot trying to do everything in a single context window, MAX routes
each request to a purpose-built agent, tracks every task through a
real state machine, and never lets an AI agent take an irreversible
action (deploying to production, spending money, deleting data) without
an explicit human checkpoint enforced in code.

### The Problem

Two separate problems, and MAX addresses both with the same underlying
design:

1. **AI assistants today are single-shot and stateless.** Ask one to
   "build this, then deploy it, then remind me tomorrow," and most
   systems either can't sequence that at all, or do it with no memory of
   what succeeded if something interrupts the process halfway through.
2. **"Autonomous AI agent" and "trustworthy" are currently in tension.**
   The more autonomy an agent has, the more a mistake costs — and most
   agent products either limit autonomy to the point of being barely
   useful, or grant it broadly and hope nothing goes wrong. MAX's core
   bet is that this is a false choice: autonomy and safety aren't
   opposed if the safety is architectural, not a policy someone has to
   remember to enforce.

### The Solution, and Why It's Actually Different

The differentiator isn't "it uses AI agents" — every competitor in this
space does. It's three specific engineering decisions:

- **Exactly two actions require a human, everything else is autonomous
  within pre-approved permissions.** Reviewing an architecture before
  code is written, and approving before anything reaches production.
  Both gates are enforced *inside the relevant function's code*, not in
  a UI that a direct API call could skip past.
- **Failure is a first-class design concern, not an afterthought.**
  Every error is classified before the system decides what to do with
  it. Resource conflicts are prevented by construction (a fixed lock
  ordering makes deadlock mathematically impossible, not just unlikely).
  A misbehaving component stops itself after repeated failure instead of
  repeating the same mistake indefinitely.
- **Nothing is scoped bigger than it needs to be, on purpose.** The
  full design covers 33 possible agents. Exactly 4 are in the current
  build scope, with an explicit, enforced rule against building agent 5
  until the first 4 are proven reliable. That's a deliberate constraint,
  not a limitation — it's what makes "actually ships" more likely than
  "impressive diagram, never finished," which is the most common failure
  mode for projects at this level of ambition.

### Current State — Stated Honestly

This is architecture and implementation planning at build-ready detail:
every component, state transition, and failure mode is specified
concretely enough that a coding agent (or a human engineer) can execute
against it directly, including a self-documenting build protocol that
lets work resume correctly across sessions, tool switches, or interrupted
work. **What this is not, yet, is a verified running product** — that's
the next phase of work, not a past one. Any conversation about funding
or partnership should proceed on that basis: the design risk is largely
retired, the execution is in progress.

### Why This Stage Is a Reasonable Point to Engage

Early support at this stage typically funds the gap between "rigorously
designed" and "running and used daily" — the phases in the accompanying
`ARCHITECTURE.md` are the literal, sequenced plan for closing that gap,
with concrete acceptance criteria per step rather than vague milestones.

### Risks, Stated Plainly

- **Solo-builder bandwidth** is the single biggest execution risk. The
  architecture is scoped specifically to make this tractable (4 agents,
  not 33), but that scope discipline has to hold in practice, not just
  on paper.
- **The personal-AI-assistant space is crowded.** MAX's differentiation
  is in reliability engineering most competitors skip, not in a feature
  no one else has thought of — that's a real, defensible edge, but it
  has to be demonstrated (via the traced scenarios in
  `MAX_Agent_Roster_and_Pipeline_Traces.md`), not just claimed.
- **Input-control agents (keyboard/mouse) are explicitly deferred**, for
  good reason — they're the highest-liability part of the roadmap and
  are intentionally not part of the near-term plan.

### The Ask

*This section is intentionally left as a template — the specific
funding amount, use of funds breakdown, and any equity or grant terms
are decisions for you to make deliberately, not something to be
generated generically. A reasonable structure to fill in:*

```
Amount requested:        [___]
Primary use of funds:     [ time to build full-time / infra costs /
                             compute+API costs / other ]
Milestone this funds:     [ e.g., "Phase 0–4 complete, 4-agent v1
                             running daily" ]
Timeline:                 [ from ARCHITECTURE.md's phase estimates ]
```

---

## PART B — Necessary Files Before Building

### The Critical Gap, Found and Fixed

`MAX_MASTER_PROMPT.md` — your own build protocol — has a hard
dependency that didn't exist yet:

> *"Connect to max_state.db. If it doesn't exist, create it from
> max_state_schema.sql, then seed phases/steps from **ARCHITECTURE.md**."*

That file didn't exist among what's been produced so far. Without it,
**step one of the mandatory first actions in your own protocol cannot
complete** — any build session following the Master Prompt would stall
immediately. It's been drafted as a companion file to this document,
matching the exact `phases`/`steps` structure your schema expects,
including the specific "Phase 4, step 4.5" scope checkpoint your Master
Prompt already refers to by name.

### Full Pre-Build File Checklist

| File | Purpose | Status |
|---|---|---|
| `max_state_schema.sql` | DB schema — build progress + runtime trace | **Exists**, extended with `api_quota_usage` |
| `ARCHITECTURE.md` | Phased build plan the protocol seeds from | **Was missing — drafted, see companion file** |
| `MAX_MASTER_PROMPT.md` | System prompt for whatever coding agent executes the plan | **Exists** |
| `README.md` | What the project is, how to run it, for anyone (including future-you) opening the repo cold | **Missing — recommended next** |
| `.env.example` | Documents which environment variables/keys are needed, with placeholder values, never real secrets | **Missing — recommended next** |
| `.gitignore` | Must exclude `max_state.db`, any `.env`, and anything the Vault would otherwise risk leaking | **Missing — recommended next** |
| `requirements.txt` / `pyproject.toml` | Pinned dependencies, matching the tech stack section in `ARCHITECTURE.md` | **Missing — needed before Phase 0.1** |
| `LICENSE` | Matters the moment this is public on GitHub at all, even privately | **Missing — decide before first push** |
| `tests/` directory structure | Referenced throughout `ARCHITECTURE.md`'s acceptance criteria | **Missing — needed by Phase 1.7** |

### Priority Order

1. `requirements.txt` and `.gitignore` — needed before Step 0.1 even runs,
   since that step initializes the repo.
2. `README.md` and `.env.example` — not blocking for the build agent, but
   should exist before anyone else (a funder, a collaborator, future-you
   after a break) looks at this repo.
3. `LICENSE` — decide before the first public push, not after.

Everything else needed to *start* building is now in place.
