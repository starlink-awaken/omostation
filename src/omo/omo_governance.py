#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from copy import deepcopy
from datetime import UTC, datetime, timezone
from pathlib import Path

from .omo_governance_surfaces import (
    main as governance_surfaces_main,
)
from .omo_governance_surfaces import (
    resolve_governance_workspace_root,
)
from .omo_ingress import upsert_debt_item
from .omo_ingress_goal import create_goal
from .omo_ingress_task_lifecycle import create_planned_task
from .omo_io import write_yaml_atomic
from .omo_redaction import redact_sensitive_text
from .omo_shared import load_yaml, load_yaml_docs

_REQUIRED_FIELDS = {
    "id",
    "title",
    "operation_level",
    "requested_by",
    "target",
    "changes",
    "change_summary",
    "impact",
    "verification_plan",
    "rollback_plan",
    "secret_refs",
    "trace_id",
}


def _utc_now() -> str:
    return (
        datetime.now(UTC)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def propose_truth_mutation(root: Path, proposal: dict, now: str) -> dict:
    missing = sorted(_REQUIRED_FIELDS - proposal.keys())
    if missing:
        raise ValueError(f"proposal missing required fields: {', '.join(missing)}")
    if _contains_secret_like_value(proposal):
        raise ValueError(
            "proposal contains secret-like raw values; use secret_refs instead"
        )

    payload = deepcopy(proposal)
    payload["status"] = "proposed"
    payload["requested_at"] = now
    payload["approved_at"] = None
    payload["applied_at"] = None
    payload["verified_at"] = None

    proposal_path = (
        root / ".omo" / "_truth" / "task-center" / "proposals" / f"{payload['id']}.yaml"
    )
    write_yaml_atomic(proposal_path, payload)
    return payload


def _load_yaml(path: Path) -> dict:
    return load_yaml(path)


def _proposal_path(root: Path, proposal_id: str) -> Path:
    return (
        root / ".omo" / "_truth" / "task-center" / "proposals" / f"{proposal_id}.yaml"
    )


def _contains_secret_like_value(value: object) -> bool:
    if isinstance(value, str):
        return redact_sensitive_text(value) != value
    if isinstance(value, dict):
        return any(_contains_secret_like_value(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_secret_like_value(item) for item in value)
    return False


def approve_truth_mutation(
    root: Path, proposal_id: str, approver: str, now: str
) -> dict:
    proposal_path = _proposal_path(root, proposal_id)
    proposal = _load_yaml(proposal_path)
    if proposal.get("status") != "proposed":
        raise ValueError(f"proposal {proposal_id} must be proposed before approve")

    proposal["status"] = "approved"
    proposal["approved_at"] = now
    proposal["approved_by"] = approver
    write_yaml_atomic(proposal_path, proposal)
    return proposal


def apply_truth_mutation(root: Path, proposal_id: str, now: str) -> dict:
    proposal_path = _proposal_path(root, proposal_id)
    proposal = _load_yaml(proposal_path)
    if proposal.get("status") != "approved":
        raise ValueError(f"proposal {proposal_id} must be approved before apply")

    target_path = root / proposal["target"]["ref"]
    target = _load_yaml(target_path)
    changes = proposal.get("changes", {}).get("set", {})
    target.update(changes)
    write_yaml_atomic(target_path, target)

    delivery_dir = (
        root / ".omo" / "_delivery" / "task-center" / "proposals" / proposal_id
    )
    apply_payload = {
        "proposal_id": proposal_id,
        "trace_id": proposal["trace_id"],
        "applied_at": now,
        "target_ref": proposal["target"]["ref"],
        "changed_keys": sorted(changes),
    }
    verify_payload = {
        "proposal_id": proposal_id,
        "trace_id": proposal["trace_id"],
        "verified_at": now,
        "status": "verified",
        "target_ref": proposal["target"]["ref"],
    }
    write_yaml_atomic(delivery_dir / "apply.yaml", apply_payload)
    write_yaml_atomic(delivery_dir / "verify.yaml", verify_payload)

    proposal["status"] = "verified"
    proposal["applied_at"] = now
    proposal["verified_at"] = now
    write_yaml_atomic(proposal_path, proposal)
    return proposal


def list_truth_mutations(root: Path) -> list[dict[str, str]]:
    proposals_dir = root / ".omo" / "_truth" / "task-center" / "proposals"
    rows: list[dict[str, str]] = []
    for path in sorted(proposals_dir.glob("*.yaml")):
        proposal = _load_yaml(path)
        rows.append(
            {
                "id": proposal["id"],
                "status": proposal["status"],
                "operation_level": proposal["operation_level"],
                "target_ref": proposal["target"]["ref"],
            }
        )
    return rows


def _load_payload_file(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.loads(text)
    return load_yaml_docs(text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="omo-governance")
    subparsers = parser.add_subparsers(dest="command", required=True)

    propose_parser = subparsers.add_parser("propose")
    propose_parser.add_argument("proposal_file")
    propose_parser.add_argument("--now")

    approve_parser = subparsers.add_parser("approve")
    approve_parser.add_argument("proposal_id")
    approve_parser.add_argument("--approver", required=True)
    approve_parser.add_argument("--now")

    apply_parser = subparsers.add_parser("apply")
    apply_parser.add_argument("proposal_id")
    apply_parser.add_argument("--now")

    subparsers.add_parser("list")

    ingress_goal_parser = subparsers.add_parser("ingress-goal")
    ingress_goal_parser.add_argument("goal_id")
    ingress_goal_parser.add_argument("title")
    ingress_goal_parser.add_argument("description")
    ingress_goal_parser.add_argument("--ingress-plane", required=True)
    ingress_goal_parser.add_argument("--source-ref", default="")
    ingress_goal_parser.add_argument("--extra-file")
    ingress_goal_parser.add_argument("--now")

    ingress_task_parser = subparsers.add_parser("ingress-task")
    ingress_task_parser.add_argument("task_file")
    ingress_task_parser.add_argument("--ingress-plane", required=True)
    ingress_task_parser.add_argument("--source-ref", default="")
    ingress_task_parser.add_argument("--now")

    ingress_debt_parser = subparsers.add_parser("ingress-debt")
    ingress_debt_parser.add_argument("debt_file")
    ingress_debt_parser.add_argument("--ingress-plane", required=True)
    ingress_debt_parser.add_argument("--source-ref", default="")
    ingress_debt_parser.add_argument("--now")

    surfaces_parser = subparsers.add_parser("surfaces")
    surfaces_parser.add_argument("--workspace-root", default=".")
    surfaces_parser.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    cwd = Path.cwd().resolve()
    if (cwd / ".omo").exists() and cwd.parent.name != "projects":
        root = cwd
    else:
        root = resolve_governance_workspace_root(cwd)

    if args.command == "propose":
        proposal = _load_yaml(Path(args.proposal_file))
        result = propose_truth_mutation(root, proposal, now=args.now or _utc_now())
        print(f"proposed {result['id']} status={result['status']}")
        return 0

    if args.command == "approve":
        result = approve_truth_mutation(
            root, args.proposal_id, approver=args.approver, now=args.now or _utc_now()
        )
        print(f"approved {result['id']} status={result['status']}")
        return 0

    if args.command == "apply":
        result = apply_truth_mutation(
            root, args.proposal_id, now=args.now or _utc_now()
        )
        print(f"applied {result['id']} status={result['status']}")
        return 0

    if args.command == "list":
        for row in list_truth_mutations(root):
            print(
                f"{row['id']} status={row['status']} level={row['operation_level']} target={row['target_ref']}"
            )
        return 0

    if args.command == "ingress-goal":
        extra_fields = (
            _load_payload_file(Path(args.extra_file)) if args.extra_file else None
        )
        result = create_goal(
            root / ".omo",
            goal_id=args.goal_id,
            title=args.title,
            description=args.description,
            ingress_plane=args.ingress_plane,
            source_ref=args.source_ref,
            extra_fields=extra_fields,
            now=args.now or _utc_now(),
        )
        print(f"ingress goal created {result['id']}")
        return 0

    if args.command == "ingress-task":
        task_data = _load_payload_file(Path(args.task_file))
        result = create_planned_task(
            root / ".omo",
            task_data=task_data,
            ingress_plane=args.ingress_plane,
            source_ref=args.source_ref,
            now=args.now or _utc_now(),
        )
        print(f"ingress task created {result['id']}")
        return 0

    if args.command == "ingress-debt":
        debt_data = _load_payload_file(Path(args.debt_file))
        result = upsert_debt_item(
            root / ".omo",
            debt_data=debt_data,
            ingress_plane=args.ingress_plane,
            source_ref=args.source_ref,
            now=args.now or _utc_now(),
        )
        print(f"ingress debt upserted {result['id']}")
        return 0

    if args.command == "surfaces":
        surface_args = ["--workspace-root", args.workspace_root]
        if args.json:
            surface_args.append("--json")
        return governance_surfaces_main(surface_args)

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
