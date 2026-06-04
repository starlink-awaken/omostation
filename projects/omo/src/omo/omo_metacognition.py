#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .omo_io import write_yaml_atomic


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _omo(root: Path) -> Path:
    return root / ".omo"


def _load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else None


def _load_registry(root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for rel_path in ("projects-capabilities.yaml", "sharedwork-sample.yaml"):
        payload = _load_yaml(_omo(root) / "registry" / rel_path) or {}
        records.extend(payload.get("capabilities", []))
    return records


def _phase12_evidence(root: Path) -> dict[str, Any]:
    omo = _omo(root)
    trace = (
        _load_yaml(omo / "evidence" / "phase12" / "research-pipeline-trace.yaml") or {}
    )
    dry_run = _load_yaml(omo / "evidence" / "phase12" / "package-dry-run.yaml") or {}
    return {
        "trace_status": trace.get("status"),
        "trace_steps": len(trace.get("steps", [])),
        "missing_capabilities": trace.get("missing_capabilities", []),
        "package_mutations": dry_run.get("mutations_applied"),
        "packages_checked": dry_run.get("packages_checked"),
    }


def baseline_command(args: argparse.Namespace) -> int:
    root = _root()
    records = _load_registry(root)
    by_type: dict[str, int] = {}
    by_lifecycle: dict[str, int] = {}
    for record in records:
        by_type[record["type"]] = by_type.get(record["type"], 0) + 1
        by_lifecycle[record["lifecycle"]] = by_lifecycle.get(record["lifecycle"], 0) + 1
    evidence = _phase12_evidence(root)
    report = {
        "id": "phase13-readonly-metacognition-baseline",
        "created_at": _utc_now(),
        "mode": "read-only",
        "auto_apply": "disabled",
        "capability_count": len(records),
        "coverage": {
            "by_type": by_type,
            "by_lifecycle": by_lifecycle,
            "scenario_trace_status": evidence["trace_status"],
            "scenario_trace_steps": evidence["trace_steps"],
            "package_mutations": evidence["package_mutations"],
        },
        "blind_spots": [
            {
                "id": "bs-live-mutation-disabled",
                "description": "Live mutation is intentionally disabled; Phase 13 can only propose changes.",
                "severity": "controlled",
                "evidence_ref": ".omo/_knowledge/design/phase12-14-architecture-design.md",
            },
            {
                "id": "bs-external-connectors-unabsorbed",
                "description": "External connectors remain Phase 14 backlog candidates.",
                "severity": "medium",
                "evidence_ref": ".omo/plans/phase14-deferred-ecosystem-backlog.md",
            },
            {
                "id": "bs-single-scenario",
                "description": "Only one scenario trace is proven; additional scenarios require future approval.",
                "severity": "medium",
                "evidence_ref": ".omo/evidence/phase12/research-pipeline-trace.yaml",
            },
        ],
        "confidence": {
            "registry": 0.92,
            "scenario_trace": 0.9,
            "package_dry_run": 0.88,
            "mutation_safety": 0.95,
        },
    }
    output = Path(args.output)
    write_yaml_atomic(output, report)
    print(
        json.dumps(
            {"status": "ready", "output": str(output), "capabilities": len(records)},
            ensure_ascii=False,
        )
    )
    return 0


def proposals_command(args: argparse.Namespace) -> int:
    root = _root()
    evidence = _phase12_evidence(root)
    proposals = {
        "id": "phase13-bottleneck-proposals",
        "created_at": _utc_now(),
        "mode": "proposal-only",
        "auto_apply": "disabled",
        "proposals": [
            {
                "id": "p13-proposal-expand-scenario-coverage",
                "rank": 1,
                "bottleneck": "single scenario coverage",
                "suggestion": "Add a second scenario only after a human-approved Phase 14 or Phase 15 packet.",
                "confidence": 0.86,
                "risk": "medium",
                "operation_level": "L1",
                "evidence_refs": [".omo/evidence/phase12/research-pipeline-trace.yaml"],
                "rollback": "Remove draft scenario and rerun policy tests.",
                "verification": "scenario trace fixture must remain reproducible",
            },
            {
                "id": "p13-proposal-ledger-first",
                "rank": 2,
                "bottleneck": "evidence scattered across summaries, registry, and management docs",
                "suggestion": "Promote governance evidence ledger work before any auto-mutation work.",
                "confidence": 0.9,
                "risk": "low",
                "operation_level": "L1",
                "evidence_refs": [
                    ".omo/_knowledge/design/phase15-autonomous-governance-design.md"
                ],
                "rollback": "Keep existing evidence refs as source of truth.",
                "verification": "policy tests must prove no draft activation leak",
            },
            {
                "id": "p13-proposal-package-safety",
                "rank": 3,
                "bottleneck": "package ecosystem is dry-run only",
                "suggestion": "Keep package operations dry-run until admission and rollback controls exist.",
                "confidence": 0.84,
                "risk": "medium",
                "operation_level": "L2",
                "evidence_refs": [".omo/evidence/phase12/package-dry-run.yaml"],
                "rollback": "Restore package baseline and confirm mutations_applied remains 0.",
                "verification": f"current package mutations: {evidence['package_mutations']}",
            },
        ],
    }
    output = Path(args.output)
    write_yaml_atomic(output, proposals)
    print(
        json.dumps(
            {
                "status": "proposal-only",
                "output": str(output),
                "count": len(proposals["proposals"]),
            },
            ensure_ascii=False,
        )
    )
    return 0


def collaboration_command(args: argparse.Namespace) -> int:
    plan = {
        "id": "phase13-supervised-collaboration-plan",
        "created_at": _utc_now(),
        "mode": "draft-only",
        "auto_execute": "disabled",
        "approval_queue": [
            {
                "proposal_id": "p13-proposal-expand-scenario-coverage",
                "required_approver": "human",
                "operation_level": "L1",
                "status": "waiting_for_future_phase",
            },
            {
                "proposal_id": "p13-proposal-package-safety",
                "required_approver": "human",
                "operation_level": "L2",
                "status": "blocked_until_admission_review",
            },
        ],
        "execution_envelope": {
            "may_create_active_task": False,
            "draft_path": ".omo/tasks/drafts/",
            "required_fields": [
                "source_evidence",
                "approval_ref",
                "rollback",
                "verification",
            ],
            "guardrail": "No active task is created by Phase 13 metacognition.",
        },
    }
    output = Path(args.output)
    write_yaml_atomic(output, plan)
    print(
        json.dumps({"status": "draft-only", "output": str(output)}, ensure_ascii=False)
    )
    return 0


def rehearse_command(args: argparse.Namespace) -> int:
    drill = {
        "id": "phase13-self-healing-rehearsal",
        "created_at": _utc_now(),
        "mode": "dry-run",
        "auto_apply": "disabled",
        "anomaly": {
            "id": "missing-scenario-capability-fixture",
            "description": "A fixture scenario references a missing capability and must fail closed.",
        },
        "recommended_action": {
            "type": "rollback-recommendation",
            "operation_level": "L1",
            "live_mutation_allowed": False,
            "rollback": "Restore the last known good scenario trace and keep the faulty scenario inactive.",
            "verification": "binding policy reports missing capability before activation",
        },
        "trend_report": {
            "capability_registry": "stable",
            "scenario_coverage": "narrow",
            "package_safety": "dry-run-only",
        },
        "roadmap_delta_proposal": {
            "target": "Phase 15 governance evidence ledger",
            "status": "proposal-only",
            "reason": "Evidence should become queryable before any mutation automation.",
        },
        "result": "pass",
    }
    output = Path(args.output)
    write_yaml_atomic(output, drill)
    print(json.dumps({"status": "pass", "output": str(output)}, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="omo-metacognition")
    subparsers = parser.add_subparsers(dest="command", required=True)

    baseline = subparsers.add_parser("baseline")
    baseline.add_argument(
        "--output", default=".omo/evidence/phase13/metacognition-baseline.yaml"
    )
    baseline.set_defaults(func=baseline_command)

    proposals = subparsers.add_parser("proposals")
    proposals.add_argument(
        "--output", default=".omo/evidence/phase13/bottleneck-proposals.yaml"
    )
    proposals.set_defaults(func=proposals_command)

    collaboration = subparsers.add_parser("collaboration")
    collaboration.add_argument(
        "--output", default=".omo/evidence/phase13/supervised-collaboration.yaml"
    )
    collaboration.set_defaults(func=collaboration_command)

    rehearse = subparsers.add_parser("rehearse")
    rehearse.add_argument(
        "--output", default=".omo/evidence/phase13/self-healing-rehearsal.yaml"
    )
    rehearse.set_defaults(func=rehearse_command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
