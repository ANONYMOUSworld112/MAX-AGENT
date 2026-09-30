# MAX-AGENT — Evolution Benchmark: OpenCode & Coding Executor Architecture

> **Forensic Audit Date**: 2026-09-30  
> **Source Commit**: `877b913` (branch: `max/p0-baseline`)  
> **Auditor**: Principal AI Systems Architect & Codebase Forensic Engineer  
> **Status**: COMPLETED & VERIFIED AGAINST SOURCE CODE  

---

## 1. Executive Forensic Clarification: OpenCode vs MAX

In the broader AI ecosystem, **OpenCode** refers to terminal-based, open-source autonomous coding agents (such as OpenCode, Aider, Claude Code CLI, or custom coding CLIs).  
In MAX-AGENT, **OpenCode is an external execution worker, NEVER the control plane.**
MAX is the master orchestrator, user interface, and safety supervisor.

### The Problem in Current Codebase
- OpenCode is **not integrated at all** in the current checkout.
- Instead, MAX uses `actions/dev_agent.py`, which is an internal, unsandboxed prompt-loop executing code on the host machine.
- This creates severe supply-chain and system stability risks.

---

## 2. Evaluation of Coding Architecture Options

We evaluate three architectural approaches for MAX's software delivery capability:

| Architecture Option | Description | Pros | Cons | Verdict |
|---|---|---|---|---|
| **Option A: Direct Tight Coupling to OpenCode** | Hardcode `subprocess.Popen(["opencode", ...])` directly into `actions/dev_agent.py`. | Fast to write initial wrapper. | Fragile. Breaks when OpenCode CLI flags change; locks MAX into a single vendor/binary. | **REJECTED** |
| **Option B: Pure In-House Coding Loop** | Retain and expand `actions/dev_agent.py` to handle all parsing, diffs, git operations, and execution. | No external binary dependencies. | Massive maintenance burden; reinventing language server protocols, AST diffs, and package managers. | **INSUFFICIENT** |
| **Option C: Provider-Agnostic `CodingExecutor` Interface** | Build a clean abstraction boundary (`CodingExecutor`) with pluggable worker backends: `OpenCodeWorker`, `CodexWorker`, `ClaudeCodeWorker`, and `InternalDevAgentWorker`. | Maximum architectural flexibility. User chooses their preferred coding engine; MAX enforces unified sandboxing, scope checks, and test verification across all backends. | Requires designing a formal execution contract. | **RECOMMENDED & ADOPTED** |

---

## 3. The `CodingExecutor` Target Abstraction

```
                              [ MAX ORCHESTRATOR ]
                                       │
                                       ▼
                              [ CodingTask Model ]
                         (Spec, Constraints, Worktree)
                                       │
                                       ▼
                          [ <<CodingExecutor>> Interface ]
                                       │
         ┌──────────────────┬──────────┴──────────┬──────────────────┐
         ▼                  ▼                     ▼                  ▼
 [ OpenCodeWorker ]  [ CodexWorker ]     [ ClaudeCodeWorker ] [ LocalDevWorker ]
 (CLI Subprocess)    (API / Harness)     (CLI Subprocess)     (Internal venv)
         │                  │                     │                  │
         └──────────────────┴──────────┬──────────┴──────────────────┘
                                       │
                                       ▼
                        [ Imposed Sandbox Boundary ]
                        ├── Dedicated Git Worktree
                        ├── Ephemeral Virtual Environment
                        ├── Wall-Clock and Output Timeouts
                        └── Non-Elevated Execution
                                       │
                                       ▼
                       [ MAX Independent Verification ]
                        ├── Scope Check (git diff --stat)
                        ├── Syntax / Compilation Check
                        ├── Test Integrity & Assertion Check
                        └── Secrets & Dependency Scan
```

---

## 4. Imposed Sandbox & Verification Requirements

An external tool like OpenCode does not inherit MAX's safety policies automatically; **MAX must impose them**:

1. **Workspace Containment**:
   - OpenCode runs strictly inside a disposable git worktree (`git worktree add -b max/task-<id>`).
   - After execution, MAX executes `git status --porcelain`. Any modified file outside the worktree causes immediate task failure and rollback.
2. **Dependency Supply-Chain Gate**:
   - MAX inspects `requirements.txt`, `package.json`, or `pyproject.toml` diffs.
   - If new packages are added, MAX checks them against known PyPI/NPM registries to prevent hallucinated squatting attacks.
   - Package installation requires human confirmation for MEDIUM+ risk operations.
3. **Independent Test Verification**:
   - MAX does not accept `"OpenCode says: All tests passed"`.
   - MAX itself executes the test suite via `ProcessManager` and verifies the test exit code, assertion counts, and execution logs independently.
