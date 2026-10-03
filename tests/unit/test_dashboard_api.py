"""
Unit tests for Structured Dashboard API & Rate Limiting (Phase 11: Task 11.2)
=============================================================================
"""

import time
import pytest
from fastapi.testclient import TestClient

from dashboard.server import DashboardServer
from core.hooks import LifecycleHookRegistry, MetricsCollectorHook


def test_api_endpoints_require_authentication():
    server = DashboardServer(token="secure-token-xyz")
    client = TestClient(server.app)

    endpoints = [
        ("GET", "/api/agents"),
        ("GET", "/api/tasks"),
        ("GET", "/api/tasks/task-123"),
        ("GET", "/api/metrics"),
        ("GET", "/api/files"),
        ("POST", "/api/command"),
        ("POST", "/api/wake"),
    ]

    for method, path in endpoints:
        if method == "GET":
            res = client.get(path)
        else:
            res = client.post(path, json={})
        assert res.status_code == 401, f"{method} {path} should require auth, got {res.status_code}"
        assert res.json().get("error") == "Unauthorized"


def test_api_tasks_listing_and_detail():
    server = DashboardServer(token="valid-token")
    server.register_task("task-101", {
        "id": "task-101",
        "description": "Run tests",
        "status": "RUNNING",
        "step": 2,
    })
    client = TestClient(server.app)
    headers = {"X-MAX-Token": "valid-token"}

    # List tasks
    res = client.get("/api/tasks", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["count"] == 1
    assert data["tasks"][0]["id"] == "task-101"

    # Detail existing task
    res_det = client.get("/api/tasks/task-101", headers=headers)
    assert res_det.status_code == 200
    assert res_det.json()["task"]["id"] == "task-101"

    # Detail non-existent task
    res_404 = client.get("/api/tasks/task-unknown", headers=headers)
    assert res_404.status_code == 404
    assert "not found" in res_404.json()["error"].lower()


def test_api_metrics_with_hooks():
    hooks = LifecycleHookRegistry()
    metrics_hook = MetricsCollectorHook()
    metrics_hook.register(hooks)

    server = DashboardServer(token="valid-token", hooks=metrics_hook)
    client = TestClient(server.app)
    headers = {"Authorization": "Bearer valid-token"}

    res = client.get("/api/metrics", headers=headers)
    assert res.status_code == 200
    metrics = res.json()["metrics"]
    assert "active_clients" in metrics
    assert "uptime_seconds" in metrics
    assert "hooks" in metrics
    assert "task_starts" in metrics["hooks"]


def test_get_endpoints_are_side_effect_free():
    """Verify that repeated GET calls do not alter internal task state."""
    server = DashboardServer(token="valid-token")
    server.register_task("task-ro", {"id": "task-ro", "status": "PENDING"})
    client = TestClient(server.app)
    headers = {"X-MAX-Token": "valid-token"}

    # Call 5 times
    for _ in range(5):
        res = client.get("/api/tasks", headers=headers)
        assert res.status_code == 200

    assert len(server._tasks) == 1
    assert server._tasks["task-ro"]["status"] == "PENDING"


def test_rate_limiting_enforcement():
    """Verify that requests exceeding rate_limit_per_minute receive HTTP 429."""
    limit = 5
    server = DashboardServer(token="valid-token", rate_limit_per_minute=limit)
    client = TestClient(server.app)
    headers = {"X-MAX-Token": "valid-token"}

    # First 5 calls within limit
    for i in range(limit):
        res = client.get("/api/tasks", headers=headers)
        assert res.status_code == 200, f"Request {i+1} should succeed"

    # 6th call exceeds limit
    res_exceeded = client.get("/api/tasks", headers=headers)
    assert res_exceeded.status_code == 429
    assert res_exceeded.json()["error"] == "Rate limit exceeded"
    assert "retry_after" in res_exceeded.json()
    assert "Retry-After" in res_exceeded.headers


def test_health_check_exempt_from_rate_limit():
    """Verify that /api/health is not blocked by rate limiting."""
    limit = 3
    server = DashboardServer(token="valid-token", rate_limit_per_minute=limit)
    client = TestClient(server.app)

    # Health check does not require auth and is exempt from rate limits
    for _ in range(limit + 5):
        res = client.get("/api/health")
        assert res.status_code == 200
