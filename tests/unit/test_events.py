"""
Unit tests for core/events.py — EventBus pub/sub and AuditWriter hash chain.
"""

import unittest
import threading
from core.events import EventBus, AuditWriter, _compute_hash
from core.contracts import EventEnvelope


class TestEventBus(unittest.TestCase):
    """Test in-memory pub/sub event bus."""

    def test_subscribe_and_publish(self):
        bus = EventBus()
        received = []
        bus.subscribe("task.created", lambda e: received.append(e))

        event = EventEnvelope(event_type="task.created", payload={"action": "test"})
        bus.publish(event)

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].event_type, "task.created")

    def test_wildcard_subscriber(self):
        bus = EventBus()
        received = []
        bus.subscribe("*", lambda e: received.append(e))

        bus.publish(EventEnvelope(event_type="task.created"))
        bus.publish(EventEnvelope(event_type="action.completed"))

        self.assertEqual(len(received), 2)

    def test_no_cross_talk(self):
        bus = EventBus()
        received = []
        bus.subscribe("task.created", lambda e: received.append(e))

        bus.publish(EventEnvelope(event_type="action.completed"))
        self.assertEqual(len(received), 0)

    def test_handler_exception_does_not_propagate(self):
        bus = EventBus()
        good_received = []

        def bad_handler(e):
            raise ValueError("Handler crash")

        bus.subscribe("test", bad_handler)
        bus.subscribe("test", lambda e: good_received.append(e))

        bus.publish(EventEnvelope(event_type="test"))
        # Bad handler crashed but good handler still received the event
        self.assertEqual(len(good_received), 1)

    def test_unsubscribe(self):
        bus = EventBus()
        received = []
        handler = lambda e: received.append(e)
        bus.subscribe("test", handler)
        bus.unsubscribe("test", handler)

        bus.publish(EventEnvelope(event_type="test"))
        self.assertEqual(len(received), 0)

    def test_event_count(self):
        bus = EventBus()
        self.assertEqual(bus.event_count, 0)
        bus.publish(EventEnvelope(event_type="a"))
        bus.publish(EventEnvelope(event_type="b"))
        self.assertEqual(bus.event_count, 2)

    def test_clear(self):
        bus = EventBus()
        bus.subscribe("test", lambda e: None)
        bus.publish(EventEnvelope(event_type="test"))
        bus.clear()
        self.assertEqual(bus.event_count, 0)

    def test_multiple_subscribers_same_type(self):
        bus = EventBus()
        r1, r2 = [], []
        bus.subscribe("test", lambda e: r1.append(e))
        bus.subscribe("test", lambda e: r2.append(e))

        bus.publish(EventEnvelope(event_type="test"))
        self.assertEqual(len(r1), 1)
        self.assertEqual(len(r2), 1)


class TestAuditWriter(unittest.TestCase):
    """Test append-only hash-chained audit log."""

    def test_write_creates_event(self):
        writer = AuditWriter()
        event = writer.write(event_type="task.created", correlation_id="t1")
        self.assertEqual(event.event_type, "task.created")
        self.assertTrue(len(event.id) > 0)
        self.assertTrue(len(event.hash) > 0)

    def test_chain_integrity(self):
        writer = AuditWriter()
        writer.write(event_type="e1")
        writer.write(event_type="e2")
        writer.write(event_type="e3")
        self.assertTrue(writer.verify_chain())

    def test_genesis_hash(self):
        writer = AuditWriter()
        event = writer.write(event_type="first")
        self.assertEqual(event.prev_hash, AuditWriter.GENESIS_HASH)

    def test_chain_links(self):
        writer = AuditWriter()
        e1 = writer.write(event_type="first")
        e2 = writer.write(event_type="second")
        self.assertEqual(e2.prev_hash, e1.hash)

    def test_chain_length(self):
        writer = AuditWriter()
        for i in range(10):
            writer.write(event_type=f"event-{i}")
        self.assertEqual(writer.length, 10)

    def test_last_hash(self):
        writer = AuditWriter()
        self.assertEqual(writer.last_hash, AuditWriter.GENESIS_HASH)
        e1 = writer.write(event_type="test")
        self.assertEqual(writer.last_hash, e1.hash)

    def test_chain_copy(self):
        writer = AuditWriter()
        writer.write(event_type="test")
        chain = writer.chain
        chain.append(None)
        self.assertEqual(writer.length, 1)  # Original unchanged

    def test_payload_in_hash(self):
        writer = AuditWriter()
        e1 = writer.write(event_type="test", payload={"key": "value1"})
        # Different payload should produce different hash
        writer2 = AuditWriter()
        e2 = writer2.write(event_type="test", payload={"key": "value2"})
        self.assertNotEqual(e1.hash, e2.hash)

    def test_concurrent_writes(self):
        writer = AuditWriter()
        errors = []

        def write_events(prefix, count):
            try:
                for i in range(count):
                    writer.write(event_type=f"{prefix}-{i}")
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=write_events, args=(f"t{t}", 20))
            for t in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0)
        self.assertEqual(writer.length, 100)
        self.assertTrue(writer.verify_chain())

    def test_audit_writer_persists_to_state_db(self):
        import tempfile
        import os
        from core.max_infra.state_db import StateDB

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_audit.db")
            db = StateDB(db_path=db_path)
            writer = AuditWriter(state_db=db)

            e1 = writer.write(event_type="action.executing", actor="user", payload={"action": "test"})
            e2 = writer.write(event_type="action.completed", actor="system", payload={"status": "ok"})

            logs = db.get_audit_logs()
            self.assertEqual(len(logs), 2)
            self.assertEqual(logs[0]["event_type"], "action.executing")
            self.assertEqual(logs[0]["prev_hash"], AuditWriter.GENESIS_HASH)
            self.assertEqual(logs[0]["hash"], e1.hash)
            self.assertEqual(logs[1]["event_type"], "action.completed")
            self.assertEqual(logs[1]["prev_hash"], e1.hash)
            self.assertEqual(logs[1]["hash"], e2.hash)
            db.close()


if __name__ == "__main__":
    unittest.main()
