# DECISIONS.md — MAX OS Architecture Decision Records

| | |
|---|---|
| **Module** | MAX OS & Computer-Use Layer |
| **Status** | **ACTIVE & CONSOLIDATED** |

---

### ADR-001: Hybrid Cross-Platform Orchestration & Windows Execution Node

**Decision:** The MAX orchestrator, 5-layer memory, and API server run cross-platform (Linux/Windows/macOS), while native computer automation utilizes platform-specific adapters (`core/platform/detector.py`, `src/system/adapters/`). The Computer-Use Layer can run co-located or as a dedicated Windows execution node connected via the `/v1/tasks` API.

**Why:** Maximizes developer productivity and cross-platform flexibility while enabling deep native integration (UIA, Win32, SendInput) on target desktop hosts without forcing a complete rewrite.

---

### ADR-002: Capability Ceiling Comes from OS Facts, Never Instruction Text

**Decision:** `CapabilityProfile` is computed exclusively from real system calls (`os.geteuid()`, `IsUserAnAdmin()`, environment variables). No user message, no LLM output, no task description can raise `max_autonomous_risk` or `control_level` above what `detect_capability_profile()` measured on the machine at that moment.

**Why:** Eliminates prompt injection vectors that attempt to escalate privileges via natural language.

---

### ADR-003: UIA/Win32-First Perception with 7-Level Fallback Hierarchy

**Decision:** Windows UI Automation and Win32 APIs are the primary perception/action mechanism; OCR and vision models are fallback-only (Levels 5–6 of 7). Dynamic coordinates are derived at runtime from element bounding boxes, never hardcoded.

**Why:** Semantic UI Automation is drift-resistant and deterministic. Coordinates are a fallback of last resort.

---

### ADR-004: Three-Tier Autonomy Model (JARVIS / FRIDAY / Ultron-lockout)

**Decision:** Every action carries one of three tiers:
1. **JARVIS-tier**: Reversible, low-risk, earned proactive autonomy.
2. **FRIDAY-tier**: Bounded step execution; halts before expanding scope.
3. **Ultron-lockout**: Unconditional per-instance human confirmation for destructive, financial, or security actions.

**Why:** Prevents the Ultron failure mode where an agent silently broadens its mandate.

---

### ADR-005: Unconditional Post-Action Verification

**Decision:** The Verification Agent evaluates every single action post-execution regardless of risk tier. An action is only marked successful when `verification.passed == True`.

**Why:** Prevents false success reporting and catches silent failures immediately.

---

### ADR-006: Unified SQLite WAL Audit Trail

**Decision:** The Computer-Use Layer writes into the existing 24-table `max_state.db` SQLite store (WAL mode) rather than introducing a parallel database.

**Why:** Single source of truth for full-system observability, timeline queries, and state recovery.

---

### ADR-007: No Standing Authorization for Ultron-Lockout Actions

**Decision:** Lockout-tier actions (payments, deletions, credential changes, submissions) cannot be pre-authorized as a standing blanket rule for a task. Every instance requires explicit confirmation against the exact consequence.

**Why:** Guarantees human oversight remains anchored to real, physical consequences.
