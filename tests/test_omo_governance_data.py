from __future__ import annotations

import json
from pathlib import Path

import yaml
from omo.omo_governance_data import build_governance_data, write_governance_data


def test_build_and_write_governance_data(tmp_path: Path) -> None:
    omo_dir = tmp_path / ".omo"
    state_dir = omo_dir / "state"
    dashboard_dir = omo_dir / "_control" / "debt-dashboard"
    state_dir.mkdir(parents=True, exist_ok=True)
    dashboard_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "system.yaml").write_text(
        yaml.safe_dump(
            {
                "health_score": 91.0,
                "health_score_raw": 100,
                "debt_weight": 0.12,
                "debt_metrics": {
                    "debt_health": 88,
                    "resolved_count": 7,
                    "unresolved_count": 3,
                },
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (dashboard_dir / "current.yaml").write_text(
        yaml.safe_dump(
            {
                "debt_categories": {"governance": 2},
                "health_trend": [{"date": "2026-06-20", "score": 91.0}],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    payload = build_governance_data(tmp_path)
    output_path = write_governance_data(tmp_path, payload)

    assert payload["debt"]["total_count"] == 10
    assert payload["debt"]["resolution_rate"] == 0.7
    written = json.loads(output_path.read_text(encoding="utf-8"))
    assert written["governance"]["health_score"] == 91.0
    assert written["categories"] == {"governance": 2}


def test_write_governance_data_skips_timestamp_only_changes(tmp_path: Path) -> None:
    omo_dir = tmp_path / ".omo"
    control_dir = omo_dir / "_control"
    control_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": "1.0",
        "generated_at": "2026-07-03T00:00:00Z",
        "governance": {"health_score": 91.0},
        "debt": {"total_count": 0},
        "categories": {},
        "trend": [],
        "projects": {},
    }

    output_path = write_governance_data(tmp_path, payload)
    first = output_path.read_text(encoding="utf-8")
    payload["generated_at"] = "2026-07-03T00:01:00Z"
    output_path = write_governance_data(tmp_path, payload)

    assert output_path.read_text(encoding="utf-8") == first


def test_build_governance_data_accepts_multi_document_yaml(tmp_path: Path) -> None:
    omo_dir = tmp_path / ".omo"
    state_dir = omo_dir / "state"
    dashboard_dir = omo_dir / "_control" / "debt-dashboard"
    state_dir.mkdir(parents=True, exist_ok=True)
    dashboard_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "system.yaml").write_text(
        "---\nstatus: active\nowner: governance\n---\n---\n"
        "health_score: 95.0\n"
        "health_score_raw: 100\n"
        "debt_weight: 0.05\n"
        "debt_metrics:\n"
        "  debt_health: 93\n"
        "  resolved_count: 9\n"
        "  unresolved_count: 1\n",
        encoding="utf-8",
    )
    (dashboard_dir / "current.yaml").write_text(
        "---\nstatus: active\nowner: governance\n---\n---\n"
        "debt_categories:\n"
        "  runtime: 1\n"
        "health_trend:\n"
        "  - date: 2026-06-23\n"
        "    score: 95.0\n",
        encoding="utf-8",
    )

    payload = build_governance_data(tmp_path)

    assert payload["governance"]["health_score"] == 95.0
    assert payload["governance"]["debt_health"] == 93
    assert payload["debt"]["total_count"] == 10
    assert payload["categories"] == {"runtime": 1}
