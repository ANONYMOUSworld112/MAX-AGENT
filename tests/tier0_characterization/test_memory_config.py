"""Tier 0 Characterization Test: Memory & Config Managers.

Tests memory.memory_manager and memory.config_manager behaviors.
"""
import json
from pathlib import Path
import memory.memory_manager as mm
import memory.config_manager as cm


def test_memory_crud_and_prompt_formatting(tmp_path: Path, monkeypatch):
    test_mem_file = tmp_path / "long_term.json"
    monkeypatch.setattr(mm, "MEMORY_PATH", test_mem_file)

    # Initial load is empty
    mem = mm.load_memory()
    assert "identity" in mem
    assert "preferences" in mem

    # Update memory using dict mapping (actual implementation signature)
    updated_mem = mm.update_memory({"preferences": {"theme": "dark"}})
    assert isinstance(updated_mem, dict)

    # Read back
    mem_reloaded = mm.load_memory()
    assert mem_reloaded["preferences"]["theme"]["value"] == "dark"

    # Format for prompt (actual header is "[WHAT YOU KNOW ABOUT THIS PERSON")
    prompt_str = mm.format_memory_for_prompt(mem_reloaded)
    assert "[WHAT YOU KNOW ABOUT THIS PERSON" in prompt_str
    assert "Theme: dark" in prompt_str

    # Search memory (returns formatted string)
    result_str = mm.search_memory("dark")
    assert "Stored facts matching 'dark'" in result_str
    assert "preferences/theme: dark" in result_str


def test_config_manager_defaults(tmp_path: Path, monkeypatch):
    test_cfg_file = tmp_path / "api_keys.json"
    test_cfg_file.write_text(
        json.dumps({
            "gemini_api_key": "test_key",
            "voice_name": "Aoede",
            "wake_word_enabled": True,
            "morning_brief_enabled": False,
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(cm, "CONFIG_FILE", test_cfg_file)

    assert cm.get_voice() == "Aoede"
    assert cm.get_wake_word_enabled() is True
    assert cm.get_brief_enabled() is False

    cm.save_wake_word_enabled(False)
    assert cm.get_wake_word_enabled() is False
