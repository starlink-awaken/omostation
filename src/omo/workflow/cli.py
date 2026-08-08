from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .core import (
    REGISTRY_PATH,
    WorkflowError,
    changed_files_from_git,
    context_from_args,
    is_default_registry_path,
    load_registry,
    validate_agent_profile,
    workflow_by_id,
)
from .diagnostics import (
    build_status_report,
    build_verify_report,
    compliance_report,
    doctor,
    observe,
    print_compliance_report,
    print_status_report,
    print_verify_report,
)
from .info import (
    bootstrap_report,
    handoff_markdown,
    list_adapters,
    list_agents,
    list_integrations,
    list_workflows,
    print_bootstrap_report,
    suggest_command,
)
from .lifecycle import (
    claim_run,
    close_run,
    closeout_run,
    print_plan,
    prune_stale_locks,
    read_run,
    run_stage,
    scan_locks,
    spawn_run,
    start_run,
    trace_attribution,
    workflow_plan,
)
from .lint import lint_registry, print_lint


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run executable project governance workflows"
    )
    parser.add_argument(
        "--registry", default=str(REGISTRY_PATH), help="Workflow registry path"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_lint = sub.add_parser("lint", help="Validate the workflow registry")
    p_lint.add_argument("--json", action="store_true")

    p_doctor = sub.add_parser("doctor", help="Report optional adapter availability")
    p_doctor.add_argument("--json", action="store_true")

    p_observe = sub.add_parser(
        "observe", help="Read-only observer audit for workflow runs and locks"
    )
    p_observe.add_argument("run_id", nargs="?")
    p_observe.add_argument("--json", action="store_true")

    p_status = sub.add_parser(
        "status", help="Show AGCP run, lock, claim, compliance, and lane status"
    )
    p_status.add_argument("--json", action="store_true")
    p_status.add_argument(
        "--health", action="store_true", help="Include doctor health checks"
    )

    p_claim = sub.add_parser(
        "claim", help="Claim paths or governance surfaces for an active run"
    )
    p_claim.add_argument("run_id")
    p_claim.add_argument("--path", action="append", default=[])
    p_claim.add_argument("--surface", action="append", default=[])
    p_claim.add_argument("--actor", default=os.environ.get("USER", "agent"))
    p_claim.add_argument(
        "--affected-hash", default=None, help="Hash from affected-graph.py"
    )
    p_claim.add_argument("--force-lock", action="store_true")
    p_claim.add_argument("--json", action="store_true")

    p_verify = sub.add_parser(
        "verify", help="Select and optionally run checks for changed files"
    )
    p_verify.add_argument("run_id", nargs="?")
    p_verify.add_argument("--from-diff", action="store_true")
    p_verify.add_argument("--file", action="append", default=[])
    p_verify.add_argument("--include-untracked", action="store_true")
    p_verify.add_argument("--all", action="store_true", dest="all_checks")
    p_verify.add_argument("--execute", action="store_true")
    p_verify.add_argument("--json", action="store_true")

    p_compliance = sub.add_parser(
        "compliance", help="Audit run, lock, ledger, and evidence compliance"
    )
    p_compliance.add_argument("run_id", nargs="?")
    p_compliance.add_argument("--json", action="store_true")

    p_list = sub.add_parser("list", help="List workflows")
    p_list.add_argument("--json", action="store_true")

    p_agents = sub.add_parser("agents", help="List registered agent profiles")
    p_agents.add_argument("--json", action="store_true")

    p_adapters = sub.add_parser("adapters", help="List external adapter contracts")
    p_adapters.add_argument("--json", action="store_true")

    p_integrations = sub.add_parser(
        "integrations", help="List internal integration contracts"
    )
    p_integrations.add_argument("--json", action="store_true")

    p_bootstrap = sub.add_parser(
        "bootstrap", help="Show one-shot startup context for agents"
    )
    p_bootstrap.add_argument("--json", action="store_true")
    p_bootstrap.add_argument("--skip-health", action="store_true")

    p_context = sub.add_parser("context", help="Alias for bootstrap")
    p_context.add_argument("--json", action="store_true")
    p_context.add_argument("--skip-health", action="store_true")

    p_show = sub.add_parser("show", help="Show a workflow plan")
    p_show.add_argument("workflow_id")
    p_show.add_argument("--project", default="")
    p_show.add_argument("--format", default="openspec")
    p_show.add_argument("--source-file", default="")
    p_show.add_argument("--run-id", default="")
    p_show.add_argument("--profile", default="")
    p_show.add_argument("--json", action="store_true")

    p_run = sub.add_parser("run", help="Run or print a workflow stage")
    p_run.add_argument("workflow_id")
    p_run.add_argument("--stage", default="preflight")
    p_run.add_argument(
        "--execute", action="store_true", help="Actually run non-manual commands"
    )
    p_run.add_argument("--project", default="")
    p_run.add_argument("--format", default="openspec")
    p_run.add_argument("--source-file", default="")
    p_run.add_argument("--run-id", default="")
    p_run.add_argument("--profile", default="")
    p_run.add_argument("--json", action="store_true")

    p_start = sub.add_parser("start", help="Create a resumable workflow run record")
    p_start.add_argument("workflow_id")
    p_start.add_argument("--project", default="")
    p_start.add_argument("--format", default="openspec")
    p_start.add_argument("--source-file", default="")
    p_start.add_argument("--actor", default=os.environ.get("USER", "agent"))
    p_start.add_argument("--profile", default="")
    p_start.add_argument("--objective", default="")
    p_start.add_argument(
        "--bet",
        default="",
        help="Bet ID from 3y-bet-ledger.yaml to resolve objective automatically",
    )
    p_start.add_argument("--dry-run", action="store_true")
    p_start.add_argument("--force-lock", action="store_true")
    p_start.add_argument(
        "--parent-run",
        default="",
        help="Parent run ID for attribution chain tracking (T6-08)",
    )
    p_start.add_argument("--json", action="store_true")

    p_spawn = sub.add_parser(
        "spawn", help="Create a child run linked to a parent (attribution chain)"
    )
    p_spawn.add_argument("parent_run_id")
    p_spawn.add_argument("workflow_id")
    p_spawn.add_argument("--project", default="")
    p_spawn.add_argument("--format", default="openspec")
    p_spawn.add_argument("--source-file", default="")
    p_spawn.add_argument("--actor", default=os.environ.get("USER", "agent"))
    p_spawn.add_argument("--profile", default="")
    p_spawn.add_argument("--objective", default="")
    p_spawn.add_argument("--dry-run", action="store_true")
    p_spawn.add_argument("--force-lock", action="store_true")
    p_spawn.add_argument("--json", action="store_true")

    p_trace = sub.add_parser("trace", help="Trace the full attribution chain for a run")
    p_trace.add_argument("run_id")
    p_trace.add_argument("--json", action="store_true")

    p_resume = sub.add_parser("resume", help="Show a resumable run plan")
    p_resume.add_argument("run_id")
    p_resume.add_argument("--json", action="store_true")

    p_show_run = sub.add_parser("show-run", help="Show a run record")
    p_show_run.add_argument("run_id")
    p_show_run.add_argument("--json", action="store_true")

    p_handoff = sub.add_parser("handoff", help="Print a compression-safe handoff note")
    p_handoff.add_argument("run_id")
    p_handoff.add_argument("--json", action="store_true")

    p_close = sub.add_parser("close", help="Close a workflow run")
    p_close.add_argument("run_id")
    p_close.add_argument("--status", choices=["ok", "failed", "blocked"], required=True)
    p_close.add_argument(
        "--evidence",
        action="append",
        default=[],
        help="Evidence note (required when --status ok; ADR-0209 A1)",
    )
    p_close.add_argument("--keep-locks", action="store_true")
    p_close.add_argument("--json", action="store_true")

    p_closeout = sub.add_parser(
        "closeout", help="Verify, observe, record evidence, and close a run"
    )
    p_closeout.add_argument("run_id")
    p_closeout.add_argument(
        "--status", choices=["ok", "failed", "blocked"], default="ok"
    )
    p_closeout.add_argument("--evidence", action="append", default=[])
    p_closeout.add_argument("--from-diff", action="store_true")
    p_closeout.add_argument("--file", action="append", default=[])
    p_closeout.add_argument("--include-untracked", action="store_true")
    p_closeout.add_argument("--all", action="store_true", dest="all_checks")
    p_closeout.add_argument("--keep-locks", action="store_true")
    p_closeout.add_argument("--json", action="store_true")

    p_suggest = sub.add_parser(
        "suggest",
        help="Advisory workflow suggestion for a set of changed files (P74 stage 3).",
    )
    p_suggest.add_argument("--file", action="append", default=[])
    p_suggest.add_argument("--from-diff", action="store_true")
    p_suggest.add_argument("--include-untracked", action="store_true")
    p_suggest.add_argument("--profile", default="")
    p_suggest.add_argument("--json", action="store_true")

    p_prune = sub.add_parser(
        "prune-locks",
        help="Remove zombie locks (expired or stale heartbeat). T1-00 AC5/AC6.",
    )
    p_prune.add_argument("--json", action="store_true")
    p_prune.add_argument(
        "--scan-only",
        action="store_true",
        help="Only scan and report locks, do not prune",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        registry_path = Path(args.registry)
        registry = load_registry(registry_path)
        include_agcp_drift = is_default_registry_path(registry_path)
        if args.command == "lint":
            errors, warnings = lint_registry(registry, include_agcp_drift)
            print_lint(errors, warnings, args.json)
            return 0 if not errors else 1
        if args.command == "doctor":
            return doctor(registry, args.json, include_agcp_drift)
        if args.command == "observe":
            return observe(registry, args.run_id, args.json)
        if args.command == "status":
            report = build_status_report(registry, args.health, include_agcp_drift)
            print_status_report(report, args.json)
            return 0 if report["ok"] else 1
        if args.command == "prune-locks":
            if args.scan_only:
                locks = scan_locks(registry)
            else:
                locks = prune_stale_locks(registry)
            if args.json:
                print(json.dumps(locks, ensure_ascii=False, indent=2))
            else:
                if args.scan_only:
                    live = [e for e in locks if e["kind"] == "live"]
                    zombie = [e for e in locks if e["kind"] != "live"]
                    print(
                        f"locks: {len(locks)} total, {len(live)} live, {len(zombie)} zombie"
                    )
                    for entry in locks:
                        tag = "LIVE" if entry["kind"] == "live" else "ZOMBIE"
                        print(f"  [{tag}] {entry['path']} — {entry['detail']}")
                else:
                    print(f"pruned {len(locks)} zombie lock(s)")
                    for entry in locks:
                        print(f"  - {entry['path']} ({entry['kind']})")
            return 0
        if args.command == "claim":
            claim = claim_run(
                registry,
                args.run_id,
                args.actor,
                args.path,
                args.surface,
                args.force_lock,
                args.affected_hash,
            )
            if args.json:
                print(json.dumps(claim, ensure_ascii=False, indent=2))
            else:
                print(f"claimed {claim['run_id']}")
                for scope in claim["scopes"]:
                    print(f"- {scope}")
            return 0
        if args.command == "verify":
            report = build_verify_report(
                registry,
                args.run_id,
                args.file,
                args.from_diff,
                args.include_untracked,
                args.all_checks,
                args.execute,
            )
            print_verify_report(report, args.json)
            return 0 if report["ok"] else 1
        if args.command == "compliance":
            report = compliance_report(registry, args.run_id)
            print_compliance_report(report, args.json)
            return 0 if report["ok"] else 1
        if args.command == "list":
            list_workflows(registry, args.json)
            return 0
        if args.command == "agents":
            list_agents(registry, args.json)
            return 0
        if args.command == "adapters":
            list_adapters(registry, args.json)
            return 0
        if args.command == "integrations":
            list_integrations(registry, args.json)
            return 0
        if args.command in {"bootstrap", "context"}:
            report = bootstrap_report(
                registry, not args.skip_health, include_agcp_drift
            )
            print_bootstrap_report(report, args.json)
            return 0 if report["ok"] else 1
        if args.command == "suggest":
            files = list(args.file or [])
            if args.from_diff:
                files.extend(changed_files_from_git(args.include_untracked))
            return suggest_command(registry, files, args.profile, args.json)
        if args.command == "show":
            workflow = workflow_by_id(registry, args.workflow_id)
            context = context_from_args(args)
            validate_agent_profile(
                registry, workflow, context["profile"], require=False
            )
            print_plan(workflow_plan(workflow, context), args.json)
            return 0
        if args.command == "run":
            workflow = workflow_by_id(registry, args.workflow_id)
            context = context_from_args(args)
            validate_agent_profile(
                registry, workflow, context["profile"], require=args.execute
            )
            return run_stage(workflow, args.stage, context, args.execute, args.json)
        if args.command == "start":
            workflow = workflow_by_id(registry, args.workflow_id)
            objective = args.objective
            if getattr(args, "bet", None):
                bet_id = args.bet
                from ..omo_paths import WORKSPACE_ROOT
                import yaml

                ledger_file = WORKSPACE_ROOT / "docs/plans/3y-bet-ledger.yaml"
                if ledger_file.exists():
                    data = {}
                    for d in yaml.safe_load_all(
                        ledger_file.read_text(encoding="utf-8")
                    ):
                        if isinstance(d, dict):
                            data.update(d)
                    for item in data.get("bets", []):
                        if isinstance(item, dict) and item.get("id") == bet_id:
                            objective = f"[{bet_id}] {item.get('title', '')} (Appetite: {item.get('appetite', '')})"
                            break
            record = start_run(
                registry,
                workflow,
                context_from_args(args),
                objective,
                args.dry_run,
                args.force_lock,
                parent_run_id=getattr(args, "parent_run", "") or "",
            )
            if args.json:
                print(json.dumps(record, ensure_ascii=False, indent=2))
            else:
                print(f"started {record['run_id']}")
                if record.get("path"):
                    print(record["path"])
            return 0
        if args.command == "spawn":
            workflow = workflow_by_id(registry, args.workflow_id)
            record = spawn_run(
                registry,
                args.parent_run_id,
                workflow,
                context_from_args(args),
                args.objective or f"spawned from {args.parent_run_id}",
                args.dry_run,
                args.force_lock,
            )
            if args.json:
                print(json.dumps(record, ensure_ascii=False, indent=2))
            else:
                print(f"spawned {record['run_id']} from {args.parent_run_id}")
                if record.get("path"):
                    print(record["path"])
            return 0
        if args.command == "trace":
            chain = trace_attribution(registry, args.run_id)
            if args.json:
                print(json.dumps(chain, ensure_ascii=False, indent=2))
            else:
                if not chain:
                    print(f"no attribution chain found for {args.run_id}")
                    return 1
                print(f"attribution chain ({len(chain)} links):")
                for i, link in enumerate(chain):
                    prefix = "  root" if i == 0 else f"  [{i}]"
                    status = link.get("status", "")
                    actor = link.get("actor", "?")
                    profile = link.get("agent_profile", "?")
                    wid = link.get("workflow_id", "?")
                    rid = link.get("run_id", "?")
                    if status == "missing":
                        print(f"{prefix} {rid} — MISSING")
                    else:
                        print(
                            f"{prefix} {rid}  actor={actor}  profile={profile}  workflow={wid}  status={status}"
                        )
            return 0
        if args.command in {"resume", "show-run"}:
            _, payload = read_run(registry, args.run_id)
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                print_plan(payload["plan"], False)
            return 0
        if args.command == "handoff":
            _, payload = read_run(registry, args.run_id)
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                print(handoff_markdown(payload))
            return 0
        if args.command == "close":
            # ADR-0209 A1: status=ok requires at least one --evidence (protocol honesty)
            if args.status == "ok" and not args.evidence:
                raise WorkflowError(
                    "close --status ok requires --evidence (ADR-0209 A1; "
                    "use closeout for auto evidence, or pass --evidence <note>)"
                )
            payload = close_run(
                registry, args.run_id, args.status, args.evidence, not args.keep_locks
            )
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                print(f"closed {payload['run_id']} as {payload['status']}")
            return 0
        if args.command == "closeout":
            report = closeout_run(
                registry,
                args.run_id,
                args.status,
                args.evidence,
                args.file,
                args.from_diff or not args.file,
                args.include_untracked,
                args.all_checks,
                args.keep_locks,
            )
            if args.json:
                print(json.dumps(report, ensure_ascii=False, indent=2))
            else:
                print(
                    f"closeout {report['run']['run_id']} as {report['run']['status']}"
                )
                print(
                    f"verify checks={report['verify']['check_count']} ok={report['verify']['ok']}"
                )
                print(f"observe={report['observe']['decision']}")
            return 0 if report["ok"] else 1
    except WorkflowError as exc:
        print(f"agent-workflow: {exc}", file=sys.stderr)
        return 2
    return 2
