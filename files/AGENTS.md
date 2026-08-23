# AGENTS.md — MAX OS Unified Agent Roster & Autonomy Contracts

| | |
|---|---|
| **Module** | MAX OS & Computer-Use Layer |
| **Status** | **RECONCILED & ACTIVE** |
| **Companion docs** | `PRD.md`, `TRD.md`, `ARCHITECTURE.md`, `DECISIONS.md` |

Every agent below is bound by the same three-tier autonomy model (`PRD.md` §3, §8). This document is each agent's contract: what it's allowed to decide on its own, and where it must hand control back.

---

## 1. Agent Roster & Autonomy Tiers

| Agent | Role | Default Autonomy Tier | Escalates to Ultron-lockout for |
|---|---|---|---|
| **Main Agent** | Orchestrates all others, owns user-facing dialogue | JARVIS (informational) | Never acts directly — delegates |
| **Planner** | Turns goal into ordered plan DAG | N/A (no direct action) | — |
| **Computer-Use Orchestrator** | Routes plan steps to specialized agents | FRIDAY | Any step tagged lockout by a specialist |
| **Vision Agent** | Screenshot/vision-model interpretation | FRIDAY (fallback role) | — |
| **OCR Agent** | Text-region extraction | FRIDAY (fallback role) | — |
| **UIA / Windows Agent** | UI Automation + Win32 control | JARVIS for reads, FRIDAY for writes | Security-setting changes |
| **Browser Agent** | DOM/accessibility browser control | FRIDAY | Payment forms, account/security settings |
| **File Agent** | Filesystem operations | FRIDAY | Delete, mass-move of unverified scope |
| **Form Agent** | Form schema detection + filling | FRIDAY (fill) | Final submission |
| **Shopping Agent** | Compare, cart, checkout navigation | FRIDAY | Final purchase/payment |
| **System Agent** | PowerShell/CMD, process/system info | FRIDAY (info), Ultron-lockout (destructive) | Destructive/irreversible commands |
| **Application Agent** | Discover + launch/close apps | JARVIS | Uninstalling, force-killing unrelated processes |
| **Research Agent** | Web research, source gathering | JARVIS | — |
| **Coding Agent** | IDE/terminal-driven code changes | FRIDAY | Force-push, deleting branches, publishing packages |
| **Communication Agent** | Drafts messages/emails | JARVIS (draft) | Send/publish |
| **Verification Agent** | Confirms post-action state | JARVIS (always runs) | — |
| **Recovery Agent** | Executes fallback chain on failure | FRIDAY | — |
| **Security Agent** | Credential handling, secret isolation | Ultron-lockout by default | Everything it touches, by design |

---

## 2. Standard Agent Interface

Every agent satisfies the standard execution contract:

```python
def agent_executor(task: Task) -> ToolResult:
    """
    Executes within the Observe->Think->Act->Verify loop.
    Returns standard ToolResult contract. Raises on fatal failure.
    Orchestrator handles retry, fallback, and audit logging.
    """
```

Registered via `orchestrator.register_agent(name, executor)`. An agent interacts with tools via `tools/interfaces.py` and `core/computer_control/` abstractions, never calling unmonitored OS primitives directly.

---

## 3. Deep-Dive Contracts

### 3.1 Main Agent
- **Owns:** the user-facing conversation, task decomposition hand-off to the Planner, final result reporting.
- **Never:** calls an OS API or browser primitive directly. If Main Agent finds itself about to click something, that's a boundary violation — it delegates instead.
- **JARVIS-style behavior:** surfaces relevant context unprompted ("this file is also open in another window") — informational only, never an unrequested action.

### 3.2 Computer-Use Orchestrator
- **Owns:** taking a `Plan` (from Planner) and routing each `Step` to the right specialized agent, enforcing the Observe→Think→Act→Verify loop around every one of them.
- **Never:** allows a specialized agent to skip Verification. Every returned `ToolResult` is checked for `verification.passed` before the next step is dispatched.
- **Escalation rule:** if any step's `risk_tier` is `ULTRON_LOCKOUT`, the Orchestrator halts the entire plan at that step and routes to `WAITING_FOR_USER`.

### 3.3 Verification Agent
- **Owns:** deciding whether an action actually succeeded — URL changed, success message appeared, file exists, confirmation number appeared, expected UI state reached.
- **Runs unconditionally** after every single action from every other agent — this is the one agent with no tier distinction.

### 3.4 Recovery Agent
- **Owns:** executing the 4-attempt fallback chain on any verification failure — retry, drop a perception level, re-observe and replan, or escalate to `WAITING_FOR_USER`.
- **Never:** silently continues a plan past an unresolved failure.

### 3.5 Security Agent
- **Owns:** credential/secret resolution and injection, least-privilege enforcement, dangerous-command detection.
- **Default tier is Ultron-lockout for everything it touches, by design.**

---

## 4. Fundamental Invariant

No agent may expand its own authority. A capability an agent doesn't currently have can only be granted by an explicit change to the permission tables and human confirmation — never inferred by an agent mid-task because it judged the expansion would serve the user's goal.
