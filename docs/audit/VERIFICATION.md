# MAX-AGENT — State Verification Forensics

> **Forensic Audit Date**: 2026-09-30  
> **Source Commit**: `877b913` (branch: `max/p0-baseline`)  
> **Auditor**: Principal AI Systems Architect & Codebase Forensic Engineer  
> **Status**: COMPLETED & VERIFIED AGAINST SOURCE CODE  

---

## 1. Executive Forensic Finding: LLM Claim vs System Evidence

In the production codebase, **almost no action performs real state verification.**  
Instead, the system routinely commits **False-Positive Completion Claims**:
- If a Python function completes without raising an exception, MAX considers the action 100% successful.
- In `main.py:_execute_tool()`, any return string (e.g. `"Opened Chrome"`, `"Done."`, `"Code generation completed"`) is packaged into a `FunctionResponse` and sent to Gemini, which announces success to the user.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      THE VERIFICATION REALITY GAP                           │
│                                                                             │
│  User Request: "Open Spotify and play Believer"                             │
│                                                                             │
│  What Actually Happened:                                                    │
│  1. actions/youtube_video.py opened a browser URL via `cmd /c start`.       │
│  2. Browser opened, but was blocked by an ad or login prompt.               │
│  3. No audio is playing.                                                    │
│                                                                             │
│  What MAX Reported:                                                         │
│  "Playing: Believer"  <── FALSE SUCCESS CLAIM!                              │
│                                                                             │
│  Why?                                                                       │
│  Zero inspection of Windows Media Session transport state.                  │
│  Zero inspection of system audio session meter.                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Action-by-Action Verification Strength Audit

| Action / Capability | Documented Success Claim | Actual Verification Performed in Code | Verification Level | True System Evidence Checked |
|---|---|---|---|---|
| **Open Application** (`open_app.py`) | *"Opened Chrome."* | `subprocess.Popen` succeeded or `pyautogui.press("enter")` ran. `time.sleep(2.5)`. | **L0 (None)** | None. Does not check process table or window handle. |
| **Desktop Automation** (`desktop.py`) | *"Done."* | `exec(code)` finished without raising an unhandled Python exception. | **L0 (None)** | None. Does not observe screen diff or target element state. |
| **Code Generation** (`dev_agent.py`) | *"Project complete."* | `exit_code == 0` when running `python main.py` for 20s. | **L1 (Partial)** | Entry point exited cleanly; no assertion tests verified. |
| **Coding Agent** (`coding_agent.py`) | *"Code generation completed."* | If `code` given: `f.write()`. Else: mock string returned. | **L0 / Stub** | None. |
| **Reminder Creation** (`reminder.py`) | *"Reminder set for [time]."* | `schtasks.exe` returncode == 0. | **L3 (OS API)** | Verified with Windows Task Scheduler. |
| **Calendar Event** (`calendar_agent.py`) | *"Calendar event scheduled."* | Returns mock dictionary with hardcoded date. | **L0 / Fake** | None. Fakes confirmation. |
| **Email Send** (`email_agent.py`) | *"Email queued for confirmation."* | Returns mock dictionary. | **L0 / Fake** | None. No email sent, no confirmation shown. |
| **Computer Use** (`computer_use.py`) | *"Computer use loop completed."* | Constructs mock `verify_result = {"status": "SUCCESS"}`. | **L0 / Fake** | None. Completely simulated. |
| **Media Playback** (`youtube_video.py`) | *"Playing: [query]"* | Browser URL launched via subprocess. | **L0 (None)** | None. Does not check media session or audio output. |
| **File Operations** (`file_controller.py`)| *"Moved [file] to [dir]."* | `shutil.move` completed. | **L3 (Filesystem)**| Filesystem check (Python standard library). |

---

## 3. The Dormant Verification Engine (`core/verification/*`)

The repository contains a suite of verification modules under `core/verification/`:
- `engine.py:VerificationEngine`: Defines `VerificationResult(SUCCESS, FAILURE, UNKNOWN)`.
- `process_verifier.py`: Checks if process PID exists and is responsive.
- `window_verifier.py`: Checks if window title and handle match expected patterns.
- `file_verifier.py`: Validates file existence, byte size, and SHA-256 hash.
- `element_verifier.py`: Checks accessibility tree for target control state.
- `state_diff_verifier.py`: Computes before/after diff of computer state.

### Why is it Dormant?
**Zero imports.** `main.py` never imports `core.verification.engine.VerificationEngine`. None of the 19 action handlers call any verifier. The verification engine was developed in isolation during Phase 3 of the previous implementation plan and never integrated into the active tool lifecycle.

---

## 4. Required Evolution (Master Spec Section 14)

1. **Mandatory Postcondition Declarations**:
   - Every capability must declare machine-checkable postconditions before execution.
   - The executing agent cannot modify or bypass its postconditions.
2. **Standardized Outcome Vocabulary**:
   - Every verification must return `SUCCESS`, `FAILURE`, or `UNKNOWN` with attached evidence references.
   - **`UNKNOWN` is never treated as `SUCCESS`**. If state cannot be proven, report `UNKNOWN` and ask the user.
3. **Verification Levels**:
   - **L3 (Deterministic OS/API)**: Process PID + Window handle, Media-session Playing state, file SHA-256 hash, SQLite read-back.
   - **L2 (Structured App State)**: UIA accessibility tree / DOM element state.
   - **L1 (Vision Grounding)**: Multimodal model interpretation of screenshot.
   - **L0 (None)**: Subprocess return code or fixed sleep.
4. **Enforce Level Thresholds**:
   - No `MEDIUM+` or `HIGH` risk action may transition to `COMPLETED` based on L0 or uncorroborated L1 verification.
