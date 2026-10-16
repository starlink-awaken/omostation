"""Exercise the mirrored host asset, including unhealthy and stale observations."""

from __future__ import annotations

import ast
import hashlib
import importlib.machinery
import importlib.util
import json
import re
import shutil
import subprocess
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
    monkeypatch.setitem(sys.modules, "refresh", module)
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
    "portfolio_collector.py.asset": "6d440d0b6a59dbb8c96cabb58783f0c39e40b8032b4c38bd9799929ca220385d",
    "refresh.py.asset": "27f4efdfecc14cd820c6b6a7a755e37af2cc0d54736c1c331e02c4ae157d5874",
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


def _task_orchestrator(monkeypatch, tmp_path, *, timestamp=None, tasks=None, failure=None):
    """Execute the mirror; fixture only external collectors and the verified store."""
    import json
    from datetime import datetime, timedelta, timezone
    package = types.ModuleType("collectors"); package.__path__ = []
    monkeypatch.setitem(sys.modules, "collectors", package)
    names = ["base", "registry", "portfolio", "workflow", "resident", "scheduler", "compute",
             "references", "orca", "multica", "ruflo", "reference_cell", "environment",
             "documents", "catalog", "strategy", "agent_brief", "personal_value"]
    for name in names:
        external = types.ModuleType("collectors." + name)
        monkeypatch.setitem(sys.modules, external.__name__, external)
        setattr(package, name, external)
    sys.modules["collectors.base"].DataCollector = object
    sys.modules["collectors.base"].CollectionError = Exception
    registry = sys.modules["collectors.registry"]
    registry.CollectorRegistry = object; registry.get_registry = lambda: object(); registry.COLLECTORS = []
    schema = types.ModuleType("models.schema"); schema.validate_data = lambda data: []
    monkeypatch.setitem(sys.modules, "models", types.ModuleType("models"))
    monkeypatch.setitem(sys.modules, "models.schema", schema)
    # Run the actual core policy function from its delivered AST; avoid importing
    # unrelated HTTP endpoints and filesystem identity globals into this unit test.
    core = types.ModuleType("live_server")
    core.json = json; core.datetime = datetime; core.timezone = timezone
    policy = next(node for node in ast.parse((ASSETS / "live_server.py.asset").read_text()).body
                  if isinstance(node, ast.FunctionDef) and node.name == "bound_payload_freshness")
    exec(compile(ast.Module(body=[policy], type_ignores=[]), "live_server.py.asset", "exec"), core.__dict__)
    monkeypatch.setitem(sys.modules, "live_server", core)
    current = datetime.now(timezone.utc)
    root = tmp_path / "state"
    task_dto = tasks if tasks is not None else {
        "source": ".omo/tasks/{active,planned,blocked,done}/*.yaml",
        "source_root": "/fixture-authority", "source_kind": "declared_state_root",
        "total": 50, "open_count": 1, "by_status": {"done": 49, "pending": 1},
        "by_bucket": {"done": 49, "active": 1}, "duplicates": [],
        "open_recent": [], "recent": [],
        "recent_done": [{"id": "WEEKLY", "status": "done", "bucket": "done", "goal_id": "OBJ-VALUE",
                         "artifacts": [{"preview": "literal <script> and __DATA__"}]}],
    }
    class Revision(types.SimpleNamespace):
        @property
        def data_path(self):
            raise AssertionError("retained bytes must not be reopened")
    revision = Revision(
        artifact_bodies={"data": json.dumps({"generated_at": timestamp or current.isoformat(),
                         "tasks": task_dto, "unrelated_producer_field": "DO NOT COPY"}).encode()},
        revision_id="a" * 64, producer_root_oid="b" * 40,
        generated_at=(current + timedelta(seconds=1)).isoformat(),
        fresh_until=(current + timedelta(minutes=10)).isoformat(),
    )
    calls = []
    runtime = types.ModuleType("runtime_paths")
    runtime.CODE_ROOT = tmp_path / "code"; runtime.STATE_ROOT = root
    runtime.legacy_doc_publication_enabled = lambda: False
    class Store:
        def __init__(self, state): assert state == root
        def load(self, *, require_fresh=True):
            calls.append(require_fresh)
            assert require_fresh is True
            if failure: raise failure
            return revision
    runtime.ProjectionRevisionStore = Store
    monkeypatch.setitem(sys.modules, "runtime_paths", runtime)
    refresh = _refresh(monkeypatch)
    for name in ("integrate_gantt", "integrate_strategy", "publish_strategy_artifacts"):
        monkeypatch.setattr(refresh, name, lambda *args, **kwargs: None)
    loader = importlib.machinery.SourceFileLoader("zhixing_task_orchestrator", str(ASSETS / "orchestrator.py.asset"))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec); loader.exec_module(module)
    return module, revision, task_dto, calls


