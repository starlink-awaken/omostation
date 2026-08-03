# mock-heavy test: monkeypatch + dynamic attribute setup; pyright cannot follow.
# pyright: reportAttributeAccessIssue=false

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ROOT = Path(__file__).resolve().parents[3]


def test_p5_radar_history_tracks_manual_and_cron_runs(tmp_path):
    module = _load_module(
        "opc_p5_radar_cron_test", ROOT / "scripts" / "opc_p5_radar_cron.py"
    )
    module.ROOT = tmp_path  # type: ignore[reportAttributeAccessIssue]
    payload = {
        "generated_at": "2026-06-12T00:00:00Z",
        "trigger_source": "manual",
        "candidates_count": 3,
        "archive_path": "/tmp/archive-1.json",
        "db_path": "/tmp/data.db",
        "candidates": [
            {
                "source": "cockpit:research",
                "timestamp": "2026-06-12T00:00:00Z",
                "next_action": "x",
                "evidence_id": 1,
            },
            {
                "source": "cockpit:research",
                "timestamp": "2026-06-12T00:00:01Z",
                "next_action": "y",
                "evidence_id": 2,
            },
            {
                "source": "cockpit:research (DB unavailable)",
                "timestamp": "2026-06-12T00:00:02Z",
                "next_action": "z",
                "evidence_id": None,
            },
        ],
    }
    history1 = module._update_history(payload)
    payload["generated_at"] = "2026-06-13T00:00:00Z"
    payload["trigger_source"] = "cron"
    payload["archive_path"] = "/tmp/archive-2.json"
    history2 = module._update_history(payload)

    assert history1["summary"]["run_count"] == 1
    assert history2["summary"]["run_count"] == 2
    assert history2["summary"]["manual_run_count"] == 1
    assert history2["summary"]["cron_run_count"] == 1
    snapshot = module._write_daily_snapshot(payload, history2)
    assert snapshot.exists()


def test_p6_weekly_loop_history_tracks_consecutive_weeks(tmp_path):
    module = _load_module(
        "opc_p6_weekly_loop_test", ROOT / "scripts" / "opc_p6_weekly_loop.py"
    )
    module.ROOT = tmp_path  # type: ignore[reportAttributeAccessIssue]
    module._call_radar = lambda: {  # type: ignore[reportAttributeAccessIssue]
        "scenario": "technical-radar",
        "candidates": [
            {
                "title": "Platform candidate",
                "source": "cockpit:research",
                "timestamp": "2026-06-12T00:00:00Z",
                "next_action": "follow up",
                "evidence_id": 1,
            }
        ],
    }
    module._call_drift = lambda: {"kinds": 4, "drift_count": 0, "results": []}  # type: ignore[reportAttributeAccessIssue]

    payload1 = module.run_one_week("2026-W23")
    payload2 = module.run_one_week("2026-W24")
    module.write_evidence("2026-W23", payload1)
    module.write_evidence("2026-W24", payload2)

    history_path = (
        tmp_path
        / "runtime"
        / "omo"
        / "_control"
        / "evolution"
        / "loop"
        / "history.json"
    )
    history = json.loads(history_path.read_text(encoding="utf-8"))
    trace_index = json.loads(
        (
            tmp_path
            / "runtime"
            / "omo"
            / "_control"
            / "evolution"
            / "loop"
            / "trace-index.json"
        ).read_text(encoding="utf-8")
    )
    assert history["summary"]["weeks_recorded"] == 2
    assert history["summary"]["max_consecutive_weeks"] == 2
    assert payload2["history"]["summary"]["latest_week"] == "2026-W24"
    assert payload1["task"]["planned"][0]["approval_required"] is True
    assert trace_index["summary"]["week_count"] == 2


def test_p6_weekly_loop_runtime_executes_pipeline(tmp_path):
    from omo.omo_weekly_loop import (  # type: ignore[reportMissingImports]
        run_weekly_loop,
        write_weekly_evidence,
    )

    payload = run_weekly_loop(
        tmp_path,
        week="2026-W25",
        now_iso="2026-06-20T00:00:00Z",
        radar_fn=lambda: {
            "scenario": "technical-radar",
            "candidates": [
                {
                    "title": "Runtime candidate",
                    "source": "cockpit:research",
                    "timestamp": "2026-06-20T00:00:00Z",
                    "next_action": "follow up",
                    "evidence_id": 1,
                }
            ],
        },
        drift_fn=lambda: {"kinds": 4, "drift_count": 0, "results": []},
    )
    md_path, json_path = write_weekly_evidence(tmp_path, "2026-W25", payload)
    assert payload["history"]["summary"]["latest_week"] == "2026-W25"
    assert payload["task"]["planned"][0]["id"] == "OPC-P6-LOOP-2026-W25-00"
    assert md_path.exists()
    assert json_path.exists()


