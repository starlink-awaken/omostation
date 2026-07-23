from __future__ import annotations

import json
import os
import re
import time
import uuid
import sys
import subprocess
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

from .core import (
    CLAIM_POLICY_MODES,
    RUN_UPDATE_LOCK_TIMEOUT_SECONDS,
    WORKSPACE,
    WorkflowError,
    display_path,
    ledger_path,
    lock_state_dir,
    normalize_repo_path,
    run_state_dir,
    substitute,
    utc_now,
    validate_agent_profile,
    command_display,
    path_matches,
    workflow_by_id,
)


def workflow_plan(workflow: dict[str, Any], context: dict[str, str]) -> dict[str, Any]:
    resolved = substitute(workflow, context)
    return {
        "id": resolved["id"],
        "title": resolved.get("title", ""),
        "purpose": resolved.get("purpose", ""),
        "agents": resolved.get("agents", {}),
        "allowed_lanes": resolved.get("allowed_lanes", []),
        "lock_scopes": resolved.get("lock_scopes", []),
        "phases": resolved.get("phases", {}),
    }


def print_plan(plan: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return
    print(f"{plan['id']} — {plan['title']}")
    print(plan["purpose"])
    roles = plan.get("agents", {}).get("roles") or []
    if roles:
        print(f"agents: {', '.join(roles)}")
    print(f"lanes: {', '.join(plan['allowed_lanes'])}")
    print(f"locks: {', '.join(plan['lock_scopes'])}")
    for phase, entries in plan["phases"].items():
        print(f"\n[{phase}]")
        for item in entries:
            mode = item.get("mode", "?")
            cwd = item.get("cwd")
            prefix = f"({mode})"
            if cwd:
                prefix += f" cwd={cwd}"
            print(f"  {item.get('id')}: {prefix} {command_display(item['command'])}")


def run_stage(
    workflow: dict[str, Any],
    stage: str,
    context: dict[str, str],
    execute: bool,
    as_json: bool,
) -> int:
    plan = workflow_plan(workflow, context)
    entries = plan["phases"].get(stage)
    if not entries:
        raise WorkflowError(f"{plan['id']} has no stage: {stage}")

    results: list[dict[str, Any]] = []
    for item in entries:
        mode = item.get("mode")
        command = item["command"]
        cwd = WORKSPACE / item.get("cwd", ".")
        skipped = mode == "manual" or not execute
        result: dict[str, Any] = {
            "id": item.get("id"),
            "mode": mode,
            "command": command_display(command),
            "cwd": str(cwd.relative_to(WORKSPACE))
            if cwd.is_relative_to(WORKSPACE)
            else str(cwd),
            "skipped": skipped,
            "ok": True,
        }
        if not skipped:
            completed = subprocess.run(command, cwd=cwd, check=False)
            result["returncode"] = completed.returncode
            result["ok"] = completed.returncode == 0 or mode == "advisory"
        results.append(result)

    report = {
        "workflow": plan["id"],
        "stage": stage,
        "execute": execute,
        "results": results,
    }
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for result in results:
            status = (
                "SKIP" if result["skipped"] else ("PASS" if result["ok"] else "FAIL")
            )
            print(f"[{status}] {result['id']} :: {result['command']}")
    return 0 if all(item["ok"] for item in results) else 1


def sanitize_lock_name(scope: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", scope).strip("_") or "workspace"


@contextmanager
def run_update_lock(registry: dict[str, Any], run_id: str):
    lock_dir = lock_state_dir(registry)
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lock_dir / f"run_{sanitize_lock_name(run_id)}.update.lock"
    deadline = time.monotonic() + RUN_UPDATE_LOCK_TIMEOUT_SECONDS
    acquired = False
    while not acquired:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(f"run_id: {run_id}\ncreated_at: {utc_now()}\n")
            acquired = True
        except FileExistsError:
            try:
                if (
                    time.time() - lock_path.stat().st_mtime
                    > RUN_UPDATE_LOCK_TIMEOUT_SECONDS
                ):
                    lock_path.unlink(missing_ok=True)
                    continue
            except FileNotFoundError:
                continue
            if time.monotonic() >= deadline:
                raise WorkflowError(
                    f"timed out waiting for run update lock: {display_path(lock_path)}"
                )
            time.sleep(0.05)
    try:
        yield
    finally:
        if acquired:
            lock_path.unlink(missing_ok=True)


def append_ledger_event(registry: dict[str, Any], event: dict[str, Any]) -> None:
    path = ledger_path(registry)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"ts": utc_now(), **event}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def ledger_mentions_run(registry: dict[str, Any], run_id: str) -> bool:
    path = ledger_path(registry)
    if not path.exists() or path.stat().st_size == 0:
        return False
    needle = f'"run_id": "{run_id}"'
    # also match compact JSON without space after colon
    needle_alt = f'"run_id":"{run_id}"'
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    return needle in text or needle_alt in text


def heal_ledger_for_run(
    registry: dict[str, Any],
    run_id: str,
    payload: dict[str, Any],
) -> bool:
    """ADR-0209 A2: if ledger has no event for a known run, replay from run yaml.

    Reconstructs a minimal start (and close if terminal) event so observe/compliance
    do not warn forever after events.jsonl was trimmed externally.
    Returns True when a heal write happened.
    """
    if ledger_mentions_run(registry, run_id):
        return False
    append_ledger_event(
        registry,
        {
            "event": "agent_workflow_start",
            "run_id": run_id,
            "workflow_id": payload.get("workflow_id"),
            "actor": payload.get("actor"),
            "agent_profile": payload.get("agent_profile"),
            "objective": payload.get("objective"),
            "path": payload.get("path"),
            "locks": payload.get("locks") or [],
            "healed": True,
            "heal_reason": "ledger_missing_run_replay_from_run_yaml",
        },
    )
    status = str(payload.get("status") or "")
    if status in {"ok", "failed", "blocked"}:
        append_ledger_event(
            registry,
            {
                "event": "agent_workflow_close",
                "run_id": run_id,
                "workflow_id": payload.get("workflow_id"),
                "status": status,
                "evidence": payload.get("evidence") or [],
                "healed": True,
                "heal_reason": "ledger_missing_run_replay_from_run_yaml",
            },
        )
    return True


def acquire_locks(
    registry: dict[str, Any],
    scopes: list[str],
    run_id: str,
    actor: str,
    force: bool,
) -> list[str]:
    lock_dir = lock_state_dir(registry)
    lock_dir.mkdir(parents=True, exist_ok=True)
    acquired: list[str] = []
    acquired_paths: list[Path] = []
    ttl_hours = float(registry.get("runner", {}).get("lock_ttl_hours", 24))
    expires_at = (datetime.now(UTC) + timedelta(hours=ttl_hours)).replace(microsecond=0)
    try:
        for scope in scopes:
            lock_path = lock_dir / f"{sanitize_lock_name(scope)}.lock.yaml"
            payload = {
                "run_id": run_id,
                "actor": actor,
                "scope": scope,
                "created_at": utc_now(),
                "expires_at": expires_at.isoformat().replace("+00:00", "Z"),
            }
            if lock_path.exists() and not force:
                existing = lock_path.read_text(encoding="utf-8").strip()
                raise WorkflowError(
                    f"lock already held for {scope}: {lock_path}\n{existing}"
                )
            with lock_path.open("w" if force else "x", encoding="utf-8") as handle:
                yaml.safe_dump(payload, handle, allow_unicode=True, sort_keys=False)
            acquired_paths.append(lock_path)
            acquired.append(display_path(lock_path))
    except Exception:
        for path in acquired_paths:
            path.unlink(missing_ok=True)
        raise
    return acquired


def release_locks(registry: dict[str, Any], run_id: str) -> list[str]:
    lock_dir = lock_state_dir(registry)
    released: list[str] = []
    if not lock_dir.exists():
        return released
    for lock_path in lock_dir.glob("*.lock.yaml"):
        try:
            payload = yaml.safe_load(lock_path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        if payload.get("run_id") == run_id:
            lock_path.unlink()
            released.append(display_path(lock_path))
    return released


def run_file_for(registry: dict[str, Any], run_id: str) -> Path:
    run_dir = run_state_dir(registry)
    direct = run_dir / f"{run_id}.yaml"
    if direct.exists():
        return direct
    matches = list(run_dir.glob(f"*{run_id}*.yaml")) if run_dir.exists() else []
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise WorkflowError(
            f"ambiguous run id {run_id}: {', '.join(str(p) for p in matches)}"
        )
    raise WorkflowError(f"run not found: {run_id}")


def start_run(
    registry: dict[str, Any],
    workflow: dict[str, Any],
    context: dict[str, str],
    objective: str,
    dry_run: bool,
    force_lock: bool,
) -> dict[str, Any]:
    validate_agent_profile(registry, workflow, context.get("profile", ""), require=True)
    plan = workflow_plan(workflow, context)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{stamp}-{plan['id']}-{uuid.uuid4().hex[:8]}"
    context = {**context, "run_id": run_id}
    plan = workflow_plan(workflow, context)
    record = {
        "run_id": run_id,
        "workflow_id": plan["id"],
        "status": "active",
        "actor": context["actor"],
        "agent_profile": context.get("profile", ""),
        "objective": objective,
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "context": context,
        "locks": [],
        "plan": plan,
        "evidence": [],
    }
    if dry_run:
        return record
    record["locks"] = acquire_locks(
        registry, plan["lock_scopes"], run_id, context["actor"], force_lock
    )
    run_dir = run_state_dir(registry)
    run_dir.mkdir(parents=True, exist_ok=True)
    run_path = run_dir / f"{run_id}.yaml"
    run_path.write_text(
        yaml.safe_dump(record, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )  # audit-exempt: non-atomic-write — run state single-writer under run_update_lock
    record["path"] = display_path(run_path)
    append_ledger_event(
        registry,
        {
            "event": "agent_workflow_start",
            "run_id": run_id,
            "workflow_id": plan["id"],
            "actor": context["actor"],
            "agent_profile": context.get("profile", ""),
            "objective": objective,
            "path": record["path"],
            "locks": record["locks"],
        },
    )
    return record


def read_run(registry: dict[str, Any], run_id: str) -> tuple[Path, dict[str, Any]]:
    path = run_file_for(registry, run_id)
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict) or not payload.get("run_id"):
        raise WorkflowError(f"invalid run file: {path}")
    return path, payload


def write_run(path: Path, payload: dict[str, Any]) -> None:
    payload["updated_at"] = utc_now()
    path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )  # audit-exempt: non-atomic-write — under run_update_lock


def claim_run(
    registry: dict[str, Any],
    run_id: str,
    actor: str,
    paths: list[str],
    surfaces: list[str],
    force_lock: bool,
) -> dict[str, Any]:
    if not paths and not surfaces:
        raise WorkflowError("claim requires at least one --path or --surface")
    with run_update_lock(registry, run_id):
        path, payload = read_run(registry, run_id)
        if payload.get("status") != "active":
            raise WorkflowError(f"cannot claim against non-active run: {run_id}")
        normalized_paths = sorted({normalize_repo_path(item) for item in paths})
        normalized_surfaces = sorted(
            {item.strip() for item in surfaces if item.strip()}
        )
        scopes = [f"path:{item}" for item in normalized_paths] + [
            f"surface:{item}" for item in normalized_surfaces
        ]
        lock_paths = acquire_locks(registry, scopes, run_id, actor, force_lock)
        try:
            payload.setdefault("locks", [])
            for lock_path in lock_paths:
                if lock_path not in payload["locks"]:
                    payload["locks"].append(lock_path)
            claim = {
                "claimed_at": utc_now(),
                "actor": actor,
                "paths": normalized_paths,
                "surfaces": normalized_surfaces,
                "scopes": scopes,
                "locks": lock_paths,
            }
            payload.setdefault("claims", []).append(claim)
            write_run(path, payload)
        except Exception:
            for lock_path in lock_paths:
                lock_file = Path(lock_path)
                if not lock_file.is_absolute():
                    lock_file = WORKSPACE / lock_file
                lock_file.unlink(missing_ok=True)
            raise
        append_ledger_event(
            registry,
            {
                "event": "agent_workflow_claim",
                "run_id": run_id,
                "actor": actor,
                "paths": normalized_paths,
                "surfaces": normalized_surfaces,
                "locks": lock_paths,
            },
        )
        return {**claim, "run_id": run_id}


def close_run(
    registry: dict[str, Any],
    run_id: str,
    status: str,
    evidence: list[str],
    release: bool,
) -> dict[str, Any]:
    path, payload = read_run(registry, run_id)
    payload["status"] = status
    payload["updated_at"] = utc_now()
    payload["closed_at"] = utc_now()
    payload.setdefault("evidence", [])
    payload["evidence"].extend(evidence)
    if release:
        payload["released_locks"] = release_locks(registry, payload["run_id"])
    path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )  # audit-exempt: non-atomic-write — under run_update_lock
    payload["path"] = display_path(path)
    append_ledger_event(
        registry,
        {
            "event": "agent_workflow_close",
            "run_id": payload["run_id"],
            "workflow_id": payload.get("workflow_id"),
            "status": status,
            "evidence": evidence,
            "released_locks": payload.get("released_locks", []),
        },
    )
    return payload


