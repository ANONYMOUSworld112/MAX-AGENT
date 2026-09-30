"""
Unit tests for core/capability_registry.py — CapabilityRegistry and CapabilityEntry.
"""

import unittest
from core.contracts import RiskLevel
from core.capability_registry import (
    CapabilityEntry,
    CapabilityRegistry,
    IdempotencyClass,
)


class TestCapabilityEntry(unittest.TestCase):
    """Tests for individual CapabilityEntry dataclass and methods."""

    def test_creation_and_defaults(self):
        entry = CapabilityEntry(name="sample_tool", description="A sample capability")
        self.assertEqual(entry.name, "sample_tool")
        self.assertEqual(entry.idempotency_class, IdempotencyClass.NON_IDEMPOTENT)
        self.assertEqual(entry.base_risk_level, RiskLevel.MEDIUM)
        self.assertTrue(entry.enabled)
        self.assertFalse(entry.is_agent)

    def test_to_tool_declaration(self):
        entry = CapabilityEntry(
            name="Open_App",
            description="Launch application",
            parameters={"type": "OBJECT", "properties": {"app_name": {"type": "string"}}},
        )
        decl = entry.to_tool_declaration()
        self.assertEqual(decl["name"], "open_app")
        self.assertEqual(decl["description"], "Launch application")
        self.assertIn("properties", decl["parameters"])

    def test_validate_schema_valid(self):
        entry = CapabilityEntry(
            name="valid_tool",
            parameters={"type": "OBJECT", "properties": {}},
        )
        self.assertEqual(entry.validate_schema(), [])

    def test_validate_schema_invalid_name(self):
        entry = CapabilityEntry(name="123-invalid-name!")
        errors = entry.validate_schema()
        self.assertTrue(any("Invalid capability name" in e for e in errors))

    def test_validate_schema_invalid_type(self):
        entry = CapabilityEntry(
            name="valid_name",
            parameters={"type": "INVALID_TYPE"},
        )
        errors = entry.validate_schema()
        self.assertTrue(any("Invalid schema type" in e for e in errors))


class TestCapabilityRegistry(unittest.TestCase):
    """Tests for CapabilityRegistry container and filtering."""

    def setUp(self):
        self.registry = CapabilityRegistry()
        self.entry_read = CapabilityEntry(
            name="get_status",
            description="Get system stats",
            declared_resources=["metrics", "os"],
            idempotency_class=IdempotencyClass.READ_ONLY,
            base_risk_level=RiskLevel.LOW,
            parameters={"type": "OBJECT"},
        )
        self.entry_write = CapabilityEntry(
            name="write_file",
            description="Write to disk",
            declared_resources=["filesystem"],
            idempotency_class=IdempotencyClass.NON_IDEMPOTENT,
            base_risk_level=RiskLevel.HIGH,
            parameters={"type": "OBJECT"},
        )
        self.registry.register(self.entry_read)
        self.registry.register(self.entry_write)

    def test_get_and_has(self):
        self.assertTrue(self.registry.has("get_status"))
        self.assertTrue(self.registry.has("GET_STATUS"))  # case-insensitive
        self.assertFalse(self.registry.has("nonexistent"))
        self.assertEqual(self.registry.get("write_file").name, "write_file")

    def test_names(self):
        names = self.registry.names()
        self.assertIn("get_status", names)
        self.assertIn("write_file", names)
        self.assertEqual(len(names), 2)

    def test_list_all(self):
        all_caps = self.registry.list_all()
        self.assertEqual(len(all_caps), 2)

    def test_find_by_resource(self):
        fs_caps = self.registry.find_by_resource("filesystem")
        self.assertEqual(len(fs_caps), 1)
        self.assertEqual(fs_caps[0].name, "write_file")

        metrics_caps = self.registry.find_by_resource("metrics")
        self.assertEqual(len(metrics_caps), 1)
        self.assertEqual(metrics_caps[0].name, "get_status")

    def test_find_by_risk(self):
        low_caps = self.registry.find_by_risk(RiskLevel.LOW)
        self.assertEqual(len(low_caps), 1)
        self.assertEqual(low_caps[0].name, "get_status")

        high_caps = self.registry.find_by_risk(RiskLevel.HIGH)
        self.assertEqual(len(high_caps), 1)
        self.assertEqual(high_caps[0].name, "write_file")

    def test_scoped_tool_declarations_bounds_exposure(self):
        # Bounded exposure: requesting only get_status returns only 1 declaration
        scoped = self.registry.get_scoped_tool_declarations(["get_status"])
        self.assertEqual(len(scoped), 1)
        self.assertEqual(scoped[0]["name"], "get_status")

        # None returns all enabled
        all_decls = self.registry.get_scoped_tool_declarations(None)
        self.assertEqual(len(all_decls), 2)

    def test_validate_schemas(self):
        bad_entry = CapabilityEntry(name="bad!name", parameters={"type": "BAD"})
        self.registry.register(bad_entry)
        errors = self.registry.validate_schemas()
        self.assertIn("bad!name", errors)
        self.assertGreater(len(errors["bad!name"]), 0)

    def test_singleton_behavior(self):
        CapabilityRegistry.reset_instance()
        r1 = CapabilityRegistry.get_instance()
        r2 = CapabilityRegistry.get_instance()
        self.assertIs(r1, r2)
        CapabilityRegistry.reset_instance()


class TestRegistryBulkIngestion(unittest.TestCase):
    """Tests for ingesting from ActionRegistry and AgentRegistry."""

    def test_ingest_from_real_agent_registry(self):
        from agents.router import AgentRegistry
        agent_reg = AgentRegistry.get_instance()
        cap_reg = CapabilityRegistry()

        count = cap_reg.load_from_agent_registry(agent_reg)
        self.assertEqual(count, 33)
        self.assertTrue(cap_reg.has("codingagent"))
        self.assertTrue(cap_reg.has("calendaragent"))
        self.assertTrue(cap_reg.get("codingagent").is_agent)

        # Re-ingesting skips duplicates
        count2 = cap_reg.load_from_agent_registry(agent_reg)
        self.assertEqual(count2, 0)


if __name__ == "__main__":
    unittest.main()