def test_p6_self_evolve_nop_carries_loop_history_ref(tmp_path):
    module = _load_module(
        "opc_p6_self_evolve_test", ROOT / "scripts" / "opc_p6_self_evolve.py"
    )
    module.ROOT = tmp_path  # type: ignore[reportAttributeAccessIssue]
    drift_dir = tmp_path / "runtime" / "omo" / "_control" / "evolution" / "drift"
    drift_dir.mkdir(parents=True, exist_ok=True)
    (drift_dir / "2026-06-12.json").write_text(
        json.dumps({"kinds": 4, "drift_count": 0, "results": []}),
        encoding="utf-8",
    )
    loop_dir = tmp_path / "runtime" / "omo" / "_control" / "evolution" / "loop"
    loop_dir.mkdir(parents=True, exist_ok=True)
    (loop_dir / "history.json").write_text(
        json.dumps({"runs": [], "summary": {"latest_week": "2026-W24"}}),
        encoding="utf-8",
    )

    tasks = module.emit_self_evolution_tasks()
    assert len(tasks) == 1
    assert tasks[0]["approval_required"] is True
    assert tasks[0]["human_approval_required"] is True
    assert tasks[0]["approval_state"] == "awaiting_human"
    assert (
        tasks[0]["loop_history_ref"]
        == "runtime/omo/_control/evolution/loop/history.json"
    )


def test_p6_approval_board_writes_current_board(tmp_path):
    module = _load_module(
        "opc_p6_approval_board_test", ROOT / "scripts" / "opc_p6_approval_board.py"
    )
    module.ROOT = tmp_path  # type: ignore[reportAttributeAccessIssue]
    planned_dir = tmp_path / ".omo" / "tasks" / "planned"
    planned_dir.mkdir(parents=True, exist_ok=True)
    (planned_dir / "OPC-P6-SELF-EVOLUTION-sample.yaml").write_text(
        "\n".join(
            [
                "id: OPC-P6-SELF-EVOLUTION-sample",
                "title: 'Sample'",
                "status: candidate",
                "approval_required: true",
                "human_approval_required: true",
                "approval_state: 'awaiting_human'",
                "latest_week: '2026-W24'",
            ]
        ),
        encoding="utf-8",
    )
    board = module.build_board()
    json_path, md_path = module.write_board(board)
    assert board["summary"]["task_count"] == 1
    assert board["summary"]["awaiting_human_count"] == 1
    assert json_path.exists()
    assert md_path.exists()


def test_p7_release_cycle_uses_incrementing_index(tmp_path):
    module = _load_module(
        "opc_p7_release_cycle_test", ROOT / "scripts" / "opc_p7_release_cycle.py"
    )
    module.ROOT = tmp_path  # type: ignore[reportAttributeAccessIssue]
    module._today = lambda: "2026-06-12"  # type: ignore[reportAttributeAccessIssue]
    module._gather_changes = lambda: {  # type: ignore[reportAttributeAccessIssue]
        "cutoff": "2026-06-10T00:00:00Z",
        "commit_count": 2,
        "commits": ["a1 first", "b2 second"],
        "previous_release_version": None,
    }
    module._gather_validation = lambda: {  # type: ignore[reportAttributeAccessIssue]
        "omo_tests": {"returncode": 0, "summary": "ok"},
        "drift": {"kinds": 4, "drift_count": 0},
    }
    module._gather_debt = lambda: {"total": 3, "open": 1, "resolved": 2}  # type: ignore[reportAttributeAccessIssue]

    cycle1 = module.run_one_cycle()
    cycle2 = module.run_one_cycle()

    assert cycle1["version"] == "v2026-06-12-r1"
    assert cycle2["version"] == "v2026-06-12-r2"
    index = json.loads(
        (
            tmp_path / "runtime" / "omo" / "_delivery" / "release" / "index.json"
        ).read_text(encoding="utf-8")
    )
    assert index["summary"]["release_count"] == 2
    assert index["summary"]["latest_version"] == "v2026-06-12-r2"
    assert index["summary"]["manual_run_count"] == 2
    assert index["summary"]["cron_run_count"] == 0


def test_p7_audit_rollout_history_index_tracks_mode_and_trigger(tmp_path):
    module = _load_module(
        "opc_p7_audit_rollout_daemon_test",
        ROOT / "scripts" / "opc_p7_audit_rollout_daemon.py",
    )
    module.ROOT = tmp_path  # type: ignore[reportAttributeAccessIssue]
    module._today = lambda: "2026-06-12"  # type: ignore[reportAttributeAccessIssue]
    module._now_iso = lambda: "2026-06-12T00:00:00Z"  # type: ignore[reportAttributeAccessIssue]
    module._trigger_source = lambda: "cron"  # type: ignore[reportAttributeAccessIssue]
    history_path = (
        tmp_path
        / "runtime"
        / "omo"
        / "_control"
        / "evolution"
        / "drift-history"
        / "2026-06-12.json"
    )
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text("{}", encoding="utf-8")
    rollout = {
        "returncode": 0,
        "output_path": "runtime/omo/_delivery/audit-rollout/2026-06-12-weekly.json",
        "payload": {"repos": {"workspace": {}, "omo": {}}},
    }
    index = module._update_history_index("weekly", rollout, history_path)
    assert index["summary"]["run_count"] == 1
    assert index["summary"]["weekly_runs"] == 1
    assert index["summary"]["cron_run_count"] == 1


