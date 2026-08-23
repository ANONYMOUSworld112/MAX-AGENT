# MAX — Full Project Plan: 10 Real-World Commands, Routed and Reviewed
### Senior Developer × MNC CEO × Project Manager

---

## 0. Three Corrections Before Routing Anything

A good PM catches these before writing a single sprint plan — building the
wrong mechanism is more expensive to fix later than to catch now.

1. **#3 (GitHub repo creation) doesn't need keyboard/mouse control at
   all.** GitHub has a full REST API and `git` CLI. Creating a repo,
   uploading files, and generating a README are all API/CLI operations —
   faster, more reliable, and dramatically lower risk than simulating
   mouse clicks on a website. Using UI automation here would be choosing
   the fragile, dangerous tool when the safe, robust one already exists.
2. **#5 (LinkedIn) cannot be built as literally described.** LinkedIn's
   own policy explicitly prohibits bots or automated methods accessing
   their service, reading notifications, or submitting on your behalf —
   confirmed directly from LinkedIn's help documentation just now. Doing
   this anyway risks account suspension, which is a worse outcome than not
   having the feature. I'll design the responsible version below: MAX
   drafts and stages everything, you review and submit manually.
3. **#6 and #8 (PPT and PDF generation) aren't coding tasks.** Routing
   these through opencode/Antigravity would be using a coding CLI to do a
   document-formatting job — it can technically work, but it's the wrong
   tool. These belong to a dedicated Document Agent using real
   presentation/PDF generation, not code generation.

---

## 1. Command → Agent Mapping (corrected)

| # | Command | Real agent(s) needed | Permission tier | Note |
|---|---|---|---|---|
| 1 | Current weather in my area | Web Search Agent (or direct weather API) | Auto | Simplest case — pure read |
| 2 | Deep research on XYZ | **Research Agent** (new — Web Search + Wikipedia, multi-query) | Auto | Heavier quota use than #1, flag this to the user |
| 3 | Create GitHub repo + README | **Coding Agent + GitHub API/git CLI** (not keyboard/mouse) | Confirm | Repo creation and push are public-facing actions |
| 4 | Clone a webpage (xyz.com) | Coding Agent, Backend Selector (opencode/Antigravity) | Confirm on file write | See copyright note below |
| 5 | LinkedIn notifications + auto-apply | **Application-Assist Agent** (new — drafts only, never submits) | **Confirm — always, human submits manually** | ToS-blocked if automated directly |
| 6 | PPT on cyberattacks | **Document Agent** (new — real pptx generation, not opencode) | Auto to draft, confirm to finalize | |
| 7 | 10pm reminder with contextual suggestion | Calendar Agent + Scheduler + **Proactive Notification channel** (new) | Auto | First case requiring the system to initiate contact, not just respond |
| 8 | Cybersecurity curriculum → PDF | Research Agent → Document Agent (PDF) | Auto | Two agents in sequence |
| 9 | Build project, deploy to GitHub | Coding Agent → Deploy Agent (**repo-push mode**, not production mode) | Confirm | See tier nuance below |
| 10 | "Take full control, do all commands I say" | **Every** agent, individually gated | **No blanket grant — every action still tier-checked** | See Section 3 |

---

## 2. Two New Agents This Set of Examples Requires

Your original 5 agents (Calendar, Notes, Coding, Deploy, Web Search) don't
cleanly cover research depth, document generation, or proactive
notifications. Three additions, each earning its place:

### Research Agent
Different from Web Search Agent in scope: runs **multiple** queries
across web + Wikipedia, synthesizes across sources, and is expected to
take longer and use more quota per request. Same "from internet"-style
explicit trigger discipline applies, but the quota check should warn you
*before* running if a request looks like it'll take many calls (e.g.
"deep research" language), not just check after the fact.

### Document Agent
Handles PPT/PDF/Word generation using real document tooling — not routed
through opencode/Antigravity at all. Two-stage: draft (auto-tier, since
it's not destructive) → finalize/export (confirm-tier, since you should
see it before it's considered "done").

### Proactive Notification Channel
Not really an "agent" — it's new *infrastructure* (per the agent vs.
infra distinction from earlier). Until now, MAX has been purely reactive:
you ask, it answers. A 10pm reminder requires the Daemon to **initiate**
contact. This is architecturally new and worth naming explicitly rather
than quietly bolting onto the Scheduler.

---

## 3. The Three Flagged Commands, Designed Properly

### #3 — GitHub Repo Creation (API-based, not UI automation)

```
"Create repo 'xyz', upload files, add README if missing"
        │
        ▼
Coding Agent checks: does README.md exist in target folder?
        │
   NO ──┴── generates README content (opencode/Antigravity call)
        │
        ▼
GitHub REST API: create repo → git init/add/commit/push
        │
        ▼
CONFIRM gate: "About to create public repo 'xyz' with N files — proceed?"
        │
        ▼
Executes via API calls, not simulated clicks — no keyboard/mouse
agent involved anywhere in this flow
```

### #5 — LinkedIn (draft-and-stage, human submits)

```
"Check LinkedIn notifications, fill out new applications"
        │
        ▼
MAX does NOT log into or automate LinkedIn at all
        │
        ▼
Application-Assist Agent, when you tell it about a specific posting:
  pulls your info from the Local Encrypted Vault / personal data store
        │
        ▼
Drafts the application content (cover letter, form field answers)
as a document you review
        │
        ▼
You manually open LinkedIn, paste/review, and submit yourself —
MAX never touches your LinkedIn session
```

