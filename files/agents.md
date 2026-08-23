# MAX OS — AGENTS.md
### Master Agent Roster & Autonomous Execution Contracts

| | |
|---|---|
| **Module** | MAX OS & Computer-Use Layer |
| **Status** | **ACTIVE & RECONCILED** |
| **Companion docs** | `PRD.md`, `TRD.md`, `ARCHITECTURE.md`, `DECISIONS.md` |

Every agent below is bound by the three-tier autonomy model (`PRD.md` §2, §3). This document defines each agent's contract: what it is authorized to decide independently, and where it must hand control back to the human operator.

---

## 1. Unified Agent Interface Contract

Every agent in MAX OS satisfies the standard executor signature:

```python
def agent_executor(task: Task) -> ToolResult:
    """
    Executes within the Observe->Think->Act->Verify loop.
    Returns standard ToolResult contract. Raises on fatal failure.
    Orchestrator handles retry, fallback, and audit logging.
    """
```

Registered via `orchestrator.register_agent(name, executor)`. Agents interact via `tools/interfaces.py` and `core/computer_control/` abstractions, never calling raw unmonitored OS primitives directly.

---

## 2. Computer-Use Specialized Agent Roster (17 Agents)

| Agent | Module / Role | Default Tier | Escalates to Ultron-lockout for |
|---|---|---|---|
| **Main Agent** | `src/core/main_agent.py` — Orchestrates all others, user dialogue | JARVIS (informational) | Never acts directly — delegates |
| **Planner** | `core/planner.py` — Turns goal into ordered plan DAG | N/A (no direct action) | — |
| **Computer-Use Orchestrator** | `core/orchestrator.py` — Routes plan steps in OTAV loop | FRIDAY | Any step tagged lockout by a specialist |
| **Vision Agent** | `core/perception/element_detection.py` — Screenshot / VLM interpretation | FRIDAY (fallback role) | — |
| **OCR Agent** | `core/perception/text_detection.py` — Text-region extraction | FRIDAY (fallback role) | — |
| **UIA / Windows Agent** | `core/perception/accessibility.py` — UI Automation + Win32 control | JARVIS (reads) / FRIDAY (writes) | Security-setting changes |
| **Browser Agent** | `agents/browser_agent.py` — DOM/accessibility browser control | FRIDAY | Payment forms, account/security settings |
| **File Agent** | `agents/file_agent.py` — Filesystem operations | FRIDAY | Delete, mass-move of unverified scope |
| **Form Agent** | `agents/form_agent.py` — Form schema detection + filling | FRIDAY (fill) | Final submission |
| **Shopping Agent** | `agents/shopping_agent.py` — Compare, cart, checkout navigation | FRIDAY | Final purchase/payment |
| **System Agent** | `agents/system_agent.py` — PowerShell/CMD, process/system info | FRIDAY (info), Ultron-lockout (destructive) | Destructive/irreversible commands |
| **Application Agent** | `agents/application_agent.py` — Discover + launch/close apps | JARVIS | Uninstalling, force-killing unrelated processes |
| **Research Agent** | `agents/research.py` — Web research, source gathering | JARVIS | — |
| **Coding Agent** | `agents/coding.py` — IDE/terminal-driven code changes | FRIDAY | Force-push, deleting branches, publishing packages |
| **Communication Agent** | `agents/communication_agent.py` — Drafts messages/emails | JARVIS (draft) | Send/publish |
| **Verification Agent** | `core/verification/engine.py` — Confirms post-action state | JARVIS (always runs) | — |
| **Recovery Agent** | `core/recovery/recovery_engine.py` — Executes fallback chain | FRIDAY | — |
| **Security Agent** | `core/security/security_gate.py` — Credential handling, secret isolation | Ultron-lockout by default | Everything it touches, by design |

---

## 3. Worker & Subsystem Agent Registry (28 Registered Agents)

