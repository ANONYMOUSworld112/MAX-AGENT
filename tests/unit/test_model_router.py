"""
Unit tests for ModelRouter by Task Complexity & Privacy (Task 9.2)
==================================================================

Covers:
- Routing low-complexity intent to fast local model
- Routing high-complexity coding task to coding-capable cloud model
- Strict enforcement of privacy="LOCAL_ONLY" (never routing to cloud)
- Raising exception when no local provider exists for LOCAL_ONLY
- Resilient fallback to secondary provider when primary is unavailable
"""

import pytest
from core.providers.base import ModelRouter, ModelRoutingCriteria
from core.providers.mock import MockProvider


def test_model_router_low_complexity():
    router = ModelRouter()
    local_fast = MockProvider(name="local-qwen-fast")
    cloud_heavy = MockProvider(name="gemini-pro")

    router.register_provider("local-qwen-fast", local_fast, is_local=True, capabilities={"general", "fast"})
    router.register_provider("gemini-pro", cloud_heavy, is_local=False, capabilities={"general", "deep_reasoning"})

    crit = ModelRoutingCriteria(complexity="LOW", task_type="routing")
    selected = router.route(crit)

    assert selected.provider_name() == "local-qwen-fast"


def test_model_router_high_complexity_coding():
    router = ModelRouter()
    local_fast = MockProvider(name="local-qwen-fast")
    cloud_coding = MockProvider(name="gemini-coding")

    router.register_provider("local-qwen-fast", local_fast, is_local=True, capabilities={"general", "fast"})
    router.register_provider("gemini-coding", cloud_coding, is_local=False, capabilities={"coding", "deep_reasoning"})

    crit = ModelRoutingCriteria(complexity="HIGH", task_type="coding")
    selected = router.route(crit)

    assert selected.provider_name() == "gemini-coding"


def test_model_router_strict_privacy_local_only():
    router = ModelRouter()
    local_model = MockProvider(name="local-phi")
    cloud_model = MockProvider(name="gemini-pro")

    router.register_provider("local-phi", local_model, is_local=True, capabilities={"general"})
    router.register_provider("gemini-pro", cloud_model, is_local=False, capabilities={"general", "coding"})

    # Even for coding or high complexity, LOCAL_ONLY must pick the local provider
    crit = ModelRoutingCriteria(complexity="HIGH", task_type="coding", privacy="LOCAL_ONLY")
    selected = router.route(crit)

    assert selected.provider_name() == "local-phi"


def test_model_router_local_only_fails_honestly_when_no_local():
    router = ModelRouter()
    cloud_model = MockProvider(name="gemini-pro")
    router.register_provider("gemini-pro", cloud_model, is_local=False)

    crit = ModelRoutingCriteria(privacy="LOCAL_ONLY")
    with pytest.raises(RuntimeError, match="No local provider"):
        router.route(crit)


def test_model_router_fallback_when_primary_unavailable():
    router = ModelRouter()
    primary_cloud = MockProvider(name="gemini-pro", available=False)
    fallback_local = MockProvider(name="local-backup", available=True)

    router.register_provider("gemini-pro", primary_cloud, is_local=False, capabilities={"general", "deep_reasoning"})
    router.register_provider("local-backup", fallback_local, is_local=True, capabilities={"general"})

    crit = ModelRoutingCriteria(complexity="HIGH")
    selected = router.route(crit)

    # Primary was unavailable, so router fell back to local-backup
    assert selected.provider_name() == "local-backup"