def test_actual_host_merge_replaces_seed_tasks_with_exact_bound_subtree(monkeypatch, tmp_path):
    import copy
    import json
    module, revision, tasks, calls = _task_orchestrator(monkeypatch, tmp_path)
    previous = {"tasks": {"total": 15}, "custom_host_field": ["preserve"],
                "live_sources": {"tasks": {"legacy": True}}, "source_states": {}}
    before = copy.deepcopy(previous); raw = revision.artifact_bodies["data"]
    result = module.RefreshOrchestrator().merge_results(previous, [
        ("workflow", {"state": "OBSERVED", "observed_at": "workflow-clock", "run_count": 2}, None)])
    state = result["source_states"]["tasks"]
    assert result["tasks"] == tasks and result["tasks"]["total"] == 50
    assert result["custom_host_field"] == previous["custom_host_field"]
    assert result["workflow"]["run_count"] == 2
    assert "unrelated_producer_field" not in result
    assert "tasks" not in result["live_sources"]
    assert state["observed_at"] == json.loads(raw)["generated_at"]
    assert state["last_success_at"] == state["observed_at"]
    assert state["last_attempt_at"] == result["generated_at"]
    assert state["data_sha256"] == hashlib.sha256(raw).hexdigest()
    assert state["task_sha256"] == module._task_digest(tasks)
    assert state["status"] == "OK" and calls == [True]
    assert previous == before and revision.artifact_bodies["data"] == raw
    assert not tmp_path.exists() or not list(tmp_path.iterdir())


def test_fresh_lease_never_promotes_old_payload_clock(monkeypatch, tmp_path):
    import copy
    from datetime import datetime, timedelta, timezone
    old = (datetime.now(timezone.utc) - timedelta(seconds=301)).isoformat()
    module, revision, tasks, calls = _task_orchestrator(monkeypatch, tmp_path, timestamp=old)
    result = {}; module.merge_published_tasks(result, {}, "new-wrapper-clock")
    state = result["source_states"]["tasks"]
    assert result["tasks"] == tasks
    assert state["status"] == "STALE_PARTIAL"
    assert state["observed_at"] == old and state["last_attempt_at"] == "new-wrapper-clock"
    assert state["last_success_at"] is None
    assert state["payload_age_seconds"] > 300
    assert state["observed_at"] != revision.generated_at and calls == [True]
    assert module.RefreshOrchestrator._compute_result_state(result) == "PARTIAL"


def test_failed_reader_drops_unbound_seed_instead_of_promoting_it(monkeypatch, tmp_path):
    module, revision, tasks, calls = _task_orchestrator(monkeypatch, tmp_path, failure=RuntimeError("private diagnostic"))
    previous = {"tasks": {"total": 15}, "source_states": {"tasks": {
        "status": "OK", "observed_at": "legacy-wrapper", "last_success_at": "legacy-wrapper"}}}
    result = module.RefreshOrchestrator().merge_results(previous, [])
    assert "tasks" not in result
    state = result["source_states"]["tasks"]
    assert state["status"] == "UNAVAILABLE" and state["available"] is False
    assert state["observed_at"] is None and state["last_success_at"] is None
    assert state["error"] == "RuntimeError" and "private" not in str(state)
    assert previous["tasks"]["total"] == 15 and calls == [True]


def test_only_digest_bound_cache_can_survive_reader_failure(monkeypatch, tmp_path):
    import copy
    module, revision, tasks, calls = _task_orchestrator(monkeypatch, tmp_path)
    bound = {}; module.merge_published_tasks(bound, {}, "first-attempt")
    class FailedStore:
        def __init__(self, root): pass
        def load(self, *, require_fresh): raise RuntimeError("missing revision")
    monkeypatch.setattr(module, "ProjectionRevisionStore", FailedStore)
    retained = copy.deepcopy(bound); module.merge_published_tasks(retained, bound, "later-attempt")
    assert retained["tasks"] == tasks
    assert retained["source_states"]["tasks"]["status"] == "STALE_UNAVAILABLE"
    assert retained["source_states"]["tasks"]["observed_at"] == bound["source_states"]["tasks"]["observed_at"]
    assert retained["source_states"]["tasks"]["last_success_at"] == bound["source_states"]["tasks"]["last_success_at"]
    mutated = copy.deepcopy(bound); mutated["tasks"]["recent_done"][0]["goal_id"] = "OTHER-GOAL"
    result = copy.deepcopy(mutated); module.merge_published_tasks(result, mutated, "after-mutation")
    assert "tasks" not in result and result["source_states"]["tasks"]["status"] == "UNAVAILABLE"


