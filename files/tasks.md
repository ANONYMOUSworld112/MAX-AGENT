# MAX OS — TASKS.md
### LIVE SNAPSHOT — generated from max_state.db
### Last generated: 2026-08-14 08:12 UTC

---

## Current Phase

All phases complete.

## Next 3 Actionable Steps



## Blocked

None currently.

## Recently Completed

- **Step 0.1**: Repo + state DB init
- **Step 0.2**: Kill Switch service
- **Step 0.3**: Local Encrypted Vault
- **Step 0.4**: Data Boundary Policy enforcement point
- **Step 1.1**: Task state machine (single-agent version)
- **Step 1.2**: Idempotency keys
- **Step 1.3**: Snapshot/rollback
- **Step 1.4**: Coding Agent (minimal)
- **Step 1.5**: Intent Classifier (Coding-only routing)
- **Step 1.6**: Trace Log Viewer
- **Step 1.7**: End-to-end Phase 1 verification
- **Step 2.1**: Calendar Agent, Notes Agent
- **Step 2.2**: Deploy Agent (repo-push mode only)
- **Step 2.3**: Resource Lock Manager
- **Step 2.4**: Heartbeat Watchdog
- **Step 2.5**: Reconciliation Check
- **Step 2.6**: Dependency graph in Planner
- **Step 2.7**: Permission Manager
- **Step 2.8**: Concurrency verification
- **Step 3.1**: DA-1 through DA-6
- **Step 3.2**: DA-7 Production Approval Gate
- **Step 3.3**: DA-8/DA-9 Production deploy + monitoring
- **Step 4.1**: Error taxonomy
- **Step 4.2**: Retry policy (jittered backoff, per class)
- **Step 4.3**: Circuit breaker (per agent)
- **Step 4.4**: Dead Letter Queue
- **Step 4.5**: SCOPE CHECKPOINT
- **Step 5.1**: Web Search Agent
- **Step 5.2**: Voice Output (TTS)
- **Step 5.3**: Research Agent
- **Step 5.4**: Document Agent
- **Step 5.5**: Application-Assist Agent
- **Step 6.1**: Multi-model backend
- **Step 6.2**: Skills framework
- **Step 6.3**: Scheduler service
- **Step 6.4**: Memory system
- **Step 6.5**: FastAPI server
- **Step 7.1**: Daily-life agents
- **Step 7.2**: Engineering agents
- **Step 7.3**: Communication channels
- **Step 7.4**: Evaluation framework
- **Step 7.5**: Agent-to-Agent protocol
- **Step 8.1**: Big infrastructure agents
- **Step 8.2**: MCP server
- **Step 8.3**: Desktop GUI
- **Step 8.4**: Speech I/O
- **Step 8.5**: Advanced sandboxing
- **Step 8.6**: Multi-platform installers
- **Step 8.7**: Input control agents
- **Step 8.8**: Learning loop

## Scope Reminder

Per ARCHITECTURE.md Phase 4, step 4.5: **Quality checkpoint gate.**
Decision D16 incorporates OpenJarvis features (Phases 6–8) while maintaining existing code-enforced safety gates and session resilience.

---

## How to Regenerate This File

Run `python update_tasks.py` or query `max_state.db` directly.
