from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
MODULE_PATH = SCRIPTS / "sync_omo_state.py"
SPEC = importlib.util.spec_from_file_location("sync_omo_state", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_completed_task_count_includes_archived_done_projection(tmp_path: Path) -> None:
    tasks = tmp_path / "tasks"
    (tasks / "done").mkdir(parents=True)
    (tasks / "archived" / "done").mkdir(parents=True)
    (tasks / "done" / "current.yaml").write_text("id: current\n", encoding="utf-8")
    (tasks / "archived" / "done" / "historical.yaml").write_text(
        "id: historical\n", encoding="utf-8"
    )

    assert MODULE._count_completed_tasks(tasks) == 2
