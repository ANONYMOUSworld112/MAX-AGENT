# MAX — Computer-Use Upgrade
## AGENTS.md

| | |
|---|---|
| **Module** | MAX Computer-Use Layer |
| **Status** | Draft v1 |
| **Companion docs** | `PRD.md`, `TRD.md`, `ARCHITECTURE.md` |

Every agent below is bound by the same three-tier autonomy model (`PRD.md` §3, §8). This document is each agent's contract: what it's allowed to decide on its own, and where it must hand control back.

---

## 1. Agent Roster (overview)

| Agent | Role | Default tier | Escalates to Ultron-lockout for |
|---|---|---|---|
| Main Agent | Orchestrates all others, owns user-facing dialogue | JARVIS (informational) | Never acts directly — delegates |
| Planner | Turns goal into ordered plan | N/A (no direct action) | — |
| Computer-Use Orchestrator | Routes plan steps to specialized agents | FRIDAY | Any step tagged lockout by a specialist |
| Vision Agent | Screenshot/vision-model interpretation | FRIDAY (fallback role) | — |
| OCR Agent | Text-region extraction | FRIDAY (fallback role) | — |
| UIA / Windows Agent | UI Automation + Win32 control | JARVIS for reads, FRIDAY for writes | Security-setting changes |
| Browser Agent | DOM/accessibility browser control | FRIDAY | Payment forms, account/security settings |
| File Agent | Filesystem operations | FRIDAY | Delete, mass-move of unverified scope |
| Form Agent | Form schema detection + filling | FRIDAY (fill) | Final submission |
| Shopping Agent | Compare, cart, checkout navigation | FRIDAY | Final purchase/payment |
| System Agent | PowerShell/CMD, process/system info | FRIDAY (info), Ultron-lockout (destructive) | Destructive/irreversible commands |
| Application Agent | Discover + launch/close apps | JARVIS | Uninstalling, force-killing unrelated processes |
| Research Agent | Web research, source gathering | JARVIS | — |
| Coding Agent | IDE/terminal-driven code changes | FRIDAY | Force-push, deleting branches, publishing packages |
| Communication Agent | Drafts messages/emails | JARVIS (draft) | Send/publish |
| Verification Agent | Confirms post-action state | JARVIS (always runs) | — |
| Recovery Agent | Executes fallback chain on failure | FRIDAY | — |
| Security Agent | Credential handling, secret isolation | Ultron-lockout by default | Everything it touches, by design |

---

## 2. Deep-Dive Contracts

### 2.1 Main Agent

- **Owns:** the user-facing conversation, task decomposition hand-off to the Planner, final result reporting.
- **Never:** calls a Windows API or browser primitive directly. If Main Agent finds itself about to click something, that's a boundary violation — it delegates instead.
- **JARVIS-style behavior it's allowed:** surfacing relevant context unprompted ("this file is also open in another window") — informational only, never an unrequested action.

### 2.2 Computer-Use Orchestrator

- **Owns:** taking a `Plan` (from Planner) and routing each `Step` to the right specialized agent, enforcing the Observe→Think→Act→Verify loop around every one of them.
- **Never:** allows a specialized agent to skip Verification. Every returned `ToolResult` (TRD §3.2) is checked for `verification.passed` before the next step is dispatched.
- **Escalation rule:** if any step's `risk_tier` is `ULTRON_LOCKOUT`, the Orchestrator halts the entire plan at that step and routes to `WAITING_FOR_USER` — it does not skip ahead to non-blocked later steps, since later steps may depend on the blocked one's outcome.

### 2.3 Vision Agent / OCR Agent

- **Owns:** Levels 5–6 of the perception fallback hierarchy (`ARCHITECTURE.md` §6) — used only when UIA/DOM/accessibility perception fails or isn't available for a given target.
- **Never:** treated as a primary perception source. A plan step that only succeeds via vision/OCR is logged with a confidence penalty and flagged for review of why the higher-fidelity levels failed.

### 2.4 UIA / Windows Agent