def test_p7_audit_rollout_fallback_writes_mode_output(tmp_path):
    """fallback 成功时 5repos.py 自身写 mode-specific 副本, daemon 不再硬编码.

    fake_run 模拟 5repos.py 跑出 mode-specific 文件 (5repos.py 内部读 OPC_MODE).
    """
    module = _load_module(
        "opc_p7_audit_rollout_daemon_fallback_test",
        ROOT / "scripts" / "opc_p7_audit_rollout_daemon.py",
    )
    module.ROOT = tmp_path  # type: ignore[reportAttributeAccessIssue]
    module._today = lambda: "2026-06-12"  # type: ignore[reportAttributeAccessIssue]
    out_dir = tmp_path / "runtime" / "omo" / "_delivery" / "audit-rollout"
    out_dir.mkdir(parents=True, exist_ok=True)

    def fake_run(cmd, cwd=None, capture_output=None, text=None, env=None, timeout=None):
        class Result:
            def __init__(self, returncode: int, stdout: str = "", stderr: str = ""):
                self.returncode = returncode
                self.stdout = stdout
                self.stderr = stderr

        if "opc_audit_rollout_5repos.py" in " ".join(cmd):
            # 5repos.py 内部同时写 5repos.json + mode-specific 副本
            payload = {"repos": {"workspace": {}}, "summary": {"total_repos": 1}}
            (out_dir / "2026-06-12-5repos.json").write_text(
                json.dumps(payload), encoding="utf-8"
            )
            # 5repos.py 读 OPC_MODE env 决定 mode (fake 这里硬编码 weekly)
            mode = (env or {}).get("OPC_MODE", "weekly")
            (out_dir / f"2026-06-12-{mode}.json").write_text(
                json.dumps(payload), encoding="utf-8"
            )
            return Result(0, stdout='{"ok": true}')
        return Result(1, stderr="primary failed")

    original_subprocess_run = module.subprocess.run
    module.subprocess.run = fake_run
    try:
        rollout = module._run_audit_rollout("weekly")
    finally:
        module.subprocess.run = original_subprocess_run
    assert rollout["returncode"] == 0
    assert rollout["fallback_used"] is True
    # 5repos.py 自身写 mode-specific 副本 (P7-H3 acceptance 仍满足)
    assert (out_dir / "2026-06-12-weekly.json").exists()


def test_p7_doc_lint_tracks_run_history(tmp_path):
    module = _load_module(
        "opc_p7_doc_lint_test", ROOT / "scripts" / "opc_p7_doc_lint.py"
    )
    module.ROOT = tmp_path  # type: ignore[reportAttributeAccessIssue]
    docs = tmp_path / "docs"
    docs.mkdir()
    for rel in [
        "PANORAMA.md",
        "ENTRY-CONVERGENCE.md",
        "JOURNEY-PROBES.md",
        "OPC-ROADMAP.md",
        "OPC-MASTER-EXECUTION-PLAYBOOK.md",
        "OPC-GOVERNANCE-CARRIERS-INDEX.md",
        "OPC-PHASE4-MODEL-COMPUTE.md",
        "OPC-PHASE5-SCENARIOS.md",
        "OPC-PHASE6-EVOLUTION-LOOP.md",
        "OPC-PHASE7-RELEASE-TRAIN.md",
    ]:
        (docs / rel).write_text("> Status: passed\n", encoding="utf-8")
    planned = tmp_path / ".omo" / "tasks" / "planned"
    planned.mkdir(parents=True)
    yaml_body = "gate: Gate E\ngate_status: passed\n"
    (planned / "OPC-P4-MODEL-COMPUTE.yaml").write_text(yaml_body, encoding="utf-8")
    (planned / "OPC-P5-SCENARIOS.yaml").write_text(
        "gate: Gate F\ngate_status: not_yet_passed\n", encoding="utf-8"
    )
    (planned / "OPC-P6-EVOLUTION-LOOP.yaml").write_text(
        "gate: Gate G\ngate_status: not_yet_passed\n", encoding="utf-8"
    )
    (planned / "OPC-P7-RELEASE-TRAIN.yaml").write_text(
        "gate: Gate H\ngate_status: not_yet_passed\n", encoding="utf-8"
    )

    rc = module.main()
    assert rc == 0
    index = json.loads(
        (tmp_path / ".omo" / "_delivery" / "doc-lint" / "index.json").read_text(
            encoding="utf-8"
        )
    )
    assert index["summary"]["run_count"] == 1
