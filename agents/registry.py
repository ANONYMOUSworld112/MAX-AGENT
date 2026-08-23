"""
MAX OS — Authoritative Canonical Agent Registry (Section 27 & 28)
agents/registry.py

Defines the complete canonical registry of all 28 worker agents and suites across MAX OS.
Tracks agent metadata, capabilities, input/output schemas, required permissions, default risk,
execution mode, concurrency rules, cancellation support, recovery support, and verification strategies.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from core.platform.detector import RiskLevel


class ExecutionMode(str, enum.Enum):
    ON_DEMAND = "on_demand"
    SCHEDULED = "scheduled"
    CONTINUOUS = "continuous"


@dataclass
class AgentDefinition:
    id: str
    name: str
    description: str
    suite: str
    capabilities: List[str]
    tools: List[str]
    default_risk: RiskLevel
    execution_mode: ExecutionMode
    supports_cancellation: bool = True
    supports_recovery: bool = True
    verification_strategy: str = "state_diff"
    concurrency_exclusive: bool = False
    module_path: str = ""
    executor_fn_name: str = ""


# Canonical Master Registry of 28 Worker Agents & Specialists
AGENT_REGISTRY: Dict[str, AgentDefinition] = {
    # Tier 1 / Core Agents
    "calendar": AgentDefinition(
        id="calendar",
        name="Calendar Agent",
        description="Schedule management, reminders, event creation, conflict detection.",
        suite="Core",
        capabilities=["calendar_read", "calendar_write", "conflict_detection"],
        tools=["calendar_api", "filesystem"],
        default_risk=RiskLevel.LOW,
        execution_mode=ExecutionMode.ON_DEMAND,
        module_path="agents/calendar.py",
        executor_fn_name="calendar_agent_executor",
    ),
    "notes": AgentDefinition(
        id="notes",
        name="Notes Agent",
        description="Capture notes, natural language retrieval, document categorization.",
        suite="Core",
        capabilities=["note_create", "note_search", "note_update"],
        tools=["filesystem"],
        default_risk=RiskLevel.LOW,
        execution_mode=ExecutionMode.ON_DEMAND,
        module_path="agents/notes.py",
        executor_fn_name="notes_agent_executor",
    ),
    "coding": AgentDefinition(
        id="coding",
        name="Coding Agent",
        description="Build/fix code against acceptance criteria, refactoring, test execution.",
        suite="Engineering",
        capabilities=["code_edit", "code_refactor", "unit_test_execution"],
        tools=["filesystem", "terminal"],
        default_risk=RiskLevel.MEDIUM,
        execution_mode=ExecutionMode.ON_DEMAND,
        module_path="agents/coding.py",
        executor_fn_name="coding_agent_executor",
    ),
    "deploy": AgentDefinition(
        id="deploy",
        name="Deploy Agent",
        description="9-stage deployment pipeline (DA-1..6 staging, DA-7 gate, DA-8..9 rollout).",
        suite="Engineering",
        capabilities=["staging_build", "deployment_gate", "rollout"],
        tools=["terminal", "filesystem", "browser"],
        default_risk=RiskLevel.HIGH,
        execution_mode=ExecutionMode.ON_DEMAND,
        module_path="agents/deploy.py",
        executor_fn_name="deploy_agent_executor",
    ),

    # Search & Information
    "websearch": AgentDefinition(
        id="websearch",
        name="Web Search Agent",
        description="Real-time lookups, structured web queries, quota-checked extraction.",
        suite="Information",
        capabilities=["web_query", "snippet_extraction"],
        tools=["browser"],
        default_risk=RiskLevel.LOW,
        execution_mode=ExecutionMode.ON_DEMAND,
        module_path="agents/websearch.py",
        executor_fn_name="websearch_agent_executor",
    ),
    "research": AgentDefinition(
        id="research",
        name="Research Agent",
        description="Multi-query deep research, web + Wikipedia synthesis, report generation.",
        suite="Information",
        capabilities=["deep_research", "multi_source_synthesis", "report_writing"],
        tools=["browser", "filesystem"],
        default_risk=RiskLevel.LOW,
        execution_mode=ExecutionMode.ON_DEMAND,
        module_path="agents/research.py",
        executor_fn_name="research_agent_executor",
    ),
    "document": AgentDefinition(
        id="document",
        name="Document Agent",
        description="PPT/PDF/Markdown presentation and document generation.",
        suite="Information",
        capabilities=["doc_generation", "pdf_render", "ppt_build"],
        tools=["filesystem"],
        default_risk=RiskLevel.LOW,
        execution_mode=ExecutionMode.ON_DEMAND,
        module_path="agents/document.py",
        executor_fn_name="document_agent_executor",
    ),
    "application_assist": AgentDefinition(
        id="application_assist",
        name="Application Assist Agent",
        description="Drafts job applications and forms; never auto-submits.",
        suite="Information",
        capabilities=["form_drafting", "resume_parsing"],
        tools=["browser", "filesystem"],
        default_risk=RiskLevel.MEDIUM,
        execution_mode=ExecutionMode.ON_DEMAND,
        module_path="agents/application_assist.py",
        executor_fn_name="application_assist_executor",
    ),

    # Computer Control & Input Agents
    "keyboard": AgentDefinition(
        id="keyboard",
        name="Keyboard Agent",
        description="Async typing & hotkeys (credential fields BLOCKED).",
        suite="ComputerUse",
        capabilities=["type_text", "press_hotkey"],
        tools=["computer_control"],
        default_risk=RiskLevel.LOW,
        execution_mode=ExecutionMode.ON_DEMAND,
        concurrency_exclusive=True,
        module_path="agents/input_control.py",
        executor_fn_name="keyboard_agent_executor",
    ),
    "mouse": AgentDefinition(
        id="mouse",
        name="Mouse Agent",
        description="Async clicks, movements & directional scrolling.",
        suite="ComputerUse",
        capabilities=["mouse_click", "mouse_move", "mouse_scroll"],
        tools=["computer_control"],
        default_risk=RiskLevel.LOW,
        execution_mode=ExecutionMode.ON_DEMAND,
        concurrency_exclusive=True,
        module_path="agents/input_control.py",
        executor_fn_name="mouse_agent_executor",
    ),
    "input_control": AgentDefinition(
        id="input_control",
        name="Input Control Agent",
        description="Multi-action desktop stream executor & UIA OCR bridge.",
        suite="ComputerUse",
        capabilities=["desktop_stream", "uia_locate", "click_element"],
        tools=["computer_control", "accessibility"],
        default_risk=RiskLevel.MEDIUM,
        execution_mode=ExecutionMode.ON_DEMAND,
        concurrency_exclusive=True,
        module_path="agents/input_control.py",
        executor_fn_name="input_control_agent_executor",
    ),
    "computer_use": AgentDefinition(
        id="computer_use",
        name="Universal Computer Use Agent",
        description="End-to-end desktop computer interaction loop (Observe -> Act -> Verify).",
        suite="ComputerUse",
        capabilities=["window_launch", "ui_click", "form_fill", "calculator_compute", "desktop_navigate"],
        tools=["computer_control", "browser", "terminal", "filesystem"],
        default_risk=RiskLevel.MEDIUM,
        execution_mode=ExecutionMode.ON_DEMAND,
        concurrency_exclusive=True,
        module_path="agents/computer_use_agent.py",
        executor_fn_name="computer_use_agent_executor",
    ),

    # Channels
    "whatsapp": AgentDefinition(
        id="whatsapp",
        name="WhatsApp Bridge",
        description="Hybrid desktop web launcher & encrypted vault API dispatch.",
        suite="Channels",
        capabilities=["send_whatsapp_message", "read_chat"],
        tools=["browser"],
        default_risk=RiskLevel.HIGH,
        execution_mode=ExecutionMode.ON_DEMAND,
        module_path="channels/whatsapp.py",
        executor_fn_name="whatsapp_agent_executor",
    ),
    "channel_manager": AgentDefinition(
        id="channel_manager",
        name="Channel Manager",
        description="Telegram, Discord, Slack, WhatsApp adapter router.",
        suite="Channels",
        capabilities=["route_message", "dispatch_channel"],
        tools=["network"],
        default_risk=RiskLevel.MEDIUM,
        execution_mode=ExecutionMode.CONTINUOUS,
        module_path="channels/manager.py",
        executor_fn_name="channel_manager_executor",
    ),

    # Daily Life Suite (6 Agents)
    "daily_inbox": AgentDefinition(
        id="daily_inbox",
        name="Daily Inbox Agent",
        description="Email triage and draft management (confirm-gated on send).",
        suite="Daily Life",
        capabilities=["read_inbox", "draft_reply"],
        tools=["browser", "network"],
        default_risk=RiskLevel.MEDIUM,
        execution_mode=ExecutionMode.SCHEDULED,
        module_path="agents/daily_life.py",
        executor_fn_name="daily_inbox_executor",
    ),
    "daily_expense": AgentDefinition(
        id="daily_expense",
        name="Daily Expense Agent",
        description="Receipt parsing and expense categorization.",
        suite="Daily Life",
        capabilities=["parse_receipt", "log_expense"],
        tools=["filesystem"],
        default_risk=RiskLevel.LOW,
        execution_mode=ExecutionMode.ON_DEMAND,
        module_path="agents/daily_life.py",
        executor_fn_name="daily_expense_executor",
    ),
    "daily_crm": AgentDefinition(
        id="daily_crm",
        name="Daily CRM Agent",
        description="Personal contact tracking and relationship follow-ups.",
        suite="Daily Life",
        capabilities=["track_contact", "schedule_followup"],
        tools=["filesystem"],
        default_risk=RiskLevel.LOW,
        execution_mode=ExecutionMode.ON_DEMAND,
        module_path="agents/daily_life.py",
        executor_fn_name="daily_crm_executor",
    ),
    "daily_content": AgentDefinition(
        id="daily_content",
        name="Daily Content Agent",
        description="Social media and newsletter drafting.",
        suite="Daily Life",
        capabilities=["draft_post", "content_calendar"],
        tools=["filesystem"],
        default_risk=RiskLevel.LOW,
        execution_mode=ExecutionMode.ON_DEMAND,
        module_path="agents/daily_life.py",
        executor_fn_name="daily_content_executor",
    ),
    "daily_brief": AgentDefinition(
        id="daily_brief",
        name="Daily Brief Agent",
        description="Morning summary generation (weather, schedule, news).",
        suite="Daily Life",
        capabilities=["compile_brief"],
        tools=["browser", "calendar"],
        default_risk=RiskLevel.LOW,
        execution_mode=ExecutionMode.SCHEDULED,
        module_path="agents/daily_life.py",
        executor_fn_name="daily_brief_executor",
    ),
    "daily_monitor": AgentDefinition(
        id="daily_monitor",
        name="Daily Monitor Agent",
        description="System and application state monitoring.",
        suite="Daily Life",
        capabilities=["system_check", "alert_notify"],
        tools=["system"],
        default_risk=RiskLevel.LOW,
        execution_mode=ExecutionMode.CONTINUOUS,
        module_path="agents/daily_life.py",
        executor_fn_name="daily_monitor_executor",
    ),

    # Engineering Suite (6 Agents)
    "eng_arch_review": AgentDefinition(
        id="eng_arch_review",
        name="Architecture Review Agent",
        description="System diagram, ADR verification, modularity audits.",
        suite="Engineering",
        capabilities=["arch_audit", "adr_check"],
        tools=["filesystem"],
        default_risk=RiskLevel.LOW,
        execution_mode=ExecutionMode.ON_DEMAND,
        module_path="agents/engineering.py",
        executor_fn_name="eng_arch_review_executor",
    ),
    "eng_security": AgentDefinition(
        id="eng_security",
        name="Security Audit Agent",
        description="Static code security scans and secret detection.",
        suite="Engineering",
        capabilities=["scan_secrets", "dependency_check"],
        tools=["filesystem"],
        default_risk=RiskLevel.LOW,
        execution_mode=ExecutionMode.ON_DEMAND,
        module_path="agents/engineering.py",
        executor_fn_name="eng_security_executor",
    ),
    "eng_testing": AgentDefinition(
        id="eng_testing",
        name="Testing Suite Agent",
        description="Test generation, pytest execution, coverage analysis.",
        suite="Engineering",
        capabilities=["run_tests", "generate_tests"],
        tools=["terminal", "filesystem"],
        default_risk=RiskLevel.LOW,
        execution_mode=ExecutionMode.ON_DEMAND,
        module_path="agents/engineering.py",
        executor_fn_name="eng_testing_executor",
    ),
    "eng_debug": AgentDefinition(
        id="eng_debug",
        name="Debug Agent",
        description="Stack trace diagnosis and log analysis.",
        suite="Engineering",
        capabilities=["log_analysis", "root_cause_diagnosis"],
        tools=["filesystem", "terminal"],
        default_risk=RiskLevel.LOW,
        execution_mode=ExecutionMode.ON_DEMAND,
        module_path="agents/engineering.py",
        executor_fn_name="eng_debug_executor",
    ),
    "eng_docgen": AgentDefinition(
        id="eng_docgen",
        name="DocGen Agent",
        description="API doc generation and README sync.",
        suite="Engineering",
        capabilities=["generate_docs", "update_readme"],
        tools=["filesystem"],
        default_risk=RiskLevel.LOW,
        execution_mode=ExecutionMode.ON_DEMAND,
        module_path="agents/engineering.py",
        executor_fn_name="eng_docgen_executor",
    ),
    "eng_codereview": AgentDefinition(
        id="eng_codereview",
        name="Code Review Agent",
        description="PR review, linter enforcement, style checks.",
        suite="Engineering",
        capabilities=["review_pr", "lint_check"],
        tools=["filesystem"],
        default_risk=RiskLevel.LOW,
        execution_mode=ExecutionMode.ON_DEMAND,
        module_path="agents/engineering.py",
        executor_fn_name="eng_codereview_executor",
    ),

    # Cyberblack Agent
    "cyberblack": AgentDefinition(
        id="cyberblack",
        name="Cyberblack Agent",
        description="Ethical OSINT, SAST vulnerability scan, curriculum generator.",
        suite="Security",
        capabilities=["osint_scan", "sast_scan", "curriculum_gen"],
        tools=["terminal", "filesystem", "browser"],
        default_risk=RiskLevel.MEDIUM,
        execution_mode=ExecutionMode.ON_DEMAND,
        module_path="agents/cyberblack.py",
        executor_fn_name="cyberblack_agent_executor",
    ),

    # Infrastructure Suite (1 Agent representing Big Infra)
    "infrastructure": AgentDefinition(
        id="infrastructure",
        name="Infrastructure Suite Agent",
        description="Database, CloudInfra, DataPipeline, BackupDR, and Analytics.",
        suite="Infrastructure",
        capabilities=["db_migration", "docker_manage", "backup_restore"],
        tools=["terminal", "filesystem"],
        default_risk=RiskLevel.HIGH,
        execution_mode=ExecutionMode.ON_DEMAND,
        module_path="agents/infrastructure.py",
        executor_fn_name="infrastructure_agent_executor",
    ),
}


class AgentRegistry:
    """
    Registry accessor and validator for MAX OS agents.
    """

    @classmethod
    def get_agent(cls, agent_id: str) -> Optional[AgentDefinition]:
        return AGENT_REGISTRY.get(agent_id)

    @classmethod
    def list_agents(cls, suite: Optional[str] = None) -> List[AgentDefinition]:
        if suite:
            return [a for a in AGENT_REGISTRY.values() if a.suite.lower() == suite.lower()]
        return list(AGENT_REGISTRY.values())

    @classmethod
    def get_total_count(cls) -> int:
        return len(AGENT_REGISTRY)