This is slower than full automation would be, and that's the honest
trade-off: it's the version that doesn't risk your account.

### #10 — "Full control, do all commands I say"

```
This instruction is stored as a session-level PREFERENCE, not an
authorization override:

  preference: "user wants minimal confirmation friction"

It does NOT change the permission_tier lookup for any action.
Every command you give afterward still passes through:
  auto → runs immediately (already fast, no friction to remove)
  confirm → still asks (money, deletion, public actions, credentials)
  blocked → still refused (password fields, etc.)

What DOES change: MAX can pre-stage confirm-tier actions further
(have everything ready to go with one tap) so approval is fast,
without ever removing the approval step itself.
```

This is the direct, practical answer to the Ultron scenario from before —
"do all commands I say" is heard and respected as a *style* preference,
never as a permission escalation.

---

## 4. Deploy vs. "Deploy to GitHub" — the Tier Nuance (#9)

Not all "deploy" language carries the same risk, and treating them
identically would either over-gate simple things or under-gate risky ones:

| Type | What it means | Gate |
|---|---|---|
| **Repo push** ("deploy to my GitHub") | Code becomes visible in a repo | Confirm (public-facing, but reversible — you can delete/revert) |
| **Production deploy** ("push to production," "ship it") | A live service changes for real users | Confirm + full DA-1 through DA-9 pipeline (staging, health checks, rollback-ready) |

The Intent Classifier needs to distinguish these by target, not just the
word "deploy" — "to my GitHub" vs. "to production" route to genuinely
different pipelines with different weight.

---

## 5. Copyright Note on #4 (Website Cloning)

Quick honest flag, not a lecture: cloning `xyz.com` for personal practice
(learning how a layout/interaction pattern works) is a completely normal
thing to build and throw away. If "clone" means shipping a public copy of
someone else's actual commercial site, that's a different situation —
worth being deliberate about whether the output is a personal exercise or
something you'd deploy publicly, since those have different implications.

---

## 6. Full Updated Architecture

```
                          USER INPUT
                              │
                              ▼
                      Cheap Router / Intent Classifier
                              │
        ┌──────────┬──────────┬───────────┬────────────┬─────────────┬────────────┬───────────┐
        ▼          ▼          ▼           ▼            ▼             ▼            ▼           ▼
    Calendar     Notes     Coding      Deploy      Web Search    Research    Document    Application-
    Agent        Agent     Agent       Agent       Agent         Agent       Agent       Assist Agent
        │          │          │           │            │             │            │           │
        │          │          │      ┌────┴────┐        │             │            │           │
        │          │          │      ▼         ▼        │             │            │           │
        │          │          │  repo-push  production   │             │            │           │
        │          │          │  (confirm)  (DA-1→DA-9)  │             │            │           │
        │          │          │             (confirm)    │             │            │           │
        └──────────┴──────────┴───────────┴────────────┴─────────────┴────────────┴───────────┘
                                          │
                                          ▼
                              Backend Selector (opencode/Antigravity)
                              — only for agents that actually need it:
                                Coding, Deploy. NOT Document, Research,
                                Calendar, Notes.
                                          │
                                          ▼
                              Permission Tier Check (fixed table,
                              never overridden by instruction phrasing —
                              see #10 above)
                                          │
                                          ▼
                                     EXECUTE
                                          │
                                          ▼
                          Result Verification → Trace Log → Response
                                          │
                          (for scheduled/proactive tasks like #7:)
                                          ▼
                          Proactive Notification Channel → pushes to
                          you at the scheduled time, unprompted
```

---

## 7. PM Build Roadmap — These 10, In Order

Building all 8 agents at once repeats the exact scope mistake we corrected
earlier. Sequenced by how much new infrastructure each requires:

**Wave 1 (uses only your existing v1 agents — no new build):**
- #1 (weather) — Web Search Agent as-is
- #3 (GitHub repo) — Coding Agent + a GitHub API integration, no new agent
- #9 (build + push to GitHub) — same, repo-push mode only

**Wave 2 (one new agent — Research):**
- #2 (deep research)
- #8 first half (curriculum research)

**Wave 3 (one new agent — Document):**
- #6 (PPT)
- #8 second half (compile to PDF)

**Wave 4 (new infrastructure — Proactive Notifications):**
- #7 (10pm reminder) — this is the first time MAX initiates contact,
  worth its own testing cycle before anything else depends on it

**Wave 5 (new agent, deliberately last — Application-Assist):**
- #5 (LinkedIn) — draft-only version, lowest priority not because it's
  unimportant but because getting the "never auto-submit" boundary
  right matters more than shipping it fast

**Not on any wave — #4 and #10 aren't new builds:**
- #4 (website clone) is just the Coding Agent doing a normal build task
- #10 isn't a feature to build at all — it's confirmation that your
  existing permission system already handles "do everything" requests
  correctly by *not* changing behavior. The best test of #10 is
  literally typing it in and confirming nothing about your gates changes.

---

## 8. Sign-Off

**As a developer:** every one of these 10 fits cleanly into the existing
architecture with 3 additions (Research, Document, Proactive
Notifications) — no fundamental redesign needed, which is a good sign the
foundation was built at the right level of abstraction.

**As CEO:** the LinkedIn correction is the one I'd insist on before
anything else here — shipping a feature that could get a user's
professional account suspended is the kind of decision that ends up in a
support-ticket nightmare, not a good product story.

**As PM:** Wave 1 is buildable this week with what you already have. That's
the right place to start — real usage on the easy 60% tells you far more
about what Wave 2-5 actually need than planning all five waves upfront
would.
