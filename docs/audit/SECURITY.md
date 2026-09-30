# MAX-AGENT — Security Architecture & Threat Vulnerability Forensics

> **Forensic Audit Date**: 2026-09-30  
> **Source Commit**: `877b913` (branch: `max/p0-baseline`)  
> **Auditor**: Principal AI Systems Architect & Codebase Forensic Engineer  
> **Status**: COMPLETED & VERIFIED AGAINST SOURCE CODE  

---

## 1. Executive Summary: Security Posture

The repository contains advanced security designs on paper (`ReflexGuardrails`, `DataBoundary`, `MaxVault`, `KillSwitch`).  
However, **none of these security mechanisms protect the actual execution path in production.**

The active system suffers from **five critical security vulnerabilities**:
1. **Unchoked Side Effects**: 37 execution call sites across 16 files execute OS commands, write files, and manipulate processes directly without passing through a single choke point.
2. **Remote Code Execution (RCE)**: `actions/desktop.py` passes LLM-generated code strings directly into Python's `exec()` function.
3. **Host Environment Contamination**: `actions/dev_agent.py` installs unpinned, unsandboxed packages into the host interpreter via `sys.executable -m pip install`.
4. **Plaintext Credential Storage**: API keys are stored in unencrypted JSON at `config/api_keys.json`.
5. **Overexposed Network Surface**: `dashboard/server.py` binds to `0.0.0.0` (all network interfaces) and attempts to automatically punch through the Windows Firewall using an elevated batch script.

---

## 2. Forensic Audit of the 7 Master Spec Threats

| Threat Vector | Master Spec Requirement | Codebase Reality | Forensic Finding |
|---|---|---|---|
| **1. Prompt Injection** | Delimit and label untrusted data in prompts; untrusted context cannot create side-effect tasks without confirmation. | Untrusted web search results, YouTube transcripts, and screen text are concatenated directly into prompts (`main.py:1385`, `actions/youtube_video.py:177`). | **CRITICAL VULNERABILITY**: Indirect prompt injection can hijack model execution. |
| **2. Audio Injection** | Gate mic during TTS output; voice alone never confirms HIGH/CRITICAL actions. | Mic is gated during TTS via `self._speaking_lock`, but voice can confirm setting changes. | **PARTIAL**: Mic gating works; lack of channel trust separation remains. |
| **3. Localhost API / CSRF** | Bind API to `127.0.0.1` only; per-install random token; validate `Origin` and `Host`. | `dashboard/server.py` binds to `0.0.0.0:8000`. Does not validate `Origin` or `Host` headers. Accepts unencrypted WebSocket commands. | **CRITICAL VULNERABILITY**: Any device on the LAN (or website via DNS rebinding) can trigger commands. |
| **4. Supply-Chain Compromise** | Installs come only from allowlisted sources with pinned versions and checksums; never pipe remote scripts into shells. | `actions/dev_agent.py` executes `pip install <dep>` on the host machine using package names proposed by Gemini Flash. | **CRITICAL VULNERABILITY**: Susceptible to PyPI typosquatting and hallucinated package attacks. |
| **5. Secret Leakage** | Single SecretStore; secrets injected only into specific child environments; redaction filter on logs/prompts/events. | API keys stored in plaintext `config/api_keys.json`. No redaction filter on `self.ui.write_log()` or console outputs. | **HIGH RISK**: API keys and personal tokens exposed in logs and child processes. |
| **6. Memory Poisoning** | Only verified task outcomes and TRUSTED-origin statements may become long-term facts/preferences. | `save_memory` can be invoked silently by Gemini based on untrusted inputs. `_save_session_summary` summarizes raw user dialogue. | **HIGH RISK**: Stored preferences and summaries can be poisoned by malicious text. |
| **7. Runaway / Hung Agent Loop** | External watchdog process; emergency stop hotkey; step and budget limits. | `Watchdog` in `core/max_infra/watchdog.py` is never started. UI interrupt button drains audio queue, but does not kill background threads. | **HIGH RISK**: Long-running loops or hung subprocesses cannot be interrupted from UI. |

---

## 3. Inventory of Unchoked Side-Effect Call Sites

All 37 direct execution call sites that bypass a security gateway are itemized in `docs/UNCHOKED_SIDE_EFFECTS.md`.  
Key offenders:
- `actions/desktop.py:97`: `exec(compile(code, "<max_desktop>", "exec"), sandbox)`
- `actions/dev_agent.py:245, 255`: `subprocess.run([sys.executable, "-m", "pip", "install", dep])`
- `actions/open_app.py:84, 97`: `subprocess.Popen(app_name, shell=True)`
- `actions/file_controller.py:112, 145`: `os.remove(path)`, `shutil.rmtree(path)`
- `actions/reminder.py:186`: `subprocess.run(["schtasks.exe", "/create", ...])`
- `dashboard/server.py:204`: `ctypes.windll.shell32.ShellExecuteW(None, "runas", bat_path, ...)`

---

## 4. Required Evolution (Master Spec Section 13)

1. **Mandatory `ExecutionGateway` (Single Choke Point)**:
   - All side effects must pass through `ExecutionGateway.execute(ActionRequest)`.
   - Gate pipeline: validate schema → compute risk tier → verify resource lease → confirmation check → execute with timeout → capture result → emit audit event.
2. **Automated AST Banned-Import Test**:
   - Prohibit direct imports of `subprocess`, `os.system`, `pyautogui`, `ctypes.windll`, `shutil.rmtree` outside of approved adapter modules.
3. **Dashboard Hardening**:
   - Re-bind dashboard to `127.0.0.1` only.
   - Enforce random token authentication, validate `Origin`/`Host` headers, and reject state changes on GET.
4. **OS Credential Keyring**:
   - Move API keys from `config/api_keys.json` to Windows Credential Manager (`keyring` library) or AES-256 encrypted `MaxVault`.
