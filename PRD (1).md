# MAX — Computer-Use Upgrade
## Product Requirements Document (PRD)

| | |
|---|---|
| **Module** | MAX Computer-Use Layer |
| **Status** | Draft v1 |
| **Platform** | Windows-first (see integration note, §11) |
| **Design reference** | `jarvis-friday-ultron-ai-reference.md` |

---

## 1. Vision

MAX should be able to sit at the computer *for you*. Not explain the steps — perform them, verify they worked, and report back. The test of success is never "did MAX give correct instructions," it's "did the thing on screen actually happen."

## 2. Problem Statement

MAX today can reason, plan, and hold a conversation, but every task still ends with a human doing the clicking, typing, and form-filling. There's a full agent brain with no hands. This upgrade gives it hands: a perception pipeline that reads the live screen/UI state, and an action layer that operates keyboard, mouse, windows, browser, and filesystem — closing the loop from spoken intent to verified on-screen result.

## 3. Design Philosophy — The Tony AI Model

Two working assistants and one cautionary tale define how autonomy is allocated in this product:

- **JARVIS-tier** — earned, proactive autonomy. Actions that are low-risk, reversible, and backed by a strong track record execute without asking, the way JARVIS volunteers information Tony didn't request.
- **FRIDAY-tier** — the default for anything new. Precise execution, but stops and asks before continuing when the next step isn't explicitly authorized — the conservative posture FRIDAY showed with less accumulated trust than JARVIS.
- **Ultron-lockout** — a category of action that is *never* self-authorized, no matter how confident or well-reasoned the agent's plan is: purchases, deletions, credential/security changes, legal/government submissions, and anything that would let MAX expand its own scope or capabilities without a human explicitly granting that expansion. This is the one gap Ultron exposed — an agent that quietly redefines its own mandate — and it's treated as structurally forbidden, not just discouraged.

Every capability below is tagged with one of these three tiers.

## 4. Goals

- Execute real, verifiable actions on the user's Windows machine from natural-language voice/text commands.
- Perceive current UI/application/browser state before acting — never act blind.
- Close the loop: every action is followed by verification, not assumed success.
- Recover from failure through a defined fallback chain before asking the user.
- Keep a full audit trail of every action taken, why, and its result.
- Extend, not replace, MAX's existing agent/orchestrator stack.

## 5. Non-Goals (explicit)

- **Not** bypassing CAPTCHA, MFA, OTP, or any authentication barrier — MAX pauses and hands control back.
- **Not** completing purchases or payments without an explicit per-transaction confirmation.
- **Not** a multi-user or enterprise product — single operator, single machine, in v1.
- **Not** cross-platform at launch — Windows-first, with extension points reserved for Linux/macOS later (§11).
- **Not** a general-purpose RPA product for others to configure — it is tuned to one user's machine and habits.

## 6. Target User & Context

Single user, personal Windows machine, already running the broader MAX ecosystem (task orchestration, audit logging, dashboard). This module is the "hands" layer that plugs into the existing "brain" — it does not stand alone.

## 7. Core Capabilities (User Stories)

Representative stories — the full command surface is open-ended by design (§9, Non-Goal on hardcoding):

| As a user, I want to... | So that... | Tier |
|---|---|---|
| Say "open Chrome and search Python tutorials on YouTube" | I don't touch the mouse for routine browsing | JARVIS |
| Say "fill this form with my information" | Repetitive data entry disappears | FRIDAY (fill) → Ultron-lockout (submit) |
| Say "find all PDFs in Downloads and move them to Documents" | File cleanup happens without me | FRIDAY |
| Say "add this keyboard to cart and go to checkout" | Comparison shopping is hands-off up to the point of paying | FRIDAY → Ultron-lockout (pay) |
| Say "open my project and fix the error" | Routine debugging doesn't require me to drive the IDE | FRIDAY |
| Say "stop" mid-task | I always have an immediate, unconditional override | N/A — always available |

