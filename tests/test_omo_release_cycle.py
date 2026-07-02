from __future__ import annotations

import json
from pathlib import Path

from omo.omo_release_cycle import (
    gather_debt,
    next_release_version,
    run_release_cycle,
    update_release_index,
    write_cycle_json,
    write_release_notes,
    write_retrospective,
)


def test_release_cycle_persistence_helpers(tmp_path: Path) -> None:
    cycle = {
        "version": "v2026-06-20-r1",
        "stage": "ship",
        "generated_at": "2026-06-20T00:00:00Z",
        "trigger_source": "manual",
        "changes": {
            "cutoff": "2026-06-13T00:00:00Z",
            "commit_count": 2,
            "commits": ["a1 first", "b2 second"],
        },
        "validation": {
            "omo_tests": {"returncode": 0, "summary": "ok"},
            "drift": {"kinds": 4, "drift_count": 0},
        },
        "debt": {"total": 3, "open": 1, "resolved": 2},
        "cycle_json_path": ".omo/_delivery/release/v2026-06-20-r1.json",
        "retro_path": "runtime/omo/tasks/registry/done/OPC-P7-H1/retrospective-v2026-06-20-r1.md",
    }
    assert next_release_version(tmp_path, "2026-06-20") == "v2026-06-20-r1"
    notes_path = write_release_notes(tmp_path, cycle["version"], cycle)
    cycle_json_path = write_cycle_json(tmp_path, cycle["version"], cycle)
    retro_path = write_retrospective(tmp_path, cycle["version"], cycle)
    index = update_release_index(tmp_path, cycle)

    assert notes_path.exists()
    assert cycle_json_path.exists()
    assert retro_path.exists()
    assert index["summary"]["release_count"] == 1
    assert (
        json.loads(cycle_json_path.read_text(encoding="utf-8"))["version"]
        == cycle["version"]
    )


def test_run_release_cycle_uses_injected_collectors(tmp_path: Path) -> None:
    cycle = run_release_cycle(
        tmp_path,
        version="v2026-06-21-r1",
        today="2026-06-21",
        generated_at="2026-06-21T00:00:00Z",
        trigger="cron",
        gather_changes_fn=lambda: {
            "cutoff": "2026-06-14T00:00:00Z",
            "commit_count": 1,
            "commits": ["a1 demo"],
            "previous_release_version": None,
        },
        gather_validation_fn=lambda: {
            "omo_tests": {"returncode": 0, "summary": "ok"},
            "drift": {"kinds": 2, "drift_count": 0},
        },
        gather_debt_fn=lambda: {"total": 1, "open": 0, "resolved": 1},
    )
    assert cycle["trigger_source"] == "cron"
    assert cycle["release_index"]["summary"]["latest_version"] == "v2026-06-21-r1"


def test_gather_debt_accepts_multi_document_yaml(tmp_path: Path) -> None:
    debt_dir = tmp_path / ".omo" / "debt" / "items"
    debt_dir.mkdir(parents=True, exist_ok=True)
    (debt_dir / "debt-a.yaml").write_text(
        "---\nstatus: active\nowner: governance\n---\n---\nstatus: open\n",
        encoding="utf-8",
    )
    (debt_dir / "debt-b.yaml").write_text(
        "---\nstatus: active\nowner: governance\n---\n---\nstatus: resolved\n",
        encoding="utf-8",
    )

    payload = gather_debt(tmp_path)

    assert payload == {"total": 2, "open": 1, "resolved": 1}
