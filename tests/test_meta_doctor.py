"""meta-doctor 单测 — M1 心跳新鲜度 + M2 引用活性 (v1.1 状态分类)."""
import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

MD = Path(__file__).resolve().parents[3] / "bin" / "gac" / "meta-doctor.py"
REAL_WS = Path("/Users/xiamingxing/Workspace")


def _load():
    spec = importlib.util.spec_from_file_location("meta_doctor", MD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_tokenize_and_candidates_filter_noise():
    mod = _load()
    line = ('0 2 * * * cd "$HOME/Workspace" && python3 -m omo.cli x '
            '&& python3 scripts/opc_x.py >> runtime/logs/a.log 2>&1')
    cands = mod.candidates_from(mod.tokenize(line))
    assert "scripts/opc_x.py" in cands
    assert all(not c.endswith(".log") for c in cands)


def test_interpreter_tokens_not_candidates():
    mod = _load()
    line = '/usr/bin/python3 "$HOME/Documents/@公共/_runtime/task.py"'
    cands = mod.candidates_from(mod.tokenize(line))
    assert "/usr/bin/python3" not in cands


def test_resolve_candidate_modes(tmp_path):
    mod = _load()
    assert mod.resolve_candidate("bin/tool.py", tmp_path) == tmp_path / "bin/tool.py"
    assert str(mod.resolve_candidate("$HOME/x/y.sh", tmp_path)).startswith(str(Path.home()))
    assert str(mod.resolve_candidate("/usr/bin/python3", tmp_path)) == "/usr/bin/python3"


def test_heartbeat_fresh_vs_stale(tmp_path):
    mod = _load()
    now = datetime.now(timezone.utc)

    fresh = tmp_path / ".omo/state/system_health.yaml"
    fresh.parent.mkdir(parents=True)
    fresh.write_text(f"last_scan: {(now - timedelta(hours=1)).timestamp()}\n")

    stale = tmp_path / ".omo/_control/debt-dashboard/current.yaml"
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_text(f'generated_at: "{(now - timedelta(days=30)).isoformat()}"\n')

    res = mod.check_heartbeats(tmp_path, now=now)
    sys_e = next(r for r in res if r["file"].endswith("system_health.yaml"))
    dash_e = next(r for r in res if "debt-dashboard" in r["file"])
    assert sys_e["ok"] is True
    assert dash_e["ok"] is False and dash_e["age_hours"] > 24 * 14


def test_scan_status_classification(tmp_path):
    mod = _load()
    live_target = REAL_WS / "scenarios/Y1Q4-B1/test_e2e.py"

    anchored_dead = '0 2 * * * cd "$HOME/Workspace" && python3 scripts/dead_job.py'
    anchored_live = f'25 9 * * * cd "$HOME/Workspace" && python3 {live_target} --json'
    unanchored = '0 6 * * * cd "$HOME/Documents" && python3 _runtime/task.py'
    prefixed_sh = '/bin/bash /usr/local/libexec/maintenance.sh'

    found = mod.scan_crontab_lines(
        [anchored_dead, anchored_live, unanchored, prefixed_sh],
        "t", REAL_WS,
    )
    by = {r["target"]: r for r in found}
    assert by["scripts/dead_job.py"]["status"] == "dead"
    assert by["scripts/dead_job.py"]["ok"] is False
    assert by[str(live_target)]["status"] == "ok" and by[str(live_target)]["ok"] is True
    assert by["_runtime/task.py"]["status"] == "skip_unanchored"
    assert by["/usr/local/libexec/maintenance.sh"]["status"] == "skip_system"
