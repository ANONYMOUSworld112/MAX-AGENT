# MAX — Final Pipeline: Background Daemon, Token-Efficient Routing,
### Local Web Dashboard, Dynamic Backend Selection (opencode / Antigravity)

---

## 1. What's New Here

| Addition | What it does |
|---|---|
| **Background Daemon** | Main Agent runs as a persistent process, not a one-shot chat session |
| **Token-Efficient Routing** | Most of the pipeline runs on zero LLM tokens — reasoning only happens where actually needed |
| **Local Web Dashboard** | Browser-based, read-only status view of everything running in the background |
| **Backend Selector** | Chooses opencode vs Antigravity CLI at runtime for each sub-agent task, based on live quota/availability |
| **Scheduled Web Search** | Recurring background checks (pre-approved), separate from the reactive "from internet" chat trigger |

---

## 2. Background Daemon Architecture

```
System boot
    │
    ▼
Kill Switch Service starts (Component #0, unchanged)
    │
    ▼
MAX Daemon starts — runs continuously in the background
    │
    ├── Task Queue (persistent, survives restarts — SQLite-backed)
    ├── Scheduler (cron-like, for recurring tasks you've configured)
    └── Dashboard Server (local web server, e.g. localhost:4200)
    │
    ▼
Daemon idles — costs ZERO tokens while waiting
    │
    ├── User sends a chat message  → wakes Main Agent reasoning
    ├── Scheduled task fires        → wakes relevant sub-agent only
    └── Dashboard requests status   → pure data read, no LLM involved
```

**The key property:** the daemon sitting idle, the dashboard refreshing,
and the scheduler checking "is it time yet" are all **plain code — zero
token cost.** The LLM only gets called at the two moments that actually
need judgment: when you send it something to interpret, or when a
scheduled sub-agent task needs to reason about what it found.

---

## 3. Token-Efficient Routing — How "Less Tokens, Long Time" Actually Works

This is the concrete design, not just a goal:

```
INCOMING TASK (from chat or scheduler)
        │
        ▼
┌─────────────────────────┐
│  CHEAP ROUTER (no LLM)    │  ← regex/keyword match first
│  "does this match a       │
│   known pattern?"         │
└─────────────────────────┘
        │
   MATCHED              NOT MATCHED / ambiguous
        │                       │
        ▼                       ▼
  Route directly          NOW call the Intent
  to the agent,           Classifier (LLM call —
  skip the LLM             this is the only token
  classification            spend so far)
  call entirely
        │                       │
        └───────────┬───────────┘
                     ▼
        ┌─────────────────────────┐
        │  CONTEXT TRIMMER          │
        │  send only what THIS      │
        │  task needs, not full      │
        │  history/memory            │
        └─────────────────────────┘
                     ▼
              Agent executes
                     ▼
        ┌─────────────────────────┐
        │  RESULT CACHE              │
        │  identical/near-identical  │
        │  requests reuse the cached │
        │  result instead of re-     │
        │  calling the model          │
        └─────────────────────────┘
```

**Concrete examples of what this saves:**
- "Remind me to call the counsellor at 5pm" → matches the Calendar
  keyword pattern instantly, **never touches the LLM at all** for routing.
  Only the (tiny) time/task extraction needs a model call, if even that.
- Dashboard polling every few seconds → pure database read, always zero tokens.
- Scheduled news check that runs daily → one search call, one summarize
  call — not a full conversation replay each time.
- Repeated "what's my deploy status" → served from the Trace Log directly,
  no model call needed at all.

**The honest trade-off:** the cheap router will occasionally misroute
something genuinely ambiguous. That's fine — it falls through to the real
classifier, same as before. You're not sacrificing correctness, you're
just not paying LLM cost for the 80% of requests that are unambiguous
pattern matches.

---

## 4. Local Web Dashboard

```
Browser → http://localhost:4200
    │
    ▼
Dashboard Server (part of the daemon, not a separate exposed service)
    │
    ├── Active tasks + status (running / done / failed / awaiting approval)
    ├── Trace log viewer (searchable, from earlier design)
    ├── Token/quota usage today (so you see cost in real time, not surprise)
    ├── Kill switch button (mirrors the hotkey, same hard-stop behavior)
    └── Approval queue — anything sitting at a confirm-gate shows here,
        you can approve/reject from the browser instead of only chat
```

