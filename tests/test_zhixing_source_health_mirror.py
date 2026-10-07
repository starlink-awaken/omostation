"""Exercise the mirrored host asset, including unhealthy and stale observations."""

from __future__ import annotations

import ast
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
