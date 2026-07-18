"""M1 closeout report — honest T+72 rejudge (ADR-0210 + ADR-0220)."""
from __future__ import annotations

import importlib.util
import json
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    path = ROOT / "bin/gac/m1-closeout-report.py"
    spec = importlib.util.spec_from_file_location("m1_closeout_report", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _seed_minimal_green(tmp_path: Path, *, with_window: bool = True) -> None:
    """Scaffold a root that passes structural hard greens (except live ratio if missing)."""
    (tmp_path / "bin/gac").mkdir(parents=True)
    (tmp_path / "bin/ssot").mkdir(parents=True)
    (tmp_path / "bin/adr").mkdir(parents=True)
    (tmp_path / ".githooks").mkdir(parents=True)
    (tmp_path / ".omo/_truth/registry").mkdir(parents=True)
    (tmp_path / ".omo/state").mkdir(parents=True)
    (tmp_path / ".omo/_delivery/swarm-conflicts").mkdir(parents=True)

    # Copy real swarm_discipline so window helpers work
    import shutil

    shutil.copy(ROOT / "bin/gac/swarm_discipline.py", tmp_path / "bin/gac/swarm_discipline.py")
    shutil.copy(
        ROOT / "bin/gac/swarm-discipline-cli.py",
        tmp_path / "bin/gac/swarm-discipline-cli.py",
    )

    (tmp_path / ".githooks/pre-push").write_text(
        "#!/bin/bash\n# protect main from direct push\nbranch=$(git rev-parse --abbrev-ref HEAD)\n",
        encoding="utf-8",
    )
    (tmp_path / ".githooks/pre-commit").write_text("#!/bin/bash\ntrue\n", encoding="utf-8")
    (tmp_path / "bin/gac/gac-worktree.sh").write_text("#!/bin/bash\n", encoding="utf-8")
    (tmp_path / "bin/gac/gac-branch-protection.sh").write_text("#!/bin/bash\n", encoding="utf-8")
    (tmp_path / "bin/gac/knowledge-foundry-cron.py").write_text(
        textwrap.dedent(
            """
            # 5:45-gitlink-check
            # submodule-gitlink-check.py
            # 5:50-swarm-window window-status
            """
        ),
        encoding="utf-8",
    )
    (tmp_path / "bin/gac/kos-seed-import.py").write_text("# kos seed\n", encoding="utf-8")
    (tmp_path / "bin/ssot/write-owner-repair-draft.py").write_text("# repair\n", encoding="utf-8")
    (tmp_path / ".omo/_truth/registry/write-owners.yaml").write_text(
        "version: 1\nowners: {}\n", encoding="utf-8"
    )
    (tmp_path / ".pre-commit-config.yaml").write_text(
        "repos: []\n# write-owner-audit\n", encoding="utf-8"
    )
    (tmp_path / ".omo/_truth/registry/swarm-coordination.yaml").write_text(
        textwrap.dedent(
            """
            version: 1
            observation:
              window_hours: 72
            gates:
              d1_adr_atomic_claim: {id: d1}
              d2_branch_occupancy: {id: d2}
              d3_shared_worktree_claim: {id: d3}
              d4_escape_hatch: {id: d4}
            delivery: {}
            """
        ),
        encoding="utf-8",
    )
    (tmp_path / ".omo/state/system.yaml").write_text(
        textwrap.dedent(
            """
            health_score: 70
            health_score_source: compass_radar_composite_isc3
            service_online_ratio: 1.0
            runtime_health_summary:
              online_services: 4
              total_services: 4
              ratio: 1.0
            """
        ),
        encoding="utf-8",
    )
    (tmp_path / ".omo/state/health.yaml").write_text(
        textwrap.dedent(
            """
            # health_score: composite (ISC-3) = {'governance': 0.3, 'freshness': 0.2, 'runtime': 0.5}
            health_score: 70
            service_online_ratio: 1.0
            """
        ),
        encoding="utf-8",
    )

    if with_window:
        m = importlib.util.spec_from_file_location(
            "sd", tmp_path / "bin/gac/swarm_discipline.py"
        )
        mod = importlib.util.module_from_spec(m)  # type: ignore[arg-type]
        assert m and m.loader
        m.loader.exec_module(mod)
        mod.start_conflict_window(tmp_path)


def test_window_open_never_phase2(tmp_path: Path):
    _seed_minimal_green(tmp_path, with_window=True)
    mod = _load()
    report = mod.build_report(tmp_path, scan_orphans=False)
    assert report["m1_verdict"] == "window_open"
    assert report["phase2_recommend"] is False
    assert report["window"]["conflict_count"] == 0
    assert report["hard_fails"] == []
    ids = {c["id"] for c in report["checks"]}
    assert ids == {
        "g-conv.1",
        "g-conv.2",
        "g-conv.3",
        "g-conv.4",
        "g-conv.5",
        "g-conv.6",
        "g-conv.7",
    }


def test_window_not_started(tmp_path: Path):
    _seed_minimal_green(tmp_path, with_window=False)
    mod = _load()
    report = mod.build_report(tmp_path, scan_orphans=False)
    assert report["m1_verdict"] == "window_not_started"
    assert report["phase2_recommend"] is False
    # g-conv.7 ok=False because window not started
    g7 = next(c for c in report["checks"] if c["id"] == "g-conv.7")
    assert g7["ok"] is False


def test_pass_only_after_72h_and_zero_conflicts(tmp_path: Path):
    _seed_minimal_green(tmp_path, with_window=True)
    mod = _load()
    # backdate window start by 73h
    from datetime import datetime, timedelta, timezone

    start = datetime.now(timezone.utc) - timedelta(hours=73)
    win = {
        "window_start": start.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "window_hours": 72,
        "window_end_target": (start + timedelta(hours=72))
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "gate": "g-conv.7",
        "adr": "0220",
    }
    (tmp_path / ".omo/_delivery/swarm-conflicts/window.json").write_text(
        json.dumps(win, indent=2) + "\n", encoding="utf-8"
    )
    # empty events
    (tmp_path / ".omo/_delivery/swarm-conflicts/events.jsonl").write_text("", encoding="utf-8")

    report = mod.build_report(tmp_path, scan_orphans=False)
    assert report["m1_verdict"] == "pass"
    assert report["phase2_recommend"] is True
    assert report["window"]["elapsed_hours"] >= 72


def test_fail_when_conflicts_after_window(tmp_path: Path):
    _seed_minimal_green(tmp_path, with_window=True)
    mod = _load()
    from datetime import datetime, timedelta, timezone

    start = datetime.now(timezone.utc) - timedelta(hours=73)
    win = {
        "window_start": start.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "window_hours": 72,
    }
    (tmp_path / ".omo/_delivery/swarm-conflicts/window.json").write_text(
        json.dumps(win) + "\n", encoding="utf-8"
    )
    # inject conflict via swarm helper
    import importlib.util as iu

    spec = iu.spec_from_file_location("sd", tmp_path / "bin/gac/swarm_discipline.py")
    sd = iu.module_from_spec(spec)  # type: ignore[arg-type]
    assert spec and spec.loader
    spec.loader.exec_module(sd)
    sd.emit_conflict_event(tmp_path, "branch_hijack", {"branch": "work/x"})

    report = mod.build_report(tmp_path, scan_orphans=False)
    assert report["m1_verdict"] == "fail"
    assert report["phase2_recommend"] is False
    assert report["window"]["conflict_count"] >= 1


def test_hard_fail_ratio_blocks_pass(tmp_path: Path):
    _seed_minimal_green(tmp_path, with_window=True)
    from datetime import datetime, timedelta, timezone

    start = datetime.now(timezone.utc) - timedelta(hours=73)
    (tmp_path / ".omo/_delivery/swarm-conflicts/window.json").write_text(
        json.dumps(
            {
                "window_start": start.replace(microsecond=0)
                .isoformat()
                .replace("+00:00", "Z"),
                "window_hours": 72,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / ".omo/state/system.yaml").write_text(
        "health_score: 70\nhealth_score_source: compass_radar_composite_isc3\n"
        "service_online_ratio: 0.5\n",
        encoding="utf-8",
    )
    mod = _load()
    report = mod.build_report(tmp_path, scan_orphans=False)
    assert report["m1_verdict"] == "fail"
    assert "g-conv.2" in report["hard_fails"]
    assert report["phase2_recommend"] is False


def test_cli_json_on_real_workspace_root_shape():
    """Smoke: CLI against repo root returns schema (verdict may be window_not_started in CI)."""
    import subprocess

    r = subprocess.run(
        [
            "python3",
            str(ROOT / "bin/gac/m1-closeout-report.py"),
            "--root",
            str(ROOT),
            "--json",
            "--no-orphan-scan",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["schema"] == "m1-closeout-report/v1"
    assert data["m1_verdict"] in {
        "window_open",
        "window_not_started",
        "pass",
        "fail",
    }
    assert "phase2_recommend" in data
    assert len(data["checks"]) == 7
    assert "ssot_root" in data


def test_ssot_root_splits_live_window_from_code(tmp_path: Path):
    """Live SSOT window + green runtime; code tree carries structural greens."""
    code = tmp_path / "code"
    live = tmp_path / "live"
    code.mkdir()
    live.mkdir()
    _seed_minimal_green(code, with_window=False)
    # live has window + ratio only
    (live / ".omo/state").mkdir(parents=True)
    (live / ".omo/_delivery/swarm-conflicts").mkdir(parents=True)
    (live / ".omo/state/system.yaml").write_text(
        "health_score: 70\nhealth_score_source: compass_radar_composite_isc3\n"
        "service_online_ratio: 1.0\n",
        encoding="utf-8",
    )
    (live / ".omo/state/health.yaml").write_text(
        "# ISC-3 0.3 0.5 0.2\nhealth_score: 70\nservice_online_ratio: 1.0\n",
        encoding="utf-8",
    )
    # start window on live via copied helper from code
    import importlib.util as iu

    spec = iu.spec_from_file_location("sd", code / "bin/gac/swarm_discipline.py")
    sd = iu.module_from_spec(spec)  # type: ignore[arg-type]
    assert spec and spec.loader
    spec.loader.exec_module(sd)
    # registry needed under live for delivery_path defaults
    (live / ".omo/_truth/registry").mkdir(parents=True)
    (live / ".omo/_truth/registry/swarm-coordination.yaml").write_text(
        "version: 1\nobservation:\n  window_hours: 72\n", encoding="utf-8"
    )
    sd.start_conflict_window(live)

    mod = _load()
    report = mod.build_report(code, ssot_root=live, scan_orphans=False)
    assert report["m1_verdict"] == "window_open"
    assert report["ssot_root"] == str(live.resolve())
    assert report["window"]["window_start"] is not None
    assert report["hard_fails"] == []