@pytest.mark.parametrize("mutation", ["missing", "bad_count", "missing_recent", "unbound_root", "relative_root", "bad_rows", "missing_clock", "naive_clock", "future_clock"])
def test_malformed_publication_never_becomes_current_tasks(monkeypatch, tmp_path, mutation):
    import json
    from datetime import datetime, timedelta, timezone
    module, revision, tasks, calls = _task_orchestrator(monkeypatch, tmp_path)
    payload = json.loads(revision.artifact_bodies["data"])
    if mutation == "missing": payload.pop("tasks")
    elif mutation == "bad_count": payload["tasks"]["total"] = True
    elif mutation == "missing_recent": payload["tasks"].pop("recent_done")
    elif mutation == "unbound_root": payload["tasks"]["source_kind"] = "code_root"
    elif mutation == "relative_root": payload["tasks"]["source_root"] = "relative"
    elif mutation == "bad_rows": payload["tasks"]["recent_done"] = ["invalid"]
    elif mutation == "missing_clock": payload.pop("generated_at")
    elif mutation == "naive_clock": payload["generated_at"] = "2026-10-14T00:00:00"
    else: payload["generated_at"] = (datetime.now(timezone.utc) + timedelta(minutes=1)).isoformat()
    revision.artifact_bodies["data"] = json.dumps(payload).encode()
    result = {"tasks": {"total": 15}}; module.merge_published_tasks(result, result.copy(), "attempt")
    assert "tasks" not in result
    assert result["source_states"]["tasks"]["status"] == "UNAVAILABLE" and calls == [True]


def test_stale_bound_source_cannot_become_healthy_on_retry(monkeypatch, tmp_path):
    import copy
    from datetime import datetime, timedelta, timezone
    old = (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()
    module, revision, tasks, calls = _task_orchestrator(monkeypatch, tmp_path, timestamp=old)
    previous = {}; module.merge_published_tasks(previous, {}, "first-wrapper")
    result = copy.deepcopy(previous); module.merge_published_tasks(result, previous, "new-wrapper")
    assert result["source_states"]["tasks"]["status"] == "STALE_PARTIAL"
    assert result["source_states"]["tasks"]["observed_at"] == old
    assert result["source_states"]["tasks"]["last_success_at"] is None


@pytest.mark.parametrize("field,value", [
    ("revision_id", "invalid"), ("data_sha256", "invalid"),
    ("task_sha256", None), ("observed_at", None),
    ("observed_at", "2026-10-14T00:00:00"), ("observed_at", "9999-01-01T00:00:00Z"),
])
def test_invalid_previous_binding_metadata_is_never_retained(monkeypatch, tmp_path, field, value):
    import copy
    module, revision, tasks, calls = _task_orchestrator(monkeypatch, tmp_path)
    previous = {}; module.merge_published_tasks(previous, {}, "first-attempt")
    previous["source_states"]["tasks"][field] = value
    class FailedStore:
        def __init__(self, root): pass
        def load(self, *, require_fresh): raise RuntimeError("not available")
    monkeypatch.setattr(module, "ProjectionRevisionStore", FailedStore)
    result = copy.deepcopy(previous); module.merge_published_tasks(result, previous, "new-attempt")
    assert "tasks" not in result and result["source_states"]["tasks"]["status"] == "UNAVAILABLE"
    assert result["source_states"]["tasks"]["observed_at"] is None


@pytest.mark.parametrize("age,status", [(300, "OK"), (300.001, "STALE_PARTIAL")])
def test_task_source_uses_exact_core_freshness_boundary(monkeypatch, tmp_path, age, status):
    from datetime import datetime, timedelta, timezone
    clock = datetime.now(timezone.utc)
    module, revision, tasks, calls = _task_orchestrator(monkeypatch, tmp_path,
        timestamp=(clock - timedelta(seconds=age)).isoformat())
    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None): return clock
    monkeypatch.setattr(sys.modules["live_server"], "datetime", FixedDatetime)
    result = {}; module.merge_published_tasks(result, {}, "attempt")
    assert result["source_states"]["tasks"]["status"] == status
    assert result["source_states"]["tasks"]["payload_age_seconds"] == age


