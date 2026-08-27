from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from kems_build_engineering_delivery_queue import EngineeringDeliveryQueueError, build_queue, write_queue


def projection(*, review_status: str = "reviewed", decision: str | None = "adopted") -> dict[str, object]:
    return {
        "schema": "engineering-delivery-review-queue/v1",
        "scene_binding": {
            "scene_id": "engineering-delivery",
            "journey_id": "intent-to-evidence",
            "outcome_metric": "verified_delivery_lead_time",
        },
        "rows": [
            {
                "workflow_run_id": "run-1",
                "trace_id": "trace-1",
                "delivery_id": "delivery-1",
                "scene_binding": {
                    "scene_id": "engineering-delivery",
                    "journey_id": "intent-to-evidence",
                    "outcome_metric": "verified_delivery_lead_time",
                },
                "workflow_state": "closed",
                "receipt_event_id": "event-1",
                "feedback_states": ["submitted", decision] if decision else ["submitted"],
                "review_status": review_status,
                "latest_decision": decision,
                "lead_time_seconds": 420,
                "evidence_count": 2,
            }
        ],
        "controls": {"read_only": True, "workflow_state_mutation": False, "provider_invocation": False},
    }


def test_build_queue_accepts_only_reviewed_metadata_and_is_deterministic() -> None:
    first = build_queue(projection())
    second = build_queue(projection())
    assert first == second
    assert first[0]["scenario_id"] == "engineering-delivery-review-v1"
    assert first[0]["source_ref"].startswith("vault://redacted/workflow-mesh/engineering-delivery/")
    assert first[0]["labels"] == {}
    assert "delivery-1" not in json.dumps(first)


def test_pending_rows_do_not_become_real_evaluation_samples() -> None:
    with pytest.raises(EngineeringDeliveryQueueError, match="no reviewed"):
        build_queue(projection(review_status="pending"))


def test_projection_rejects_raw_content_and_invalid_controls() -> None:
    raw = projection() | {"document_body": "private"}
    with pytest.raises(EngineeringDeliveryQueueError, match="raw content"):
        build_queue(raw)
    blocked = projection()
    blocked["controls"] = {"read_only": False, "provider_invocation": True}
    with pytest.raises(EngineeringDeliveryQueueError, match="controls"):
        build_queue(blocked)


def test_write_queue_is_private_and_atomic(tmp_path: Path) -> None:
    output = tmp_path / "queue" / "engineering.jsonl"
    write_queue(build_queue(projection()), output)
    assert output.stat().st_mode & 0o077 == 0
    assert not list(output.parent.glob(".*.tmp"))
    assert json.loads(output.read_text(encoding="utf-8").splitlines()[0])
