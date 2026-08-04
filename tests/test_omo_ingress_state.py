from __future__ import annotations

import json
from pathlib import Path

import yaml
from omo.omo_ingress_state import sync_state_projection


def test_sync_state_projection_skips_timestamp_only_changes(tmp_path: Path) -> None:
    omo_dir = tmp_path / ".omo"
    state_dir = omo_dir / "state"
    state_dir.mkdir(parents=True)
    (state_dir / "system.yaml").write_text(
        yaml.safe_dump({"current_phase": 42}, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    governance_data = {
        "version": "1.0",
        "generated_at": "2026-07-03T00:00:00Z",
        "governance": {"health_score": 91},
        "debt": {"total_count": 0},
        "categories": {},
        "trend": [],
        "projects": {},
    }
    report = sync_state_projection(
        tmp_path,
        health_content='# generated_at: 2026-07-03T00:00:00Z\ngenerated_at: "2026-07-03T00:00:00Z"\nhealth_score: 91\n',
        system_updates={
            "health_score": 91,
            "health_score_generated_at": "2026-07-03T00:00:00Z",
        },
        brief_content="# BRIEF.md\n\n> **Generated**: `2026-07-03T00:00:00Z`\n",
        governance_data=governance_data,
    )

    assert report["changed_count"] == 4
    assert report["artifact_ref"]
    assert (state_dir / "health.yaml").exists()
    assert (tmp_path / "BRIEF.md").exists()
    assert (omo_dir / "_control" / "governance-data.json").exists()

    governance_data["generated_at"] = "2026-07-03T00:01:00Z"
    second = sync_state_projection(
        tmp_path,
        health_content='# generated_at: 2026-07-03T00:01:00Z\ngenerated_at: "2026-07-03T00:01:00Z"\nhealth_score: 91\n',
        system_updates={
            "health_score": 91,
            "health_score_generated_at": "2026-07-03T00:01:00Z",
        },
        brief_content="# BRIEF.md\n\n> **Generated**: `2026-07-03T00:01:00Z`\n",
        governance_data=governance_data,
    )

    assert second["changed_count"] == 0
    assert second["artifact_ref"] == ""
    written_governance = json.loads(
        (omo_dir / "_control" / "governance-data.json").read_text(encoding="utf-8")
    )
    assert written_governance["generated_at"] == "2026-07-03T00:00:00Z"

    semantic_change = sync_state_projection(
        tmp_path,
        health_content="# generated_at: 2026-07-03T00:02:00Z\nhealth_score: 92\n",
        system_updates={
            "health_score": 92,
            "health_score_generated_at": "2026-07-03T00:02:00Z",
        },
        brief_content="# BRIEF.md\n\n> **Generated**: `2026-07-03T00:02:00Z`\n",
        governance_data=governance_data,
    )

    assert semantic_change["changed_count"] == 2
    assert semantic_change["artifact_ref"]
