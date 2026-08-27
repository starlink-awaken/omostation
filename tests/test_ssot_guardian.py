from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "bin/ssot/ssot-guardian.py"
SPEC = importlib.util.spec_from_file_location("ssot_guardian", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_task_count_includes_blocked_tasks(tmp_path: Path, monkeypatch) -> None:
    tasks_dir = tmp_path / "tasks"
    for group in ("active", "planned", "blocked", "done"):
        group_dir = tasks_dir / group
        group_dir.mkdir(parents=True)
        (group_dir / f"{group}.yaml").write_text(f"id: {group}\n", encoding="utf-8")

    monkeypatch.setattr(MODULE, "TASKS_DIR", tasks_dir)

    assert MODULE._count_tasks() == {
        "active": 1,
        "planned": 1,
        "blocked": 1,
        "done": 1,
        "total": 4,
    }
