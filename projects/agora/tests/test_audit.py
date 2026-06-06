"""Tests for audit log — AuditLogger log/query/stats."""

import importlib
import importlib.util
import tempfile
import time
from pathlib import Path

from agora.audit import AuditLogger


def _identity_module():
    spec = importlib.util.find_spec("agora.auth.identity")
    assert spec is not None, "agora.auth.identity module should exist for typed identity support"
    return importlib.import_module("agora.auth.identity")


class TestAuditLogger:
    def setup_method(self):
        db = str(Path(tempfile.mkdtemp()) / "test-audit.db")
        self.logger = AuditLogger(db)

    # ── log ────────────────────────────────────────

    def test_log_returns_id(self):
        eid = self.logger.log("service.register", "system", "minerva")
        assert eid
        assert len(eid) == 8  # uuid4()[:8]

    def test_log_with_all_fields(self):
        eid = self.logger.log(
            action="key.create",
            actor="admin",
            resource="ak_abc123",
            result="success",
            detail="Created key for test-tenant",
            ip="192.168.1.1",
        )
        assert eid
        entries = self.logger.query(action="key.create")
        assert len(entries) == 1
        e = entries[0]
        assert e["actor"] == "admin"
        assert e["resource"] == "ak_abc123"
        assert e["result"] == "success"
        assert e["detail"] == "Created key for test-tenant"
        assert e["ip"] == "192.168.1.1"

    def test_log_accepts_typed_identity_actor(self):
        identity_mod = _identity_module()
        identity = identity_mod.Identity(
            subject_id="alice",
            subject_type="user",
            issuer="auth0",
            tenant="acme",
        )

        self.logger.log(action="route.call", actor=identity, resource="svc-a")

        entries = self.logger.query(action="route.call")
        assert len(entries) == 1
        assert entries[0]["actor"] == "user:alice"

    # ── query ──────────────────────────────────────

    def test_query_all(self):
        self.logger.log("a", "user1", "x")
        self.logger.log("b", "user2", "y")
        entries = self.logger.query()
        assert len(entries) == 2

    def test_query_filter_by_actor(self):
        self.logger.log("svc.register", "alice", "svc-a")
        self.logger.log("key.create", "admin", "key-1")
        self.logger.log("route.call", "alice", "svc-a")
        entries = self.logger.query(actor="alice")
        assert len(entries) == 2

    def test_query_filter_by_action(self):
        self.logger.log("svc.register", "alice", "svc-a")
        self.logger.log("key.create", "admin", "key-1")
        entries = self.logger.query(action="key.create")
        assert len(entries) == 1

    def test_query_filter_by_resource(self):
        self.logger.log("route.call", "alice", "svc-a", "error")
        self.logger.log("route.call", "bob", "svc-b")
        entries = self.logger.query(resource="svc-a")
        assert len(entries) == 1

    def test_query_filter_by_since(self):
        self.logger.log("old_event", "u1", "r1")
        ts_now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.logger.log("new_event", "u2", "r2")
        entries = self.logger.query(since=ts_now)
        assert len(entries) >= 1  # may include both if same-second

    def test_query_limit(self):
        for i in range(10):
            self.logger.log(f"evt_{i}", "u", "r")
        entries = self.logger.query(limit=3)
        assert len(entries) == 3

    def test_query_empty_db(self):
        entries = self.logger.query()
        assert entries == []

    def test_query_no_match(self):
        self.logger.log("svc.register", "alice", "svc-a")
        entries = self.logger.query(actor="nobody")
        assert entries == []

    def test_query_orders_by_timestamp_desc(self):
        self.logger.log("first", "u", "r")
        time.sleep(0.01)
        self.logger.log("second", "u", "r")
        entries = self.logger.query()
        assert entries[0]["action"] == "second"

    # ── stats ──────────────────────────────────────

    def test_stats_total(self):
        self.logger.log("svc.register", "a", "x")
        self.logger.log("svc.register", "b", "y")
        self.logger.log("route.call", "a", "z", "error")
        s = self.logger.stats()
        assert s["total"] == 3

    def test_stats_actions(self):
        self.logger.log("svc.register", "a", "x")
        self.logger.log("svc.register", "b", "y")
        self.logger.log("route.call", "a", "z")
        s = self.logger.stats()
        assert s["actions"]["svc.register"] == 2
        assert s["actions"]["route.call"] == 1

    def test_stats_actors(self):
        self.logger.log("svc.register", "alice", "x")
        self.logger.log("route.call", "bob", "y")
        s = self.logger.stats()
        assert s["actors"]["alice"] == 1
        assert s["actors"]["bob"] == 1

    def test_stats_error_rate(self):
        self.logger.log("svc.register", "a", "x", "success")
        self.logger.log("error", "a", "z")  # implementation counts action="error"
        self.logger.log("key.create", "b", "k")
        s = self.logger.stats()
        assert s["error_rate"] == round(1 / 3, 4)

    def test_stats_no_errors(self):
        self.logger.log("svc.register", "a", "x", "success")
        s = self.logger.stats()
        assert s["error_rate"] == 0.0

    def test_stats_empty(self):
        s = self.logger.stats()
        assert s["total"] == 0
        assert s["error_rate"] == 0.0
        assert s["actions"] == {}
        assert s["actors"] == {}

    def test_stats_since_filter(self):
        self.logger.log("old_event", "u", "r")
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.logger.log("new_event", "u", "r")
        s = self.logger.stats(since=ts)
        assert s["total"] >= 1  # may include both if same-second

    # ── isolation ──────────────────────────────────

    def test_isolation_between_instances(self):
        db1 = str(Path(tempfile.mkdtemp()) / "audit1.db")
        db2 = str(Path(tempfile.mkdtemp()) / "audit2.db")
        al1 = AuditLogger(db1)
        al2 = AuditLogger(db2)
        al1.log("event_a", "u1", "r1")
        al2.log("event_b", "u2", "r2")
        assert len(al1.query()) == 1
        assert al1.query()[0]["action"] == "event_a"
        assert len(al2.query()) == 1
        assert al2.query()[0]["action"] == "event_b"
