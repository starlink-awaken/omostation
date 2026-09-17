import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin/panorama/panorama-collect.py"


def _module():
    spec = importlib.util.spec_from_file_location("panorama_task_projection_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_collect_tasks_reads_canonical_per_file_queue(tmp_path, monkeypatch) -> None:
    module = _module()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    _write(tmp_path / ".omo/tasks/active/active-task.yaml", "id: TASK-A\ntitle: Active\nstatus: pending\npriority: P0\nowner: agent\n")
    _write(tmp_path / ".omo/tasks/planned/planned-task.yaml", "id: TASK-B\ntitle: Planned\nstatus: candidate\npriority: P1\nowner: human\n")
    _write(tmp_path / ".omo/tasks/blocked/blocked-task.yaml", "id: TASK-C\ntitle: Blocked\nstatus: blocked\npriority: P1\nowner: human\n")
    _write(tmp_path / ".omo/tasks/done/done-task.yaml", "id: TASK-D\ntitle: Done\nstatus: done\n")
    _write(tmp_path / ".omo/tasks/planned/duplicate-task.yaml", "id: TASK-A\ntitle: Duplicate\nstatus: candidate\n")

    report = module.collect_tasks()

    assert report["source"] == ".omo/tasks/{active,planned,blocked,done}/*.yaml"
    assert report["total"] == 5
    assert report["open_count"] == 4
    assert report["by_bucket"] == {"active": 1, "planned": 2, "blocked": 1, "done": 1}
    assert report["duplicates"] == [{"id": "TASK-A", "buckets": ["active", "planned"]}]
    assert report["open_recent"][0]["id"] == "TASK-A"
    assert report["open_recent"][0]["bucket"] == "active"
    assert {task["id"] for task in report["open_recent"]} == {"TASK-A", "TASK-B", "TASK-C"}


def test_collect_service_lifecycle_separates_service_registry(tmp_path, monkeypatch) -> None:
    module = _module()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    registry = tmp_path / ".omo/state/task-registry.yaml"
    _write(registry, "tasks:\n  daemon-a:\n    system: compute\n    carrier: launchd\n    lifecycle: active\n    purpose: daemon\n  daemon-b:\n    system: compute\n    carrier: cron\n    lifecycle: proposed\n    purpose: pending\n")

    report = module.collect_service_lifecycle()

    assert report["source"] == ".omo/state/task-registry.yaml"
    assert report["total"] == 2
    assert report["by_lifecycle"] == {"active": 1, "proposed": 1}
    assert {row["id"] for row in report["recent"]} == {"daemon-a", "daemon-b"}