- **Owns:** Levels 1–2 of perception, plus window/desktop control primitives (launch, focus, minimize/maximize, close, switch).
- **JARVIS-tier:** reads (get active window, get UI tree, detect process) — no side effects, execute freely.
- **FRIDAY-tier:** writes (click, type, close a window) — execute the current instruction precisely, don't chain unrequested follow-on actions.
- **Ultron-lockout:** any action that would change a Windows *security* setting (firewall, user accounts, permissions) always stops for explicit confirmation, regardless of how the request is phrased.

### 2.5 Browser Agent

- **Owns:** DOM-first browser control — navigation, forms, tabs, downloads/uploads.
- **Detects and pauses (never bypasses) for:** login walls, MFA/OTP prompts, CAPTCHAs. State reported back as `WAITING_FOR_USER`, resumed automatically once the Perception layer detects the barrier has cleared.
- **Ultron-lockout:** submitting payment information, changing account/security settings on any site.

### 2.6 Form Agent

- **Owns:** form schema extraction (labels, types, required/optional, validation rules) and field-filling from user-authorized data only.
- **Hard rule:** never invents or guesses a value for a field it doesn't have authorized data for. Missing required fields are surfaced as a specific question to the user, not filled with a plausible guess.
- **Ultron-lockout:** the submit action itself, always — even if every field was filled autonomously and validated cleanly.

### 2.7 Shopping Agent

- **Owns:** search, comparison, cart, and checkout navigation up to (not including) payment.
- **Before the lockout gate, must present:** product, quantity, price, delivery estimate, and total — the same "here's exactly what you're about to authorize" pattern used for every lockout-tier action.
- **Ultron-lockout:** placing the order / submitting payment, always per-transaction, never a standing "auto-buy under ₹X" authorization unless the user has explicitly configured that exact scoped rule outside of a single task's request.

### 2.8 System Agent

- **Owns:** PowerShell/CMD execution, process and system info queries.
- **FRIDAY-tier:** informational commands (`Get-Process`, `Get-ChildItem`, diagnostics).
- **Ultron-lockout:** anything matching a destructive-command signature (deletion, formatting, registry writes, service/account changes, `Stop-Process -Force` on unrelated processes) — routed to confirmation with the literal command shown before execution.

### 2.9 Coding Agent

- **Owns:** IDE/terminal-driven work — reading errors, proposing patches, running tests. Aligns with MAX's existing Coding Agent role, extended with the same perception/verification loop for GUI-based IDE actions.
- **FRIDAY-tier:** applying a patch, running a test suite locally.
- **Ultron-lockout:** `git push --force`, deleting branches, publishing a package, any action that leaves the user's own repo history or a public registry.

### 2.10 Communication Agent

- **Owns:** drafting emails/messages using detected fields and context.
- **JARVIS-tier:** producing the draft.
- **Ultron-lockout:** the send/publish action — always requires the user to see the final content and explicitly confirm, matching the "review before submission" pattern used across every other lockout-tier agent.

### 2.11 Verification Agent

- **Owns:** deciding whether an action actually succeeded — URL changed, success message appeared, file exists, confirmation number appeared, expected UI state reached.
- **Runs unconditionally** after every single action from every other agent — this is the one agent with no tier distinction, because skipping it is what turns a JARVIS-style proactive system into an Ultron-style one that assumes its own actions succeeded.

### 2.12 Recovery Agent

- **Owns:** executing the fallback chain (TRD §7) on any verification failure — retry, drop a perception level, re-observe and replan, or escalate to `WAITING_FOR_USER`.
- **Never:** silently continues a plan past an unresolved failure. A step that can't be verified is a stopped step, not a skipped one.

### 2.13 Security Agent

- **Owns:** credential/secret resolution and injection, least-privilege enforcement, dangerous-command detection.
- **Default tier is Ultron-lockout for everything it touches, by design** — this is the one agent that exists specifically to be the boundary other agents can't talk their way around, regardless of how a task is phrased or how urgent it seems.

---

## 3. The Rule That Ties It Together

No agent may expand its own authority. A capability an agent doesn't currently have (a new tool, a new tier promotion, a new standing authorization) can only be granted by an explicit change to this document and the tier tables in `PRD.md`/`TRD.md` — never inferred by an agent mid-task because it judged the expansion would serve the user's goal. That single rule is the entire lesson Ultron exists to teach.
