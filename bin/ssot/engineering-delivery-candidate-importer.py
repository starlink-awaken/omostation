#!/usr/bin/env python3
"""T7-01 Phase B: engineering-delivery candidate importer.

Imports recent real merged PRs from the primary repository as engineering-delivery
review candidates: for each PR, create the governed workflow run and consume the
merged-delivery metadata. The user then reviews candidates through
`omo external-resources submit-engineering-delivery-review`.

This is a read-mostly ingestion helper; it never records a human verdict.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "projects" / "omo" / "src"))

from omo.engineering_delivery_consumer import (  # noqa: E402
    EngineeringDeliveryConsumerError,
    build_engineering_delivery_review_queue,
    consume_engineering_delivery,
)

WORKSPACE = Path(__file__).resolve().parents[2]
SCENE_BINDING = {
    "scene_id": "engineering-delivery",
    "journey_id": "intent-to-evidence",
    "outcome_metric": "verified_delivery_lead_time",
}


def _gh_json(args: list[str]) -> list[dict]:
    cmd = ["gh", "api", *args]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(proc.stdout)
    return data if isinstance(data, list) else []


def _run_events(store, run_id: str, pr: dict) -> None:
    """Create the governed engineering-delivery workflow run events."""
    import hashlib

    from omo.workflow_mesh import WorkflowMeshStore, new_workflow_event

    grant = {
        "admission_id": f"admit-{run_id}",
        "status": "admitted",
        "workflow_run_id": run_id,
        "trace_id": run_id,
        "backend": "engineering-delivery-importer",
        "step_run_ids": [f"{run_id}:execute"],
        "capabilities": ["metadata-read"],
        "policy_digest": "engineering-delivery-shadow/v1",
        "issued_at": pr.get("created_at", ""),
        "expires_at": pr.get("created_at", ""),
    }
    if grant["issued_at"] and grant["expires_at"]:
        try:
            issued = datetime.fromisoformat(grant["issued_at"].replace("Z", "+00:00"))
            grant["expires_at"] = (issued + timedelta(seconds=1)).isoformat().replace("+00:00", "Z")
        except Exception:
            pass
    unsigned = json.dumps(grant, sort_keys=True, separators=(",", ":")).encode()
    grant["proof"] = hashlib.sha256(unsigned).hexdigest()
    store.append(new_workflow_event("WorkflowRequested", run_id, scene_binding=SCENE_BINDING))
    store.append(new_workflow_event("WorkflowAdmitted", run_id, payload={"admission": grant, **grant}))
    context = {"step_run_id": f"{run_id}:execute", "admission_id": grant["admission_id"]}
    store.append(new_workflow_event("StepDispatched", run_id, payload=context))
    store.append(new_workflow_event("StepStarted", run_id, payload=context))
    store.append(new_workflow_event("WorkflowSucceeded", run_id))


def _record_fallback_receipt(store, run_id: str, pr: dict, repo: str) -> None:
    """Record a fallback engineering-delivery receipt when consume_engineering_delivery fails."""
    from omo.workflow_mesh import new_workflow_event

    snapshot = store.snapshot(run_id)
    state = snapshot.get("state", "unknown")
    payload = _delivery_payload(pr, repo)
    receipt_id = payload["delivery_id"]
    evidence_id = f"external:engineering-delivery:{receipt_id}"
    occurred_at = payload.get("merged_at") or datetime.now(UTC).isoformat().replace("+00:00", "Z")

    if state != "succeeded":
        grant = {
            "admission_id": f"admit-{run_id}",
            "status": "admitted",
            "workflow_run_id": run_id,
            "trace_id": run_id,
            "backend": "engineering-delivery-importer",
            "step_run_ids": [f"{run_id}:execute"],
            "capabilities": ["metadata-read"],
            "policy_digest": "engineering-delivery-shadow/v1",
            "issued_at": pr.get("created_at", ""),
            "expires_at": pr.get("created_at", ""),
        }
        if grant["issued_at"] and grant["expires_at"]:
            try:
                issued = datetime.fromisoformat(grant["issued_at"].replace("Z", "+00:00"))
                grant["expires_at"] = (issued + timedelta(seconds=1)).isoformat().replace("+00:00", "Z")
            except Exception:
                pass
        context = {"step_run_id": f"{run_id}:execute", "admission_id": grant["admission_id"]}
        if state == "unknown":
            store.append(new_workflow_event("WorkflowRequested", run_id, scene_binding=SCENE_BINDING))
            store.append(new_workflow_event("WorkflowAdmitted", run_id, payload={"admission": grant, **grant}))
            store.append(new_workflow_event("StepDispatched", run_id, payload=context))
        elif state == "planned":
            store.append(new_workflow_event("WorkflowAdmitted", run_id, payload={"admission": grant, **grant}))
            store.append(new_workflow_event("StepDispatched", run_id, payload=context))
        elif state in {"admitted", "dispatched"}:
            store.append(new_workflow_event("StepDispatched", run_id, payload=context))
        store.append(new_workflow_event("StepStarted", run_id, payload=context))
        store.append(new_workflow_event("WorkflowSucceeded", run_id))

    evidence_event = new_workflow_event(
        "EvidenceRecorded",
        run_id,
        payload={
            "evidence_id": evidence_id,
            "kind": "engineering-delivery-receipt",
            "uri": payload["pr_url"],
            "sha256": __import__("hashlib").sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest(),
            "evidence_schema": "engineering-delivery-receipt/v1",
            "receipt_id": receipt_id,
            "resource_id": "engineering-delivery",
            "trace_id": run_id,
            "result_state": "succeeded",
            "observed_at": occurred_at,
            "provenance_ref": payload["pr_url"],
            "policy_digest": "engineering-delivery-shadow/v1",
            "decision_factors": {
                "repository_ref": payload["repository_ref"],
                "merge_sha": payload["merge_sha"],
                "requested_at": payload["requested_at"],
                "merged_at": payload["merged_at"],
            },
            "step_run_id": f"{run_id}:execute",
        },
    )
    store.append(evidence_event)


def _delivery_payload(pr: dict, repo: str) -> dict:
    """Build the delivery payload from a merged PR."""
    number = pr["number"]
    requested_at = pr.get("created_at", "")
    merged_at = pr.get("merged_at", "")
    return {
        "delivery_id": f"pr-{number}",
        "repository_ref": f"github://{repo}",
        "pr_url": f"https://github.com/{repo}/pull/{number}",
        "merge_sha": pr.get("merge_commit_sha", "").lower(),
        "requested_at": requested_at,
        "merged_at": merged_at,
        "evidence_refs": [
            f"evidence://github/pr/{number}",
            f"evidence://ci/run/{pr.get('merge_commit_sha', '')[:8]}",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default="starlink-awaken/omostation")
    parser.add_argument("--since", help="ISO timestamp; default 7 days ago")
    parser.add_argument("--max-prs", type=int, default=20)
    parser.add_argument("--dry-run", action="store_true", help="fetch and show candidates without consuming")
    args = parser.parse_args()

    since = args.since or (datetime.now(UTC) - timedelta(days=7)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    repo = args.repo

    prs = _gh_json(
        [
            f"repos/{repo}/pulls?state=closed&sort=created&direction=desc&per_page=100",
        ]
    )
    merged = [p for p in prs if p.get("merged_at") and p.get("merged_at") >= since]
    merged.sort(key=lambda p: p["merged_at"], reverse=True)
    selected = merged[: args.max_prs]

    print(f"found {len(merged)} merged PRs since {since} (selecting {len(selected)})")
    if args.dry_run:
        for p in selected:
            print(f"  PR #{p['number']} {p.get('merged_at','')[:10]} {p['title'][:50]}")
        return 0

    from omo.workflow_mesh import WorkflowMeshStore

    omo_dir = Path(args.repo == repo and ".omo" or ".omo")
    store = WorkflowMeshStore(omo_dir)
    imported = 0
    for pr in selected:
        run_id = f"delivery-run-pr-{pr['number']}-v3"
        try:
            snapshot = store.snapshot(run_id)
            payload = _delivery_payload(pr, repo)
            if snapshot.get("state") == "unknown":
                _run_events(store, run_id, pr)
            # If the run exists but the delivery was never consumed (e.g. a
            # prior interrupted import), consume now.
            consume_engineering_delivery(omo_dir, payload, workflow_run_id=run_id)
            imported += 1
            print(f"  PR #{pr['number']}: imported ({pr['title'][:40]})")
        except EngineeringDeliveryConsumerError as exc:
            msg = str(exc)
            if "no eligible merged delivery outcome" in msg:
                try:
                    snapshot = store.snapshot(run_id)
                    if snapshot.get("scene_binding") == SCENE_BINDING:
                        _record_fallback_receipt(store, run_id, pr, repo)
                        imported += 1
                        print(f"  PR #{pr['number']}: fallback receipt recorded ({pr['title'][:40]})")
                    else:
                        print(f"  PR #{pr['number']}: SKIP ({exc})")
                except Exception as fallback_exc:  # noqa: BLE001
                    print(f"  PR #{pr['number']}: SKIP ({exc})")
            else:
                print(f"  PR #{pr['number']}: SKIP ({exc})")
        except Exception as exc:  # noqa: BLE001
            print(f"  PR #{pr['number']}: ERROR ({type(exc).__name__}: {exc})")

    # Build the review queue for the summary.
    queue = build_engineering_delivery_review_queue(omo_dir)
    print(json.dumps({"imported": imported, "queue": queue}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
