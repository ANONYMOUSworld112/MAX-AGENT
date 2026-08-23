# MAX — The General Decomposition Engine + Complete Agent Roster
### Not 10 fixed commands — one mechanism that handles anything

---

## 0. What Was Missing Before

The last file solved 10 specific commands with specific routing. What you
actually asked for is the **general-purpose mechanism**: take *any* input,
break it into ordered steps, figure out which agent owns each step, run
them, commit each result. The 10 commands should be *proof the mechanism
works*, not the limit of what it handles.

I also audited every file from this entire conversation for every agent
that's been designed — the table in Section 2 is the complete roster,
not just the 8 relevant to last time's examples.

---

## 1. The General Decomposition Engine

This generalizes the "Planner" and the compound-task handling from
earlier into the one mechanism *every* input goes through — not a special
case for complex requests, the actual default path.

```
ANY USER INPUT
        │
        ▼
┌─────────────────────────────────────────┐
│  DECOMPOSITION                             │
│  Break the request into an ordered,        │
│  possibly-branching list of atomic steps.  │
│  Each step maps to exactly ONE agent       │
│  from the full roster (Section 2).         │
└─────────────────────────────────────────┘
        │
        ▼
INSERT INTO tasks (a "plan" parent row)
        │
        ▼
For each step:
  INSERT INTO tasks (parent_task_id = plan.id, agent_type = ?, ...)
        │
        ▼
┌─────────────────────────────────────────┐
│  DEPENDENCY CHECK                          │
│  Does this step need a prior step's        │
│  output? If yes, wait. If independent,      │
│  it can run in parallel with others.        │
└─────────────────────────────────────────┘
        │
        ▼
Each step runs through the FULL existing
pipeline, unchanged:
  Permission Tier Check → Resource Lock →
  Backend Selector → Execute → Verify
        │
        ▼
┌─────────────────────────────────────────┐
│  COMMIT (two meanings, both happen)        │
│  1. SQL: UPDATE tasks SET status='success' │
│     — the step's state is now permanent     │
│  2. For Coding/Deploy specifically: a real  │
│     git commit of whatever changed          │
└─────────────────────────────────────────┘
        │
        ▼
   step failed? ──▶ bounded retry loop (as designed earlier)
        │                    │
        │              still fails after
        │              bounded attempts?
        │                    │
        │                    ▼
        │            Halt only the steps that DEPEND
        │            on this one. Independent steps
        │            that already succeeded stay
        │            committed — partial progress is
        │            never thrown away.
        ▼
All steps resolved (success or escalated)
        │
        ▼
Aggregate results → one response to the user,
covering what succeeded, what's pending
approval, and what needs their attention
```

**This is what "committing the changes" means concretely**: every step is
a permanent, queryable database record the moment it succeeds — not held
in memory until the whole plan finishes. If step 3 of 5 fails, you don't
lose steps 1 and 2.

---

## 2. Complete Agent Roster (every agent designed this conversation)

Organized by status, so "complete" doesn't mean "build all of it now" —
that's the same scope-discipline principle from every earlier section,
just applied to a longer list.

### Orchestration (not worker agents — route and shape requests)

| Agent | Role |
|---|---|
| Main Agent | Owns the conversation, invokes the Decomposition Engine |
| Prompt Agent | Shapes context per step before it reaches a worker agent |

### Tier 1 — Active in v1

| Agent | Role |
|---|---|
| Calendar Agent | Scheduling, reminders |
| Notes Agent | Capture, logging |
| Coding Agent | Build, fix, write code |
| Deploy Agent | Repo-push mode and full production mode |

### Tier 2 — Designed, ready to add next

| Agent | Role |
|---|---|
| Web Search Agent | Explicit-trigger real-time lookups |
| Research Agent | Multi-query deep research across web + Wikipedia |
| Document Agent | PPT/PDF/office document generation |
| Application-Assist Agent | Drafts job applications; never auto-submits (LinkedIn ToS) |

### Tier 3 — Daily-life, deferred

| Agent | Role |
|---|---|
| Inbox Agent | Email triage, draft replies (never auto-send) |
| Expense Agent | Spending logs, anomaly flags |
| Founder CRM Agent | Investor/customer contact tracking |
| Content Draft Agent | Drafts social posts, never auto-posts |
| Daily Brief Agent | Morning summary across calendar/notes/inbox |

