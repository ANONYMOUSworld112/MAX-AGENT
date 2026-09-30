"""
Unit tests for Structured Memory Schema & SQLite Backing (Task 6.3)
====================================================================

Covers:
- StateDB memory_layers CRUD operations and indexed search
- Lossless, non-destructive migration from flat JSON to SQLite StateDB
- Exporting structured SQLite memories back to JSON
"""

import json
from pathlib import Path
import pytest

from core.max_infra.state_db import StateDB
import memory.memory_manager as mm


@pytest.fixture
def state_db(tmp_path: Path):
    db_file = tmp_path / "test_memory_state.db"
    return StateDB(db_path=db_file)


def test_statedb_memory_layers_crud(state_db):
    # 1. Set memory in Layer 1 (Identity) and Layer 2 (Preference)
    state_db.set_memory(layer=1, key="owner_name", value="Alice", metadata={"origin": "TRUSTED"})
    state_db.set_memory(layer=2, key="theme", value="dark", metadata={"origin": "TRUSTED"})

    # 2. Get memory
    rec = state_db.get_memory(layer=1, key="owner_name")
    assert rec is not None
    assert rec["value"] == "Alice"
    assert rec["metadata"]["origin"] == "TRUSTED"

    # 3. Layer queries
    layer1_entries = state_db.get_memories_by_layer(1)
    assert len(layer1_entries) == 1
    assert layer1_entries[0]["key"] == "owner_name"

    # 4. Search queries
    results = state_db.search_memories("dark")
    assert len(results) == 1
    assert results[0]["key"] == "theme"
    assert results[0]["value"] == "dark"

    # 5. Delete memory
    assert state_db.delete_memory(layer=2, key="theme") is True
    assert state_db.get_memory(layer=2, key="theme") is None


def test_lossless_migration_from_json_to_sqlite(tmp_path: Path, state_db):
    sample_json = tmp_path / "source_long_term.json"
    sample_data = {
        "identity": {
            "name": {"value": "Dave", "updated": "2026-09-30"},
            "city": {"value": "San Francisco", "updated": "2026-09-30"},
        },
        "preferences": {
            "ide": {"value": "VS Code", "updated": "2026-09-30"},
        },
        "projects": {
            "max": {"value": "AI operating system agent", "updated": "2026-09-30"},
        },
        "notes": {
            "todo": {"value": "Refactor scheduler", "updated": "2026-09-30"},
        },
    }
    sample_json.write_text(json.dumps(sample_data), encoding="utf-8")

    # Migrate to SQLite
    migrated_count = mm.migrate_json_to_sqlite(sample_json, state_db)
    assert migrated_count == 5

    # Original JSON must remain untouched
    assert sample_json.exists()
    assert json.loads(sample_json.read_text(encoding="utf-8")) == sample_data

    # Verify SQLite contents
    id_entry = state_db.get_memory(layer=1, key="name")
    assert id_entry is not None
    assert id_entry["value"] == "Dave"

    pref_entry = state_db.get_memory(layer=2, key="ide")
    assert pref_entry is not None
    assert pref_entry["value"] == "VS Code"

    proj_entry = state_db.get_memory(layer=4, key="max")
    assert proj_entry is not None
    assert proj_entry["value"] == "AI operating system agent"


def test_export_sqlite_to_json(tmp_path: Path, state_db):
    state_db.set_memory(layer=1, key="name", value="Eva", metadata={"category": "identity"})
    state_db.set_memory(layer=2, key="editor", value="Neovim", metadata={"category": "preferences"})

    export_file = tmp_path / "exported.json"
    data = mm.export_sqlite_to_json(state_db, target_json_path=export_file)

    assert "identity" in data
    assert data["identity"]["name"]["value"] == "Eva"
    assert data["preferences"]["editor"]["value"] == "Neovim"

    # Exported file exists and matches
    assert export_file.exists()
    loaded = json.loads(export_file.read_text(encoding="utf-8"))
    assert loaded["identity"]["name"]["value"] == "Eva"
