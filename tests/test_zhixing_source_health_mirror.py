"""Exercise the mirrored host asset, including unhealthy and stale observations."""

from __future__ import annotations

import ast
import hashlib
import importlib.machinery
import importlib.util
import sys
import types
from pathlib import Path

import pytest


# __file__ locates the resolver module only; the inspected checkout is selected
# by the repository's read-root contract, rather than a runtime state profile.
_resolver_file = Path(__file__).resolve().parents[1] / "bin/lib/repo_root.py"
_resolver_spec = importlib.util.spec_from_file_location("zhixing_asset_repo_root", _resolver_file)
assert _resolver_spec is not None and _resolver_spec.loader is not None
_resolver = importlib.util.module_from_spec(_resolver_spec)
_resolver_spec.loader.exec_module(_resolver)
ASSETS = _resolver.code_root() / "bin/panorama/assets/host"


def _refresh(monkeypatch):
    # Loading the host asset must not need a running host or execute its main.
    monkeypatch.setitem(sys.modules, "probe_utils", types.ModuleType("probe_utils"))
    loader = importlib.machinery.SourceFileLoader(
        "zhixing_mirrored_refresh", str(ASSETS / "refresh.py.asset")
    )
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


@pytest.mark.parametrize("asset", [
    "workflow_collector.py.asset", "scheduler_collector.py.asset",
    "orchestrator.py.asset", "refresh.py.asset",
])
def test_all_four_source_assets_are_executable_python(asset):
    source = (ASSETS / asset).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=asset)
    assert tree.body
    compile(tree, asset, "exec")


@pytest.mark.parametrize("body,expected", [
    ({"state": "OBSERVED", "ok": True}, "OK"),
    ({"state": "OBSERVED", "ok": False}, "DEGRADED"),
    ({"state": "OBSERVED", "status": "PARTIAL"}, "PARTIAL"),
    ({"state": "OBSERVED", "available": False}, "UNAVAILABLE"),
    ({"state": "UNPROVABLE", "ok": True}, "UNPROVABLE"),
    (None, "UNKNOWN"),
])
def test_explicit_failure_cannot_be_promoted_by_transport_success(monkeypatch, body, expected):
    assert _refresh(monkeypatch).source_health(body) == expected


def test_valid_failed_observation_updates_observation_clock_only(monkeypatch):
    mod = _refresh(monkeypatch)
    previous = {
        "metadata": {}, "presentation": {}, "observed_at": "earlier",
        "roadmap": {"gates": []}, "portfolio": {},
        "source_states": {"scheduler": {
            "status": "OK", "last_success_at": "prior-healthy",
            "health_semantics": mod.HEALTH_SEMANTICS,
        }},
        "live_sources": {"scheduler": {"ok": True, "observed_at": "prior-healthy"}},
    }
    body = {"state": "DEGRADED", "ok": False, "observed_at": "new-observation", "orphan_count": 6}
    result = mod.apply_results(previous, [("scheduler", body, None)], "new-attempt")
    state = result["source_states"]["scheduler"]
    assert state["status"] == "DEGRADED"
    assert state["last_success_at"] == "prior-healthy"
    assert state["last_observed_at"] == "new-observation"
    assert state["last_attempt_at"] == "new-attempt"
    assert result["live_sources"]["scheduler"]["orphan_count"] == 6
    assert previous["source_states"]["scheduler"]["status"] == "OK"


def test_transport_failure_retains_old_observation_without_new_success(monkeypatch):
    mod = _refresh(monkeypatch)
    previous = {
        "metadata": {}, "presentation": {}, "observed_at": "earlier",
        "roadmap": {"gates": []}, "portfolio": {},
        "source_states": {"workflow": {
            "status": "DEGRADED", "last_success_at": "prior-healthy",
            "last_observed_at": "old-observation", "health_semantics": mod.HEALTH_SEMANTICS,
        }},
        "live_sources": {"workflow": {"state": "DEGRADED", "observed_at": "old-observation", "run_count": 223}},
    }
    result = mod.apply_results(previous, [("workflow", None, "TimeoutExpired")], "new-attempt")
    state = result["source_states"]["workflow"]
    assert state["status"].startswith("STALE")
    assert state["last_success_at"] == "prior-healthy"
    assert (state.get("last_observed_at") or state.get("observed_at")) == "old-observation"
    assert state["last_attempt_at"] == "new-attempt"
    assert result["live_sources"]["workflow"]["run_count"] == 223


