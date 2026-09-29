import pytest
from fastapi.testclient import TestClient
from dashboard.server import DashboardServer


def test_dashboard_api_agents():
    server = DashboardServer()
    client = TestClient(server.app)

    response = client.get("/api/agents")
    assert response.status_code == 200
    data = response.json()
    assert "agents" in data
    assert data["count"] == 33
    names = [a["name"] for a in data["agents"]]
    assert "CodingAgent" in names
    assert "SystemMonitorAgent" in names
    assert "EmailAgent" in names
