# MAX OS — Architecture Delta & Subsystem Compatibility Map (Phase 0)

## 1. Subsystem Inventory & Compatibility Mapping

| Subsystem | Existing File(s) | Status | Action / Integration Plan |
|---|---|---|---|
| **Voice Interface / Input** | `core/speech_io.py`, `agents/nova_voice_operator.py` | Reuse as-is / Extend | Reuse audio input capture and conversational framing; route recognized voice commands to the unified `CommandModel` dispatcher. |
| **TTS / Audio Queue** | `core/single_tts_queue.py`, `core/voice_output.py` | Reuse as-is | Keep the serial FIFO audio queue and non-overlapping audio arbiter intact. All agents narrate execution status through `SingleTTSQueue`. |
| **Input Control Primitives** | `core/win32_interactive_session.py`, `agents/input_control.py` | Extend & Refactor | Reuse low-level Win32 hardware input calls (`user32.mouse_event`, `user32.keybd_event`, smooth cursor gliding). Refactor out hardcoded task scripts (`execute_natural_command`) in favor of semantic `MouseController` and `KeyboardController`. |
| **Task Scheduler & Concurrency** | `core/scheduler.py`, `core/task_state.py`, `core/lock_manager.py` | Extend | Extend scheduler to detect independent vs. dependent concurrent agent tasks; route all physical mouse/keyboard execution through the single `InputArbiter`. |
| **Rollback & Transactions** | `core/snapshot.py`, `core/reconciliation.py` | Reuse & Extend | Reuse atomic filesystem snapshot manager and rollback boundaries. Wire into Tier 2 computer-use transaction wrappers (`TransactionManager`). |
| **Heartbeat Watchdog** | `core/watchdog.py` | Reuse as-is | Monitor long-running computer-use tasks; trigger halt and rollback on missed heartbeats (default 45s). |
| **Security Gate** | `core/permissions.py`, `core/kill_switch.py`, `core/data_boundary.py` | Extend & Harden | Implement deterministic static risk tiering (Tier 0 / Tier 1 / Tier 2), strict per-instance confirmation on destructive/sensitive actions, prompt-injection defense against observed environmental text, and unconditional kill switch preemption. |
| **Tracing & Telemetry** | `core/task_state.py` (`task_trace`), `core/outcome_tracker.py`, `cli/trace.py` | Extend | Extend `task_trace` and live telemetry with action-level computer-use observations, element descriptors, confidence scores, verification outcomes, retries, and recovery strategies. |
| **5-Layer Memory Context Heap** | `core/memory/memory_manager.py` | Extend | Extend Layer 4 (Project/Task Memory) to persist discovered UI structures and application layouts across sessions. |
| **CLI & GUI & API Interfaces** | `cli/main.py`, `cli/operate_desktop.py`, `cli/run_command_flow.py`, `gui/app.py`, `server/app.py` | Extend & Unify | Unify all command execution paths onto the single dynamic computer-use execution engine. |

---

## 2. New Subsystems & Components (Gaps to Build)

### 2.1 Perception Engine (`core/perception/`)
1. **`screen_capture.py`**: High-performance multi-monitor screenshot capture, high-DPI scaling coordinate normalization, active window bounding box cropping.
2. **`accessibility.py`**: Native COM `IUIAutomation` wrapper (`UIAutomationCore.dll` via `comtypes`) for structured accessibility tree walking, element roles, states, and exact bounding boxes.
3. **`browser_dom.py`**: Browser DOM / accessibility snapshot extractor for in-browser semantic interaction (Chrome, Brave, Edge).
4. **`text_detection.py`**: Text extraction and OCR fallback engine.
5. **`element_detection.py`**: Visual element detection fallback for custom-rendered, canvas, and non-UIA application windows.
6. **`ui_detection.py`**: Composite UI detector fusing UIA (Priority 1) -> DOM (Priority 2) -> Window metadata (Priority 3) -> Visual/OCR (Priority 4).
7. **`state_builder.py`**: Rebuilds complete `ComputerState` snapshots (active window, visible windows, processes, monitors, cursor pos, focused element, detected elements with confidence, clipboard metadata, filesystem/terminal contexts, task state).

