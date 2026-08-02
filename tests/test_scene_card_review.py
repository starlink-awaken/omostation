from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).parents[1] / "bin/ssot/scene-card-review.py"
SPEC = importlib.util.spec_from_file_location("scene_card_review", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def _payload() -> dict[str, object]:
    return {
        "schema": "scene-card-candidate/v1",
        "mode": "candidate_only",
        "activation": "forbidden",
        "candidates": [
            {
                "candidate_id": "scene-candidate:engineering-delivery",
                "title": "工程研发与系统进化",
                "discovery_refs": ["docs/STRATEGY-3YEAR-PANORAMA.md#W6"],
                "proposed_scene_id": "engineering-delivery",
                "proposed_journey_id": "intent-to-evidence",
                "outcome_metric_hint": "verified_delivery_lead_time",
                "capability_refs": ["omo.workflow_mesh"],
                "safe_observations": ["结果需要回到业务目标"],
                "activation_evidence_refs": [],
                "sample_refs": [],
                "demand_evidence_refs": [],
                "opportunity_window": "",
                "missing_activation_fields": ["owner", "sample_refs"],
            }
        ],
    }


def test_pending_receipt_is_manual_and_non_activating() -> None:
    receipt = MODULE.create_review_receipt(
        _payload(), candidate_id="scene-candidate:engineering-delivery"
    )

    assert receipt["schema"] == "scene-card-review/v1"
    assert receipt["status"] == "pending"
    assert receipt["manual_consumption"] == "review_queue"
    assert receipt["activation"] == "forbidden"
    assert receipt["activation_attempted"] is False
    assert receipt["note_digest"] == ""


def test_approval_is_blocked_until_scene_card_is_complete() -> None:
    receipt = MODULE.create_review_receipt(
        _payload(),
        candidate_id="scene-candidate:engineering-delivery",
        decision="approve",
        reviewer_ref="operator://redacted/reviewer-1",
        note="候选方向合理，但当前证据不完整",
    )

    assert receipt["decision"] == "approve"
    assert receipt["status"] == "blocked"
    assert receipt["reason"] == "scene_card_incomplete"
    assert receipt["activation"] == "forbidden"
    assert "候选方向" not in json.dumps(receipt, ensure_ascii=False)
    assert str(receipt["note_digest"]).startswith("sha256:")


def test_request_evidence_and_reject_are_reviewable_decisions() -> None:
    for decision, status in (("request_evidence", "needs_evidence"), ("reject", "rejected")):
        receipt = MODULE.create_review_receipt(
            _payload(),
            candidate_id="scene-candidate:engineering-delivery",
            decision=decision,
            reviewer_ref="operator://redacted/reviewer-1",
            note="请补充或关闭该候选",
        )
        assert receipt["status"] == status
        assert receipt["activation_attempted"] is False


def test_invalid_candidate_projection_fails_closed() -> None:
    payload = _payload()
    payload["activation"] = "active"

    with pytest.raises(MODULE.ReviewInputError, match="forbid activation"):
        MODULE.create_review_receipt(
            payload, candidate_id="scene-candidate:engineering-delivery"
        )


def test_cli_reads_stdin_and_does_not_write(tmp_path: Path, monkeypatch, capsys) -> None:
    input_file = tmp_path / "candidate.json"
    input_file.write_text(json.dumps(_payload(), ensure_ascii=False), encoding="utf-8")
    before = sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*"))
    monkeypatch.setattr(sys, "stdin", input_file.open(encoding="utf-8"))

    assert (
        MODULE.main(
            ["--candidate-id", "scene-candidate:engineering-delivery"]
        )
        == 0
    )
    receipt = json.loads(capsys.readouterr().out)
    after = sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*"))
    assert receipt["status"] == "pending"
    assert after == before


def test_cli_reads_private_review_envelope_from_stdin(monkeypatch, capsys) -> None:
    payload = _payload()
    payload["_review"] = {
        "reviewer_ref": "operator://redacted/reviewer-1",
        "note": "这条意见只允许进入摘要哈希",
    }
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload, ensure_ascii=False)))

    assert (
        MODULE.main(
            [
                "--candidate-id",
                "scene-candidate:engineering-delivery",
                "--decision",
                "request_evidence",
                "--review-envelope-stdin",
            ]
        )
        == 0
    )
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["status"] == "needs_evidence"
    assert "这条意见" not in json.dumps(receipt, ensure_ascii=False)
