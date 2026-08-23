# MAX OS — Production-Grade Autonomous Computer-Use Operating Layer

MAX OS is a production-grade autonomous Computer-Use AI operating layer engineered to see, understand, plan, execute, and verify tasks on interactive desktop environments in real time.

---

## 🎮 Master Cockpit Runner

MAX OS includes a unified master cockpit runner connecting all subsystems:

```bash
# 1. Launch the interactive master cockpit (9 options)
python3 main.py

# 2. Launch the Marvel AI Terminal directly
python3 main.py --terminal

# 3. Execute natural language computer-use and system commands
python3 main.py "organize files in Downloads folder"
python3 main.py "run command ls -la"
python3 main.py "open google.com and search quantum computing"
python3 main.py "generate security audit presentation"
```

---

## 🌟 Key System Invariants & Autonomy Model

1. **The Tony AI Autonomy Model**:
   - **JARVIS-tier**: Reversible, low-risk, earned proactive autonomy (executes and reports).
   - **FRIDAY-tier**: Default step-bounded execution; halts before expanding beyond requested scope.
   - **Ultron-lockout**: Unconditional per-instance human confirmation for destructive, financial, or security actions.
2. **Dynamic Perception Over Fixed Coordinates**: Screen coordinates are derived dynamically from Windows UI Automation (`IUIAutomation`), Win32 HWND geometry, Linux X11/Wayland, or Browser DOM—never hardcoded.
3. **OS-Fact Capability Ceiling**: Permissions are measured directly from operating system facts (`IsUserAnAdmin()`, process elevation, session state). LLMs cannot self-authorize.
4. **Single Input Arbitration**: Hardware input (keyboard, mouse, window focus) is owned by exactly one actor at a time via `OwnershipLease`.
5. **Deterministic Closed-Loop Verification**: Every action executes in a mandatory Observe→Think→Act→Verify (OTAV) loop and resolves strictly to `SUCCESS`, `FAILURE`, or `UNKNOWN`.
6. **Emergency Kill Switch (Component #0)**: Immediate revocation of input leases and cancellation of automation loops in < 1 second upon trigger via `core/kill_switch.py`.
7. **Dual-Engine Voice Synthesis & STT**: High-fidelity ElevenLabs voice synthesis with local Faster-Whisper offline transcription.

---

## 🏗️ 10-Layer Architecture Pipeline

```text
USER REQUEST / VOICE / CLI
       │
   L0: INTERFACE LAYER (Speech / STT / VAD / Live HUD / Terminal Shell)
       │
   L1: MAIN AGENT & INTENT CLASSIFIER (Dynamic 10-Domain Routing)
       │
   L2: PLANNER & TASK DECOMPOSITION (DAG Generation)
       │
   L3: TASK QUEUE & STATE STORE (max_state.db WAL)
       │
   L4: COMPUTER-USE ORCHESTRATOR (OTAV Loop Driver)
       │
   L5: SPECIALIZED AGENT ROSTER (Filesystem, Terminal, Browser, Desktop, Coding, Deploy, Notes, Calendar, Research, Doc)
       │
   L6: ACTION PRIMITIVES (Mouse, Keyboard, Window, Filesystem, System)
       │
   L8: REAL OS / DESKTOP / BROWSER INTERACTION
       │
   L7: 7-LEVEL PERCEPTION LAYER (UIA → Win32 → DOM → A11y → OCR → VLM → Coords)
       │
   L9: VERIFICATION & 4-ATTEMPT RECOVERY ENGINE
       │
   AUDIT LOGGING (SQLite WAL) & 5-LAYER MEMORY UPDATE
```

---

## 🧪 Verification & Testing

```bash
# Run unit & integration test suite
pytest

# Run system smoke test
python3 smoke_test.py

# Run live ambient presence & memory demo
python3 demo_jarvis_supreme_live.py

# Run live multi-agent routing pipeline demo
python3 demo_live_routing.py
```

---

## 📚 Core Documentation Suite (in `files/`)

All system specification, architecture, and design documents are cataloged inside the **[`files/`](file:///home/anonymous/MAX-AGENT-main/files/)** directory:

- **[files/PRD.md](file:///home/anonymous/MAX-AGENT-main/files/PRD.md)** — Product Requirements & Autonomy Model
- **[files/ARCHITECTURE.md](file:///home/anonymous/MAX-AGENT-main/files/ARCHITECTURE.md)** — 10-Layer System Blueprint & OTAV Loop
- **[files/TRD.md](file:///home/anonymous/MAX-AGENT-main/files/TRD.md)** — Technical Requirements & `ToolResult` Contract
- **[files/AGENTS.md](file:///home/anonymous/MAX-AGENT-main/files/AGENTS.md)** — Unified Agent Roster & Autonomy Contracts
- **[files/DECISIONS.md](file:///home/anonymous/MAX-AGENT-main/files/DECISIONS.md)** — Architectural Decision Records (ADR-001 through ADR-012)
- **[files/REPO_AUDIT.md](file:///home/anonymous/MAX-AGENT-main/files/REPO_AUDIT.md)** — Phase 0 Repo Ground Truth Audit
- **[files/API_CONTRACT.md](file:///home/anonymous/MAX-AGENT-main/files/API_CONTRACT.md)** — REST API Endpoints & Control Seams
- **[files/COMPLETE_PROJECT_RECORD_AND_IMPLEMENTATION_GUIDE.md](file:///home/anonymous/MAX-AGENT-main/files/COMPLETE_PROJECT_RECORD_AND_IMPLEMENTATION_GUIDE.md)** — Master Project Implementation Guide
