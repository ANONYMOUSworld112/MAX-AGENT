import pytest
from agents.base import AgentInput
from agents.router import AgentRegistry
from agents.software import (
    CodingAgent,
    CodeReviewer,
    TestWriter,
    DevOpsAgent,
    DBAgent,
    APIDesigner,
    DocWriter,
    DependencyMgr,
)


def test_cluster_software_agents_instantiation_and_tiers():
    agents = [
        (CodingAgent(), "CodingAgent", 1),
        (CodeReviewer(), "CodeReviewer", 0),
        (TestWriter(), "TestWriter", 1),
        (DevOpsAgent(), "DevOpsAgent", 2),
        (DBAgent(), "DBAgent", 2),
        (APIDesigner(), "APIDesigner", 0),
        (DocWriter(), "DocWriter", 0),
        (DependencyMgr(), "DependencyMgr", 1),
    ]

    registry = AgentRegistry()

    for agent, expected_name, expected_tier in agents:
        assert agent.name == expected_name
        assert agent.permission_tier == expected_tier
        tool_def = agent.get_tool_definition()
        assert tool_def["name"] == expected_name.lower()
        assert "parameters" in tool_def

        # Register in registry
        registry.register(agent)
        retrieved = registry.get(expected_name)
        assert retrieved is not None
        assert retrieved.name == expected_name


def test_cluster_software_execution_cycle(tmp_path):
    # 1. CodingAgent
    target_file = tmp_path / "hello.py"
    coding = CodingAgent()
    out_code = coding.run(AgentInput(
        task_id="sw_1",
        task_description="Create hello world script",
        target_files=[str(target_file)],
        parameters={"filepath": str(target_file), "code": "print('hello world')\n", "action": "write"},
    ))
    assert out_code.success is True
    assert target_file.exists()
    assert "hello world" in target_file.read_text(encoding="utf-8")

    # 2. CodeReviewer
    reviewer = CodeReviewer()
    out_rev = reviewer.run(AgentInput(
        task_id="sw_2",
        task_description="Review code snippet",
        parameters={"code": "eval('2+2')\npassword = '123'"},
    ))
    assert out_rev.success is True
    assert out_rev.artifacts["status"] == "CHANGES_REQUESTED"
    assert len(out_rev.artifacts["findings"]) >= 2

    # 3. TestWriter
    tw = TestWriter()
    out_tw = tw.run(AgentInput(
        task_id="sw_3",
        task_description="Write tests for auth service",
        parameters={"module_name": "auth_service"},
    ))
    assert out_tw.success is True
    assert "test_code" in out_tw.artifacts

    # 4. DevOpsAgent
    devops = DevOpsAgent()
    out_dev = devops.run(AgentInput(
        task_id="sw_4",
        task_description="Generate GitHub actions workflow",
        parameters={"env": "production"},
    ))
    assert out_dev.success is True
    assert out_dev.artifacts["requires_confirmation"] is True

    # 5. DBAgent
    db = DBAgent()
    out_db = db.run(AgentInput(
        task_id="sw_5",
        task_description="Create user profile table",
        parameters={"table": "user_profiles"},
    ))
    assert out_db.success is True
    assert "CREATE TABLE" in out_db.artifacts["sql"]

    # 6. APIDesigner
    api = APIDesigner()
    out_api = api.run(AgentInput(
        task_id="sw_6",
        task_description="Design user signup endpoint",
        parameters={"endpoint": "/api/v1/auth/signup", "method": "POST"},
    ))
    assert out_api.success is True
    assert "openapi" in out_api.artifacts["spec"]

    # 7. DocWriter
    doc = DocWriter()
    out_doc = doc.run(AgentInput(
        task_id="sw_7",
        task_description="Document auth module",
        parameters={"title": "Authentication Guide"},
    ))
    assert out_doc.success is True
    assert "# Authentication Guide" in out_doc.artifacts["content"]

    # 8. DependencyMgr
    dep = DependencyMgr()
    out_dep = dep.run(AgentInput(
        task_id="sw_8",
        task_description="Audit security vulnerabilities in dependencies",
        parameters={"dependencies": ["pydantic", "fastapi"]},
    ))
    assert out_dep.success is True
    assert out_dep.artifacts["packages_scanned"] == 2
