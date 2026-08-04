from __future__ import annotations

import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .core import (
    REGISTRY_PATH,
    WORKSPACE,
    WorkflowError,
    adapter_rows,
    changed_files_from_git,
    command_display,
    display_path,
    integration_rows,
    ledger_path,
    normalize_repo_path,
    path_matches,
    substitute,
)
from .lifecycle import (
    append_ledger_event,
    claim_coverage_report,
    claim_policy,
    heal_ledger_for_run,
    ledger_mentions_run,
    load_lock_records,
    load_run_records,
    read_run,
    recommended_next,
    staged_lane_report,
)
from .lint import agcp_drift_check, diff_check_rows


def run_check_command(check: dict[str, Any], context: dict[str, str]) -> dict[str, Any]:
    command = substitute(check["command"], context)
    # Honor both cwd and legacy workdir (ADR-0209 A3: workdir was ignored → omo.cli ModuleNotFound)
    cwd_raw = check.get("cwd") or check.get("workdir") or "."
    cwd = WORKSPACE / substitute([cwd_raw], context)[0]
    env = os.environ.copy()
    matched_files = check.get("matched_files", [])
    if matched_files:
        env["AGENT_WORKFLOW_MATCHED_FILES"] = json.dumps(
            matched_files, ensure_ascii=False
        )
    allowed_lanes = check.get("allowed_lanes") or []
    if matched_files and allowed_lanes:
        env["AGENT_WORKFLOW_ALLOWED_LANES"] = ",".join(
            str(item) for item in allowed_lanes
        )
    started = time.monotonic()
    completed = subprocess_run(command, cwd=cwd, env=env)
    duration_s = round(time.monotonic() - started, 3)
    stdout = completed.stdout[-4000:] if completed.stdout else ""
    stderr = completed.stderr[-4000:] if completed.stderr else ""
    return {
        "id": check["id"],
        "description": check.get("description", ""),
        "required": bool(check.get("required", True)),
        "command": command_display(command),
        "cwd": str(cwd.relative_to(WORKSPACE))
        if cwd.is_relative_to(WORKSPACE)
        else str(cwd),
        "returncode": completed.returncode,
        "duration_s": duration_s,
        "ok": completed.returncode == 0 or not check.get("required", True),
        "stdout_tail": stdout,
        "stderr_tail": stderr,
        "matched_files": matched_files,
        "allowed_lanes": allowed_lanes,
    }


def subprocess_run(command: list[str], cwd: Path, env: dict[str, str]) -> Any:
    # Helper to execute subprocess
    import subprocess

    return subprocess.run(
        command, cwd=cwd, env=env, capture_output=True, text=True, check=False
    )