### 2.2 Controllers & Input Arbitration (`core/controllers/`, `core/input_arbiter.py`)
1. **`mouse_controller.py`**: Semantic element target resolution -> smooth curved gliding -> click, double click, right click, drag, scroll.
2. **`keyboard_controller.py`**: Target focus validation -> click-to-focus if needed -> type text, hotkey sequences, key down/up, clipboard paste/copy.
3. **`input_arbiter.py`**: Exclusive ownership stream of physical input devices with unconditional kill switch revocation.

### 2.3 Verification Engine (`core/verification/`)
1. **`engine.py`**: Central verification engine evaluating before/after state diffs to output strictly `SUCCESS`, `FAILURE`, or `UNKNOWN`.
2. **Specialized Verifiers**:
   - `window_verifier.py`: Window title, focus, and presence verification.
   - `process_verifier.py`: Process launch, existence, and exit code verification.
   - `element_verifier.py`: UI element state, text change, and presence verification.
   - `text_verifier.py`: Expected text pattern presence in window / document.
   - `url_verifier.py`: Browser URL change and page readiness verification.
   - `file_verifier.py`: File creation, modification, size, and hash verification.
   - `state_diff_verifier.py`: Holistic before/after `ComputerState` diff verification.
   - `visual_verifier.py`: Screen region visual diff verification.

### 2.4 Hardened Security Gate & Recovery Engine (`core/security/`, `core/recovery/`)
1. **`security_gate.py`**: Static rule-based risk classification:
   - **Tier 0**: Auto-execute (read, observe, scroll, search, navigate, safe type).
   - **Tier 1**: Confirm once per task (click, form submit without payment/external send, safe save-as).
   - **Tier 2**: Confirm every instance, cannot be batched or bypassed (delete, send external message/email, purchase/payment, admin command, overwrite file, system setting change, kill untargeted process).
   - **Prompt Injection Defense**: Structural isolation of observed environment data from instruction stream.
   - **Irreversible Action Re-confirmation**: Specific consequence warning before non-reversible actions.
   - **Kill Switch Preempt**: Instant physical input revocation on emergency halt.
2. **`recovery_engine.py`**:
   - Failure taxonomy (13 distinct failure classes).
   - Ordered recovery strategy pipeline: `re-observe -> refresh state -> search again -> alternative method -> retry -> change strategy -> replan -> ask user`.
   - Strict retry cap (default 3) and wall-clock timeout budget.

### 2.5 Universal Command Model & Execution Loop (`core/command_model.py`, `core/execution_loop.py`)
- **Universal Command Model**: `Goal -> Intent Object -> Task Plan -> Action Objects` with static risk tiering and verification requirements.
- **Dynamic Execution Loop**: `OBSERVE -> UNDERSTAND -> PLAN -> ACT -> VERIFY -> RECOVER` applied reactively per step.

### 2.6 Agent Layer (`agents/`)
1. **`computer_use_agent.py`**: Master universal operator composing perception, controllers, security gate, verification, and recovery.
2. **`desktop_agent.py`**: Start Menu, taskbar, desktop, windows, dialogs, generic app launch and focus.
3. **`browser_agent.py`**: Browser launch/focus, tabs, navigation, search, form interaction, popup handling.
4. **`application_agent.py`**: Universal `DISCOVER -> CONNECT -> OBSERVE -> INTERACT -> VERIFY` protocol with application adapters (`applications/vscode_adapter.py`, `browser_adapter.py`, `file_explorer_adapter.py`, `terminal_adapter.py`, `office_adapter.py`) and unknown application fallback.
5. **`research_agent.py`**: Multi-source research with citation tracking and blocked page recovery.
6. **`file_agent.py`**: File discovery, move/copy/rename, hash/size verification.
7. **`terminal_agent.py`**: PowerShell execution, output capture, exit-code verification.

---

## 3. Phase 0 Exit Gate Verification
- [x] Entire existing codebase audited across all 37 test files and 32 core modules.
- [x] Subsystem mapping completed (reuse / extend / build).
- [x] Native COM UI Automation (`IUIAutomation`) verified operational on Windows.
- [x] Build decisions and gap resolutions logged to `build_decisions.log`.