# Run the template's real renderer and polling branch, not a Python translation.
def _source_health_ui(snapshot, actions=()):
    template = (ASSETS / "template.html").read_text(encoding="utf-8")
    health = template.split("// Source health uses evidence clocks,", 1)[1].split(
        "// End source health snapshot rendering.", 1)[0]
    health = health[health.index("function sourceHealthSummary"):]
    poll = template.split("function checkForUpdates() {", 1)[1].split(
        "// Restore state after page load", 1)[0]
    node = shutil.which("node")
    assert node, "Node.js is required to execute the shipped UI logic"
    scripts = [body for attrs, body in re.findall(r"<script([^>]*)>(.*?)</script>", template, re.S)
               if 'application/json' not in attrs]
    program = r"""
const vm = require('node:vm');
const input = JSON.parse(process.argv[1]);
for (const script of input.scripts) new vm.Script(script);
const nodes = {};
const node = id => nodes[id] ||= {textContent:'', innerHTML:'', style:{}};
const context = {
  D:input.snapshot, healthUpdateError:false, _lastObservedAt:input.snapshot.observed_at,
  Date:{now:()=>Date.parse('2026-10-14T12:00:00Z'),parse:Date.parse},
  $:node, dt:value=>value || '未观测',
  esc:value=>String(value).replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),
  document:{hidden:false,querySelector:()=>null,getElementById:node},
  setTimeout:()=>{}, console:{warn:()=>{}}, _gracefulReload:()=>{}, populateHealth:()=>{}
};
vm.createContext(context);
vm.runInContext(input.health + '\nfunction checkForUpdates() {' + input.poll, context);
const capture = () => JSON.parse(JSON.stringify(nodes));
(async()=>{
  context.refreshHealth(); const results=[capture()];
  for (const action of input.actions) {
    if (action.kind==='render') {context.D=action.snapshot; context.refreshHealth();}
    else {
      context.fetch=()=>Promise.resolve({ok:action.kind!=='poll_error',json:()=>Promise.resolve(action.snapshot)});
      context.checkForUpdates(); await new Promise(resolve=>setImmediate(resolve));
    }
    results.push(capture());
  }
  process.stdout.write(JSON.stringify(results));
})().catch(error=>{console.error(error);process.exit(1)});
"""
    result = subprocess.run([node, "-e", program, json.dumps({"snapshot": snapshot,
        "actions": list(actions), "health": health, "poll": poll, "scripts": scripts})],
        text=True, capture_output=True, check=True)
    return json.loads(result.stdout)


def _healthy_ui_snapshot():
    return {"generated_at": "2026-10-14T11:59:00Z", "observed_at": "same-revision",
            "source_states": {"tasks": {"status": "OK", "observed_at": "2026-10-14T11:58:00Z",
                "last_attempt_at": "2026-10-14T11:59:00Z", "last_success_at": "2026-10-14T11:57:00Z"}}}


def test_source_ui_counts_actual_twenty_sources_without_global_health_claims():
    snapshot = _healthy_ui_snapshot()
    snapshot["source_states"] = {f"source-{i}": {"status": "OK" if i < 15 else "PARTIAL",
        "observed_at": "2026-10-14T11:59:00Z"} for i in range(20)}
    nodes = _source_health_ui(snapshot)[0]
    assert "15/20 项观测正常 · 5 项降级" in nodes["health-status-headline"]["textContent"]
    assert nodes["health-pulse-dot"]["style"]["background"] == "#f59e0b"
    assert nodes["health-diagnostic-content"]["innerHTML"].count('class="chip good"') == 15
    text = json.dumps(nodes, ensure_ascii=False)
    for unsupported in ["8/11", "100%", "全域绿灯", "已隔离", "实时在线"]:
        assert unsupported not in text


@pytest.mark.parametrize("clock", [None, "not-a-clock", "2026-10-14T11:00:00Z", "2026-10-14T12:01:00Z"])
def test_source_ui_old_missing_invalid_or_future_snapshot_cannot_turn_green(clock):
    snapshot = _healthy_ui_snapshot(); snapshot["generated_at"] = clock; snapshot.pop("observed_at")
    nodes = _source_health_ui(snapshot)[0]
    assert nodes["health-pulse-dot"]["style"]["background"] != "#10b981"
    assert "时间有效" not in nodes["health-status-headline"]["textContent"]