def closeout_run(
    registry: dict[str, Any],
    run_id: str,
    status: str,
    evidence: list[str],
    files: list[str],
    from_diff: bool,
    include_untracked: bool,
    all_checks: bool,
    keep_locks: bool,
) -> dict[str, Any]:
    from .diagnostics import build_verify_report, build_observe_report

    verify_report = build_verify_report(
        registry,
        run_id,
        files,
        from_diff,
        include_untracked,
        all_checks,
        execute=True,
    )
    observe_report = build_observe_report(registry, run_id)
    if status == "ok" and not verify_report["ok"]:
        raise WorkflowError("closeout blocked: verify failed")
    if status == "ok" and not observe_report["ok"]:
        raise WorkflowError(
            f"closeout blocked: observe decision={observe_report['decision']}"
        )
    closeout_evidence = [
        *evidence,
        f"agent-workflow verify: {verify_report['check_count']} checks ok={verify_report['ok']}",
        f"agent-workflow observe: {observe_report['decision']}",
    ]
    payload = close_run(registry, run_id, status, closeout_evidence, not keep_locks)
    report = {
        "ok": status == "ok",
        "run": payload,
        "verify": verify_report,
        "observe": observe_report,
    }
    append_ledger_event(
        registry,
        {
            "event": "agent_workflow_closeout",
            "run_id": run_id,
            "status": status,
            "ok": report["ok"],
            "verify_ok": verify_report["ok"],
            "observe_decision": observe_report["decision"],
        },
    )
    if status == "ok":
        try:
            import subprocess

            # 1. Loop Convergence: auto-run evidence-smoke.py (silently)
            smoke_script = WORKSPACE / "bin/gac/evidence-smoke.py"
            subprocess.run(
                [sys.executable, str(smoke_script), "--quiet"],
                cwd=WORKSPACE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            # 2. Sync state officially using omo CLI
            omo_cmd = [
                sys.executable,
                "-m",
                "omo.cli",
                "state",
                "sync",
            ]
            env = os.environ.copy()
            env["PYTHONPATH"] = str(WORKSPACE / "projects/omo/src")
            subprocess.run(
                omo_cmd,
                cwd=str(WORKSPACE / "projects/omo"),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env,
                check=False,
            )
            # 3. KOS Knowledge Ingress Sync (Incremental + Ontology Rebuild)
            # Refreshes L2 Knowledge Engine dynamically during closeout
            kos_cli_path = WORKSPACE / "projects/kairon/packages/kos/kos-cli.py"
            if kos_cli_path.is_file():
                env_kos = os.environ.copy()
                env_kos["KOS_HOME"] = str(WORKSPACE / "kos")
                env_kos["PYTHONPATH"] = str(
                    WORKSPACE / "projects/kairon/packages/kos/src"
                )
                # 3.1 Incremental Ingest
                subprocess.run(
                    [sys.executable, str(kos_cli_path), "ingest", "--incremental"],
                    cwd=WORKSPACE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    env=env_kos,
                    check=False,
                )
                # 3.2 Ontology Rebuild
                subprocess.run(
                    [sys.executable, str(kos_cli_path), "onto", "rebuild"],
                    cwd=WORKSPACE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    env=env_kos,
                    check=False,
                )
                # 3.3 Ontology Infer (performs layer dependency reasoning)
                subprocess.run(
                    [sys.executable, str(kos_cli_path), "onto", "infer"],
                    cwd=WORKSPACE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    env=env_kos,
                    check=False,
                )
                # 3.4 Sync KOS Reasoning Anomalies to OMO State (Active Feedback Loop via authorized broker)
                gac_sync_path = WORKSPACE / "bin" / "gac-kos-sync.py"
                if gac_sync_path.is_file():
                    subprocess.run(
                        [sys.executable, str(gac_sync_path)],
                        cwd=WORKSPACE,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=False,
                    )
                # 3.5 Auto Consensus Gene Injection (Active Agent Evolution)
                gac_consensus_path = WORKSPACE / "bin" / "gac-consensus-inject.py"
                if gac_consensus_path.is_file():
                    subprocess.run(
                        [sys.executable, str(gac_consensus_path)],
                        cwd=WORKSPACE,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=False,
                    )
        except Exception:
            pass
    return report


def load_run_records(
    registry: dict[str, Any],
) -> dict[str, tuple[Path, dict[str, Any]]]:
    run_dir = run_state_dir(registry)
    records: dict[str, tuple[Path, dict[str, Any]]] = {}
    if not run_dir.exists():
        return records
    for path in sorted(run_dir.glob("*.yaml")):
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            payload = {}
        run_id = payload.get("run_id") if isinstance(payload, dict) else None
        if run_id:
            records[str(run_id)] = (path, payload)
    return records


def load_lock_records(registry: dict[str, Any]) -> list[tuple[Path, dict[str, Any]]]:
    lock_dir = lock_state_dir(registry)
    records: list[tuple[Path, dict[str, Any]]] = []
    if not lock_dir.exists():
        return records
    for path in sorted(lock_dir.glob("*.lock.yaml")):
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            payload = {"run_id": None, "parse_error": True}
        records.append(
            (
                path,
                payload
                if isinstance(payload, dict)
                else {"run_id": None, "parse_error": True},
            )
        )
    return records


def normalize_claim_mode(raw_mode: Any, default: str = "advisory") -> str:
    mode = str(raw_mode or default)
    return mode if mode in CLAIM_POLICY_MODES else default


def claim_policy(registry: dict[str, Any]) -> dict[str, Any]:
    policy = registry.get("claim_policy")
    if not isinstance(policy, dict):
        return {"mode": "advisory", "required_paths": [], "tiers": []}
    mode = normalize_claim_mode(policy.get("mode"))
    required_paths = policy.get("required_paths") or []
    normalized_required_paths = [
        str(item) for item in required_paths if isinstance(item, str)
    ]
    tiers: list[dict[str, Any]] = []
    if normalized_required_paths:
        tiers.append(
            {
                "id": "legacy-required-paths",
                "mode": mode,
                "paths": normalized_required_paths,
            }
        )
    for index, tier in enumerate(policy.get("tiers") or []):
        if not isinstance(tier, dict):
            continue
        paths = [str(item) for item in tier.get("paths") or [] if isinstance(item, str)]
        if not paths:
            continue
        tier_mode = normalize_claim_mode(tier.get("mode"), default="advisory")
        if tier_mode == "off":
            continue
        tiers.append(
            {
                "id": str(tier.get("id") or f"tier-{index + 1}"),
                "mode": tier_mode,
                "paths": paths,
            }
        )
    return {
        "mode": mode,
        "required_paths": normalized_required_paths,
        "tiers": tiers,
    }


def claimed_paths(payload: dict[str, Any]) -> list[str]:
    paths: set[str] = set()
    for claim in payload.get("claims") or []:
        if not isinstance(claim, dict):
            continue
        for item in claim.get("paths") or []:
            if isinstance(item, str) and item.strip():
                paths.add(normalize_repo_path(item))
    return sorted(paths)


def claim_covers_path(claimed_path: str, changed_path: str) -> bool:
    normalized_claim = normalize_repo_path(claimed_path)
    normalized_changed = normalize_repo_path(changed_path)
    if normalized_claim == ".":
        return True
    if path_matches([normalized_claim], normalized_changed):
        return True
    return normalized_changed.startswith(normalized_claim.rstrip("/") + "/")


def is_read_only_workflow(registry: dict[str, Any], workflow_id: str) -> bool:
    """True when workflow declares empty write surfaces (ADR-0209 A4)."""
    if not workflow_id:
        return False
    try:
        workflow = workflow_by_id(registry, workflow_id)
    except WorkflowError:
        return False
    surfaces = workflow.get("surfaces") or {}
    write = surfaces.get("write")
    # Explicit empty write list => read-only. Missing write key is NOT exempt
    # (legacy workflows may omit surfaces entirely).
    return isinstance(write, list) and len(write) == 0


def claim_coverage_report(
    registry: dict[str, Any],
    run_id: str | None,
    changed_files: list[str],
) -> dict[str, Any]:
    policy = claim_policy(registry)
    mode = str(policy["mode"])
    if mode == "off" or not run_id:
        return {
            "ok": True,
            "mode": mode,
            "checked": False,
            "run_id": run_id,
            "required_paths": policy["required_paths"],
            "tiers": policy["tiers"],
            "claimed_paths": [],
            "missing_files": [],
            "missing_required_files": [],
            "missing_advisory_files": [],
            "warnings": [],
        }
    _, payload = read_run(registry, run_id)
    # ADR-0209 A4: read-only runs must not be treated as write claim subjects
    if is_read_only_workflow(registry, str(payload.get("workflow_id") or "")):
        return {
            "ok": True,
            "mode": "read_only_exempt",
            "checked": False,
            "read_only": True,
            "run_id": run_id,
            "required_paths": policy["required_paths"],
            "tiers": policy["tiers"],
            "claimed_paths": claimed_paths(payload),
            "missing_files": [],
            "missing_required_files": [],
            "missing_advisory_files": [],
            "warnings": [
                "claim_policy skipped: workflow has empty write surfaces (read-only)"
            ],
        }
    claimed = claimed_paths(payload)
    tiers = policy["tiers"] or [
        {"id": "default", "mode": mode, "paths": policy["required_paths"]}
    ]
    missing_required: list[str] = []
    missing_advisory: list[str] = []
    for item in changed_files:
        matching_tiers = [
            tier
            for tier in tiers
            if not tier.get("paths") or path_matches(tier.get("paths", []), item)
        ]
        if not matching_tiers:
            continue
        if any(claim_covers_path(claimed_path, item) for claimed_path in claimed):
            continue
        if any(tier.get("mode") == "required" for tier in matching_tiers):
            missing_required.append(item)
        else:
            missing_advisory.append(item)
    missing = sorted({*missing_required, *missing_advisory})
    ok = not missing_required
    warnings = [
        f"unclaimed required file under claim_policy: {item}"
        for item in missing_required
    ] + [
        f"unclaimed advisory file under claim_policy: {item}"
        for item in missing_advisory
    ]
    return {
        "ok": ok,
        "mode": mode,
        "checked": True,
        "run_id": run_id,
        "required_paths": policy["required_paths"],
        "tiers": tiers,
        "claimed_paths": claimed,
        "missing_files": missing,
        "missing_required_files": sorted(missing_required),
        "missing_advisory_files": sorted(missing_advisory),
        "warnings": warnings,
    }


def staged_lane_report() -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, "bin/change-lane-check.py", "--staged", "--json"],
        cwd=WORKSPACE,
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        payload = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError:
        payload = {}
    return {
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "lanes": payload.get("lanes", []),
        "files": payload.get("files", []),
        "message": payload.get("message") or completed.stderr.strip(),
    }


def recommended_next(status: dict[str, Any]) -> str:
    if status["stale_locks"] > 0:
        return "Run `agent-workflow observe` and inspect stale locks before editing."
    claim_coverage = status.get("claim_coverage")
    if isinstance(claim_coverage, dict) and claim_coverage.get("missing_files"):
        run_id = status.get("current_run_id") or "<run-id>"
        return (
            f"Claim missing files with `agent-workflow claim {run_id} --path <path>`."
        )
    if status["active_runs"]:
        run_id = status["active_runs"][0]
        return f"Continue with `agent-workflow verify {run_id} --from-diff --execute` or closeout."
    if not status["staged_lane"]["ok"]:
        return "Resolve the staged lane split or use a run-scoped/file-scoped gate for AGCP work."
    return "Start a governed run with `agent-workflow start <workflow-id> --profile <agent-profile>`."
