from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).parents[1] / "bin/ssot/scene-card-intake.py"
SPEC = importlib.util.spec_from_file_location("scene_card_intake", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def _scene_card(**overrides: object) -> dict[str, object]:
    card: dict[str, object] = {
        "schema": "scene-card/v1",
        "lifecycle": "proposal_only",
        "activation": "forbidden",
        "scene_id": "research-brief",
        "journey_id": "question-to-brief",
        "goal": "形成可核验的研究简报",
        "trigger": "研究问题进入待处理队列",
        "input_contract": "evidence://research/input-contract",
        "result_contract": "evidence://research/result-contract",
        "outcome_metric": "verified_brief_acceptance",
        "consumer": "research-owner",
        "approver": "business-owner",
        "owner": "research-operator",
        "failure_cost": "错误结论进入决策材料",
        "data_classification": "internal",
        "data_scope": "redacted-reference-only",
        "operator": "human-under-review",
        "permission_ref": "permission://research/read",
        "rollback_plan": "stop-and-retract-draft",
        "sample_refs": [
            "sample://research/1",
            "sample://research/2",
            "sample://research/3",
        ],
        "demand_evidence_refs": ["evidence://research/demand"],
        "activation_evidence_refs": ["evidence://research/approval"],
        "required_capabilities": ["source.research"],
    }
    card.update(overrides)
    return card


def test_complete_card_is_proposal_only_and_safe() -> None:
    result = MODULE.build_intake(_scene_card())

    assert result["schema"] == "scene-card-intake/v1"
    assert result["mode"] == "proposal_only_intake"
    assert result["status"] == "proposal_only"
    assert result["next_action"] == "run_external_activation_preflight"
    assert result["activation"] == "forbidden"
    assert result["scene_card"]["required_capabilities"] == ["source.research"]
    assert result["side_effects"]["omo_written"] is False


def test_incomplete_card_is_blocked_with_actionable_fields() -> None:
    card = _scene_card(
        owner="",
        sample_refs=["sample://research/1"],
        activation_evidence_refs=[],
        required_capabilities=[],
    )

    result = MODULE.build_intake(card)

    assert result["status"] == "blocked"
    assert "owner" in result["missing_fields"]
    assert "sample_refs:3-10" in result["missing_fields"]
    assert "activation_evidence_refs" in result["missing_fields"]
    assert result["next_action"] == "complete_scene_card_and_resubmit"


def test_raw_content_and_non_opaque_refs_fail_closed() -> None:
    with pytest.raises(MODULE.IntakeInputError, match="forbidden field"):
        MODULE.build_intake(_scene_card(private_context={"document_body": "secret"}))

    with pytest.raises(MODULE.IntakeInputError, match="opaque references"):
        MODULE.build_intake(_scene_card(sample_refs=["/tmp/sample.txt"]))


def test_requested_activation_is_blocked_even_when_card_is_complete() -> None:
    result = MODULE.build_intake(_scene_card(activation="active"))

    assert result["status"] == "blocked"
    assert result["missing_fields"] == ["activation_must_be_forbidden"]
    assert result["activation"] == "forbidden"
    assert result["side_effects"]["activation_attempted"] is False


def test_cli_is_machine_readable_and_does_not_write(tmp_path: Path, capsys) -> None:
    input_path = tmp_path / "scene-card.json"
    input_path.write_text(
        json.dumps(_scene_card(), ensure_ascii=False), encoding="utf-8"
    )
    before = sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*"))

    assert MODULE.main(["--input", str(input_path)]) == 0
    result = json.loads(capsys.readouterr().out)

    after = sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*"))
    assert result["status"] == "proposal_only"
    assert after == before
