"""Tests for the accounting module."""

from __future__ import annotations

import importlib
import importlib.util
import os
import tempfile
from datetime import UTC, datetime

import pytest
from agora.accounting import CallRecord, ResourceAccountDB, estimate_cost


@pytest.fixture
def tmp_db():
    """Create a ResourceAccountDB backed by a temporary file."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = ResourceAccountDB(path)
    yield db
    db.close()
    os.unlink(path)


def _make_call(
    caller_id: str,
    service: str = "minerva",
    tool: str = "research",
    inp: int = 1000,
    out: int = 500,
    cost: float | None = None,
) -> CallRecord:
    """Helper to create a CallRecord with consistent timestamp."""
    if cost is None:
        cost = estimate_cost(inp, out)
    return CallRecord(
        caller_id=caller_id,
        service_name=service,
        tool_name=tool,
        input_tokens=inp,
        output_tokens=out,
        cost_usd=cost,
        billed_to=caller_id,
        timestamp=datetime.now(UTC).isoformat(),
    )


def _identity_module():
    spec = importlib.util.find_spec("agora.auth.identity")
    assert spec is not None, "agora.auth.identity module should exist for typed identity support"
    return importlib.import_module("agora.auth.identity")


class TestCallRecord:
    """CallRecord dataclass basics."""

    def test_defaults(self):
        """CallRecord should provide sensible defaults."""
        rec = CallRecord(caller_id="alice", service_name="svc", tool_name="tool")
        assert rec.input_tokens == 0
        assert rec.output_tokens == 0
        assert rec.cost_usd == 0.0
        assert rec.billed_to == ""
        assert rec.timestamp  # should be auto-generated

    def test_custom_values(self):
        rec = CallRecord(
            caller_id="bob",
            service_name="minerva",
            tool_name="research_now",
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.045,
            billed_to="project-x",
            timestamp="2026-01-01T00:00:00",
        )
        assert rec.caller_id == "bob"
        assert rec.input_tokens == 100
        assert rec.cost_usd == 0.045

    def test_from_identity_derives_caller_and_billing_subjects(self):
        identity_mod = _identity_module()
        assert hasattr(CallRecord, "from_identity")

        identity = identity_mod.Identity(
            subject_id="alice",
            subject_type="user",
            issuer="auth0",
            tenant="acme",
        )
        rec = CallRecord.from_identity(identity, service_name="svc", tool_name="tool")

        assert rec.caller_id == "user:alice"
        assert rec.billed_to == "tenant:acme"


class TestResourceAccountDB:
    """ResourceAccountDB with temporary SQLite database."""

    # ── Test: record 3 calls, verify they're stored ──────────────

    def test_record_and_count(self, tmp_db):
        calls = [
            _make_call("alice", "minerva", "research_now", inp=500, out=200),
            _make_call("bob", "sophia", "analyze", inp=1000, out=500),
            _make_call("alice", "minerva", "research_topic", inp=300, out=100),
        ]
        for c in calls:
            tmp_db.record_call(c)

        report = tmp_db.get_report(period="all")
        assert report["total_calls"] == 3
        assert report["unique_callers"] == 2

    def test_record_stores_cost(self, tmp_db):
        c = _make_call("charlie", "eidos", "process", inp=2000, out=1000)
        tmp_db.record_call(c)

        report = tmp_db.get_report(period="all")
        assert report["total_calls"] == 1
        expected = estimate_cost(2000, 1000)
        assert abs(report["total_cost"] - expected) < 1e-9

    # ── Test: get_top_callers returns sorted results ──────────────

    def test_top_callers_sorted(self, tmp_db):
        tmp_db.record_call(_make_call("alice", "svc", "t1", inp=100, out=50, cost=0.01))
        tmp_db.record_call(_make_call("alice", "svc", "t2", inp=100, out=50, cost=0.01))
        tmp_db.record_call(_make_call("bob", "svc", "t1", inp=1000, out=500, cost=0.10))
        tmp_db.record_call(_make_call("bob", "svc", "t2", inp=1000, out=500, cost=0.10))
        tmp_db.record_call(_make_call("charlie", "svc", "t1", inp=50, out=25, cost=0.005))

        top = tmp_db.get_top_callers(period="all", limit=5)
        assert len(top) >= 3

        # Verify sorted descending by total_cost
        costs = [r["total_cost"] for r in top[:3]]
        for i in range(len(costs) - 1):
            assert costs[i] >= costs[i + 1], f"Costs not sorted: {costs}"

    def test_top_callers_limits(self, tmp_db):
        for i in range(5):
            tmp_db.record_call(_make_call(f"user{i}", "svc", "t", cost=0.01))
        top = tmp_db.get_top_callers(period="all", limit=3)
        assert len(top) == 3

    def test_top_callers_respects_period(self, tmp_db):
        """Calls with old timestamps should be excluded from 'day' period."""
        import datetime as dt

        old = CallRecord(
            caller_id="old_user",
            service_name="svc",
            tool_name="t",
            input_tokens=0,
            output_tokens=0,
            cost_usd=1.0,
            billed_to="old_user",
            timestamp=(datetime.now(dt.UTC) - dt.timedelta(days=7)).isoformat(),
        )
        tmp_db.record_call(old)
        tmp_db.record_call(_make_call("new_user", "svc", "t", cost=0.01))

        top_day = tmp_db.get_top_callers(period="day", limit=10)
        caller_ids = [r["caller_id"] for r in top_day]
        assert "old_user" not in caller_ids
        assert "new_user" in caller_ids

    # ── Test: get_report returns correct totals ───────────────────

    def test_get_report_totals(self, tmp_db):
        tmp_db.record_call(_make_call("alice", "minerva", "r1", inp=500, out=200))
        tmp_db.record_call(_make_call("bob", "sophia", "a1", inp=1000, out=500))
        tmp_db.record_call(_make_call("alice", "minerva", "r2", inp=300, out=100))

        report = tmp_db.get_report(period="all")
        assert report["total_calls"] == 3
        assert report["unique_callers"] == 2
        expected_cost = estimate_cost(500, 200) + estimate_cost(1000, 500) + estimate_cost(300, 100)
        assert abs(report["total_cost"] - expected_cost) < 1e-9

    def test_get_report_by_service(self, tmp_db):
        minerva_cost = estimate_cost(500, 200) + estimate_cost(300, 100)
        sophia_cost = estimate_cost(1000, 500)

        tmp_db.record_call(_make_call("alice", "minerva", "r1", inp=500, out=200))
        tmp_db.record_call(_make_call("alice", "minerva", "r2", inp=300, out=100))
        tmp_db.record_call(_make_call("bob", "sophia", "a1", inp=1000, out=500))

        report = tmp_db.get_report(period="all")
        by_svc = {s["service_name"]: s for s in report["by_service"]}

        assert "minerva" in by_svc
        assert "sophia" in by_svc
        assert by_svc["minerva"]["call_count"] == 2
        assert abs(by_svc["minerva"]["total_cost"] - minerva_cost) < 1e-9
        assert by_svc["sophia"]["call_count"] == 1
        assert abs(by_svc["sophia"]["total_cost"] - sophia_cost) < 1e-9

    def test_get_report_empty(self, tmp_db):
        report = tmp_db.get_report(period="all")
        assert report["total_calls"] == 0
        assert report["total_cost"] == 0.0
        assert report["unique_callers"] == 0
        assert report["avg_cost_per_call"] == 0.0

    # ── Test: get_quota ──────────────────────────────────────────

    def test_get_quota_no_calls(self, tmp_db):
        q = tmp_db.get_quota("nobody")
        assert q["caller_id"] == "nobody"
        assert q["total_cost"] == 0.0
        assert q["today_cost"] == 0.0

    def test_get_quota_with_calls(self, tmp_db):
        tmp_db.record_call(_make_call("alice", "svc", "t", inp=1000, out=500))
        tmp_db.record_call(_make_call("alice", "svc", "t2", inp=500, out=200))
        q = tmp_db.get_quota("alice")
        expected = estimate_cost(1000, 500) + estimate_cost(500, 200)
        assert abs(q["total_cost"] - expected) < 1e-9


class TestEstimateCost:
    """Cost estimation logic."""

    def test_default_rates(self):
        # 1M input tokens @ $0.15/M = $0.15
        # 1M output tokens @ $0.60/M = $0.60
        # Total = $0.75
        cost = estimate_cost(1_000_000, 1_000_000)
        assert abs(cost - 0.75) < 1e-9

    def test_zero_tokens(self):
        assert estimate_cost(0, 0) == 0.0

    def test_partial_tokens(self):
        cost = estimate_cost(1000, 500)
        expected = (1000 / 1_000_000 * 0.15) + (500 / 1_000_000 * 0.60)
        assert abs(cost - expected) < 1e-9

    def test_custom_rates(self):
        cost = estimate_cost(1000, 500, input_rate_per_m=1.0, output_rate_per_m=2.0)
        expected = (1000 / 1_000_000 * 1.0) + (500 / 1_000_000 * 2.0)
        assert abs(cost - expected) < 1e-9
