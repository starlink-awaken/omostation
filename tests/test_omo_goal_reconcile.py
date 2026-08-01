from __future__ import annotations

from pathlib import Path

import yaml

from omo.omo_ingress_goal import reconcile_goals


def test_reconcile_repairs_frontmatter_and_records_audit(tmp_path: Path) -> None:
    omo_dir = tmp_path / ".omo"
    goal_file = omo_dir / "goals" / "current.yaml"
    goal_file.parent.mkdir(parents=True)
    goal_file.write_text(
        "status: active\nowner: governance\n---\nphase: 45\n"
        "current_wave: W1\ngoals:\n"
        "- id: G45.1\n  status: done\n  progress: 100\n",
        encoding="utf-8",
    )

    payload = reconcile_goals(
        omo_dir,
        phase=47,
        current_wave="W1",
        execution_mode="waiting-for-scenario/next-bet",
        theme="P47 resilience",
        archive_completed=True,
        now="2026-08-01T12:00:00Z",
    )

    documents = list(yaml.safe_load_all(goal_file.read_text(encoding="utf-8")))
    assert len(documents) == 2
    assert payload["phase"] == 47
    assert payload["current_wave"] == "W1"
    assert payload["execution_mode"] == "waiting-for-scenario/next-bet"
    assert payload["goals"][0]["status"] == "archived"
    assert list((tmp_path / "runtime/omo/_delivery/ingress/goals").glob("reconcile-*.yaml"))
    mutation_log = tmp_path / "runtime/omo/change-log/mutations.jsonl"
    assert "reconcile_goals" in mutation_log.read_text(encoding="utf-8")
