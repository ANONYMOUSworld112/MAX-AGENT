# MAX OS — Architecture & Foundation Reference

This directory contains master reference documentation and specifications for the **MAX OS** multi-agent autonomous execution platform.

---

## Key References

- **[AGENTS.md](file:///home/anonymous/MAX-AGENT-main/files/AGENTS.md)**: Master agent roster, autonomy tiers, standard executor interfaces, and safety contracts.
- **[DECISIONS.md](file:///home/anonymous/MAX-AGENT-main/files/DECISIONS.md)**: Architectural Decision Records (ADR-001 through ADR-007) governing system invariants.
- **[AGENT_BUILD_REFERENCE.md](file:///home/anonymous/MAX-AGENT-main/files/AGENT_BUILD_REFERENCE.md)**: Technical specifications for controllers, tool wrappers, and platform backends.

---

## Architectural Core

1. **Observe→Think→Act→Verify (OTAV) Loop**: Every action executes in a closed loop with post-action verification.
2. **Three-Tier Autonomy Model**:
   - `JARVIS-tier`: Proactive, reversible, informational.
   - `FRIDAY-tier`: Conservative, step-bounded execution.
   - `Ultron-lockout`: Hard confirmation gate for critical actions.
3. **7-Level Perception Fallback Hierarchy**: Semantic UI Automation → Win32 → DOM → App APIs → OCR → Vision → Derived Coordinates.
4. **Unified State & Memory**: 24-table SQLite database (`max_state.db`) in WAL mode with 5-layer Bayesian memory.
