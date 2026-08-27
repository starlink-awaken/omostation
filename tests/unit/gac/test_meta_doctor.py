"""meta-doctor 单测 — M1 心跳新鲜度 + M2 引用活性 (v1.1 状态分类)."""
import importlib.util
import json
import re
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
    now = datetime.now(timezone.utc)  # noqa: UP017 - match macOS Python 3.9 runtime

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


def test_dead_refs_emit_broker_proposals_without_direct_debt_write(
    tmp_path, monkeypatch, capsys
):
    mod = _load()
    dead_ref = {
        "source": ".omo/cron/operating-rhythm-crontab",
        "line": 17,
        "target": "bin/gac/missing-wrapper.sh",
        "resolved": str(tmp_path / "bin/gac/missing-wrapper.sh"),
        "exists": False,
        "ok": False,
        "status": "dead",
    }
    monkeypatch.setattr(mod, "collect_references", lambda _root: [dead_ref])

    result = mod.main(["--workspace", str(tmp_path), "--refs-only"])

    assert result == 1
    report = json.loads(capsys.readouterr().out)
    proposal = report["debt_proposals"][0]
    assert proposal["schema"] == "meta-doctor-debt-proposal/v1"
    assert re.fullmatch(r"MDEAD-[0-9a-f]{20}", proposal["id"])
    assert proposal["title"] == "引用断链: missing-wrapper.sh"
    assert proposal["lifecycle_state"] == "proposed"
    assert re.fullmatch(
        r"meta-doctor-source://sha256/[0-9a-f]{64}#L17",
        proposal["source_ref"],
    )
    assert re.fullmatch(
        r"meta-doctor-target://sha256/[0-9a-f]{64}", proposal["target_ref"]
    )
    assert "operating-rhythm-crontab" not in json.dumps(proposal)
    assert "bin/gac" not in json.dumps(proposal)
    assert not (tmp_path / ".omo" / "debt").exists()


def test_debt_proposal_identity_is_stable_unique_and_control_character_safe():
    mod = _load()
    common = {
        "line": 17,
        "target": "/Users/alice/private/secret\nkey.py",
        "status": "dead",
    }
    first = mod.build_debt_proposals([{**common, "source": "cron-a"}])[0]
    replay = mod.build_debt_proposals([{**common, "source": "cron-a"}])[0]
    second = mod.build_debt_proposals([{**common, "source": "cron-b"}])[0]

    assert first == replay
    assert first["id"] != second["id"]
    assert re.fullmatch(r"MDEAD-[0-9a-f]{20}", first["id"])
    serialized = json.dumps(first, ensure_ascii=False)
    assert "/Users/alice" not in serialized
    assert "private" not in serialized
    assert "\n" not in first["id"]
    assert "\n" not in first["title"]
    assert len(first["title"]) <= 70


def test_omo_workspace_root_cron_anchor_is_checked(tmp_path, monkeypatch):
    mod = _load()
    monkeypatch.setattr(mod, "SYSTEM_PREFIXES", ("/usr/", "/bin/", "/opt/"))
    target = tmp_path / "bin/gac/tool.py"
    target.parent.mkdir(parents=True)
    target.write_text("", encoding="utf-8")

    refs = mod.scan_crontab_lines(
        [
            '0 9 * * * test -n "$OMO_WORKSPACE_ROOT" && '
            'cd "$OMO_WORKSPACE_ROOT" && python3 bin/gac/tool.py'
        ],
        "cron-template",
        tmp_path,
    )

    assert refs == [
        {
            "source": "cron-template",
            "line": 1,
            "target": "bin/gac/tool.py",
            "resolved": str(target),
            "exists": True,
            "ok": True,
            "status": "ok",
        }
    ]