def select_diff_checks(
    registry: dict[str, Any],
    files: list[str],
    all_checks: bool,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for check in diff_check_rows(registry):
        patterns = check["paths"]
        matched_files = sorted(file for file in files if path_matches(patterns, file))
        if all_checks or check["always"] or matched_files:
            selected.append({**check, "matched_files": matched_files})
    return selected


def build_verify_report(
    registry: dict[str, Any],
    run_id: str | None,
    files: list[str],
    from_diff: bool,
    include_untracked: bool,
    all_checks: bool,
    execute: bool,
) -> dict[str, Any]:
    if from_diff:
        files = [*files, *changed_files_from_git(include_untracked)]
    normalized_files = sorted({normalize_repo_path(item) for item in files})
    if not from_diff and not normalized_files and not all_checks:
        raise WorkflowError("verify requires --from-diff, --file, or --all")
    context: dict[str, str] = {"run_id": run_id or ""}
    if run_id:
        _, run_payload = read_run(registry, run_id)
        context.update(
            {
                str(key): str(value)
                for key, value in (run_payload.get("context") or {}).items()
            }
        )
    checks = select_diff_checks(registry, normalized_files, all_checks)
    results: list[dict[str, Any]] = []
    for check in checks:
        if execute:
            result = run_check_command(check, context)
        else:
            result = {
                "id": check["id"],
                "description": check.get("description", ""),
                "required": bool(check.get("required", True)),
                "command": command_display(substitute(check["command"], context)),
                "cwd": check.get("cwd", "."),
                "matched_files": check.get("matched_files", []),
                "skipped": True,
                "ok": True,
            }
        results.append(result)
    claim_coverage = claim_coverage_report(registry, run_id, normalized_files)
    ok = all(result.get("ok", False) for result in results) and bool(
        claim_coverage["ok"]
    )
    report = {
        "ok": ok,
        "run_id": run_id,
        "from_diff": from_diff,
        "include_untracked": include_untracked,
        "execute": execute,
        "changed_files": normalized_files,
        "claim_coverage": claim_coverage,
        "check_count": len(results),
        "checks": results,
    }
    if run_id:
        append_ledger_event(
            registry,
            {
                "event": "agent_workflow_verify",
                "run_id": run_id,
                "ok": ok,
                "execute": execute,
                "from_diff": from_diff,
                "changed_files": normalized_files,
                "claim_coverage": {
                    "mode": claim_coverage.get("mode"),
                    "ok": claim_coverage.get("ok"),
                    "missing_files": claim_coverage.get("missing_files"),
                },
                "checks": [
                    {
                        "id": item.get("id"),
                        "ok": item.get("ok"),
                        "required": item.get("required"),
                        "returncode": item.get("returncode"),
                        "duration_s": item.get("duration_s"),
                    }
                    for item in results
                ],
            },
        )
    return report


def print_verify_report(report: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    mode = "executed" if report["execute"] else "planned"
    print(f"agent-workflow verify: {'ok' if report['ok'] else 'failed'} ({mode})")
    print(f"files={len(report['changed_files'])} checks={report['check_count']}")
    claim_coverage = report.get("claim_coverage")
    if isinstance(claim_coverage, dict):
        for warning in claim_coverage.get("warnings") or []:
            print(f"[WARN] claim_policy: {warning}")
    for result in report["checks"]:
        status = (
            "PASS"
            if result.get("ok") and not result.get("skipped")
            else "SKIP"
            if result.get("skipped")
            else "FAIL"
        )
        print(f"[{status}] {result['id']} :: {result['command']}")


def parse_utc_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def build_observe_report(
    registry: dict[str, Any], run_id: str | None
) -> dict[str, Any]:
    runs = load_run_records(registry)
    locks = load_lock_records(registry)
    now = datetime.now(UTC)
    findings: list[dict[str, Any]] = []

    selected_runs = {run_id: runs[run_id]} if run_id and run_id in runs else runs
    if run_id and run_id not in runs:
        findings.append(
            {
                "severity": "halt",
                "kind": "run_missing",
                "message": f"run not found: {run_id}",
                "run_id": run_id,
            }
        )

    for lock_path, lock in locks:
        lock_run_id = str(lock.get("run_id") or "")
        if run_id and lock_run_id != run_id:
            continue
        lock_rel = display_path(lock_path)
        if lock.get("parse_error"):
            findings.append(
                {
                    "severity": "halt",
                    "kind": "lock_parse_error",
                    "message": f"lock file is not valid YAML: {lock_rel}",
                    "path": lock_rel,
                }
            )
            continue
        if not lock_run_id or lock_run_id not in runs:
            findings.append(
                {
                    "severity": "halt",
                    "kind": "orphan_lock",
                    "message": f"lock has no matching run record: {lock_rel}",
                    "path": lock_rel,
                    "run_id": lock_run_id or None,
                }
            )
            continue
        expires_at = parse_utc_timestamp(str(lock.get("expires_at") or ""))
        if expires_at and expires_at < now:
            findings.append(
                {
                    "severity": "escalate",
                    "kind": "expired_lock",
                    "message": f"lock expired: {lock_rel}",
                    "path": lock_rel,
                    "run_id": lock_run_id,
                    "expires_at": lock.get("expires_at"),
                }
            )
        run_status = runs[lock_run_id][1].get("status")
        if run_status in {"ok", "failed", "blocked"}:
            findings.append(
                {
                    "severity": "halt",
                    "kind": "closed_run_lock",
                    "message": f"closed run still holds a lock: {lock_rel}",
                    "path": lock_rel,
                    "run_id": lock_run_id,
                    "status": run_status,
                }
            )

    lock_paths_by_run: dict[str, set[str]] = {}
    for lock_path, lock in locks:
        lock_run_id = str(lock.get("run_id") or "")
        if lock_run_id:
            lock_paths_by_run.setdefault(lock_run_id, set()).add(
                display_path(lock_path)
            )

    for current_run_id, (path, payload) in selected_runs.items():
        expected_locks = set(payload.get("locks") or [])
        if payload.get("status") == "active":
            missing_locks = sorted(
                expected_locks - lock_paths_by_run.get(current_run_id, set())
            )
            if missing_locks:
                findings.append(
                    {
                        "severity": "halt",
                        "kind": "active_run_missing_locks",
                        "message": f"active run is missing lock files: {current_run_id}",
                        "run_id": current_run_id,
                        "missing_locks": missing_locks,
                    }
                )
        # ADR-0209 A2: self-heal missing ledger rows from run yaml before warn
        if not ledger_mentions_run(registry, current_run_id):
            healed = heal_ledger_for_run(registry, current_run_id, payload)
            if healed and ledger_mentions_run(registry, current_run_id):
                findings.append(
                    {
                        "severity": "info",
                        "kind": "ledger_healed_from_run",
                        "message": (
                            f"ledger missing run event; replayed from run yaml: "
                            f"{current_run_id}"
                        ),
                        "run_id": current_run_id,
                        "path": display_path(path),
                    }
                )
            else:
                findings.append(
                    {
                        "severity": "warn",
                        "kind": "ledger_missing_run",
                        "message": f"ledger has no event for run: {current_run_id}",
                        "run_id": current_run_id,
                        "path": display_path(path),
                    }
                )

    severities = {finding["severity"] for finding in findings}
    decision = (
        "escalate"
        if "escalate" in severities
        else "halt"
        if "halt" in severities
        else "continue"
    )
    report = {
        "ok": decision == "continue",
        "decision": decision,
        "run_count": len(selected_runs),
        "lock_count": len(
            [
                lock
                for _, lock in locks
                if not run_id or str(lock.get("run_id") or "") == run_id
            ]
        ),
        "ledger": display_path(ledger_path(registry)),
        "findings": findings,
    }
    return report


def observe(registry: dict[str, Any], run_id: str | None, as_json: bool) -> int:
    report = build_observe_report(registry, run_id)
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"agent-workflow observe: {report['decision']}")
        print(
            f"runs={report['run_count']} locks={report['lock_count']} ledger={report['ledger']}"
        )
        for finding in report["findings"]:
            print(
                f"[{finding['severity'].upper()}] {finding['kind']}: {finding['message']}"
            )
    return 0 if report["decision"] == "continue" else 1


def ledger_events(registry: dict[str, Any]) -> list[dict[str, Any]]:
    path = ledger_path(registry)
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            events.append({"parse_error": True, "raw": line})
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def p74_solidification_report(
    registry: dict[str, Any],
    events: list[dict[str, Any]],
    runs: dict[str, Any],
) -> dict[str, Any]:
    import fnmatch

    silent_policy = registry.get("silent_workflow_policy") or {}

    # P74 silent detection: workflow is silent iff has_recent_run == False
    # AND has_check_coverage == False (per ADR-0130 §4.4).
    # run_frequency drives warn_after threshold (on_demand=30d, periodic=7d,
    # continuous=1d), single-sourced from SSOT
    # silent_workflow_policy.warn_after_days_by_frequency (ADR-0211 D2/D3).
    # Excluded workflow list removed in ADR-0211; rationale = no double SSOT.

    started_runs: dict[str, str] = {}
    for event in events:
        if str(event.get("event") or "") == "agent_workflow_start":
            workflow_id = str(event.get("workflow_id") or "")
            if workflow_id:
                started_runs[workflow_id] = str(event.get("ts") or "")

    covered_paths: set[str] = set()
    for check in registry.get("diff_checks") or []:
        if isinstance(check, dict):
            for path in check.get("paths") or []:
                if isinstance(path, str):
                    covered_paths.add(path)
    for check in registry.get("doctor_checks") or []:
        if isinstance(check, dict):
            for path in check.get("paths") or []:
                if isinstance(path, str):
                    covered_paths.add(path)

    doctor_commands: list[str] = []
    for check in registry.get("doctor_checks") or []:
        if isinstance(check, dict):
            command = check.get("command") or []
            if isinstance(command, list):
                doctor_commands.extend(
                    str(item) for item in command if isinstance(item, str)
                )

    workflows_summary: list[dict[str, Any]] = []
    for workflow in registry.get("workflows") or []:
        if not isinstance(workflow, dict):
            continue
        workflow_id = str(workflow.get("id") or "")
        surfaces = workflow.get("surfaces") or {}
        write_patterns = surfaces.get("write") if isinstance(surfaces, dict) else None
        read_patterns = surfaces.get("read") if isinstance(surfaces, dict) else None
        workflow_paths = [str(p) for p in (write_patterns or []) if isinstance(p, str)]
        if not workflow_paths:
            workflow_paths = [
                str(p) for p in (read_patterns or []) if isinstance(p, str)
            ]
        has_check_coverage = (
            any(
                any(fnmatch.fnmatch(pattern, p) for p in covered_paths)
                for pattern in workflow_paths
            )
            if workflow_paths
            else False
        )
        if not has_check_coverage and workflow_id:
            has_check_coverage = any(
                workflow_id in command for command in doctor_commands
            )
        last_start = started_runs.get(workflow_id, "")
        run_frequency = str(workflow.get("run_frequency") or "on_demand")
        # ADR-0211 D2: run_frequency drives warn_after threshold. Single-sourced
        # from SSOT silent_workflow_policy.warn_after_days_by_frequency
        # (on_demand=30d / periodic=7d / continuous=1d). Fallback to warn_after_days.
        freq_map = silent_policy.get("warn_after_days_by_frequency") or {}
        warn_after = int(
            freq_map.get(run_frequency) or silent_policy.get("warn_after_days") or 30
        )
        has_recent_run = False
        if last_start:
            try:
                last_dt = datetime.fromisoformat(str(last_start).replace("Z", "+00:00"))
                now_dt = datetime.now(UTC)
                age_h = (now_dt - last_dt).total_seconds() / 3600
                has_recent_run = age_h <= warn_after * 24
            except ValueError:
                # unparseable ts → treat as no evidence of recent run
                has_recent_run = False
        silent_health = "active" if has_recent_run or has_check_coverage else "warn"
        workflows_summary.append(
            {
                "workflow_id": workflow_id,
                "run_frequency": run_frequency,
                "warn_after_days": warn_after,
                "has_recent_run": has_recent_run,
                "last_start_ts": last_start,
                "has_check_coverage": has_check_coverage,
                "silent_health": silent_health,
                "agents": workflow.get("agents"),
            }
        )

    warn_count = sum(1 for item in workflows_summary if item["silent_health"] == "warn")
    return {
        "ok": warn_count == 0,
        "policy": silent_policy,
        "summary_count": len(workflows_summary),
        "warn_count": warn_count,
        "workflows": workflows_summary,
    }


def _git_name_only(args: list[str]) -> list[str]:
    """Return normalized paths from git name-only listing."""
    import subprocess

    completed = subprocess.run(
        args,
        cwd=WORKSPACE,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return []
    out: list[str] = []
    for line in completed.stdout.splitlines():
        item = line.strip()
        if item:
            out.append(normalize_repo_path(item))
    return out


def staged_files_from_git() -> list[str]:
    return sorted(set(_git_name_only(["git", "diff", "--cached", "--name-only"])))


def requirement_iteration_report(registry: dict[str, Any]) -> dict[str, Any]:
    """ADR-0203 gate: staged requirement-scope files require an active workflow run.

    Design notes (multi-agent worktrees):
    - Hard fail uses **staged** files only (about to commit), not dirty unstaged noise.
    - Working-tree (unstaged) in-scope files produce advisory warnings only.
    - Bypass: AGCP_REQUIREMENT_ITERATION_GATE=0
    """
    import os

    policy = registry.get("requirement_iteration_policy")
    if not isinstance(policy, dict):
        return {
            "ok": True,
            "checked": False,
            "mode": "off",
            "reason": "no requirement_iteration_policy",
            "findings": [],
            "staged_in_scope": [],
            "unstaged_in_scope": [],
            "active_runs": [],
        }

    mode = str(policy.get("mode") or "off")
    if mode not in {"off", "advisory", "required"}:
        mode = "off"

    if os.environ.get("AGCP_REQUIREMENT_ITERATION_GATE", "1") in {"0", "false", "no"}:
        return {
            "ok": True,
            "checked": False,
            "mode": mode,
            "bypassed": True,
            "reason": "AGCP_REQUIREMENT_ITERATION_GATE disabled",
            "findings": [],
            "staged_in_scope": [],
            "unstaged_in_scope": [],
            "active_runs": [],
        }

    if mode == "off":
        return {
            "ok": True,
            "checked": False,
            "mode": mode,
            "findings": [],
            "staged_in_scope": [],
            "unstaged_in_scope": [],
            "active_runs": [],
        }

    default_include = [
        "projects/**",
        ".omo/_truth/**",
        ".omo/standards/**",
        ".omo/_knowledge/decisions/**",
        ".omo/_knowledge/patterns/**",
        ".agents/**",
        "bin/**",
        "docs/**",
        "tests/**",
        "AGENTS.md",
        "CLAUDE.md",
        "ARCHITECTURE.md",
        "README.md",
    ]
    default_exclude = [
        ".omo/state/**",
        ".omo/_delivery/**",
        ".omo/_control/**",
        "runtime/**",
        "**/__pycache__/**",
        "**/*.pyc",
    ]
    include = [
        str(p)
        for p in (policy.get("in_scope_paths") or default_include)
        if isinstance(p, str)
    ]
    exclude = [
        str(p)
        for p in (policy.get("exclude_paths") or default_exclude)
        if isinstance(p, str)
    ]

    def in_scope(path: str) -> bool:
        if exclude and path_matches(exclude, path):
            return False
        return path_matches(include, path) if include else False

    staged = [p for p in staged_files_from_git() if in_scope(p)]
    working = changed_files_from_git(include_untracked=False)
    staged_set = set(staged)
    unstaged = [p for p in working if p not in staged_set and in_scope(p)]

    runs = load_run_records(registry)
    active_runs = sorted(
        run_id
        for run_id, (_, payload) in runs.items()
        if payload.get("status") == "active"
    )

    findings: list[dict[str, Any]] = []
    if staged and not active_runs:
        severity = "halt" if mode == "required" else "warn"
        findings.append(
            {
                "severity": severity,
                "kind": "requirement_iteration_no_active_run",
                "message": (
                    f"staged requirement-scope files without active agent-workflow run "
                    f"({len(staged)} file(s)); start+claim first (ADR-0203)"
                ),
                "files": staged[:20],
            }
        )
    if unstaged and not active_runs:
        findings.append(
            {
                "severity": "warn",
                "kind": "requirement_iteration_dirty_without_run",
                "message": (
                    f"unstaged requirement-scope dirty files without active run "
                    f"({len(unstaged)} file(s)); advisory only"
                ),
                "files": unstaged[:20],
            }
        )

    severities = {f["severity"] for f in findings}
    ok = "halt" not in severities
    return {
        "ok": ok,
        "checked": True,
        "mode": mode,
        "bypassed": False,
        "staged_in_scope": staged,
        "unstaged_in_scope": unstaged,
        "active_runs": active_runs,
        "findings": findings,
        "policy_adr": policy.get("adr"),
    }


def compliance_report(registry: dict[str, Any], run_id: str | None) -> dict[str, Any]:
    runs = load_run_records(registry)
    events = ledger_events(registry)
    observe_report = build_observe_report(registry, run_id)
    findings: list[dict[str, Any]] = []
    event_names_by_run: dict[str, set[str]] = {}
    for event in events:
        current_run_id = str(event.get("run_id") or "")
        if current_run_id:
            event_names_by_run.setdefault(current_run_id, set()).add(
                str(event.get("event") or "")
            )
        if event.get("parse_error"):
            findings.append(
                {
                    "severity": "halt",
                    "kind": "ledger_parse_error",
                    "message": "ledger contains a non-JSON line",
                }
            )
    selected_runs = {run_id: runs[run_id]} if run_id and run_id in runs else runs
    if run_id and run_id not in runs:
        findings.append(
            {
                "severity": "halt",
                "kind": "run_missing",
                "message": f"run not found: {run_id}",
                "run_id": run_id,
            }
        )
    for current_run_id, (_, payload) in selected_runs.items():
        status = payload.get("status")
        evidence = payload.get("evidence") or []
        if status == "active":
            findings.append(
                {
                    "severity": "warn",
                    "kind": "active_run",
                    "message": f"run is still active: {current_run_id}",
                    "run_id": current_run_id,
                }
            )
        if status == "ok" and not evidence:
            findings.append(
                {
                    "severity": "halt",
                    "kind": "closed_run_missing_evidence",
                    "message": f"closed run has no evidence: {current_run_id}",
                    "run_id": current_run_id,
                }
            )
        event_names = event_names_by_run.get(current_run_id, set())
        if status == "ok" and "agent_workflow_verify" not in event_names:
            # D1 (ADR-0355 方案A): close 手动 evidence 算 manual verify (ADR-0209 A1 protocol honesty),
            # 不 warn missing_verify 噪音; 降级 info 区分 manual vs auto verify.
            # 无 evidence 的 halt 由 closed_run_missing_evidence (上 above) 兜底.
            if evidence:
                findings.append(
                    {
                        "severity": "info",
                        "kind": "closed_run_manual_verify",
                        "message": f"closed run uses manual evidence (ADR-0209 A1), no auto verify event: {current_run_id}",
                        "run_id": current_run_id,
                    }
                )
            else:
                findings.append(
                    {
                        "severity": "warn",
                        "kind": "closed_run_missing_verify_event",
                        "message": f"closed run has no verify event and no evidence: {current_run_id}",
                        "run_id": current_run_id,
                    }
                )
        close_event_names = {"agent_workflow_closeout", "agent_workflow_close"}
        if status == "ok" and not event_names.intersection(close_event_names):
            findings.append(
                {
                    "severity": "warn",
                    "kind": "closed_run_missing_closeout_event",
                    "message": f"closed run did not use closeout: {current_run_id}",
                    "run_id": current_run_id,
                }
            )
    severities = {
        finding["severity"] for finding in [*findings, *observe_report["findings"]]
    }
    decision = (
        "halt"
        if "halt" in severities
        else "escalate"
        if "escalate" in severities
        else "continue"
    )
    p74_report = p74_solidification_report(registry, events, runs)
    req_report = requirement_iteration_report(registry)
    for finding in req_report.get("findings") or []:
        findings.append(finding)
    severities = {
        finding["severity"] for finding in [*findings, *observe_report["findings"]]
    }
    decision = (
        "halt"
        if "halt" in severities
        else "escalate"
        if "escalate" in severities
        else "continue"
    )
    return {
        "ok": decision == "continue",
        "decision": decision,
        "run_count": len(selected_runs),
        "event_count": len(events),
        "observe": observe_report,
        "findings": findings,
        "slo": registry.get("compliance_slo") or {},
        "p74_solidification": p74_report,
        "requirement_iteration": req_report,
    }


def print_compliance_report(report: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    print(f"agent-workflow compliance: {report['decision']}")
    print(f"runs={report['run_count']} events={report['event_count']}")
    for finding in report["findings"]:
        print(
            f"[{finding['severity'].upper()}] {finding['kind']}: {finding['message']}"
        )
    for finding in report["observe"]["findings"]:
        print(
            f"[{finding['severity'].upper()}] {finding['kind']}: {finding['message']}"
        )
    p74 = report.get("p74_solidification") or {}
    if p74:
        ok = "OK" if p74.get("ok") else "WARN"
        print(
            f"P74 solidification: [{ok}] {p74.get('warn_count', 0)} silent workflow(s)"
        )
        for wf in p74.get("workflows", []):
            if wf.get("silent_health") != "active":
                print(
                    f"  - {wf['workflow_id']}: {wf['silent_health']} "
                    f"(run={wf['has_recent_run']}, check={wf['has_check_coverage']})"
                )
    req = report.get("requirement_iteration") or {}
    if req:
        label = "OK" if req.get("ok") else "HALT" if not req.get("ok") else "WARN"
        if req.get("bypassed"):
            label = "BYPASS"
        print(
            f"requirement_iteration: [{label}] mode={req.get('mode')} "
            f"staged={len(req.get('staged_in_scope') or [])} "
            f"active_runs={len(req.get('active_runs') or [])}"
        )


def last_ledger_event(
    events: list[dict[str, Any]],
    names: set[str],
) -> dict[str, Any] | None:
    for event in reversed(events):
        if str(event.get("event") or "") in names:
            return event
    return None


def build_status_report(
    registry: dict[str, Any],
    include_health: bool,
    include_agcp_drift: bool = True,
) -> dict[str, Any]:
    runs = load_run_records(registry)
    active_runs = sorted(
        run_id
        for run_id, (_, payload) in runs.items()
        if payload.get("status") == "active"
    )
    closed_runs = sorted(
        run_id
        for run_id, (_, payload) in runs.items()
        if payload.get("status") in {"ok", "failed", "blocked"}
    )
    observe_report = build_observe_report(registry, None)
    compliance = compliance_report(registry, None)
    events = ledger_events(registry)
    staged_lane = staged_lane_report()
    stale_locks = len(
        [
            finding
            for finding in observe_report["findings"]
            if finding.get("kind") == "expired_lock"
        ]
    )
    current_run_id = active_runs[0] if len(active_runs) == 1 else None
    changed_files = changed_files_from_git(include_untracked=False)
    policy = claim_policy(registry)
    claim_coverage = (
        claim_coverage_report(registry, current_run_id, changed_files)
        if current_run_id
        else {
            "ok": True,
            "mode": policy["mode"],
            "checked": False,
            "run_id": current_run_id,
            "required_paths": policy["required_paths"],
            "tiers": policy["tiers"],
            "claimed_paths": [],
            "missing_files": [],
            "missing_required_files": [],
            "missing_advisory_files": [],
            "warnings": ["multiple active runs; pass a run id to verify/closeout"]
            if len(active_runs) > 1
            else [],
        }
    )
    health = (
        build_doctor_report(registry, include_agcp_drift) if include_health else None
    )
    report = {
        "ok": observe_report["decision"] == "continue"
        and compliance["decision"] == "continue"
        and (health is None or bool(health["ok"])),
        "active_runs": active_runs,
        "closed_runs": closed_runs,
        "run_count": len(runs),
        "lock_count": observe_report["lock_count"],
        "stale_locks": stale_locks,
        "current_run_id": current_run_id,
        "last_verify": last_ledger_event(events, {"agent_workflow_verify"}),
        "last_closeout": last_ledger_event(
            events, {"agent_workflow_closeout", "agent_workflow_close"}
        ),
        "compliance": {
            "ok": compliance["ok"],
            "decision": compliance["decision"],
            "slo": compliance["slo"],
            "findings": compliance["findings"],
            "observe_findings": compliance["observe"]["findings"],
        },
        "requirement_iteration": compliance.get("requirement_iteration")
        or requirement_iteration_report(registry),
        "staged_lane": staged_lane,
        "changed_files": changed_files,
        "claim_coverage": claim_coverage,
        "health": None
        if health is None
        else {"ok": health["ok"], "checks": check_summary(health["checks"])},
    }
    report["recommended_next"] = recommended_next(report)
    return report


def print_status_report(report: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    print(f"agent-workflow status: {'ok' if report['ok'] else 'attention'}")
    print(
        f"runs active={len(report['active_runs'])} closed={len(report['closed_runs'])} "
        f"locks={report['lock_count']} stale={report['stale_locks']}"
    )
    staged_lane = report["staged_lane"]
    print(
        f"staged_lane={'PASS' if staged_lane['ok'] else 'WARN'} lanes={','.join(staged_lane['lanes']) or '-'}"
    )
    claim_coverage = report.get("claim_coverage")
    if isinstance(claim_coverage, dict):
        for warning in claim_coverage.get("warnings") or []:
            print(f"[WARN] claim_policy: {warning}")
    print(f"compliance={report['compliance']['decision']}")
    req = report.get("requirement_iteration") or {}
    if req:
        flag = "ok" if req.get("ok") else "attention"
        print(
            f"requirement_iteration={flag} mode={req.get('mode')} "
            f"staged={len(req.get('staged_in_scope') or [])} "
            f"active={len(req.get('active_runs') or [])}"
        )
    print(f"next: {report['recommended_next']}")


def run_doctor_check(check_item: dict[str, Any]) -> dict[str, Any]:
    import subprocess

    command = check_item["command"]
    env = os.environ.copy()
    env.pop("VIRTUAL_ENV", None)
    try:
        completed = subprocess.run(
            command,
            cwd=WORKSPACE,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        ok = completed.returncode == 0
        return {
            "id": check_item["id"],
            "description": check_item.get("description", ""),
            "required": bool(check_item.get("required", True)),
            "command": command_display(command),
            "ok": ok,
            "returncode": completed.returncode,
            "stdout": completed.stdout.strip()[-1000:],
            "stderr": completed.stderr.strip()[-1000:],
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "id": check_item["id"],
            "description": check_item.get("description", ""),
            "required": bool(check_item.get("required", True)),
            "command": command_display(command),
            "ok": False,
            "error": str(exc),
        }


def build_doctor_report(
    registry: dict[str, Any], include_agcp_drift: bool = True
) -> dict[str, Any]:
    integrations = integration_rows(registry)
    for integration in integrations:
        name = str(integration["name"])
        health = None
        health_command = integration.get("health_command")
        health_required = bool(integration.get("health_required", False))
        if isinstance(health_command, list) and health_command:
            health = run_doctor_check(
                {
                    "id": f"integration-{name}-health",
                    "description": f"Internal integration health check for {name}.",
                    "required": health_required,
                    "command": health_command,
                }
            )
        integration["health"] = health

    adapters = adapter_rows(registry)
    for adapter in adapters:
        name = str(adapter["name"])
        health = None
        health_command = adapter.get("health_command")
        health_required = bool(adapter.get("health_required", False))
        if isinstance(health_command, list) and health_command:
            health = run_doctor_check(
                {
                    "id": f"adapter-{name}-health",
                    "description": f"External adapter health check for {name}.",
                    "required": health_required,
                    "command": health_command,
                }
            )
        adapter["health"] = health
    checks = [run_doctor_check(item) for item in registry.get("doctor_checks", [])]
    if include_agcp_drift:
        checks.insert(0, agcp_drift_check(registry))
    required_integration_health = [
        integration["health"]
        for integration in integrations
        if integration.get("health_required")
        and isinstance(integration.get("health"), dict)
    ]
    required_adapter_health = [
        adapter["health"]
        for adapter in adapters
        if adapter.get("health_required") and isinstance(adapter.get("health"), dict)
    ]
    ok = all(
        (not item["required"]) or item["ok"]
        for item in [*checks, *required_integration_health, *required_adapter_health]
    )
    return {
        "ok": ok,
        "registry": str(REGISTRY_PATH.relative_to(WORKSPACE)),
        "integrations": integrations,
        "adapters": adapters,
        "checks": checks,
    }


def print_doctor_report(report: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    print(f"registry: {report['registry']}")
    for integration in report["integrations"]:
        health = integration.get("health")
        health_status = ""
        if isinstance(health, dict):
            label = (
                "PASS"
                if health["ok"]
                else ("FAIL" if integration.get("health_required") else "WARN")
            )
            health_status = f" health={label}"
        print(
            f"{integration['name']:<14} {integration['status']:<12} "
            f"{integration['authority']:<16}{health_status}"
        )
    for adapter in report["adapters"]:
        status = "available" if adapter["available"] else "missing"
        suffix = f" ({adapter['path']})" if adapter["path"] else ""
        health = adapter.get("health")
        if isinstance(health, dict):
            health_status = (
                "PASS"
                if health["ok"]
                else ("FAIL" if adapter.get("health_required") else "WARN")
            )
            suffix += f" health={health_status}"
        print(f"{adapter['name']:<14} {status}{suffix}")
    for item in report["checks"]:
        status = "PASS" if item["ok"] else ("WARN" if not item["required"] else "FAIL")
        print(f"[{status}] {item['id']} :: {item['command']}")
        if not item["ok"] and item.get("stderr"):
            print(item["stderr"], file=sys.stderr)


def doctor(
    registry: dict[str, Any], as_json: bool, include_agcp_drift: bool = True
) -> int:
    report = build_doctor_report(registry, include_agcp_drift)
    print_doctor_report(report, as_json)
    return 0 if report["ok"] else 1


def health_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for row in rows:
        health = row.get("health")
        summary.append(
            {
                "name": row.get("name"),
                "status": row.get("status"),
                "authority": row.get("authority"),
                "required": bool(row.get("health_required", False)),
                "health_ok": health.get("ok") if isinstance(health, dict) else None,
                "command": health.get("command")
                if isinstance(health, dict)
                else command_display(row.get("health_command", [])),
                "advisory": not bool(row.get("health_required", False)),
            }
        )
    return summary


def check_summary(checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": check.get("id"),
            "required": bool(check.get("required", True)),
            "ok": bool(check.get("ok", False)),
            "command": check.get("command"),
        }
        for check in checks
    ]
