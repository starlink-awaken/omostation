"""The host mirrors exercise source behavior and keep the existing allowlist exact."""
import importlib.machinery
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT/"bin/panorama/assets/host"


def load(name, file):
    loader = importlib.machinery.SourceFileLoader(name, str(file))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec); loader.exec_module(module)
    return module


def test_host_sync_registers_brief_without_dropping_existing_fifteen():
    tool = load("gantt_brief_sync", ROOT/"bin/gac/zhixing-host-sync.py")
    assert len(tool.HOST_FILES) == 16
    assert dict(tool.HOST_FILES)["collectors/agent_brief.py"] == "agent_brief_collector.py.asset"
    assert {"strategy_projection.py", "refresh.py", "orchestrator.py", "live_server.py", "collectors/portfolio.py"} <= set(dict(tool.HOST_FILES))
    assert all((ASSETS/repo).is_file() for _, repo in tool.HOST_FILES)


def test_refresh_mirror_preserves_exact_track_unknown_dates_and_source_clock(monkeypatch):
    # Source-only loader avoids a production refresh, service launch or write.
    import sys
    from types import SimpleNamespace
    # The shared deployment helper has no Root mirror; stub only its redactor,
    # not either behavior under test, so CI remains independent of host files.
    monkeypatch.setitem(sys.modules, "probe_utils", SimpleNamespace(redact_secrets=lambda s: s))
    monkeypatch.syspath_prepend(str(ROOT/"bin/lib"))
    module = load("gantt_brief_refresh_asset", ASSETS/"refresh.py.asset")
    p = {"bet_records": [module.project_bet({"id": "B", "track": "T16-DRIFT-GUARD"})],
         "sha": "a"*40, "ledger_sha256": "b"*64, "observed_at": "source-clock", "state": "PARTIAL"}
    g = module.generate_dynamic_gantt(p)
    assert g["current_as_of"] == "source-clock" and g["ledger_sha256"] == p["ledger_sha256"]
    lane = g["first_100_days"]["lanes"][0]
    assert lane["lane_id"] == "T16-DRIFT-GUARD"
    assert lane["items"][0]["start"] is lane["items"][0]["end"] is None