def test_legacy_success_timestamp_from_failed_body_is_unknown(monkeypatch):
    mod = _refresh(monkeypatch)
    assert mod.prior_healthy_success(
        {"status": "OK", "last_success_at": "old-stamp"},
        {"state": "OBSERVED", "ok": False, "observed_at": "old-stamp"},
    ) is None


# These digests name the reviewed Dashboard Git objects, rather than whichever
# files happen to be running on this machine. A new mirror delivery updates them.
PORTFOLIO_FREEZE = {
    "portfolio_collector.py.asset": "992f9719873dd9f58493d00cb06dc34e193e08ec4b193f82c04e6050759bd00c",
    "refresh.py.asset": "295c0af997547c0ed2f1eb3bf8c900b81ef0fff89d0aefe52c915248af942047",
    "strategy_projection.py.asset": "ad9123da7a58f10394df493b6ab6172866dd1056ff82f9ee7b76dd9ec4298648",
}


@pytest.mark.parametrize("asset,expected", PORTFOLIO_FREEZE.items())
def test_portfolio_mirrors_match_frozen_git_bytes(asset, expected):
    raw = (ASSETS / asset).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == expected
    compile(raw, asset, "exec")


def _portfolio(monkeypatch):
    # Only the external registration/base interfaces are fixtures. Load and
    # execute the delivered source helper and projection without a host runtime.
    package = types.ModuleType("collectors")
    package.__path__ = []
    base = types.ModuleType("collectors.base")
    base.DataCollector = object
    class CollectionError(Exception):
        def __init__(self, source, reason, cause=None):
            self.reason = reason
            super().__init__(reason)
    base.CollectionError = CollectionError
    registry = types.ModuleType("collectors.registry")
    registry.register = lambda *args, **kwargs: lambda cls: cls
    monkeypatch.setitem(sys.modules, "collectors", package)
    monkeypatch.setitem(sys.modules, "collectors.base", base)
    monkeypatch.setitem(sys.modules, "collectors.registry", registry)
    loader = importlib.machinery.SourceFileLoader("collectors.portfolio", str(ASSETS / "portfolio_collector.py.asset"))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "collectors.portfolio", module)
    loader.exec_module(module)
    return module


def test_actual_portfolio_and_legacy_mirrors_share_raw_object_reader(monkeypatch):
    mod = _portfolio(monkeypatch)
    raw = b"meta: {total_bets: 999}\r\nbets:\r\n  - {id: fixture-one, status: pending}\r\n  \r\n"
    oid = "a" * 40
    monkeypatch.setattr(mod, "_read_cmd", lambda argv, **kwargs: oid.encode() if "commits/main" in argv[2] else raw)
    legacy = _refresh(monkeypatch)
    # Legacy richer projection consults the redactor interface, unrelated here.
    sys.modules["probe_utils"].redact_secrets = lambda value: value
    for value in (mod.PortfolioCollector().collect(), legacy.probe_portfolio()):
        assert value["ledger_sha256"] == hashlib.sha256(raw).hexdigest()
        assert value["sha"] == oid and value["actual"] == 1
        assert value["counts"] == {"pending": 1} and value["source_lane"] == "REMOTE_MAIN"


def test_actual_strategy_mirror_keeps_current_content_clock(monkeypatch):
    # Ontology enrichment is an external interface and not changed in this wave.
    ontology = types.ModuleType("ontology_model")
    ontology.get_entity_plane = lambda kind: "fixture-plane"
    ontology.check_axioms = lambda *args, **kwargs: {}
    ontology.build_cross_plane_mesh = lambda **kwargs: {}
    monkeypatch.setitem(sys.modules, "ontology_model", ontology)
    loader = importlib.machinery.SourceFileLoader("zhixing_mirrored_strategy", str(ASSETS / "strategy_projection.py.asset"))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    clock = "2026-01-01T00:00:00+00:00"
    snapshot = {"portfolio": {"state": "PARTIAL", "observed_at": clock,
                  "ledger_sha256": "c" * 64, "sha": "a" * 40, "source": "fixture", "bet_records": []},
                "source_states": {"portfolio": {"status": "PARTIAL", "last_success_at": "2026-01-02T00:00:00+00:00"}}}
    result = module.build_strategy(snapshot, {"documents": [], "records": {}, "source_states": []})
    source = next(s for s in result["source_states"] if s["id"] == "source:remote-portfolio")
    assert source["observed_at"] == clock and source["sha256"] == "c" * 64
    assert result["state"] == "PARTIAL"
