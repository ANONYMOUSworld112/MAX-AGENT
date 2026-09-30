"""Tier 0 Characterization Test: Action Loader & Registry.

Tests discover_actions, ActionRecord validation, and ActionRegistry dispatch.
"""
from pathlib import Path
from core.action_loader import discover_actions, ActionRegistry, ActionRecord


def test_discover_actions_returns_valid_registry(tmp_path: Path):
    # Create sample action file
    action_file = tmp_path / "sample_action.py"
    action_file.write_text(
        '''
def sample_handler(parameters, **kwargs):
    return f"Executed with {parameters.get('key', 'default')}"

TOOL = {
    "name": "sample_tool",
    "description": "A sample tool for testing.",
    "parameters": {"type": "OBJECT", "properties": {"key": {"type": "STRING"}}},
    "handler": sample_handler,
}
''',
        encoding="utf-8",
    )

    registry = discover_actions(tmp_path, reserved_names={"reserved_tool"}, logger=lambda _: None)
    assert isinstance(registry, ActionRegistry)
    assert registry.has("sample_tool")
    assert "sample_tool" in registry.names()

    # Verify declaration schema
    decls = registry.get_tool_declarations()
    assert len(decls) == 1
    assert decls[0]["name"] == "sample_tool"
    assert decls[0]["description"] == "A sample tool for testing."

    # Verify dispatch
    res = registry.run("sample_tool", {"key": "alpha"})
    assert res == "Executed with alpha"


def test_discover_actions_rejects_reserved_and_invalid(tmp_path: Path):
    # Action that collides with reserved name
    reserved_file = tmp_path / "reserved_action.py"
    reserved_file.write_text(
        '''
def fn(parameters, **kw): return "ok"
TOOL = {"name": "blocked_tool", "description": "desc", "parameters": {"type": "OBJECT"}, "handler": fn}
''',
        encoding="utf-8",
    )

    # Action missing description
    invalid_file = tmp_path / "invalid_action.py"
    invalid_file.write_text(
        '''
def fn2(parameters, **kw): return "ok"
TOOL = {"name": "invalid_tool", "parameters": {"type": "OBJECT"}, "handler": fn2}
''',
        encoding="utf-8",
    )

    registry = discover_actions(tmp_path, reserved_names={"blocked_tool"}, logger=lambda _: None)
    assert not registry.has("blocked_tool")
    assert not registry.has("invalid_tool")
    assert registry.run("nonexistent", {}) == "Action 'nonexistent' is not available."
