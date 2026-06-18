from __future__ import annotations

import json
from pathlib import Path

import yaml

from omo.omo_cockpit_bridge import (
    append_hitl_override,
    archive_scenario_receipt,
    approve_hitl_proposal,
    list_hitl_proposals,
    reject_hitl_proposal,
)


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def test_archive_scenario_receipt_writes_delivery_artifact(tmp_path: Path) -> None:
    result = {
        "scenario": "assistant",
        "query": "OPC P5 progress",
        "generated_at": "2026-06-18T11:00:00Z",
        "status": "ok",
    }

    archive_path = Path(archive_scenario_receipt(tmp_path / ".omo", result))

    assert archive_path.exists()
    assert archive_path.parent == tmp_path / ".omo" / "_delivery" / "scenarios" / "assistant"
    payload = json.loads(archive_path.read_text(encoding="utf-8"))
    assert payload["scenario"] == "assistant"
    assert payload["query"] == "OPC P5 progress"


def test_hitl_proposal_helpers_cover_list_approve_reject(tmp_path: Path) -> None:
    proposal_dir = tmp_path / ".omo" / "state" / "proposals"
    proposal_dir.mkdir(parents=True, exist_ok=True)
    proposal = proposal_dir / "p-001.yaml"
    proposal.write_text(
        yaml.safe_dump(
            {
                "id": "p-001",
                "type": "budget_increase",
                "created_at": "2026-06-18T11:00:00Z",
                "debt_id": "D-1",
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    proposals = list_hitl_proposals(tmp_path / ".omo")
    assert [item["id"] for item in proposals] == ["p-001"]

    success, error = approve_hitl_proposal(
        tmp_path / ".omo",
        "p-001",
        execute_mutation=lambda item: item["type"] == "budget_increase",
    )
    assert success is True
    assert error is None
    assert not proposal.exists()

    proposal.write_text(
        yaml.safe_dump(
            {
                "id": "p-001",
                "type": "budget_increase",
                "created_at": "2026-06-18T11:05:00Z",
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    assert reject_hitl_proposal(tmp_path / ".omo", "p-001") is True
    assert not proposal.exists()


def test_append_hitl_override_appends_jsonl_record(tmp_path: Path) -> None:
    path = Path(
        append_hitl_override(
            tmp_path / ".omo",
            "budget_overrides.jsonl",
            {
                "ts": "2026-06-18T11:00:00Z",
                "debt_id": "D-1",
                "action": "increase_limit",
            },
        )
    )

    assert path == tmp_path / ".omo" / "state" / "budget_overrides.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["action"] == "increase_limit"
