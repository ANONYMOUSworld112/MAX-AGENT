# MAX OS — Deploy Agent
### Turning the delivery pipeline into an invokable agent, not a fixed flow

---

## 1. Where It Sits in the Agent Roster

```
MAIN AGENT
  │
  ├── Intent Classifier
  │     │
  │     ├── "build X" / "add feature Y"     → Planning Engine → Coding Agents
  │     ├── "research / compare"            → Research Agent
  │     ├── "scan for vulnerabilities"       → Security Agent
  │     ├── "review this code"               → Code Review Agent
  │     ├── "push / deploy / ship / release" → DEPLOY AGENT   ⬅ NEW
  │     └── (anything else)                  → normal conversation
  │
  ▼  (only on deploy intent, and only after confirmation)
DEPLOY AGENT
```

The Deploy Agent is **dormant by default**. It only activates when:
1. Intent Classifier detects deploy-type language ("push this live," "deploy
   to prod," "ship it," "release v2"), **and**
2. There's an active project in context (Main Agent knows the working
   directory / repo from the conversation), **and**
3. Main Agent gets a one-line confirmation from the user before invoking it —
   because triggering a deploy is itself a "confirm" tier permission, not
   "auto-allow."

```
User: "push this to production"
   ↓
Main Agent: "Deploying `dashboard-app` from branch `main` — confirm?"
   ↓ (user: yes)
Main Agent → hands off to Deploy Agent
```

---

## 2. Handoff Contract (what Main Agent passes in)

```json
{
  "project_path": "/home/claude/projects/dashboard-app",
  "repo_url": "git@github.com:user/dashboard-app.git",
  "branch": "main",
  "target_env": "production",
  "requested_by": "user",
  "conversation_ref": "session_id_123"
}
```

The Deploy Agent doesn't re-plan or re-architect anything — the project
already exists. Its job is entirely **validate → secure → ship → watch**.

---

## 3. Deploy Agent Internal Pipeline

This reuses the back half of the full pipeline from before, trimmed down
since there's no requirement-gathering or code generation left to do.

```
DA-1  PREFLIGHT
      Locate project → detect stack → check git status
      (uncommitted changes? ask user: commit now or abort)
        │
DA-2  VALIDATION
      Lint → unit tests → type check
      FAIL → attempt auto-fix (if trivial + permitted) → retry once
      still FAIL → escalate to Debug Agent → halt deploy, report to user
        │
DA-3  SECURITY & QUALITY SCAN
      SAST → dependency vuln scan → secrets scan
      FAIL → hard stop, report findings, do NOT proceed
        │
DA-4  VERSION CONTROL
      Tag release → changelog → backup
        │
DA-5  BUILD & PACKAGE
      Docker build → image scan → push to registry
        │
DA-6  STAGING DEPLOY
      Deploy to staging → smoke tests → health check
        │
DA-7  PRODUCTION APPROVAL GATE  ⛔ always human, never auto-approved
      Show: diff summary, test results, security scan results
      User: approve / reject / request changes
        │
DA-8  PRODUCTION DEPLOY
      Blue/green or canary rollout → health check window →
      auto-rollback if health check fails
        │
DA-9  MONITORING & FEEDBACK
      Live metrics → error tracking → write outcome to Memory
      (so future deploys of this project get faster/smarter)
```

**Hard rule:** DA-1 through DA-6 can run fully autonomously if the user has
already granted deploy permission for this project. **DA-7 cannot be
auto-approved under any settings** — it's the one non-negotiable checkpoint,
same as SPECIAL's rule for destructive actions or payments.

---

## 4. How It Talks Back to the Main Agent

The Deploy Agent doesn't just run silently and dump a final report — it
emits events the Main Agent relays conversationally as they happen:

```
deploy.started
deploy.validation.passed | .failed
deploy.security.passed | .failed
deploy.staging.ready
deploy.awaiting_approval        ← Main Agent surfaces this directly to user
deploy.production.success | .failed
deploy.rolled_back
```

Example, from the user's side:

```
You: push this to production

Main Agent: Deploying dashboard-app from main — confirm? 
You: yes

Main Agent: Running tests and lint... ✅ passed
Main Agent: Running security scan... ✅ no issues found
Main Agent: Deployed to staging, smoke tests passed.
Main Agent: Ready for production. Here's what's changing: [diff summary]
            Approve deploy? 
You: approve

Main Agent: Deployed. Health checks passing. Monitoring for the next 10 min.
```

---

## 5. Why This Is Better Than Baking It Into One Fixed Flow

- **Reusable** — the same Deploy Agent handles every project, not just the
  one being discussed right now. Main Agent just swaps the handoff payload.
- **Composable** — Main Agent can invoke Deploy Agent as one step inside a
  bigger request too (e.g. your earlier "build it, scan it, then book movie
  tickets" example) without duplicating pipeline logic.
- **Safe by construction** — the approval gate lives *inside* the agent, so
  no matter how Deploy Agent gets invoked, production can never be skipped
  past.

---

## 6. Build Note

For Phase 1–2 of your build plan, this doesn't need to be a separate
process or service — it can literally be a Python class `DeployAgent` with
methods `preflight()`, `validate()`, `scan()`, `build()`, `deploy_staging()`,
`await_approval()`, `deploy_prod()`, `monitor()`, called in sequence by the
Task Orchestrator. The "agent" boundary is about **responsibility and
interface**, not about needing microservices from day one.
