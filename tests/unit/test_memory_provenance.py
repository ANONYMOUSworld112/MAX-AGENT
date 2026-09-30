"""
Unit tests for Memory Provenance Gating (Task 6.1)
==================================================

Covers:
- Untrusted origin blocked from modifying identity and preferences
- Untrusted origin permitted to modify non-sensitive notes
- Trusted origin succeeds across all memory categories
- Untrusted origin blocked from deleting sensitive keys
- Owner inspection and deletion of records
"""

import json
from pathlib import Path
import pytest

import memory.memory_manager as mm
from memory.memory_manager import MemoryOrigin


@pytest.fixture
def isolated_memory(tmp_path: Path, monkeypatch):
    test_mem = tmp_path / "long_term.json"
    monkeypatch.setattr(mm, "MEMORY_PATH", test_mem)
    return test_mem


def test_untrusted_origin_blocked_from_preferences(isolated_memory):
    # Untrusted write to preferences should be rejected
    with pytest.raises(PermissionError) as exc_info:
        mm.update_memory(
            {"preferences": {"theme": "hacked_theme"}},
            origin=MemoryOrigin.UNTRUSTED,
        )
    assert "Untrusted origin cannot modify sensitive memory category 'preferences'" in str(exc_info.value)

    # Verify nothing was written
    mem = mm.load_memory()
    assert "theme" not in mem["preferences"]


def test_untrusted_origin_blocked_from_identity(isolated_memory):
    # Untrusted write to identity should be rejected
    with pytest.raises(PermissionError) as exc_info:
        mm.update_memory(
            {"identity": {"name": "Malicious Attacker"}},
            origin=MemoryOrigin.UNTRUSTED,
        )
    assert "Untrusted origin cannot modify sensitive memory category 'identity'" in str(exc_info.value)

    mem = mm.load_memory()
    assert "name" not in mem["identity"]


def test_trusted_origin_succeeds_for_sensitive_categories(isolated_memory):
    # Trusted write to preferences and identity succeeds
    mm.update_memory(
        {"identity": {"name": "Alice"}, "preferences": {"theme": "dark"}},
        origin=MemoryOrigin.TRUSTED,
    )

    mem = mm.load_memory()
    assert mem["identity"]["name"]["value"] == "Alice"
    assert mem["identity"]["name"]["origin"] == MemoryOrigin.TRUSTED
    assert mem["preferences"]["theme"]["value"] == "dark"


def test_untrusted_origin_allowed_for_notes(isolated_memory):
    # Untrusted write to notes is accepted but tracked
    mm.update_memory(
        {"notes": {"scratchpad": "temporary meeting note"}},
        origin=MemoryOrigin.UNTRUSTED,
    )

    mem = mm.load_memory()
    assert mem["notes"]["scratchpad"]["value"] == "temporary meeting note"
    assert mem["notes"]["scratchpad"]["origin"] == MemoryOrigin.UNTRUSTED


def test_provenance_gated_deletion(isolated_memory):
    # Set up sensitive preference
    mm.update_memory({"preferences": {"locale": "en_US"}}, origin=MemoryOrigin.TRUSTED)

    # Untrusted deletion rejected
    with pytest.raises(PermissionError):
        mm.delete_memory_entry("preferences", "locale", origin=MemoryOrigin.UNTRUSTED)

    # Trusted deletion succeeds
    assert mm.delete_memory_entry("preferences", "locale", origin=MemoryOrigin.TRUSTED) is True
    mem = mm.load_memory()
    assert "locale" not in mem["preferences"]
