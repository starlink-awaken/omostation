#!/usr/bin/env python3
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import yaml

try:
    from .omo_io import write_yaml_atomic
    from .omo_redaction import redact_sensitive_text
except ModuleNotFoundError:
    from .omo_io import write_yaml_atomic
    from .omo_redaction import redact_sensitive_text


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
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def propose_truth_mutation(root: Path, proposal: dict, now: str) -> dict:
    missing = sorted(_REQUIRED_FIELDS - proposal.keys())
    if missing:
        raise ValueError(f"proposal missing required fields: {', '.join(missing)}")
    if _contains_secret_like_value(proposal):
        raise ValueError("proposal contains secret-like raw values; use secret_refs instead")

    payload = deepcopy(proposal)
    payload["status"] = "proposed"
    payload["requested_at"] = now
    payload["approved_at"] = None
    payload["applied_at"] = None
    payload["verified_at"] = None

    proposal_path = root / ".omo" / "_truth" / "task-center" / "proposals" / f"{payload['id']}.yaml"
    write_yaml_atomic(proposal_path, payload)
    return payload


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _proposal_path(root: Path, proposal_id: str) -> Path:
    return root / ".omo" / "_truth" / "task-center" / "proposals" / f"{proposal_id}.yaml"


def _contains_secret_like_value(value: object) -> bool:
    if isinstance(value, str):
        return redact_sensitive_text(value) != value
    if isinstance(value, dict):
        return any(_contains_secret_like_value(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_secret_like_value(item) for item in value)
    return False


def approve_truth_mutation(root: Path, proposal_id: str, approver: str, now: str) -> dict:
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

    delivery_dir = root / ".omo" / "_delivery" / "task-center" / "proposals" / proposal_id
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


def main() -> int:
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

    args = parser.parse_args()
    root = Path.cwd()

    if args.command == "propose":
        proposal = _load_yaml(Path(args.proposal_file))
        result = propose_truth_mutation(root, proposal, now=args.now or _utc_now())
        print(f"proposed {result['id']} status={result['status']}")
        return 0

    if args.command == "approve":
        result = approve_truth_mutation(root, args.proposal_id, approver=args.approver, now=args.now or _utc_now())
        print(f"approved {result['id']} status={result['status']}")
        return 0

    if args.command == "apply":
        result = apply_truth_mutation(root, args.proposal_id, now=args.now or _utc_now())
        print(f"applied {result['id']} status={result['status']}")
        return 0

    if args.command == "list":
        for row in list_truth_mutations(root):
            print(f"{row['id']} status={row['status']} level={row['operation_level']} target={row['target_ref']}")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
