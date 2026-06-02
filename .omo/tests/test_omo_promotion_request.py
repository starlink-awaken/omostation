from __future__ import annotations

from scripts.omo_promotion_request import (
    build_promotion_approval_proposal,
    build_promotion_approval_request,
    promotion_approval_ref,
)


def test_promotion_approval_ref_uses_task_id_and_timestamp_slug():
    assert promotion_approval_ref("P19-W3-ARCHIVE-TS", "2026-06-03T00:00:00Z") == (
        ".omo/workers/runs/P19-W3-ARCHIVE-TS-promotion-approval-2026-06-03T00-00-00Z.yaml"
    )


def test_build_promotion_approval_request_creates_requested_record():
    approval_ref = promotion_approval_ref("P19-W3-ARCHIVE-TS", "2026-06-03T00:00:00Z")

    record = build_promotion_approval_request(
        task_id="P19-W3-ARCHIVE-TS",
        task_ref=".omo/tasks/planned/P19-W3-ARCHIVE-TS.yaml",
        requested_operation_level="L2",
        requested_at="2026-06-03T00:00:00Z",
        approval_ref=approval_ref,
    )

    assert record["approval_id"] == "P19-W3-ARCHIVE-TS-promotion-approval-2026-06-03T00-00-00Z"
    assert record["approval_status"] == "requested"
    assert record["approval_scope"] == "task.promote_apply"
    assert record["refs"]["task_ref"] == ".omo/tasks/planned/P19-W3-ARCHIVE-TS.yaml"
    assert record["refs"]["readiness_ref"] == ".omo/workers/promotion/readiness.yaml"


def test_build_promotion_approval_proposal_targets_requested_record():
    approval_ref = promotion_approval_ref("P19-W3-ARCHIVE-TS", "2026-06-03T00:00:00Z")

    proposal = build_promotion_approval_proposal(
        task_id="P19-W3-ARCHIVE-TS",
        requested_by="copilot-cli",
        approval_ref=approval_ref,
    )

    assert proposal["id"] == "P19-W3-ARCHIVE-TS-promotion-approval-2026-06-03T00-00-00Z-proposal"
    assert proposal["target"]["ref"] == approval_ref
    assert proposal["changes"]["set"]["approval_status"] == "granted"
    assert proposal["requested_by"] == "copilot-cli"
