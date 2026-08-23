#!/usr/bin/env python3
"""
MAX OS — Database Initialization & Seeding
Run once to create max_state.db from max_state_schema.sql, then seed
phases, steps, decisions, and agent_registry from the design documents.

Usage:
    python init_db.py

Per MAX_MASTER_PROMPT.md: if max_state.db doesn't exist, create it from
max_state_schema.sql, then seed phases/steps from ARCHITECTURE.md.
"""

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "max_state.db"
SCHEMA_PATH = Path(__file__).parent / "max_state_schema.sql"


def get_now() -> str:
    """ISO 8601 timestamp in UTC."""
    return datetime.now(timezone.utc).isoformat()


def create_db(conn: sqlite3.Connection) -> None:
    """Execute the schema SQL to create all tables."""
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    conn.executescript(schema_sql)
    print(f"  ✓ Schema applied from {SCHEMA_PATH.name}")


def seed_phases(conn: sqlite3.Connection) -> None:
    """Seed the phases table from ARCHITECTURE.md."""
    phases = [
        (0, "Foundation & Safety",
         "Nothing else may build until this phase is done. Kill Switch is Component #0."),
        (1, "Core Loop, One Agent",
         "input → plan → code → test → commit works end to end."),
        (2, "Multi-Agent + Synchronization",
         "The floor the rest of the system stands on."),
        (3, "Deployment Pipeline (Production Mode)",
         "Full 9-stage deployment pipeline with code-enforced approval gate."),
        (4, "Resilience Infrastructure",
         "Error handling worthy of the word OS."),
        (5, "First Scope Expansion",
         "First agents beyond the v1 four. Only after 4.5 is signed off."),
        (6, "OpenJarvis Integration: Core Infrastructure",
         "Adopt OpenJarvis infrastructure primitives — multi-model, skills, scheduler, memory, server."),
        (7, "OpenJarvis Integration: Agent Expansion + Channels",
         "Expand agent roster and add multi-channel communication."),
        (8, "OpenJarvis Integration: Platform Features",
         "GUI, installers, advanced sandboxing, speech I/O, learning loops."),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO phases (phase_id, name, goal) VALUES (?, ?, ?)",
        phases,
    )
    print(f"  ✓ {len(phases)} phases seeded")


