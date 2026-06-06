"""Tests for governance — audit log + API key + quota management."""

import tempfile
from pathlib import Path

from agora.audit import AuditLogger
from agora.governance import KeyManager, QuotaManager


class TestAuditLogger:
    def setup_method(self):
        db = str(Path(tempfile.mkdtemp()) / "test-audit.db")
        self.logger = AuditLogger(db)

    def test_log_and_query(self):
        eid = self.logger.log("service.register", "system", "minerva")
        assert eid
        entries = self.logger.query(action="service.register")
        assert len(entries) >= 1
        assert entries[0]["action"] == "service.register"

    def test_log_multiple_and_filter(self):
        self.logger.log("service.register", "alice", "svc-a")
        self.logger.log("key.create", "admin", "key-1")
        self.logger.log("route.call", "alice", "svc-a")
        entries = self.logger.query(actor="alice")
        assert len(entries) == 2
        entries = self.logger.query(action="key.create")
        assert len(entries) == 1

    def test_stats(self):
        self.logger.log("service.register", "a", "x")
        self.logger.log("service.register", "b", "y")
        self.logger.log("route.call", "a", "z", "error")
        s = self.logger.stats()
        assert s["total"] == 3
        assert s["actions"]["service.register"] == 2


class TestKeyManager:
    def setup_method(self):
        db = str(Path(tempfile.mkdtemp()) / "test-keys.db")
        self.km = KeyManager(db)

    def test_create_and_validate(self):
        kid, secret = self.km.create_key("test-key", ["read", "write"], "test-tenant")
        assert kid.startswith("ak_")
        assert secret.startswith("agora_")
        key = self.km.validate(secret)
        assert key is not None
        assert key.name == "test-key"
        assert "read" in key.scopes

    def test_validate_bad_secret(self):
        assert self.km.validate("bad_secret") is None

    def test_revoke(self):
        kid, secret = self.km.create_key("temp-key")
        assert self.km.validate(secret) is not None
        self.km.revoke(kid)
        assert self.km.validate(secret) is None

    def test_rotate(self):
        kid, old_secret = self.km.create_key("rotate-me")
        result = self.km.rotate(kid)
        assert result is not None
        new_kid, new_secret = result
        assert new_kid != kid
        assert self.km.validate(old_secret) is None
        assert self.km.validate(new_secret) is not None

    def test_list_keys(self):
        self.km.create_key("k1", ["read"], "t1")
        self.km.create_key("k2", ["write"], "t1")
        self.km.create_key("k3", ["admin"], "t2")
        all_keys = self.km.list_keys()
        assert len(all_keys) == 3
        t1_keys = self.km.list_keys("t1")
        assert len(t1_keys) == 2

    def test_check_scope(self):
        _, secret = self.km.create_key("scoped", ["read"])
        key = self.km.validate(secret)
        assert self.km.check_scope(key, "read") is True
        assert self.km.check_scope(key, "write") is False


class TestQuotaManager:
    def test_check_allows(self):
        qm = QuotaManager()
        for _ in range(5):
            assert qm.check("test-key", limit_per_minute=10) is True

    def test_check_denies(self):
        qm = QuotaManager()
        for _ in range(3):
            assert qm.check("test-key", limit_per_minute=3) is True
        assert qm.check("test-key", limit_per_minute=3) is False

    def test_usage(self):
        qm = QuotaManager()
        qm.check("usage-key", limit_per_minute=60)
        qm.check("usage-key", limit_per_minute=60)
        u = qm.usage("usage-key")
        assert u["requests_last_minute"] == 2