**Stays local by default.** If you ever want to check this from your
phone while away from your desktop, the safe path is a personal VPN
(e.g. Tailscale) into your own machine — not opening the port to the
public internet. Worth being explicit about this choice when you get there,
since it's the difference between "only I can reach this" and "anyone who
finds the port can."

---

## 5. Backend Selector — opencode vs Antigravity

This decides, per sub-agent task, which CLI actually executes it:

```
Sub-agent task ready to run
        │
        ▼
┌─────────────────────────┐
│  BACKEND SELECTOR          │
│  checks, in order:         │
│  1. task type — does it    │
│     need something one     │
│     tool handles better?   │
│  2. current quota/         │
│     availability of each   │
│  3. last-known latency/    │
│     reliability per tool   │
└─────────────────────────┘
        │
   ┌────┴────┐
   ▼         ▼
opencode   Antigravity
(existing   (fallback or
 tmux setup) alt-strength tool)
        │
        ▼
Task runs, result logged with
WHICH backend handled it — so
you can see over time which
tool is actually more reliable
for which task type
```

**Why this matters practically:** you already have opencode wired into
PHONEX-CORE's tmux setup — that stays the default. Antigravity becomes the
fallback when opencode is unavailable, rate-limited, or when a specific
task type performs better on it. The selector logs its choice every time,
so the Outcome Tracker can eventually tell you "opencode fails more often
on frontend tasks, route those to Antigravity" — a real, earned
optimization instead of a guess.

**Honest note, consistent with before:** verify current quota/access for
both tools directly before relying on either — this space has changed
multiple times in 2026 already.

---

## 6. Reconciled Web Search — Reactive vs Scheduled

```
REACTIVE (in chat)                    SCHEDULED (background)
──────────────────                    ──────────────────────
User must say "from internet"          You configure it once
or equivalent trigger phrase           ("check RBI rate daily at 9am")
        │                                       │
        ▼                                       ▼
Same as before — quota check,          Runs automatically at the
grounded search, cited response         scheduled time, same quota
                                        check, result appears on
                                        dashboard + optionally
                                        pushed to Daily Brief
```

Consent for scheduled tasks is given once, at setup — not re-asked every
time it fires. This is the honest version of "automated," as opposed to
the Main Agent deciding on its own, mid-conversation, that a search seems
useful.

---

## 7. The Full Final Pipeline

```
                         SYSTEM BOOT
                              │
                    Kill Switch (Component #0)
                              │
                        MAX Daemon starts
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
        Task Queue      Scheduler        Dashboard Server
        (persistent)    (recurring       (localhost:4200,
                          tasks)           read/approve only)
              │               │
              └───────┬───────┘
                      ▼
              ┌─────────────────┐
              │  CHEAP ROUTER      │  ← zero tokens, pattern match
              └─────────────────┘
                      │
              matched?      not matched
                 │               │
                 │               ▼
                 │      Intent Classifier (LLM call)
                 │               │
                 └───────┬───────┘
                         ▼
                  Context Trimmer
                  (send only what's needed)
                         ▼
                  Permission Tier Check
                         │
                 auto          confirm
                  │               │
                  │        Dashboard/chat approval
                  │        queue, waits
                  │               │
                  └───────┬───────┘
                          ▼
                 Backend Selector
                 (opencode / Antigravity)
                          │
                          ▼
                   Sub-agent executes
                 (retry/watchdog/rollback,
                  as designed earlier)
                          │
                          ▼
                   Result Cache updated
                          │
                          ▼
                Trace Log + Outcome Tracker
                (token usage, backend used,
                 success/fail — all visible
                 on Dashboard)
                          │
                          ▼
              Response → chat AND/OR dashboard,
              depending on where the task originated
```

---

## 8. Where This Fits Your Build Order

This is a natural **v1.5 → v2 addition**, after your 4-core-agent v1 is
running reliably:

1. **Daemon + Task Queue** — straightforward, wraps what you already have
2. **Cheap Router** — genuinely easy win, add this early, it pays for
   itself immediately in token cost
3. **Dashboard** — build once you have 2+ agents worth watching; before
   that, the trace log CLI is enough
4. **Backend Selector** — add once you've actually hit a quota wall on one
   tool and need the fallback for real, not preemptively
5. **Scheduler for background tasks** — last, since it's the piece most
   likely to need the Kill Switch and confirm-gates already battle-tested
   on reactive tasks first

Same principle as every stage before this one: each piece earns its place
by solving a problem you've actually hit, not one you're anticipating.
