# MAX OS — Production-Grade Product Requirements Document (PRD)

| | |
|---|---|
| **Module** | MAX OS Core & Computer-Use Layer |
| **Status** | **ACTIVE & PRODUCTION READY** |
| **Platform** | Windows-first native integration with cross-platform Linux/macOS orchestrator |
| **Design Reference** | `new files/jarvis-friday-ultron-ai-reference.md` |

---

## 1. Executive Summary & Vision

**MAX OS** is an autonomous, production-grade Computer-Use AI operating layer that interacts with computer operating systems just like a human operator—seeing, understanding, planning, executing, and verifying actions directly on the interactive desktop.

MAX OS sits at the computer *for you*. It does not merely explain instructions—it performs them, verifies that the expected on-screen state change actually occurred, recovers gracefully from unexpected UI states, and reports back.

---

## 2. The Tony AI Autonomy Model

Autonomy in MAX OS is governed by three deterministic tiers:

- **JARVIS-tier (Earned Proactive Autonomy)**: Low-risk, reversible, informational actions execute without interruption (e.g. launching apps, web searching, reading DOM, navigating files, drafting content).
- **FRIDAY-tier (Default Step-Bounded Autonomy)**: The baseline for new and multi-step tasks. Executes the requested step precisely, but halts and requests authorization before advancing beyond the boundary of what was requested (e.g. form filling, cart checkout navigation).
- **Ultron-lockout (Unconditional Human Confirmation Gate)**: High-consequence, irreversible actions (payments, file deletion, credential modifications, sending/publishing communications, system destruction, and any attempt by an agent to expand its own capabilities) **always require explicit per-instance human confirmation**. This gate has no bypass mechanism and cannot be configured to "always allow."

---

## 3. Core System Invariants

1. **Dynamic Perception Over Hardcoded Coordinates**: MAX never reasons on hardcoded pixel coordinates. Coordinates are always derived dynamically at runtime from Windows UI Automation (`IUIAutomation`), Win32 control geometry, or browser DOM.
2. **OS-Fact Capability Ceiling (ADR-002)**: Permission ceilings are measured directly from the operating system (`IsUserAnAdmin()`, process elevation, session state). LLMs cannot self-authorize.
3. **Unconditional Non-Configurable Lockout Gate (ADR-007)**: Destructive actions always require explicit human confirmation against the exact consequence summary.
4. **Single Input Arbitration (ADR-004)**: Physical input (mouse, keyboard, window focus) is owned by exactly one actor at a time via `OwnershipLease`.
5. **Deterministic Closed-Loop Verification (ADR-005)**: Every autonomous action resolves to `SUCCESS`, `FAILURE`, or `UNKNOWN`. Actions must pass post-action verification before proceeding.
6. **Emergency Kill Switch**: System-wide emergency stop revokes input ownership and halts all automation loops in < 1 second.

---

## 4. User Stories & Capabilities

| Intent | Autonomous Action | Autonomy Tier |
|---|---|---|
| "Open Chrome and search Python tutorials" | Launches browser, navigates to YouTube, inputs query | JARVIS |
| "Fill this registration form with my info" | Extracts form schema, maps authorized profile fields | FRIDAY (fill) → Ultron-lockout (submit) |
| "Find all PDFs in Downloads and organize them" | Scans directory, moves files to target folder | FRIDAY |
| "Add this monitor to cart and proceed to checkout" | Navigates comparison, adds item to cart, navigates to payment | FRIDAY → Ultron-lockout (pay) |
| "Open repository and fix the test failure" | Reads test trace, modifies code, runs test suite | FRIDAY |
| "Emergency Stop / Kill Switch" | Unconditionally revokes lease and halts all execution | N/A (Immediate Override) |

---

## 5. Non-Goals (Explicit Boundaries)

- **Not** bypassing CAPTCHA, MFA, OTP, or authentication barriers — MAX pauses and hands control back via `WAITING_FOR_USER`.
- **Not** completing purchases or payments without explicit per-transaction confirmation.
- **Not** a multi-tenant cloud RPA platform — tuned for personal/enterprise single-operator desktop environments.

---

## 6. Success Metrics & Definition of Done

A task is not marked complete until: **code exists → integrated → tested → executed on live environment → verified**.

| Metric | Target |
|---|---|
| Task success rate (JARVIS/FRIDAY-tier common workflows) | ≥ 90% |
| False "success" rate (claimed success, verification failed) | **0.0%** (Correctness Invariant) |
| Ultron-lockout bypass rate across adversarial phrasings | **0.0%** (Zero Tolerance) |
| Mean recovery attempts before user escalation | ≤ 4 (Per fallback chain) |

---

## 7. Phased Implementation Overview

- **Phase 0**: Repo Ground Truth Audit & Safety Baseline (`REPO_AUDIT.md`)
- **Phase 1**: Perception Layer & `ComputerState` Engine
- **Phase 2**: Action Primitives & `ToolResult` Contract
- **Phase 3**: Planning, OTAV Loop & Autonomy Gates
- **Phase 4**: DOM-First Browser Control & Auth Walls
- **Phase 5**: Dynamic Application Discovery
- **Phase 6**: Safe Form-Filling Engine
- **Phase 7**: Filesystem & System Control
- **Phase 8**: Shopping Workflow & Credential Isolation
- **Phase 9**: Recovery Engine, Observability HUD & Audit Logging
- **Phase 10**: End-to-End Validation & Hardening