@pytest.mark.parametrize("sources", [None, {}, [], "OK", {"tasks": None}, {"tasks": {}}])
def test_source_ui_absent_or_malformed_sources_are_unknown(sources):
    snapshot = _healthy_ui_snapshot(); snapshot["source_states"] = sources
    nodes = _source_health_ui(snapshot)[0]
    assert nodes["health-pulse-dot"]["style"]["background"] != "#10b981"
    assert "未确认" in json.dumps(nodes, ensure_ascii=False) or "UNKNOWN" in json.dumps(nodes)


@pytest.mark.parametrize("clock", [None, "bad", "2026-10-14T11:00:00Z", "2026-10-14T12:01:00Z"])
def test_fresh_wrapper_does_not_hide_old_or_unknown_source_observation(clock):
    snapshot = _healthy_ui_snapshot(); snapshot["source_states"]["tasks"]["observed_at"] = clock
    nodes = _source_health_ui(snapshot)[0]
    assert "0/1 项观测正常" in nodes["health-status-headline"]["textContent"]
    assert nodes["health-pulse-dot"]["style"]["background"] != "#10b981"


def test_same_revision_poll_recomputes_degradation_and_recovery_and_all_clocks():
    import copy
    initial = _healthy_ui_snapshot(); failed = copy.deepcopy(initial)
    failed["source_states"]["tasks"].update(status="FAIL", observed_at="2026-10-14T11:59:30Z",
        last_attempt_at="2026-10-14T11:59:40Z")
    healthy, degraded, recovered = _source_health_ui(initial, [
        {"kind": "poll", "snapshot": failed}, {"kind": "poll", "snapshot": initial}])
    assert healthy["health-pulse-dot"]["style"]["background"] == "#10b981"
    assert "1 项降级" in degraded["health-status-headline"]["textContent"]
    assert "1 项降级" in degraded["metrics-freshness"]["textContent"]
    drawer = degraded["health-diagnostic-content"]["innerHTML"]
    assert "来源观测: 2026-10-14T11:59:30Z" in drawer
    assert "最近尝试: 2026-10-14T11:59:40Z" in drawer
    assert "最后成功: 2026-10-14T11:57:00Z" in drawer
    assert recovered["health-status-headline"]["textContent"] == healthy["health-status-headline"]["textContent"]
    assert recovered["metrics-freshness"]["textContent"] == healthy["metrics-freshness"]["textContent"]
    assert recovered["health-pulse-dot"]["style"]["background"] == "#10b981"


def test_same_snapshot_direct_source_change_is_recomputed_each_render():
    import copy
    initial = _healthy_ui_snapshot(); changed = copy.deepcopy(initial)
    changed["source_states"]["tasks"]["status"] = "STALE_UNAVAILABLE"
    nodes = _source_health_ui(initial, [{"kind": "render", "snapshot": changed}])[-1]
    assert "1 项降级" in nodes["health-status-headline"]["textContent"]


def test_latest_snapshot_read_failure_clears_green_then_recovers():
    initial = _healthy_ui_snapshot()
    _, failed, recovered = _source_health_ui(initial, [
        {"kind": "poll_error"}, {"kind": "poll", "snapshot": initial}])
    assert "最新快照读取失败" in failed["health-status-headline"]["textContent"]
    assert failed["health-pulse-dot"]["style"]["background"] != "#10b981"
    assert "最新快照读取失败" not in recovered["health-status-headline"]["textContent"]
    assert recovered["health-pulse-dot"]["style"]["background"] == "#10b981"


def test_source_status_and_name_are_text_and_html_escaped():
    snapshot = _healthy_ui_snapshot(); attack = '<img src=x onerror="alert(1)">'
    snapshot["source_states"] = {attack: {"status": attack, "last_success_at": attack}}
    nodes = _source_health_ui(snapshot)[0]; drawer = nodes["health-diagnostic-content"]["innerHTML"]
    assert attack not in drawer and "&lt;img" in drawer
    assert "1 项降级" in nodes["health-status-headline"]["textContent"]


@pytest.mark.parametrize("clock,green", [("2026-10-14T11:50:00Z", True),
                                       ("2026-10-14T11:49:59Z", False)])
def test_source_ui_respects_existing_ten_minute_window(clock, green):
    snapshot = _healthy_ui_snapshot(); snapshot["generated_at"] = clock
    snapshot["source_states"]["tasks"]["observed_at"] = clock
    nodes = _source_health_ui(snapshot)[0]
    assert (nodes["health-pulse-dot"]["style"]["background"] == "#10b981") is green