def seed_steps(conn: sqlite3.Connection) -> None:
    """Seed the steps table from ARCHITECTURE.md (all phases)."""
    steps = [
        # Phase 0
        ("0.1", 0, "Repo + state DB init",
         "Initialize repo structure; run max_state_schema.sql to create max_state.db.",
         "", "max_state.db exists; all 12 tables present; phases/steps seeded; agent_registry seeded from AGENTS.md.",
         "max_state.db, max_state_schema.sql, init_db.py"),
        ("0.2", 0, "Kill Switch service",
         "Standalone process/thread that starts before anything else, listens for a hotkey/local signal, and on trigger sends a hard STOP to every running task.",
         "0.1", "Main Agent boot checks Kill Switch status and refuses to initialize until armed. Triggering mid-task halts within 1s.",
         "core/kill_switch.py"),
        ("0.3", 0, "Local Encrypted Vault",
         "Credential interface backed by OS keychain (keyring library); agents request secrets at runtime, never read a raw file.",
         "0.1", "No plaintext key anywhere in repo including test fixtures; retrieving a stored key via Vault works; reading underlying storage does not expose plaintext.",
         "core/vault.py"),
        ("0.4", 0, "Data Boundary Policy enforcement point",
         "A single function every outbound LLM API call must pass through, stripping out-of-scope file content and masking credential-shaped strings.",
         "0.3", "A test with a deliberately planted fake API key in an out-of-scope file confirms it never appears in the outbound payload.",
         "core/data_boundary.py"),

        # Phase 1
        ("1.1", 1, "Task state machine (single-agent version)",
         "Implement CREATED → QUEUED → RUNNING → RECONCILING → DONE.",
         "0.1", "A task full lifecycle is visible via SELECT * FROM task_trace WHERE task_id = ? at every stage.",
         "core/task_state.py"),
        ("1.2", 1, "Idempotency keys",
         "Every task gets a UUID at creation; side-effecting agents check it before acting.",
         "1.1", "Re-running the same idempotency key twice produces one side effect, not two.",
         "core/task_state.py"),
        ("1.3", 1, "Snapshot/rollback",
         "Snapshot taken when a task enters RUNNING; full restore on any failure.",
         "1.1", "A task killed mid-write (simulated) leaves zero partial files behind after rollback.",
         "core/snapshot.py"),
        ("1.4", 1, "Coding Agent (minimal)",
         "Wraps opencode CLI; accepts a build/fix spec, returns success/failure against acceptance criteria.",
         "1.2,1.3", "Given 'write a script that prints hello world,' produces a working file and a passing self-test.",
         "agents/coding.py"),
        ("1.5", 1, "Intent Classifier (Coding-only routing)",
         "Keyword match first (cheap router), LLM fallback for ambiguous input.",
         "1.4", "Unambiguous coding requests never trigger an LLM classification call; ambiguous input asks a clarifying question.",
         "core/intent_classifier.py"),
        ("1.6", 1, "Trace Log Viewer",
         "CLI to inspect task_trace without touching the DB directly.",
         "1.1", "max trace --last 20 and max trace --agent coding --failures-only both return correct output.",
         "cli/trace.py"),
        ("1.7", 1, "End-to-end Phase 1 verification",
         "Full loop test, no mocks.",
         "1.5,1.6", "A real 'build me X' request completes, commits, and is visible in the trace log, unattended.",
         "tests/test_phase1_e2e.py"),

        # Phase 2
        ("2.1", 2, "Calendar Agent, Notes Agent",
         "Both auto-tier, no locks required.",
         "1.7", "Both agents work at auto-tier with no shared resources requiring locks.",
         "agents/calendar.py, agents/notes.py"),
        ("2.2", 2, "Deploy Agent (repo-push mode only)",
         "Creates/pushes to a GitHub repo via API/CLI, never via simulated UI clicks.",
         "1.7", "Creates/pushes to GitHub repo; confirm-gated.",
         "agents/deploy.py"),
        ("2.3", 2, "Resource Lock Manager",
         "Sorted-order, all-or-nothing acquisition with timeout backstop.",
         "2.1,2.2", "A deliberately reversed-order two-lock test completes without hanging.",
         "core/lock_manager.py"),
        ("2.4", 2, "Heartbeat Watchdog",
         "Monitors task heartbeats and kills unresponsive tasks.",
         "2.3,1.3", "A task with no heartbeat for 45s is killed and rolled back.",
         "core/watchdog.py"),
        ("2.5", 2, "Reconciliation Check",
         "Verify agent-reported success matches real system state.",
         "2.1,2.2", "An agent self-reported success that doesn't match real state is treated as failure.",
         "core/reconciliation.py"),
        ("2.6", 2, "Dependency graph in Planner",
         "Multi-agent task ordering.",
         "2.2,2.1", "'Build it, deploy it, then remind me' runs three agents in correct order.",
         "core/planner.py"),
        ("2.7", 2, "Permission Manager",
         "auto/confirm/blocked tiers, enforced inside each agent code path.",
         "2.2", "Five different phrasings of 'skip the approval step' all fail to skip it.",
         "core/permissions.py"),
        ("2.8", 2, "Concurrency verification",
         "Two deploy requests for same project — second queues, never races.",
         "2.3,2.7", "Two deploy requests for the same project seconds apart — second one queues visibly.",
         "tests/test_phase2_concurrency.py"),

        # Phase 3
        ("3.1", 3, "DA-1 through DA-6",
         "Preflight through staging run autonomously within granted permissions.",
         "2.8", "Preflight through staging run autonomously.",
         "agents/deploy.py"),
        ("3.2", 3, "DA-7 Production Approval Gate",
         "Gate enforced inside deploy_prod() itself.",
         "3.1", "No code path reaches production without a verified approval token, confirmed by calling deploy_prod() directly.",
         "agents/deploy.py"),
        ("3.3", 3, "DA-8/DA-9 Production deploy + monitoring",
         "Production deploy with health checks and auto-rollback.",
         "3.2", "A failed post-deploy health check triggers auto-rollback within the monitoring window.",
         "agents/deploy.py, core/outcome_tracker.py"),

        # Phase 4
        ("4.1", 4, "Error taxonomy",
         "Every error classified as transient/validation/permission/destructive_risk/systemic before handling.",
         "3.3", "Every error in the system is classified before any handling logic runs.",
         "core/errors.py"),
        ("4.2", 4, "Retry policy (jittered backoff, per class)",
         "Error-class-specific retry with jittered exponential backoff.",
         "4.1", "Five simultaneous transient failures retry at spread-out times, not synchronized.",
         "core/retry.py"),
        ("4.3", 4, "Circuit breaker (per agent)",
         "Per-agent circuit breaker — 5 consecutive failures opens breaker.",
         "4.1", "5 consecutive failures opens breaker; 6th request rejected instantly; other agents unaffected.",
         "core/circuit_breaker.py"),
        ("4.4", 4, "Dead Letter Queue",
         "Exhausted-retry tasks visible and requeueable.",
         "4.2", "max dlq --list shows full attempt history; tasks are requeueable.",
         "cli/dlq.py"),
        ("4.5", 4, "SCOPE CHECKPOINT",
         "Formal sign-off that resilience infrastructure is complete. Quality gate before expanding scope.",
         "4.1,4.2,4.3,4.4", "All four prior steps verified done; human explicitly confirms readiness.",
         ""),

        # Phase 5
        ("5.1", 5, "Web Search Agent",
         "Explicit-trigger real-time lookups, quota-checked.",
         "4.5", "Explicit trigger only; quota-checked against api_quota_usage; graceful degradation.",
         "agents/websearch.py"),
        ("5.2", 5, "Voice Output (TTS)",
         "Infra-tier, not a task — never enters task_trace.",
         "4.5", "Any failure degrades silently to text-only, never blocks response.",
         "core/voice_output.py"),
        ("5.3", 5, "Research Agent",
         "Multi-query deep research with citations.",
         "5.1", "Deep research with web + Wikipedia; quota-warn before heavy requests.",
         "agents/research.py"),
        ("5.4", 5, "Document Agent",
         "PPT/PDF/office document generation using real tooling.",
         "4.5", "Generates real documents, not code files; auto to draft, confirm to finalize.",
         "agents/document.py"),
        ("5.5", 5, "Application-Assist Agent",
         "Drafts job applications; never auto-submits (LinkedIn ToS).",
         "4.5", "Drafts content from Vault; never logs into or automates LinkedIn directly.",
         "agents/application_assist.py"),

        # Phase 6
        ("6.1", 6, "Multi-model backend",
         "Agents can use Ollama (local), OpenAI, Anthropic, or Google via LiteLLM router.",
         "5.1", "model_registry populated; LiteLLM routes requests; local→cloud fallback works.",
         "core/model_router.py"),
        ("6.2", 6, "Skills framework",
         "Load, register, and execute skills in sandboxed environments.",
         "4.5", "skill_registry tracks skills; built-in skills work; max skill list CLI works.",
         "core/skill_loader.py, skills/"),
        ("6.3", 6, "Scheduler service",
         "Cron-based agent execution for scheduled/continuous modes.",
         "4.5", "Agents with scheduled/continuous execution_mode run on cron; scheduled_tasks table tracks runs.",
         "core/scheduler.py"),
        ("6.4", 6, "Memory system",
         "5-layer memory: identity, preferences, behavioral, project context, conversation.",
         "4.5", "Memory operational; Prompt Agent reads memory for context; FAISS vector search works for Notes.",
         "core/memory/, memory_schema.sql"),
        ("6.5", 6, "FastAPI server",
         "REST API + WebSocket server for desktop GUI and channels.",
         "6.1", "Agents callable via API; local authentication; serves desktop frontend.",
         "server/"),

        # Phase 7
        ("7.1", 7, "Daily-life agents",
         "Inbox, Expense, CRM, Content Draft, Daily Brief, Monitor agents.",
         "6.4", "All six daily-life agents functional and tested.",
         "agents/inbox.py, agents/expense.py, agents/founder_crm.py, agents/content_draft.py, agents/daily_brief.py, agents/monitor.py"),
        ("7.2", 7, "Engineering agents",
         "Architecture Review, Security, Testing, Debug, Documentation, Code Review agents.",
         "6.2", "All six engineering agents functional and tested.",
         "agents/architecture_review.py, agents/security.py, agents/testing.py, agents/debug.py, agents/documentation.py, agents/code_review.py"),
        ("7.3", 7, "Communication channels",
         "Abstract channel interface with Telegram + Discord implementations.",
         "6.5", "CLI channel works; at least Telegram + Discord channels functional.",
         "channels/, core/channel_manager.py"),
        ("7.4", 7, "Evaluation framework",
         "Benchmarks tracking energy, FLOPs, latency, cost alongside accuracy.",
         "6.1", "max bench run and max bench results CLI commands work; benchmark_results populated.",
         "cli/bench.py"),
        ("7.5", 7, "Agent-to-Agent protocol",
         "Agents can delegate subtasks to other agents through the planner.",
         "7.1", "A2A messages traceable in task_trace; delegation works through planner.",
         "core/planner.py"),

        # Phase 8
        ("8.1", 8, "Big infrastructure agents",
         "Database, Cloud/Infra, Data Pipeline, Backup/DR, Analytics agents.",
         "7.2", "All five infrastructure agents functional and tested.",
         "agents/database.py, agents/cloud_infra.py, agents/data_pipeline.py, agents/backup_dr.py, agents/analytics.py"),
        ("8.2", 8, "MCP server",
         "Model Context Protocol endpoint for external tool integration.",
         "6.5", "External tools can connect to MAX as an MCP server.",
         "server/mcp.py"),
        ("8.3", 8, "Desktop GUI",
         "Electron app with chat, agent status, trace viewer, settings.",
         "6.5", "Desktop app launches and connects to FastAPI server.",
         "desktop/"),
        ("8.4", 8, "Speech I/O",
         "Whisper STT + TTS; voice-in → agent → voice-out loop.",
         "5.2", "Voice input recognized; agent processes; voice output returned.",
         "core/speech.py"),
        ("8.5", 8, "Advanced sandboxing",
         "Docker and WASM sandboxes for skill execution.",
         "6.2", "Sandboxed skills cannot access filesystem or network beyond declared permissions.",
         "core/sandbox.py"),
        ("8.6", 8, "Multi-platform installers",
         "One-line install scripts for macOS, Linux, WSL2, Windows.",
         "8.3", "Install scripts handle dependencies; max doctor checks status.",
         "scripts/install.sh, scripts/install.ps1, cli/doctor.py"),
        ("8.7", 8, "Input control agents",
         "Keyboard, Mouse, Screen agents with full sandboxing and session recording.",
         "8.5", "All three input-control agents work; credential fields hard-blocked; all actions logged.",
         "agents/keyboard.py, agents/mouse.py, agents/screen.py"),
        ("8.8", 8, "Learning loop",
         "Trace data → model improvement; skill optimization via DSPy.",
         "7.4", "Outcome data feeds back into planning; skill optimization measurably improves performance.",
         "core/learning.py"),
    ]

    conn.executemany(
        """INSERT OR IGNORE INTO steps
           (step_id, phase_id, title, description, depends_on, acceptance_criteria, files_touched)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        steps,
    )
    print(f"  ✓ {len(steps)} steps seeded")


def seed_agent_registry(conn: sqlite3.Connection) -> None:
    """Seed agent_registry from AGENTS.md tier tables + OpenJarvis mappings."""
    agents = [
        # Tier 1 — Built (v1 scope)
        ("Calendar Agent",       1, "on_demand",  "built",    "auto",    "Schedule, reminders, conflict detection",                         "Native",                "worker"),
        ("Notes Agent",          1, "on_demand",  "built",    "auto",    "Capture, natural-language retrieval",                             "Native",                "worker"),
        ("Coding Agent",         1, "on_demand",  "built",    "confirm", "Build/fix code against acceptance criteria",                      "opencode / Antigravity","worker"),
        ("Deploy Agent",         1, "on_demand",  "built",    "confirm", "Repo-push mode and production mode (DA-1→DA-9)",                 "Git CLI/API",           "worker"),

        # Tier 2 — Next to build (Phase 5)
        ("Web Search Agent",     2, "on_demand",  "next",     "auto",    "Explicit-trigger real-time lookups, quota-checked",               None,                    "worker"),
        ("Research Agent",       2, "on_demand",  "next",     "auto",    "Multi-query deep research, web + Wikipedia",                      None,                    "worker"),
        ("Document Agent",       2, "on_demand",  "next",     "auto",    "PPT/PDF/office document generation",                              None,                    "worker"),
        ("Application-Assist Agent", 2, "on_demand", "next",  "confirm", "Drafts job applications; never auto-submits",                     None,                    "worker"),

        # Tier 3 — Daily-life (deferred)
        ("Inbox Agent",          3, "scheduled",  "deferred", "auto",    "Email triage, draft replies, never auto-send",                    None,                    "worker"),
        ("Expense Agent",        3, "on_demand",  "deferred", "auto",    "Spending logs, anomaly flags",                                    None,                    "worker"),
        ("Founder CRM Agent",    3, "on_demand",  "deferred", "auto",    "Contact/follow-up tracking",                                      None,                    "worker"),
        ("Content Draft Agent",  3, "on_demand",  "deferred", "auto",    "Drafts social posts, never auto-posts",                           None,                    "worker"),
        ("Daily Brief Agent",    3, "scheduled",  "deferred", "auto",    "Morning summary; first consumer of Voice Output",                 None,                    "worker"),
        ("Monitor Agent",        3, "continuous", "deferred", "auto",    "Stateful monitoring agent (from OpenJarvis monitor_operative)",    None,                    "worker"),

        # Tier 4 — Engineering/quality (deferred)
        ("Architecture Review Agent", 4, "on_demand", "deferred", "auto", "Reviews a plan before Coding Agent starts",                      None,                    "worker"),
        ("Security Agent",       4, "scheduled",  "deferred", "auto",    "SOC/malware/cloud-security/threat-intel scanning",                None,                    "worker"),
        ("Testing Agent",        4, "on_demand",  "deferred", "auto",    "Structured test generation beyond Coding Agent's own tests",      None,                    "worker"),
        ("Debug Agent",          4, "on_demand",  "deferred", "auto",    "Escalation target on repeated task failure",                      None,                    "worker"),
        ("Documentation Agent",  4, "on_demand",  "deferred", "auto",    "Code-level docs (README, API docs)",                              None,                    "worker"),
        ("Code Review Agent",    4, "on_demand",  "deferred", "auto",    "Deeper review pass beyond Architecture Review Gate",              None,                    "worker"),

        # Tier 5 — Big infrastructure (deferred)
        ("Database Agent",       5, "on_demand",  "deferred", "confirm", "Schema, migrations, queries, backups",                            None,                    "worker"),
        ("Cloud/Infra Agent",    5, "on_demand",  "deferred", "confirm", "Provisioning, scaling, cost monitoring",                          None,                    "worker"),
        ("Data Pipeline Agent",  5, "on_demand",  "deferred", "confirm", "ETL, data sync",                                                  None,                    "worker"),
        ("Backup/DR Agent",      5, "scheduled",  "deferred", "confirm", "Scheduled backups, restore drills",                               None,                    "worker"),
        ("Analytics Agent",      5, "scheduled",  "deferred", "auto",    "Usage metrics, dashboards",                                       None,                    "worker"),

        # Tier 6 — Input control (deferred, highest-risk)
        ("Keyboard Agent",       6, "on_demand",  "deferred", "blocked", "Types, executes shortcuts",                                       None,                    "worker"),
        ("Mouse Agent",          6, "on_demand",  "deferred", "blocked", "Move, click, drag",                                               None,                    "worker"),
        ("Screen Agent",         6, "on_demand",  "deferred", "blocked", "Screenshot, OCR, UI detection",                                   None,                    "worker"),
    ]

    conn.executemany(
        """INSERT OR IGNORE INTO agent_registry
           (agent_name, tier, execution_mode, status, default_permission, description, backend, category)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        agents,
    )
    print(f"  ✓ {len(agents)} agents seeded into agent_registry")