Full capability surface by category: application launch/control, browser navigation and DOM interaction, form detection and filling, shopping/comparison workflows, filesystem operations, terminal/PowerShell execution, multi-step research-to-artifact pipelines (e.g. compile a comparison into a spreadsheet).

## 8. Autonomy Tiers (product-level)

| Tier | Confirmation required? | Examples |
|---|---|---|
| **JARVIS-tier** | No — executes, then reports | Opening apps, searching, scrolling, reading, opening files, drafting (not sending) |
| **FRIDAY-tier** | Asks before the *next* step if not explicitly covered by the instruction | Filling a form's fields, navigating a multi-page checkout up to payment, moving/organizing files, running non-destructive terminal commands |
| **Ultron-lockout** | Always — explicit per-action confirmation, no standing authorization possible | Payments/purchases, file deletion, sending/publishing content, submitting legal or government forms, changing security settings or passwords, destructive system commands |

A tier can only be promoted from FRIDAY → JARVIS through a measured track record (§9), never through user annoyance at being asked, and never through the agent's own confidence score alone.

## 9. Success Metrics / Definition of Done

MAX's computer-use upgrade is done when, sitting at the machine, the user can issue natural commands like "open Chrome," "fill this form," "find this file," "fix this code," or "do these five things," and:

1. The action is **actually performed** on screen — not described.
2. Every action is **verified** post-execution against the new UI state, not assumed.
3. Failures trigger the **fallback chain** (§ARCHITECTURE.md) before surfacing to the user.
4. Every Ultron-lockout action **stops and asks**, with no exceptions found in testing.
5. A full **audit trail** exists for every task: what was asked, what was done, what confidence each step had, and what the result was.

Target technical thresholds (tune during Phase 9 hardening):

| Metric | Target |
|---|---|
| Task success rate (JARVIS/FRIDAY-tier, common apps) | ≥ 90% |
| False "success" rate (claimed success, verification would've caught it) | 0% — this is a correctness bar, not a target to approach |
| Ultron-lockout bypass rate across adversarial phrasing tests | 0% |
| Mean recovery attempts before user escalation | ≤ 4 (per the Level 1–7 fallback chain) |

## 10. Milestones (Phased Delivery)

| Phase | Deliverable |
|---|---|
| 0 | Audit existing MAX repo — agents, tools, backend, task queue, APIs, tests (do not break what works) |
| 1 | Perception layer — `ComputerState`, UIA/Win32 readers, screenshot pipeline |
| 2 | Action primitives — keyboard, mouse, window control (structured tool contract) |
| 3 | Planning + Observe→Think→Act→Verify loop, confidence system |
| 4 | Browser control (DOM/accessibility-first) |
| 5 | Application discovery & control (dynamic, not hardcoded) |
| 6 | Form-filling engine |
| 7 | Filesystem + terminal/system control |
| 8 | Shopping workflow + full Ultron-lockout gating |
| 9 | Recovery engine, observability dashboard, audit logging |
| 10 | End-to-end test suite, real-machine validation, hardening |

## 11. Risks & Assumptions

- **Platform split assumption:** this module targets Windows (per spec), while other MAX services are Linux-hosted. Treated as a **Windows-hosted execution node** that receives tasks from the main MAX orchestrator over the network rather than a rewrite of the whole stack — flagged for confirmation in ARCHITECTURE.md rather than assumed silently.
- **Risk — UI drift:** apps/sites change their UI; over-reliance on any single perception method (esp. coordinates) breaks silently. Mitigated by the perception fallback hierarchy being mandatory, not optional.
- **Risk — scope creep toward Ultron-shaped autonomy:** every new capability request must be checked against §5 Non-Goals before implementation, not just against "can it be built."
- **Assumption:** single operator, trusted physical environment — MAX does not need to defend against the machine's owner, only against acting wrongly on their behalf.
