from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "bin/ssot/current-state-coherence.py"
SPEC = importlib.util.spec_from_file_location("current_state_coherence", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _write_fixture(
    root: Path,
    *,
    phase: int = 49,
    goal_phase: int = 49,
    active_tasks: int = 0,
    execution_mode: str = "waiting-for-scenario/next-bet",
    stored_total: int = 1,
) -> None:
    omo = root / ".omo"
    (omo / "state").mkdir(parents=True)
    (omo / "goals").mkdir()
    for group in ("active", "planned", "blocked", "done"):
        (omo / "tasks" / group).mkdir(parents=True)
    (root / "docs").mkdir()
    (root / "docs/scene-cards").mkdir(parents=True)
    (root / "docs/scene-card-candidate-seeds.yaml").write_text(
        "schema: scene-card-candidate-seeds/v1\n"
        "candidates:\n"
        "  - candidate_id: candidate:one\n"
        "    title: one\n",
        encoding="utf-8",
    )
    (omo / "state/system.yaml").write_text(
        f"current_phase: {phase}\ncurrent_wave: W5\n"
        f"active_tasks: {active_tasks}\nplanned_tasks: 0\n"
        f"completed_tasks: 0\ntotal_tasks: {stored_total}\n"
        "divergence_flags: []\n",
        encoding="utf-8",
    )
    (omo / "goals/current.yaml").write_text(
        "---\nstatus: active\n---\n"
        f"phase: {goal_phase}\ncurrent_wave: W5\n"
        f"execution_mode: {execution_mode}\n"
        "goals:\n  - id: historical\n    status: done\n    tasks: []\n",
        encoding="utf-8",
    )


def test_waiting_state_is_valid_and_scene_activation_stays_blocked(tmp_path: Path) -> None:
    _write_fixture(tmp_path, stored_total=0)

    report = MODULE.build_report(tmp_path)

    assert report["ok"] is True
    assert report["status"] == "waiting_for_scenario"
    assert report["execution"]["counts"] == {
        "active": 0,
        "planned": 0,
        "blocked": 0,
        "done": 0,
    }
    assert report["scene_activation"]["status"] == "candidate_only"
    assert report["scene_activation"]["activation_allowed"] is False
    assert report["scene_activation"]["candidate_count"] == 1


def test_phase_mismatch_is_blocking(tmp_path: Path) -> None:
    _write_fixture(tmp_path, goal_phase=48, stored_total=0)

    report = MODULE.build_report(tmp_path)

    assert report["ok"] is False
    assert "phase_mismatch:goals=48:state=49" in report["errors"]


def test_stored_task_count_drift_is_blocking(tmp_path: Path) -> None:
    _write_fixture(tmp_path, stored_total=1)

    report = MODULE.build_report(tmp_path)

    assert report["ok"] is False
    assert "total_tasks_mismatch:expected=0:state=1" in report["errors"]


def test_active_task_cannot_use_waiting_mode(tmp_path: Path) -> None:
    _write_fixture(tmp_path, active_tasks=1, stored_total=1)
    (tmp_path / ".omo/tasks/active/task.yaml").write_text("id: task-1\n", encoding="utf-8")

    report = MODULE.build_report(tmp_path)

    assert report["ok"] is False
    assert "execution_mode_mismatch:active_tasks_present" in report["errors"]


def test_completed_monitoring_goal_does_not_create_execution_work(tmp_path: Path) -> None:
    _write_fixture(tmp_path, stored_total=0)
    (tmp_path / ".omo/goals/current.yaml").write_text(
        "---\nstatus: active\n---\n"
        "phase: 49\ncurrent_wave: W5\n"
        "execution_mode: waiting-for-scenario/next-bet\n"
        "goals:\n"
        "  - id: KOS-Q-GROWTH\n"
        "    status: active\n"
        "    progress: 100\n"
        "    quarterly_targets:\n"
        "      - target: maintain\n",
        encoding="utf-8",
    )

    report = MODULE.build_report(tmp_path)

    assert report["ok"] is True
    assert report["status"] == "waiting_for_scenario"
    assert report["execution"]["monitoring_goal_ids"] == ["KOS-Q-GROWTH"]