| Agent | Module Path | Does | Execution Mode | Default Permission | Status |
|---|---|---|---|---|---|
| **Calendar Agent** | `agents/calendar.py` | Schedule, reminders, conflict detection | on_demand | auto | verified |
| **Notes Agent** | `agents/notes.py` | Capture, natural-language retrieval | on_demand | auto | verified |
| **Coding Agent** | `agents/coding.py` | Build/fix code against acceptance criteria | on_demand | confirm | verified |
| **Deploy Agent** | `agents/deploy.py` | 9-Stage Pipeline (DA-1..6 staging, DA-7 gate, DA-8..9 rollout) | on_demand | confirm | verified |
| **Web Search Agent** | `agents/websearch.py` | Real-time lookups, quota-checked | on_demand | auto | verified |
| **Research Agent** | `agents/research.py` | Multi-query deep research & report synthesis | on_demand | auto | verified |
| **Document Agent** | `agents/document.py` | PPT/PDF/Markdown generation | on_demand | auto | verified |
| **Application Assist** | `agents/application_assist.py` | Drafts applications & forms (never auto-submits) | on_demand | confirm | verified |
| **Inbox Agent** | `agents/daily_life.py` | Email triage, spam filtering, thread summaries | scheduled | auto | verified |
| **Expense Agent** | `agents/daily_life.py` | Receipt parsing, expense categorization, budget tracking | on_demand | auto | verified |
| **Founder CRM Agent** | `agents/daily_life.py` | Contact sync, interaction notes, follow-up reminders | on_demand | auto | verified |
| **Content Draft Agent** | `agents/daily_life.py` | Blog/social/newsletter drafts (never auto-publishes) | on_demand | auto | verified |
| **Daily Brief Agent** | `agents/daily_life.py` | Morning synthesis: weather, calendar, urgent items | scheduled | auto | verified |
| **Monitor Agent** | `agents/daily_life.py` | System health, URL uptime, background process alerts | continuous | auto | verified |
| **Architecture Review** | `agents/engineering.py` | Evaluates proposed changes against architectural ADRs | on_demand | auto | verified |
| **Security Agent** | `agents/engineering.py` | Dependency audits, secret scanning, permission checks | scheduled | auto | verified |
| **Testing Agent** | `agents/engineering.py` | Generates test cases, runs test suites, computes coverage | on_demand | auto | verified |
| **Debug Agent** | `agents/engineering.py` | Stack trace analysis, log triage, root-cause diagnosis | on_demand | auto | verified |
| **Documentation Agent**| `agents/engineering.py` | Syncs docstrings, updates architecture docs, changelogs | on_demand | auto | verified |
| **Code Review Agent** | `agents/engineering.py` | PR-level review: style, logic, security, test gaps | on_demand | auto | verified |
| **Database Agent** | `agents/infrastructure.py`| Schema migrations, query profiling, index suggestions | on_demand | confirm | verified |
| **Cloud/Infra Agent** | `agents/infrastructure.py`| Terraform/IaC templates, resource cost estimation | on_demand | confirm | verified |
| **Data Pipeline Agent** | `agents/infrastructure.py`| ETL task scaffolding, data quality validation | on_demand | confirm | verified |
| **Backup/DR Agent** | `agents/infrastructure.py`| Snapshot verification, backup integrity checks | scheduled | confirm | verified |
| **Analytics Agent** | `agents/infrastructure.py`| Metric aggregation, usage reporting, performance stats | scheduled | auto | verified |
| **Keyboard Agent** | `agents/input_control.py` | Non-blocking async typing & hotkeys | on_demand | blocked (gated) | verified |
| **Mouse Agent** | `agents/input_control.py` | Async clicks, movements & scrolling | on_demand | blocked (gated) | verified |
| **Screen Agent** | `agents/input_control.py` | Parallel desktop stream & OCR bridge | on_demand | blocked (gated) | verified |

---

## 4. The Cardinal Safety Invariant

No agent may expand its own authority. A capability an agent does not currently possess can only be granted by an explicit update to the permission schema and human confirmation — never inferred by an agent mid-task because it judged the expansion would serve the user's goal.
