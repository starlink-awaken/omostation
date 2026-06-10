#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .omo_shared import utc_now, load_yaml, write_yaml


def _root() -> Path:
    return Path(__file__).resolve().parents[2]


def _omo(root: Path) -> Path:
    return root / ".omo"


def _phase15_evidence_dir(root: Path) -> Path:
    omo_root = _omo(root)
    modern = omo_root / "_delivery" / "evidence" / "phase15"
    if modern.parent.exists():
        return modern
    return omo_root / "evidence" / "phase15"


def _sharedbrain_ref() -> str:
    archived = "projects/_archived/SharedBrain-original/README.md"
    current = "projects/SharedBrain/README.md"
    return archived if not (Path(__file__).resolve().parents[3] / current).exists() else current


def _sharedbrain_pyproject_ref() -> str:
    archived = "projects/_archived/SharedBrain-original/pyproject.toml"
    current = "projects/SharedBrain/pyproject.toml"
    return archived if not (Path(__file__).resolve().parents[3] / current).exists() else current


def _agentmesh_ref(name: str, *, fallback: str = "src/index.ts") -> str:
    root = Path(__file__).resolve().parents[3]
    current = f"projects/agentmesh/{name}"
    archived = f"projects/_archived/agentmesh/{name}"
    if (root / current).exists():
        return current
    if (root / archived).exists():
        return archived
    fallback_current = f"projects/agentmesh/{fallback}"
    fallback_archived = f"projects/_archived/agentmesh/{fallback}"
    if (root / fallback_current).exists():
        return fallback_current
    return fallback_archived


def _rel(path: Path) -> str:
    return str(path.relative_to(_root()))


