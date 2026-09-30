"""
Unit tests for ContextEngine Scoped Context Packages (Task 6.2)
================================================================

Covers:
- Strict token budget limit enforcement
- Keyword relevance filtering (relevant facts included, irrelevant excluded)
- Identity memory always prioritized
- Lowest-priority memories pruned when budget is constrained
"""

import pytest

from core.context_engine import ContextEngine, ContextPackage
from core.contracts import ChannelTrust, TaskIntent


def test_context_engine_budget_enforcement():
    engine = ContextEngine(default_budget=150, chars_per_token=4.0)

    intent = TaskIntent(
        action="build_project",
        target="MAX-AGENT",
        channel=ChannelTrust.TRUSTED,
    )

    # Massive memory store that would easily exceed 150 tokens
    large_memory = {
        "identity": {"name": "Bob", "role": "Developer"},
        "projects": {
            f"project_{i}": {"value": "Detailed project description with lots of information and words" * 5}
            for i in range(20)
        },
    }

    pkg = engine.build_context_package(intent, memory=large_memory, token_budget=150)

    # Package must strictly respect budget
    assert pkg.total_estimated_tokens <= 150
    assert pkg.budget_limit == 150
    # Identity preserved
    assert "Bob" in pkg.memory_context
    # Pruned memories tracked
    assert len(pkg.pruned_memories) > 0


def test_relevance_filtering_includes_matching_facts_excludes_irrelevant():
    engine = ContextEngine(default_budget=1000)

    intent = TaskIntent(
        action="deploy",
        target="cloud-backend",
        parameters={"env": "staging"},
    )

    memory = {
        "identity": {
            "name": "Alice",
        },
        "projects": {
            "cloud-backend": {"value": "Deploys to AWS ECS cluster in staging region"},
            "mobile-app": {"value": "Flutter client on iOS App Store"},
        },
        "relationships": {
            "sister": {"value": "Sarah plays tennis on weekends"},
            "dentist": {"value": "Dr. Davis appointment in November"},
        },
    }

    pkg = engine.build_context_package(intent, memory=memory)

    # Relevant project is included
    assert "cloud-backend" in pkg.memory_context
    assert "AWS ECS" in pkg.memory_context

    # Irrelevant relationships are excluded
    assert "Sarah plays tennis" not in pkg.memory_context
    assert "Dr. Davis" not in pkg.memory_context
    assert "relationships/sister" in pkg.pruned_memories


def test_context_package_structure_and_serialization():
    engine = ContextEngine(default_budget=500)
    intent = TaskIntent(action="query_status", target="system")
    tools = [{"name": "get_cpu_usage", "description": "Returns current CPU load"}]

    pkg = engine.build_context_package(intent, tools=tools)

    assert "TASK SPECIFICATION:" in pkg.task_spec
    assert len(pkg.tools_spec) == 1
    d = pkg.to_dict()
    assert d["budget_limit"] == 500
    assert d["tools_count"] == 1
    assert "total_estimated_tokens" in d