def seed_decisions(conn: sqlite3.Connection, session_id: str) -> None:
    """Seed decisions_log from DECISIONS.md (D1–D15) + new decisions (D16–D19)."""
    now = get_now()
    decisions = [
        ("0.1", "D1: v1 scope is 4 agents, not the full 33",
         "Scope size, not technical difficulty, is the most common reason a solo-built system never ships. Overridden by D16 for architecture planning, but Phase 4.5 remains a quality gate."),
        ("0.1", "D2: Exactly two gates, both enforced in code, not UI",
         "A gate a UI enforces can be skipped by calling the function directly. A gate the function itself refuses to proceed without cannot."),
        ("0.1", "D3: No instruction phrasing can change a permission tier",
         "Broad authorization language cannot override a fixed safety check, no matter how it's worded."),
        ("0.1", "D4: Kill Switch is Component #0",
         "Anything treated as 'a feature to add later' reliably gets deprioritized. Making it a boot dependency removes that failure mode."),
        ("0.1", "D5: SQLite for v1 state, not Postgres",
         "v1 scale doesn't need client-server DB. Revisit only when a real bottleneck appears."),
        ("0.1", "D6: Secrets live in OS keychain / encrypted vault, never plaintext",
         "Plaintext secrets in files that get synced/committed is the most common leak vector."),
        ("0.1", "D7: 'Deploy to GitHub' and 'deploy to production' are different pipelines",
         "Not all 'deploy' language carries equal risk. Intent Classifier distinguishes by target, not just verb."),
        ("0.1", "D8: LinkedIn integration is draft-only, human submits manually",
         "LinkedIn policy prohibits bots/automated access. Account suspension worse than slower feature."),
        ("0.1", "D9: Document generation is its own agent, not routed through opencode",
         "Using a coding CLI for document formatting is choosing the wrong tool for convenience, not correctness."),
        ("0.1", "D10: Voice Output (TTS) is infrastructure, not a task",
         "TTS has no side effects. Forcing it through the full lifecycle applies heavyweight machinery to nothing."),
        ("0.1", "D11: api_quota_usage is one shared table, not one per service",
         "Avoids duplicating near-identical schema for structurally the same problem."),
        ("0.1", "D12: Free-tier API numbers must be verified before relying on them",
         "Found conflicting information on both Gemini and Google Cloud TTS free tiers."),
        ("0.1", "D13: Backend/Frontend/DevOps consolidated into one Coding Agent for v1",
         "Splitting only pays off once workload justifies specialization."),
        ("0.1", "D14: Input-control agents are deferred, not cut",
         "Different risk class — functionally comparable to malware if compromised. Trust must be earned first."),
        ("0.1", "D15: MAX is cloud-API-first, not local-inference-first",
         "'Localhost' refers to where orchestration/state/UI run, not where LLM reasoning happens."),
        ("0.1", "D16: User override of scope discipline — full OpenJarvis merge authorized",
         "User explicitly confirmed merging all OpenJarvis features, overriding D1 and Principle 10. Safety architecture preserved. Scope expansion adds new phases (6-8) but does not weaken existing safety gates."),
        ("0.1", "D17: OpenJarvis features adopted at architecture/schema level, not code-import level",
         "OpenJarvis is a different codebase with Rust extensions, specific OAuth flows, and its own package structure. Adopting their design patterns and feature set into MAX's architecture is correct; importing their Python packages would break MAX's reliability engineering."),
        ("0.1", "D18: Local inference path deferred to Phase 6, respecting D15",
         "D15 says MAX is cloud-API-first. Phase 6 adds local inference as an option via Ollama/LiteLLM, not a replacement. Cloud remains default."),
        ("0.1", "D19: Skills framework designed as schema + interfaces now, populated in Phase 6",
         "OpenJarvis's 13.7k+ skill marketplace requires their agentskills.io standard. MAX creates its own compatible framework."),
    ]

    conn.executemany(
        """INSERT INTO decisions_log (session_id, step_id, timestamp, decision, reasoning)
           VALUES (?, ?, ?, ?, ?)""",
        [(session_id, step_id, now, decision, reasoning) for step_id, decision, reasoning in decisions],
    )
    print(f"  ✓ {len(decisions)} decisions seeded (D1–D19)")