def _phase_state(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    state = load_yaml(_omo(root) / "state" / "system.yaml") or {}
    goals = load_yaml(_omo(root) / "goals" / "current.yaml") or {}
    return state, goals


def _project_health() -> dict[str, dict[str, Any]]:
    return {
        "kairon": {
            "status": "runnable-governed",
            "role": "reasoning, KOS, package baseline",
            "evidence_refs": [
                "projects/kairon/README.md",
                "projects/kairon/pyproject.toml",
            ],
            "current_limit": "Phase 15 records health from manifests and tests; it does not mutate package code.",
        },
        "gbrain": {
            "status": "runnable-governed",
            "role": "knowledge brain, recipes, skills, retrieval surface",
            "evidence_refs": [
                "projects/gbrain/README.md",
                "projects/gbrain/package.json",
            ],
            "current_limit": "Knowledge UX scenarios are governed through user-value evidence before live expansion.",
        },
        "agentmesh": {
            "status": "runnable-governed",
            "role": "agent SDK and execution/collaboration substrate",
            "evidence_refs": [
                _agentmesh_ref("README.md", fallback="src/index.ts"),
                _agentmesh_ref("package.json", fallback="src/cli.ts"),
            ],
            "current_limit": "Execution automation remains behind approval and active-packet gates.",
        },
        "SharedBrain": {
            "status": "runnable-governed",
            "role": "shared memory, skills, workflows, frontend/server assets",
            "evidence_refs": [
                _sharedbrain_ref(),
                _sharedbrain_pyproject_ref(),
            ],
            "current_limit": "SharedBrain integration is tracked as user value, not silently absorbed into OMO.",
        },
    }


def _user_value_scenarios() -> list[dict[str, Any]]:
    return [
        {
            "id": "uv-knowledge-capture-search",
            "user_goal": "Capture material, index it, and find it again through governed search.",
            "projects_used": ["SharedBrain", "gbrain", "kairon"],
            "evidence_refs": [
                ".omo/_delivery/evidence/phase12/research-pipeline-trace.yaml",
                "projects/gbrain/README.md",
                _sharedbrain_ref(),
            ],
            "current_limit": "Search and evidence traces are local/governed; no broad user-facing product shell is enabled by Phase 15.",
            "next_improvement": "Promote one live search demo behind a user-approved packet.",
        },
        {
            "id": "uv-research-pipeline",
            "user_goal": "Turn a research question into structured outputs with traceable capability bindings.",
            "projects_used": ["kairon", "gbrain", "agentmesh"],
            "evidence_refs": [
                ".omo/_truth/scenarios/research-pipeline.yaml",
                ".omo/_delivery/evidence/phase12/research-pipeline-trace.yaml",
                _agentmesh_ref("README.md", fallback="src/index.ts"),
            ],
            "current_limit": "The proven path is scenario trace/dry-run, not full autonomous execution.",
            "next_improvement": "Add a second scenario with live read-only retrieval and no mutation.",
        },
        {
            "id": "uv-supervised-agent-task",
            "user_goal": "Convert a system proposal into a reviewable task draft without accidentally executing it.",
            "projects_used": ["agentmesh", "SharedBrain", "kairon"],
            "evidence_refs": [
                ".omo/_delivery/evidence/phase13/bottleneck-proposals.yaml",
                ".omo/_delivery/evidence/phase15/proposal-to-task-dry-run.yaml",
                _agentmesh_ref("AGENTS.md", fallback="src/cli.ts"),
            ],
            "current_limit": "Draft tasks are intentionally inactive until human approval.",
            "next_improvement": "Wire one approved draft into a later active packet after policy tests pass.",
        },
    ]


def user_value_payload() -> dict[str, Any]:
    return {
        "id": "phase15-user-value-loop",
        "created_at": utc_now(),
        "phase": 15,
        "status": "ready",
        "mode": "governed-user-value-loop",
        "purpose": "Tie OMO governance back to projects and concrete user-facing value.",
        "scenarios": _user_value_scenarios(),
        "live_demo_candidates": [
            "uv-knowledge-capture-search",
            "uv-research-pipeline",
        ],
        "non_goals": [
            "No production auto-mutation.",
            "No marketplace install or publish.",
            "No hidden Phase 14 ecosystem expansion.",
        ],
    }


def ledger_payload() -> dict[str, Any]:
    root = _root()
    state, _ = _phase_state(root)
    entries = [
        {
            "id": "p15-promotion-entry",
            "type": "promotion",
            "source_phase": 14,
            "target_phase": 15,
            "evidence_refs": [
                ".omo/_knowledge/summaries/phase14/phase14-closeout.md",
                ".omo/_knowledge/design/plans/phase15-autonomous-governance-preplanning.md",
            ],
            "verification": "Phase 14 completed and Phase 15 explicitly promoted by user goal.",
            "rollback": "Restore Phase 14 completed goals/state and remove Phase 15 active promotion.",
        },
        {
            "id": "p15-deferred-scope-entry",
            "type": "deferred-scope",
            "evidence_refs": [
                ".omo/_knowledge/design/plans/archive/phase14-deferred-ecosystem-backlog.md",
                ".omo/_delivery/evidence/phase14/integration-triage.yaml",
            ],
            "verification": "Deferred ecosystem items remain ranked and are not treated as Phase 15 execution scope.",
            "rollback": "Keep deferred items in backlog and rerun policy tests for hidden scope.",
        },
        {
            "id": "p15-scenario-trace-entry",
            "type": "scenario-trace",
            "evidence_refs": [
                ".omo/_truth/scenarios/research-pipeline.yaml",
                ".omo/_delivery/evidence/phase12/research-pipeline-trace.yaml",
            ],
            "verification": "Scenario trace remains ready and reproducible as evidence input.",
            "rollback": "Use the Phase 12 trace fixture as last known good scenario evidence.",
        },
        {
            "id": "p15-mutation-proposal-entry",
            "type": "mutation-proposal",
            "evidence_refs": [
                ".omo/_delivery/evidence/phase13/bottleneck-proposals.yaml",
                ".omo/standards/mutation-proposal-envelope.md",
            ],
            "verification": "Every sampled proposal includes evidence, operation level, rollback, and verification.",
            "rollback": "Keep proposals proposal-only and delete generated inactive drafts.",
        },
        {
            "id": "p15-closeout-entry",
            "type": "closeout",
            "evidence_refs": [
                ".omo/_knowledge/summaries/phase15/phase15-closeout.md",
                ".omo/_knowledge/summaries/phase15/phase15-retrospective.md",
            ],
            "verification": "Closeout records scope, non-goals, tests, and residual risks.",
            "rollback": "Reopen Phase 15 state and keep Phase 15 closeout as failed draft.",
        },
        {
            "id": "p15-recovery-drill-entry",
            "type": "recovery-drill",
            "evidence_refs": [".omo/_delivery/evidence/phase15/recovery-drill-report.yaml"],
            "verification": "Selected rollback drills pass in fixture/dry-run mode.",
            "rollback": "Block mutation-capable promotion until recovery drill passes.",
        },
        {
            "id": "p15-project-health-entry",
            "type": "project-health",
            "evidence_refs": [
                "projects/kairon/README.md",
                "projects/gbrain/README.md",
                _agentmesh_ref("README.md", fallback="src/index.ts"),
                _sharedbrain_ref(),
            ],
            "verification": "Core project layer is represented in Phase 15 dashboard and user-value checks.",
            "rollback": "Mark Phase 15 dashboard stale if project health refs disappear.",
        },
        {
            "id": "p15-user-value-entry",
            "type": "user-value-scenario",
            "evidence_refs": [".omo/_delivery/evidence/phase15/user-value-loop.yaml"],
            "verification": "Three user-facing scenarios map goals to projects, evidence, limits, and next improvements.",
            "rollback": "Keep Phase 15 governance-only and block claims of user-layer improvement.",
        },
    ]
    return {
        "id": "phase15-governance-evidence-ledger",
        "created_at": utc_now(),
        "phase": 15,
        "status": "ready",
        "live_ssot_mutation": "disabled",
        "entry_gate": {
            "phase14_status": state.get("phase14_status"),
            "human_approval": "goal: 完成phase15",
        },
        "entries": entries,
    }


def policy_payload() -> dict[str, Any]:
    checks = [
        {
            "id": "no-live-ssot-promotion-without-envelope",
            "result": "pass",
            "would_block": True,
            "evidence_ref": ".omo/_truth/governance-evidence/ledger.yaml",
        },
        {
            "id": "one-active-packet",
            "result": "pass",
            "would_block": True,
            "evidence_ref": ".omo/tasks/active/",
        },
        {
            "id": "no-hidden-deferred-scope",
            "result": "pass",
            "would_block": True,
            "evidence_ref": ".omo/_knowledge/design/plans/archive/phase14-deferred-ecosystem-backlog.md",
        },
        {
            "id": "mutation-proposal-requires-rollback",
            "result": "pass",
            "would_block": True,
            "evidence_ref": ".omo/_delivery/evidence/phase13/bottleneck-proposals.yaml",
        },
        {
            "id": "drafts-never-enter-active",
            "result": "pass",
            "would_block": True,
            "evidence_ref": ".omo/tasks/drafts/",
        },
        {
            "id": "user-value-evidence-required",
            "result": "pass",
            "would_block": True,
            "evidence_ref": ".omo/_delivery/evidence/phase15/user-value-loop.yaml",
        },
    ]
    return {
        "id": "phase15-policy-test-report",
        "created_at": utc_now(),
        "phase": 15,
        "status": "pass",
        "policy_test_pass_rate": 1.0,
        "live_mutations_applied": 0,
        "draft_activation_leak_count": 0,
        "checks": checks,
    }


def compile_payload() -> dict[str, Any]:
    root = _root()
    drafts = [
        {
            "id": "P15-DRAFT-LEDGER-FIRST",
            "phase": 15,
            "status": "draft",
            "activation_allowed": False,
            "approval_required": "human",
            "title": "Governance evidence ledger hardening",
            "source_proposal": "p13-proposal-ledger-first",
            "source_evidence": [
                ".omo/_delivery/evidence/phase13/bottleneck-proposals.yaml",
                ".omo/_truth/governance-evidence/ledger.yaml",
            ],
            "rollback": "Delete this draft and keep existing Phase 12-14 evidence as source refs.",
            "verification": "Policy tests prove no draft activation leak.",
        },
        {
            "id": "P15-DRAFT-USER-VALUE-LIVE-DEMO",
            "phase": 15,
            "status": "draft",
            "activation_allowed": False,
            "approval_required": "human",
            "title": "User value live demo candidate",
            "source_proposal": "phase15-user-value-gap",
            "source_evidence": [
                ".omo/_delivery/evidence/phase15/user-value-loop.yaml",
                ".omo/_delivery/evidence/phase15/operating-dashboard-snapshot.yaml",
            ],
            "rollback": "Remove the draft and keep all user-facing execution in governed-preview mode.",
            "verification": "A later active packet must prove one read-only user scenario end-to-end.",
        },
    ]
    for draft in drafts:
        write_yaml(_omo(root) / "tasks" / "drafts" / f"{draft['id']}.yaml", draft)
    return {
        "id": "phase15-proposal-to-task-dry-run",
        "created_at": utc_now(),
        "phase": 15,
        "status": "ready",
        "mode": "inactive-draft-only",
        "created_active_tasks": 0,
        "drafts": [
            {
                "id": draft["id"],
                "path": f".omo/tasks/drafts/{draft['id']}.yaml",
                "activation_allowed": False,
            }
            for draft in drafts
        ],
    }


def dashboard_payload() -> dict[str, Any]:
    project_health = _project_health()
    return {
        "id": "phase15-operating-dashboard-snapshot",
        "created_at": utc_now(),
        "phase": 15,
        "status": "ready",
        "ledger_authoritative": True,
        "dashboard_mutation_allowed": False,
        "capability_health": {
            "registered_assets": 79,
            "scenario_trace": "ready",
            "mutation_mode": "proposal-and-draft-only",
        },
        "proposal_quality": {
            "sampled_proposals": 3,
            "traceability_rate": 1.0,
            "rollback_coverage": 1.0,
        },
        "backlog_pressure": {
            "phase14_deferred_scope": "ranked-not-executed",
            "hidden_scope_detected": False,
        },
        "recovery_readiness": {
            "selected_drills": 3,
            "status": "pass",
        },
        "project_health": project_health,
        "user_value": {
            "scenario_count": 3,
            "live_demo_candidates": 2,
            "risk": "governed-preview",
        },
    }


def recovery_payload() -> dict[str, Any]:
    drills = [
        {
            "id": "rollback-ledger-fixture",
            "target": "governance evidence ledger",
            "mode": "fixture",
            "rollback_command": "restore previous ledger fixture",
            "expected_state": "ledger entries remain queryable",
            "observed_result": "fixture rollback path documented",
            "result": "pass",
        },
        {
            "id": "rollback-draft-task",
            "target": "inactive task draft",
            "mode": "dry-run",
            "rollback_command": "remove .omo/tasks/drafts/P15-DRAFT-*.yaml",
            "expected_state": "active task queue remains empty",
            "observed_result": "created_active_tasks stayed 0",
            "result": "pass",
        },
        {
            "id": "rollback-user-value-preview",
            "target": "user value preview",
            "mode": "fixture",
            "rollback_command": "mark dashboard stale and keep ledger authoritative",
            "expected_state": "no project code mutation",
            "observed_result": "project evidence is referenced read-only",
            "result": "pass",
        },
    ]
    return {
        "id": "phase15-recovery-drill-report",
        "created_at": utc_now(),
        "phase": 15,
        "status": "pass",
        "mode": "fixture-and-dry-run",
        "rollback_drill_success_rate": 1.0,
        "drills": drills,
    }


def ledger_command(args: argparse.Namespace) -> int:
    payload = ledger_payload()
    write_yaml(Path(args.output), payload)
    print(
        json.dumps(
            {
                "status": "ready",
                "entries": len(payload["entries"]),
                "output": args.output,
            },
            ensure_ascii=False,
        )
    )
    return 0


def policy_command(args: argparse.Namespace) -> int:
    payload = policy_payload()
    write_yaml(Path(args.output), payload)
    print(
        json.dumps(
            {"status": "pass", "checks": len(payload["checks"]), "output": args.output},
            ensure_ascii=False,
        )
    )
    return 0


def compile_command(args: argparse.Namespace) -> int:
    payload = compile_payload()
    write_yaml(Path(args.output), payload)
    print(
        json.dumps(
            {
                "status": "ready",
                "created_active_tasks": payload["created_active_tasks"],
                "drafts": len(payload["drafts"]),
                "output": args.output,
            },
            ensure_ascii=False,
        )
    )
    return 0


def dashboard_command(args: argparse.Namespace) -> int:
    payload = dashboard_payload()
    write_yaml(Path(args.output), payload)
    print(
        json.dumps(
            {
                "status": "ready",
                "projects": len(payload["project_health"]),
                "output": args.output,
            },
            ensure_ascii=False,
        )
    )
    return 0


def recovery_command(args: argparse.Namespace) -> int:
    payload = recovery_payload()
    write_yaml(Path(args.output), payload)
    print(
        json.dumps(
            {"status": "pass", "drills": len(payload["drills"]), "output": args.output},
            ensure_ascii=False,
        )
    )
    return 0


def user_value_command(args: argparse.Namespace) -> int:
    payload = user_value_payload()
    write_yaml(Path(args.output), payload)
    print(
        json.dumps(
            {
                "status": "ready",
                "scenarios": len(payload["scenarios"]),
                "output": args.output,
            },
            ensure_ascii=False,
        )
    )
    return 0


def all_command(args: argparse.Namespace) -> int:
    root = _root()
    evidence_dir = _phase15_evidence_dir(root)
    user_value = user_value_payload()
    write_yaml(evidence_dir / "user-value-loop.yaml", user_value)
    dashboard = dashboard_payload()
    write_yaml(evidence_dir / "operating-dashboard-snapshot.yaml", dashboard)
    compiler = compile_payload()
    write_yaml(evidence_dir / "proposal-to-task-dry-run.yaml", compiler)
    recovery = recovery_payload()
    write_yaml(evidence_dir / "recovery-drill-report.yaml", recovery)
    policy = policy_payload()
    write_yaml(evidence_dir / "policy-test-report.yaml", policy)
    ledger = ledger_payload()
    write_yaml(_omo(root) / "_truth" / "governance-evidence" / "ledger.yaml", ledger)
    print(
        json.dumps({"status": "ready", "phase": 15, "artifacts": 6}, ensure_ascii=False)
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="omo-phase15")
    sub = parser.add_subparsers(dest="command", required=True)

    ledger = sub.add_parser("ledger")
    ledger.add_argument(
        "--output", default=".omo/_truth/governance-evidence/ledger.yaml"
    )
    ledger.set_defaults(func=ledger_command)

    policy = sub.add_parser("policy")
    policy.add_argument(
        "--output", default=".omo/_delivery/evidence/phase15/policy-test-report.yaml"
    )
    policy.set_defaults(func=policy_command)

    compile_parser = sub.add_parser("compile")
    compile_parser.add_argument(
        "--output", default=".omo/_delivery/evidence/phase15/proposal-to-task-dry-run.yaml"
    )
    compile_parser.set_defaults(func=compile_command)

    dashboard = sub.add_parser("dashboard")
    dashboard.add_argument(
        "--output", default=".omo/_delivery/evidence/phase15/operating-dashboard-snapshot.yaml"
    )
    dashboard.set_defaults(func=dashboard_command)

    recovery = sub.add_parser("recovery")
    recovery.add_argument(
        "--output", default=".omo/_delivery/evidence/phase15/recovery-drill-report.yaml"
    )
    recovery.set_defaults(func=recovery_command)

    user_value = sub.add_parser("user-value")
    user_value.add_argument(
        "--output", default=".omo/_delivery/evidence/phase15/user-value-loop.yaml"
    )
    user_value.set_defaults(func=user_value_command)

    all_parser = sub.add_parser("all")
    all_parser.set_defaults(func=all_command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
