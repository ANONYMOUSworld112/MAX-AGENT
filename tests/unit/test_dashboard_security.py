"""
Unit tests for Dashboard Security & Network Hardening (Task 7.2)
================================================================

Covers:
- Elimination of _ensure_network_access (no firewall mutation or UAC elevation)
- Default bind host is 127.0.0.1
- Token authentication enforcement on protected endpoints
- Support for X-MAX-Token and Authorization: Bearer <token>
- Protection against DNS rebinding (Host header validation)
- Protection against Cross-Origin / CSWSH (Origin header validation)
- Health check endpoint
"""

import pytest
from fastapi.testclient import TestClient

import dashboard.server as dserver
from dashboard.server import DashboardServer


def test_ensure_network_access_removed():
    """Verify that _ensure_network_access function does not exist anywhere in server module."""
    assert not hasattr(dserver, "_ensure_network_access"), "_ensure_network_access must be completely removed"


def test_dashboard_server_defaults():
    server = DashboardServer(token="secret-test-token")
    assert server.host == "127.0.0.1"
    assert "secret-test-token" in server._tokens


def test_dashboard_health_endpoint():
    server = DashboardServer(token="test-token-123")
    client = TestClient(server.app)

    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["host"] == "127.0.0.1"


def test_protected_endpoint_rejects_unauthenticated():
    server = DashboardServer(token="valid-secret-token")
    client = TestClient(server.app)

    # Without token
    res = client.post("/api/wake")
    assert res.status_code == 401
    assert res.json().get("error") == "Unauthorized"

    # With invalid token
    res = client.post("/api/wake", headers={"X-MAX-Token": "wrong-token"})
    assert res.status_code == 401


def test_protected_endpoint_accepts_valid_tokens():
    server = DashboardServer(token="valid-secret-token")
    client = TestClient(server.app)

    # With X-MAX-Token header
    res1 = client.post("/api/wake", headers={"X-MAX-Token": "valid-secret-token"})
    assert res1.status_code == 200
    assert res1.json().get("ok") is True

    # With Authorization: Bearer header
    res2 = client.post("/api/wake", headers={"Authorization": "Bearer valid-secret-token"})
    assert res2.status_code == 200
    assert res2.json().get("ok") is True


def test_dns_rebinding_protection():
    server = DashboardServer(token="valid-secret-token")
    client = TestClient(server.app)

    # Malicious host header
    res = client.get("/api/health", headers={"Host": "malicious-site.com"})
    assert res.status_code == 403
    assert "Invalid Host header" in res.json().get("error", "")

    # Legitimate host header
    res = client.get("/api/health", headers={"Host": "127.0.0.1:8000"})
    assert res.status_code == 200


def test_origin_header_validation():
    server = DashboardServer(token="valid-secret-token")
    client = TestClient(server.app)

    # Malicious Origin
    res = client.post(
        "/api/wake",
        headers={
            "X-MAX-Token": "valid-secret-token",
            "Origin": "http://evil-attacker.org",
        },
    )
    assert res.status_code == 403
    assert "Invalid Origin" in res.json().get("error", "")

    # Allowed Origin
    res = client.post(
        "/api/wake",
        headers={
            "X-MAX-Token": "valid-secret-token",
            "Origin": "http://127.0.0.1:8000",
        },
    )
    assert res.status_code == 200