### Tier 4 — Engineering/quality, deferred

| Agent | Role |
|---|---|
| Architecture Review Agent | Reviews a plan before Coding Agent starts |
| Security Agent | SOC/malware/cloud-security/threat-intel scanning |
| Testing Agent | Structured test generation, beyond Coding Agent's own tests |
| Debug Agent | Escalation target when a task fails repeatedly |
| Documentation Agent | Code-level docs (README, API docs) — *distinct from Document Agent above*, which handles business documents like PPTs |
| Code Review Agent | Deeper review pass beyond the Architecture Review Gate |

**Note on Backend/Frontend/DevOps split:** the original design had these as
separate agents. In the scoped v1, they're internal modes of the single
Coding Agent — worth re-splitting only once Coding Agent's workload
actually justifies specialized sub-agents, not before.

### Tier 5 — Big infrastructure, deferred

| Agent | Role |
|---|---|
| Database Agent | Schema, migrations, queries, backups |
| Cloud/Infra Agent | Provisioning, scaling, cost monitoring |
| Data Pipeline Agent | ETL, data sync |
| Backup/DR Agent | Scheduled backups, restore drills |
| Analytics Agent | Usage metrics, dashboards |

### Tier 6 — Input control, deferred and highest-risk (the "SPECIAL" layer)

| Agent | Role |
|---|---|
| Keyboard Agent | Types, executes shortcuts |
| Mouse Agent | Move, click, drag |
| Screen Agent | Screenshot, OCR, UI detection |

*(Session Recorder and Kill Switch support these but aren't themselves
decision-making agents — they're infrastructure, per the agent/infra
distinction from earlier.)*

**27 worker agents total across 6 tiers, plus 2 orchestration components.**
Every one of them plugs into the same Decomposition Engine — adding a new
agent later means adding one routing table row, not redesigning the engine.

---

## 3. Worked Example — A Brand-New Request, Not One of the Original 10

To prove this generalizes, here's a request that never appeared before,
spanning four different tiers including one not yet built:

> **"Check my deployed app for security issues. If you find any, fix them
> and redeploy. Log what happened either way."**

```
DECOMPOSITION produces:

Step 1: security_scan          → Security Agent        (Tier 4)
Step 2: [conditional on Step 1] fix_if_needed → Coding Agent (Tier 1)
Step 3: [conditional on Step 2] redeploy      → Deploy Agent (Tier 1)
Step 4: [always runs]           log_outcome   → Notes Agent  (Tier 1)

Dependency graph:
  Step 1 → Step 2 → Step 3
                        │
  Step 4 waits for whichever of (1, 2, 3) is the actual last one to
  finish — it always runs, but what it logs depends on the outcome
```

If Step 1 finds nothing, Steps 2 and 3 are skipped entirely (not
"attempted and passed" — genuinely never queued), and Step 4 logs "scan
clean, no action needed." If Step 1 finds an issue, all four steps run in
order, each committing independently — so if Step 3 (redeploy) hits a
health-check failure, you still have Step 1 and 2's committed results
(the scan findings and the fix are saved) even though the redeploy itself
escalates to you.

This is the same mechanism that would have handled any of the original 10
— it's just now the one path everything takes, instead of something
special-cased for compound requests.

---

## 4. What Doesn't Change

Everything established earlier still holds inside this engine, per step:

- **Permission tier is never overridden by phrasing** — each step's tier
  is looked up fresh, regardless of how the original request was worded
- **Production deploys still require the full DA-1 through DA-9 gate**,
  even if they're step 3 of a 4-step plan
- **The bounded retry loop applies per step**, not per whole plan — one
  stuck step escalates on its own, it doesn't stall everything else
- **Application-Assist Agent still never auto-submits**, no matter what
  step number it shows up as

---

## 5. Build Note, Same Principle as Every Section Before This One

This document makes the roster complete on paper. It does not mean build
27 agents. The Decomposition Engine itself is worth building once — as
soon as you have 2+ agents in Tier 1 working, because that's exactly when
you'll first need it (even "remind me after you build this" is technically
a 2-step plan). Everything past Tier 1 gets added exactly the way it's
always been added in this conversation: one at a time, when a real request
needs it.