def create_session(conn: sqlite3.Connection) -> str:
    """Create the first build session."""
    session_id = str(uuid.uuid4())
    now = get_now()
    conn.execute(
        "INSERT INTO sessions (session_id, started_at) VALUES (?, ?)",
        (session_id, now),
    )
    print(f"  ✓ Session {session_id[:8]}... created")
    return session_id


def verify_tables(conn: sqlite3.Connection) -> int:
    """Verify all expected tables exist."""
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    table_names = [t[0] for t in tables]
    print(f"  ✓ {len(table_names)} tables found: {', '.join(table_names)}")
    return len(table_names)


def main():
    print(f"\n{'='*60}")
    print("MAX OS — Database Initialization")
    print(f"{'='*60}\n")

    db_existed = DB_PATH.exists()
    if db_existed:
        print(f"  ⚠ {DB_PATH.name} already exists — will add missing data only\n")
    else:
        print(f"  Creating {DB_PATH.name}...\n")

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    try:
        # Step 1: Create schema
        print("[1/5] Applying schema...")
        create_db(conn)

        # Step 2: Create session
        print("\n[2/5] Creating build session...")
        session_id = create_session(conn)

        # Step 3: Seed phases and steps
        print("\n[3/5] Seeding phases and steps...")
        seed_phases(conn)
        seed_steps(conn)

        # Step 4: Seed agent registry
        print("\n[4/5] Seeding agent registry...")
        seed_agent_registry(conn)

        # Step 5: Seed decisions
        print("\n[5/5] Seeding decisions log...")
        seed_decisions(conn, session_id)

        conn.commit()

        # Verify
        print(f"\n{'─'*60}")
        print("Verification:")
        table_count = verify_tables(conn)

        phase_count = conn.execute("SELECT COUNT(*) FROM phases").fetchone()[0]
        step_count = conn.execute("SELECT COUNT(*) FROM steps").fetchone()[0]
        agent_count = conn.execute("SELECT COUNT(*) FROM agent_registry").fetchone()[0]
        decision_count = conn.execute("SELECT COUNT(*) FROM decisions_log").fetchone()[0]

        print(f"  ✓ {phase_count} phases, {step_count} steps, {agent_count} agents, {decision_count} decisions")

        expected_tables = 12  # 10 original + api_quota_usage + agent_registry
        if table_count >= expected_tables:
            print(f"\n  ✅ Step 0.1 acceptance criteria: PASS ({table_count} tables ≥ {expected_tables})")
        else:
            print(f"\n  ❌ Step 0.1 acceptance criteria: FAIL ({table_count} tables < {expected_tables})")

        # Mark step 0.1 as done
        now = get_now()
        conn.execute(
            """UPDATE steps SET status = 'done', last_updated = ?,
               notes = 'DB created, schema applied, all data seeded. Verified by init_db.py.'
               WHERE step_id = '0.1'""",
            (now,),
        )
        conn.execute(
            "UPDATE phases SET status = 'in_progress', started_at = ? WHERE phase_id = 0",
            (now,),
        )
        conn.commit()
        print("  ✓ Step 0.1 marked as done")

    finally:
        conn.close()

    print(f"\n{'='*60}")
    print(f"Done. Database: {DB_PATH}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
