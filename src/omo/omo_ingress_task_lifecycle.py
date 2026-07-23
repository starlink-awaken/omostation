"""omo_ingress task lifecycle (从 God Module 拆出, SRP · P60+ 第七步第一批).

_task_payload_with_metadata / create_planned_task / create_blocked_task.
task 创建 (planned/blocked) + metadata 注入. 依赖 paths + registry + trail
+ omo_io + omo_audit + task_schema — 无循环.
"""

from __future__ import annotations

from copy import deepcopy
import os
from pathlib import Path
import re
import signal
import subprocess
import threading
import time
from typing import Any

from omo.omo_audit import record as record_audit
from omo.omo_io import fcntl_lock, write_text_atomic, write_yaml_atomic
from omo.omo_task_schema import validate_task_data
from omo.omo_ingress_paths import (
    _artifact_lifecycle_fields,
    _audit_log_path,
    _delivery_root,
    _find_task_path,
    _load_yaml,
    _lock_path,
    _timestamp_slug,
    _utc_now,
    _workspace_relative,
)


# P110 R1: 3 子模块 (promotion + contract + archive) extracted 936L from omo_ingress_task_lifecycle.py
# Re-export 保持向后兼容 (cli.py / worker / 外部 import 调用点不破)
from .omo_ingress_task_promotion import (  # noqa: E402, F401
    promote_task_to_active,
    repair_task_promotion_approval,
    request_task_promotion_approval,
    revert_task_to_planned,
)

from .omo_ingress_task_contract import (  # noqa: E402, F401
    record_task_contract_request,
    route_self_evolution_to_remediation,
)

from .omo_ingress_task_archive import (  # noqa: E402, F401
    archive_done_task,
    normalize_legacy_planned_task,
    yield_task_to_planned,
)


def _task_payload_with_metadata(
    task_data: dict[str, Any],
    *,
    ingress_plane: str,
    source_ref: str,
) -> dict[str, Any]:
    payload = deepcopy(task_data)
    metadata = payload.setdefault("metadata", {})
    if isinstance(metadata, dict):
        metadata.setdefault("ingress_plane", ingress_plane)
        metadata.setdefault("broker", "projects/omo/src/omo/omo_ingress.py")
        if source_ref:
            metadata.setdefault("source_ref", source_ref)
    return payload


def create_planned_task(
    omo_dir: Path,
    *,
    task_data: dict[str, Any],
    ingress_plane: str,
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    from omo.omo_ingress import (
        _load_registry,
        _record_mutation,
        _record_trail,
        _register_ingress,
        _write_registry,
    )

    errors = validate_task_data(task_data, group="planned")
    if errors:
        raise ValueError("invalid planned task: " + "; ".join(errors))

    task_id = str(task_data["id"])
    task_path = omo_dir / "tasks" / "planned" / f"{task_id}.yaml"
    timestamp = now or _utc_now()
    payload = _task_payload_with_metadata(
        task_data, ingress_plane=ingress_plane, source_ref=source_ref
    )
    artifact_ref = f"runtime/omo/_delivery/ingress/tasks/{task_id}.yaml"

    with fcntl_lock(_lock_path(omo_dir)):
        registry = _load_registry(omo_dir)

        if source_ref:
            mapped_task_id = registry["tasks"]["by_source_ref"].get(source_ref)
            if mapped_task_id and mapped_task_id != task_id:
                raise ValueError(
                    f"source_ref already mapped to different task: {source_ref} -> {mapped_task_id}"
                )

        if task_path.exists():
            existing_payload = _load_yaml(task_path)
            if existing_payload == payload:
                _register_ingress(
                    registry,
                    kind="tasks",
                    item_id=task_id,
                    source_ref=source_ref,
                    artifact_ref=artifact_ref,
                    fingerprint=payload,
                    created_at=str(
                        existing_payload.get("metadata", {}).get(
                            "created_at", timestamp
                        )
                    ),
                )
                _write_registry(omo_dir, registry)
                return existing_payload
            raise ValueError(
                f"planned task already exists with different payload: {task_id}"
            )

        write_yaml_atomic(task_path, payload)

        artifact = {
            "kind": "planned_task_created",
            "task_id": task_id,
            "title": payload.get("title", ""),
            "ingress_plane": ingress_plane,
            "source_ref": source_ref,
            "created_at": timestamp,
            "task_ref": f".omo/tasks/planned/{task_id}.yaml",
            "evidence_required": payload.get("evidence_required", []),
            "source_docs": payload.get("source_docs", []),
            **_artifact_lifecycle_fields(artifact_ref=artifact_ref),
        }
        artifact_path = _delivery_root(omo_dir) / "tasks" / f"{task_id}.yaml"
        write_yaml_atomic(artifact_path, artifact)
        _register_ingress(
            registry,
            kind="tasks",
            item_id=task_id,
            source_ref=source_ref,
            artifact_ref=artifact_ref,
            fingerprint=payload,
            created_at=timestamp,
        )
        _write_registry(omo_dir, registry)

        parent_step_id = f"ingress:task:{task_id}:{timestamp}"
        details = (
            f"task_id={task_id} ingress_plane={ingress_plane} "
            f"source_ref={source_ref or '-'} artifact={_workspace_relative(artifact_path)}"
        )
        record_audit(
            action="ingress_create_planned_task",
            debt_id="",
            actor=ingress_plane,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{ingress_plane}",
            action="create_planned_task",
            target=f".omo/tasks/planned/{task_id}.yaml",
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=ingress_plane,
            action="create_planned_task",
            target=f".omo/tasks/planned/{task_id}.yaml",
            artifact_ref=artifact["artifact_ref"],
            source_ref=source_ref,
            created_at=timestamp,
            extra={"task_id": task_id, "ingress_plane": ingress_plane},
        )
        return payload


def create_blocked_task(
    omo_dir: Path,
    *,
    task_data: dict[str, Any],
    actor: str,
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    from omo.omo_ingress import _record_mutation, _record_trail

    errors = validate_task_data(task_data, group="blocked")
    if errors:
        raise ValueError("invalid blocked task: " + "; ".join(errors))

    task_id = str(task_data["id"])
    task_filename = f"{task_id.lower()}.yaml"
    task_path = omo_dir / "tasks" / "blocked" / task_filename
    timestamp = now or _utc_now()

    with fcntl_lock(_lock_path(omo_dir)):
        if task_path.exists():
            existing_payload = _load_yaml(task_path)
            if existing_payload == task_data:
                return existing_payload
            raise ValueError(
                f"blocked task already exists with different payload: {task_id}"
            )

        write_yaml_atomic(task_path, task_data)

        artifact = {
            "kind": "blocked_task_created",
            "task_id": task_id,
            "task_ref": f".omo/tasks/blocked/{task_filename}",
            "actor": actor,
            "source_ref": source_ref,
            "created_at": timestamp,
        }
        artifact_path = (
            _delivery_root(omo_dir)
            / "tasks"
            / f"{task_id}-blocked-{_timestamp_slug(timestamp)}.yaml"
        )
        write_yaml_atomic(artifact_path, artifact)

        parent_step_id = f"ingress:task-blocked:{task_id}:{timestamp}"
        details = (
            f"task_id={task_id} actor={actor} source_ref={source_ref or '-'} "
            f"artifact={_workspace_relative(artifact_path)}"
        )
        record_audit(
            action="ingress_create_blocked_task",
            debt_id="",
            actor=actor,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="create_blocked_task",
            target=f".omo/tasks/blocked/{task_filename}",
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="create_blocked_task",
            target=f".omo/tasks/blocked/{task_filename}",
            artifact_ref=f"runtime/omo/_delivery/ingress/tasks/{artifact_path.name}",
            source_ref=source_ref,
            created_at=timestamp,
            extra={"task_id": task_id},
        )
        return deepcopy(task_data)


def record_task_consensus(
    omo_dir: Path,
    *,
    task_id: str,
    actor: str,
    message: str,
    task_status: str | None = None,
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    from omo.omo_ingress import _record_mutation, _record_trail

    timestamp = now or _utc_now()
    resolved = _find_task_path(omo_dir, task_id, groups=("active", "blocked", "done"))
    if resolved is None:
        raise ValueError(f"task not found in active/blocked/done: {task_id}")
    group, task_path = resolved
    evidence_filename = f"{task_id.lower()}-{_timestamp_slug(timestamp)}.yaml"
    evidence_path = (
        omo_dir / "_delivery" / "task-center" / "consensus" / evidence_filename
    )

    with fcntl_lock(_lock_path(omo_dir)):
        payload = _load_yaml(task_path)
        evidence = {
            "task_id": task_id,
            "classification": "positive_confirmation",
            "message": message,
            "confirmed_at": timestamp,
            "task_status": task_status or payload.get("status"),
        }
        evidence_ref = f".omo/_delivery/task-center/consensus/{evidence_filename}"
        handoff_refs = payload.setdefault("handoff_refs", [])
        if isinstance(handoff_refs, list) and evidence_ref not in handoff_refs:
            handoff_refs.append(evidence_ref)

        errors = validate_task_data(payload, group=group)
        if errors:
            raise ValueError(
                "invalid task after consensus update: " + "; ".join(errors)
            )

        write_yaml_atomic(evidence_path, evidence)
        write_yaml_atomic(task_path, payload)

        artifact = {
            "kind": "task_consensus_recorded",
            "task_id": task_id,
            "task_ref": f".omo/tasks/{group}/{task_path.name}",
            "evidence_ref": evidence_ref,
            "actor": actor,
            "source_ref": source_ref,
            "recorded_at": timestamp,
        }
        artifact_path = (
            _delivery_root(omo_dir)
            / "tasks"
            / f"{task_id}-consensus-{_timestamp_slug(timestamp)}.yaml"
        )
        write_yaml_atomic(artifact_path, artifact)

        parent_step_id = f"ingress:task-consensus:{task_id}:{timestamp}"
        details = (
            f"task_id={task_id} actor={actor} evidence_ref={evidence_ref} "
            f"source_ref={source_ref or '-'} artifact={_workspace_relative(artifact_path)}"
        )
        record_audit(
            action="ingress_record_task_consensus",
            debt_id="",
            actor=actor,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="record_task_consensus",
            target=evidence_ref,
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="record_task_consensus",
            target=evidence_ref,
            artifact_ref=f"runtime/omo/_delivery/ingress/tasks/{artifact_path.name}",
            source_ref=source_ref,
            created_at=timestamp,
            extra={"task_id": task_id, "task_group": group},
        )
        return artifact


def record_task_execution(
    omo_dir: Path,
    *,
    task_id: str,
    actor: str,
    command: str,
    exit_code: int,
    log_ref: str,
    closeout_ref: str = "",
    source_ref: str = "",
    allow_command_override: bool = False,
    now: str | None = None,
) -> dict[str, Any]:
    """Record a human/worker execution result without executing a command."""
    from omo.omo_ingress import _record_mutation, _record_trail

    if not command.strip():
        raise ValueError("command must be a non-empty string")
    if not isinstance(exit_code, int) or isinstance(exit_code, bool):
        raise ValueError("exit_code must be an integer")
    if not log_ref.strip():
        raise ValueError("log_ref must be a non-empty workspace reference")

    timestamp = now or _utc_now()
    resolved = _find_task_path(omo_dir, task_id, groups=("planned", "active", "done"))
    if resolved is None:
        raise ValueError(f"task not found in planned/active/done: {task_id}")
    group, task_path = resolved
    execution_filename = f"{task_id.lower()}-{_timestamp_slug(timestamp)}.yaml"
    execution_path = (
        omo_dir / "_delivery" / "task-center" / "execution" / execution_filename
    )
    execution_ref = f".omo/_delivery/task-center/execution/{execution_filename}"

    with fcntl_lock(_lock_path(omo_dir)):
        payload = _load_yaml(task_path)
        metadata = payload.setdefault("metadata", {})
        if not isinstance(metadata, dict):
            raise ValueError("task metadata must be a mapping")
        expected_command = str(metadata.get("command") or command).strip()
        if not allow_command_override and expected_command != command.strip():
            raise ValueError("execution command does not match the task contract")
        if allow_command_override:
            expected_command = command.strip()
        execution = {
            "command": expected_command,
            "exit_code": exit_code,
            "log_ref": log_ref.strip(),
            "closeout_ref": closeout_ref.strip() or None,
            "actor": actor,
            "recorded_at": timestamp,
        }
        metadata["execution_audit"] = execution
        handoff_refs = payload.setdefault("handoff_refs", [])
        if isinstance(handoff_refs, list) and execution_ref not in handoff_refs:
            handoff_refs.append(execution_ref)
        errors = validate_task_data(payload, group=group)
        if errors:
            raise ValueError(
                "invalid task after execution record: " + "; ".join(errors)
            )

        write_yaml_atomic(
            execution_path,
            {
                "task_id": task_id,
                "task_ref": f".omo/tasks/{group}/{task_path.name}",
                **execution,
            },
        )
        write_yaml_atomic(task_path, payload)
        artifact = {
            "kind": "task_execution_recorded",
            "task_id": task_id,
            "task_ref": f".omo/tasks/{group}/{task_path.name}",
            "execution_ref": execution_ref,
            **execution,
            "source_ref": source_ref,
        }
        artifact_path = (
            _delivery_root(omo_dir)
            / "tasks"
            / f"{task_id}-execution-{_timestamp_slug(timestamp)}.yaml"
        )
        write_yaml_atomic(artifact_path, artifact)
        parent_step_id = f"ingress:task-execution:{task_id}:{timestamp}"
        record_audit(
            action="ingress_record_task_execution",
            debt_id="",
            actor=actor,
            details=(
                f"task_id={task_id} exit_code={exit_code} log_ref={log_ref.strip()} "
                f"execution_ref={execution_ref}"
            ),
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="record_task_execution",
            target=execution_ref,
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="record_task_execution",
            target=execution_ref,
            artifact_ref=f"runtime/omo/_delivery/ingress/tasks/{artifact_path.name}",
            source_ref=source_ref,
            created_at=timestamp,
            extra={"task_id": task_id, "task_group": group, "exit_code": exit_code},
        )
        return artifact


def execute_controlled_task(
    omo_dir: Path,
    *,
    task_id: str,
    actor: str,
    timeout_seconds: int = 120,
    source_ref: str = "",
    command_override: str | None = None,
) -> dict[str, Any]:
    """Run a low-risk project verification and record its result through ingress."""
    max_timeout_seconds = 900
    if not isinstance(timeout_seconds, int) or isinstance(timeout_seconds, bool):
        raise ValueError("timeout_seconds must be an integer")
    timeout_seconds = max(1, min(timeout_seconds, max_timeout_seconds))
    task_path = omo_dir / "tasks" / "active" / f"{task_id}.yaml"
    if not task_path.exists():
        raise ValueError("Only active tasks can be controlled-executed")

    payload = _load_yaml(task_path)
    metadata = payload.get("metadata") or {}
    if metadata.get("controlled_execution") is not True:
        raise ValueError("Task is not eligible for controlled execution")
    command = str(command_override or metadata.get("command") or "").strip()
    if not command:
        raise ValueError("Task has no execution command")
    action_id = str(metadata.get("action_id") or "")
    if action_id not in {"copy-verify-command", "runtime-check-ports"}:
        raise ValueError(
            "Only project verification and runtime port probes can be controlled-executed"
        )

    workspace_root = omo_dir.parent.resolve()
    cwd = workspace_root
    command_body = command
    if action_id == "copy-verify-command":
        match = re.fullmatch(r'cd "([^"]+)" && (.+)', command, flags=re.DOTALL)
        if not match:
            raise ValueError(
                "Controlled verification command must declare an explicit working directory"
            )
        cwd = Path(match.group(1)).expanduser().resolve()
        try:
            cwd.relative_to(workspace_root)
        except ValueError as exc:
            raise ValueError(
                "Controlled verification working directory must be inside Workspace"
            ) from exc
        command_body = match.group(2).strip()
        if any(
            token in command_body
            for token in (";", "|", ">", "<", "$(", "`", "&&", "||", "\n", "\r")
        ):
            raise ValueError(
                "Controlled verification command contains unsupported shell composition"
            )

    timestamp = _utc_now()
    slug = _timestamp_slug(timestamp)
    log_path = _delivery_root(omo_dir) / "task-execution" / f"{task_id}-{slug}.log"
    try:
        if action_id == "runtime-check-ports":
            ports = metadata.get("probe_ports")
            if (
                not isinstance(ports, list)
                or not ports
                or any(
                    isinstance(port, bool)
                    or not isinstance(port, int)
                    or not 1 <= port <= 65535
                    for port in ports
                )
            ):
                raise ValueError("Runtime port probe must declare valid probe_ports")
            outputs = []
            exit_code = 0
            for port in ports:
                result = subprocess.run(
                    ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"],
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                    check=False,
                )
                if result.returncode != 0:
                    exit_code = 1
                outputs.append(
                    f"port={port}\n{result.stdout or ''}{result.stderr or ''}"
                )
            output = "\n".join(outputs)
        else:
            result = subprocess.run(
                command_body,
                cwd=cwd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
            exit_code = result.returncode
            output = (result.stdout or "") + (result.stderr or "")
    except subprocess.TimeoutExpired as exc:
        exit_code = 124
        stdout = (
            exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        )
        stderr = (
            exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        )
        output = stdout + stderr + f"\nTimed out after {timeout_seconds}s\n"
    write_text_atomic(log_path, output)
    log_ref = str(log_path.resolve().relative_to(workspace_root))
    artifact = record_task_execution(
        omo_dir,
        task_id=task_id,
        actor=actor,
        command=command,
        exit_code=exit_code,
        log_ref=log_ref,
        source_ref=source_ref,
        allow_command_override=command_override is not None,
        now=timestamp,
    )
    return {
        **artifact,
        "exit_code": exit_code,
        "log_ref": log_ref,
        "timed_out": exit_code == 124,
    }


def _controlled_process_context(
    omo_dir: Path, task_id: str
) -> tuple[Path, dict[str, Any]]:
    task_path = omo_dir / "tasks" / "active" / f"{task_id}.yaml"
    if not task_path.exists():
        raise ValueError("Only active tasks can control a service process")
    payload = _load_yaml(task_path)
    metadata = payload.get("metadata") or {}
    if metadata.get("controlled_process") is not True:
        raise ValueError("Task is not eligible for controlled process execution")
    if str(metadata.get("action_id") or "") != "copy-start-command":
        raise ValueError("Only project start actions can control a service process")
    command = str(metadata.get("command") or "").strip()
    match = re.fullmatch(r'cd "([^"]+)" && (.+)', command, flags=re.DOTALL)
    if not match:
        raise ValueError(
            "Controlled start command must declare an explicit working directory"
        )
    cwd = Path(match.group(1)).expanduser().resolve()
    workspace_root = omo_dir.parent.resolve()
    try:
        cwd.relative_to(workspace_root)
    except ValueError as exc:
        raise ValueError(
            "Controlled start working directory must be inside Workspace"
        ) from exc
    command_body = match.group(2).strip()
    if any(
        token in command_body
        for token in (";", "|", ">", "<", "$(", "`", "&&", "||", "&", "\n", "\r")
    ):
        raise ValueError(
            "Controlled start command contains unsupported shell composition"
        )
    return task_path, {
        "payload": payload,
        "metadata": metadata,
        "command": command,
        "cwd": cwd,
        "command_body": command_body,
        "workspace_root": workspace_root,
    }


def start_controlled_task(
    omo_dir: Path,
    *,
    task_id: str,
    actor: str,
    source_ref: str = "",
) -> dict[str, Any]:
    """Start an approved project service in its own process group and audit it."""
    from omo.omo_ingress import _record_mutation, _record_trail

    task_path, context = _controlled_process_context(omo_dir, task_id)
    payload = context["payload"]
    if payload.get("human_approval_required"):
        approval_ref = payload.get("approval_ref")
        approval_path = omo_dir.parent / str(approval_ref or "")
        approval = _load_yaml(approval_path) if approval_ref else {}
        if approval.get("approval_status") != "granted":
            raise ValueError("Task approval must be granted before process start")
    prior = context["metadata"].get("execution_process")
    if isinstance(prior, dict) and prior.get("status") == "started":
        raise ValueError(
            "Task already has a started process; stop it before starting again"
        )

    timestamp = _utc_now()
    slug = _timestamp_slug(timestamp)
    log_path = (
        _delivery_root(omo_dir) / "task-execution" / f"{task_id}-start-{slug}.log"
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("ab") as log_file:
        process = subprocess.Popen(
            context["command_body"],
            cwd=context["cwd"],
            shell=True,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    log_ref = str(log_path.resolve().relative_to(context["workspace_root"]))
    process_record = {
        "status": "started",
        "pid": process.pid,
        "process_group_id": process.pid,
        "command": context["command"],
        "log_ref": log_ref,
        "actor": actor,
        "started_at": timestamp,
    }
    execution_filename = f"{task_id.lower()}-process-{slug}.yaml"
    execution_path = (
        omo_dir / "_delivery" / "task-center" / "execution" / execution_filename
    )
    execution_ref = f".omo/_delivery/task-center/execution/{execution_filename}"
    with fcntl_lock(_lock_path(omo_dir)):
        payload = _load_yaml(task_path)
        payload.setdefault("metadata", {})["execution_process"] = process_record
        handoff_refs = payload.setdefault("handoff_refs", [])
        if execution_ref not in handoff_refs:
            handoff_refs.append(execution_ref)
        write_yaml_atomic(execution_path, {"task_id": task_id, **process_record})
        write_yaml_atomic(task_path, payload)
        artifact = {
            "kind": "task_process_started",
            "task_id": task_id,
            "task_ref": f".omo/tasks/active/{task_path.name}",
            "execution_ref": execution_ref,
            **process_record,
            "source_ref": source_ref,
        }
        artifact_path = (
            _delivery_root(omo_dir) / "tasks" / f"{task_id}-process-start-{slug}.yaml"
        )
        write_yaml_atomic(artifact_path, artifact)
        parent_step_id = f"ingress:task-process-start:{task_id}:{timestamp}"
        record_audit(
            action="ingress_start_task_process",
            debt_id="",
            actor=actor,
            details=f"task_id={task_id} pid={process.pid} log_ref={log_ref} execution_ref={execution_ref}",
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="start_task_process",
            target=execution_ref,
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="start_task_process",
            target=execution_ref,
            artifact_ref=f"runtime/omo/_delivery/ingress/tasks/{artifact_path.name}",
            source_ref=source_ref,
            created_at=timestamp,
            extra={"task_id": task_id, "pid": process.pid},
        )
    watcher = threading.Thread(
        target=_watch_controlled_process,
        args=(omo_dir, task_id, task_path, process, execution_ref, actor, source_ref),
        name=f"omo-process-watch-{task_id}",
        daemon=True,
    )
    watcher.start()
    return {**process_record, "execution_ref": execution_ref}


def _watch_controlled_process(
    omo_dir: Path,
    task_id: str,
    task_path: Path,
    process: subprocess.Popen,
    execution_ref: str,
    actor: str,
    source_ref: str,
) -> None:
    """Persist a child exit code without moving execution ownership to Cockpit."""
    try:
        exit_code = process.wait()
    except OSError:
        return

    from omo.omo_ingress import _record_mutation, _record_trail

    timestamp = _utc_now()
    with fcntl_lock(_lock_path(omo_dir)):
        if not task_path.exists():
            return
        payload = _load_yaml(task_path)
        metadata = payload.setdefault("metadata", {})
        current = metadata.get("execution_process") or {}
        if (
            not isinstance(current, dict)
            or int(current.get("pid") or -1) != process.pid
        ):
            return
        status = (
            current.get("status")
            if current.get("status") in {"stopped", "not_running"}
            else "exited"
        )
        process_record = {
            **current,
            "status": status,
            "exit_code": exit_code,
            "exited_at": timestamp,
        }
        metadata["execution_process"] = process_record
        write_yaml_atomic(task_path, payload)
        execution_path = omo_dir.parent / execution_ref
        write_yaml_atomic(execution_path, {"task_id": task_id, **process_record})
        artifact_path = (
            _delivery_root(omo_dir)
            / "tasks"
            / f"{task_id}-process-exit-{_timestamp_slug(timestamp)}.yaml"
        )
        write_yaml_atomic(
            artifact_path,
            {
                "kind": "task_process_exited",
                "task_id": task_id,
                "task_ref": f".omo/tasks/active/{task_path.name}",
                **process_record,
                "source_ref": source_ref,
            },
        )
        parent_step_id = f"ingress:task-process-exit:{task_id}:{timestamp}"
        record_audit(
            action="ingress_record_task_process_exit",
            debt_id="",
            actor=actor,
            details=f"task_id={task_id} pid={process.pid} status={status} exit_code={exit_code}",
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="record_task_process_exit",
            target=execution_ref,
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="record_task_process_exit",
            target=execution_ref,
            artifact_ref=f"runtime/omo/_delivery/ingress/tasks/{artifact_path.name}",
            source_ref=source_ref,
            created_at=timestamp,
            extra={"task_id": task_id, "pid": process.pid, "exit_code": exit_code},
        )


def get_controlled_process_status(omo_dir: Path, *, task_id: str) -> dict[str, Any]:
    """Read the last process record and report whether its PID is alive."""
    resolved = _find_task_path(omo_dir, task_id, groups=("active", "done"))
    if resolved is None:
        raise ValueError(f"task not found in active/done: {task_id}")
    _, task_path = resolved
    payload = _load_yaml(task_path)
    process_record = (payload.get("metadata") or {}).get("execution_process") or {}
    if not isinstance(process_record, dict) or not process_record.get("pid"):
        return {"status": "not_started", "pid": None, "log_ref": None}
    pid = int(process_record["pid"])
    status = "running" if _controlled_pid_is_running(pid) else "exited"
    return {**process_record, "status": status, "pid": pid}


def _controlled_pid_is_running(pid: int) -> bool:
    """Treat a terminated shell child in zombie state as exited."""
    try:
        os.kill(pid, 0)
    except (OSError, ValueError):
        return False
    try:
        probe = subprocess.run(
            ["ps", "-o", "stat=", "-p", str(pid)],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return True
    state = probe.stdout.strip().split(None, 1)[0] if probe.stdout.strip() else ""
    return not state.startswith("Z")


def stop_controlled_task(
    omo_dir: Path,
    *,
    task_id: str,
    actor: str,
    source_ref: str = "",
) -> dict[str, Any]:
    """Stop a previously started project process and append an OMO audit event."""
    from omo.omo_ingress import _record_mutation, _record_trail

    task_path, _ = _controlled_process_context(omo_dir, task_id)
    timestamp = _utc_now()
    with fcntl_lock(_lock_path(omo_dir)):
        payload = _load_yaml(task_path)
        metadata = payload.setdefault("metadata", {})
        process_record = metadata.get("execution_process") or {}
        if not isinstance(process_record, dict) or not process_record.get("pid"):
            raise ValueError("Task has no controlled process to stop")
        pid = int(process_record["pid"])
        stop_status = "stopped"
        try:
            if not _controlled_pid_is_running(pid):
                stop_status = "not_running"
            else:
                os.killpg(
                    int(process_record.get("process_group_id") or pid), signal.SIGTERM
                )
        except ProcessLookupError:
            stop_status = "not_running"
        except OSError as exc:
            raise ValueError(f"Unable to stop controlled process: {exc}") from exc
        process_record = {
            **process_record,
            "status": stop_status,
            "stopped_at": timestamp,
            "stopped_by": actor,
        }
        metadata["execution_process"] = process_record
        write_yaml_atomic(task_path, payload)
        artifact = {
            "kind": "task_process_stopped",
            "task_id": task_id,
            "task_ref": f".omo/tasks/active/{task_path.name}",
            **process_record,
            "source_ref": source_ref,
        }
        artifact_path = (
            _delivery_root(omo_dir)
            / "tasks"
            / f"{task_id}-process-stop-{_timestamp_slug(timestamp)}.yaml"
        )
        write_yaml_atomic(artifact_path, artifact)
        parent_step_id = f"ingress:task-process-stop:{task_id}:{timestamp}"
        record_audit(
            action="ingress_stop_task_process",
            debt_id="",
            actor=actor,
            details=f"task_id={task_id} pid={pid} status={stop_status}",
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="stop_task_process",
            target=f".omo/tasks/active/{task_path.name}",
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="stop_task_process",
            target=f".omo/tasks/active/{task_path.name}",
            artifact_ref=f"runtime/omo/_delivery/ingress/tasks/{artifact_path.name}",
            source_ref=source_ref,
            created_at=timestamp,
            extra={"task_id": task_id, "pid": pid, "status": stop_status},
        )
    return process_record


def restart_controlled_task(
    omo_dir: Path,
    *,
    task_id: str,
    actor: str,
    source_ref: str = "",
    timeout_seconds: float = 5.0,
) -> dict[str, Any]:
    """Restart a controlled process only after the old process has exited."""
    current = get_controlled_process_status(omo_dir, task_id=task_id)
    if current.get("status") != "running":
        raise ValueError("Task must have a running controlled process to restart")

    stop_controlled_task(
        omo_dir,
        task_id=task_id,
        actor=actor,
        source_ref=f"{source_ref}:stop" if source_ref else "restart:stop",
    )
    deadline = time.monotonic() + max(0.1, timeout_seconds)
    while time.monotonic() < deadline:
        if (
            get_controlled_process_status(omo_dir, task_id=task_id).get("status")
            != "running"
        ):
            break
        time.sleep(0.05)
    else:
        raise ValueError("Controlled process did not exit before restart timeout")

    return start_controlled_task(
        omo_dir,
        task_id=task_id,
        actor=actor,
        source_ref=f"{source_ref}:start" if source_ref else "restart:start",
    )


def complete_task(
    omo_dir: Path,
    *,
    task_id: str,
    actor: str,
    source_ref: str = "",
    now: str | None = None,
    evidence_paths: list[str] | None = None,
) -> dict[str, Any]:
    from omo.omo_ingress import _record_mutation, _record_trail

    timestamp = now or _utc_now()
    task_roots = {
        "active": omo_dir / "tasks" / "active" / f"{task_id}.yaml",
        "planned": omo_dir / "tasks" / "planned" / f"{task_id}.yaml",
    }
    done_path = omo_dir / "tasks" / "done" / f"{task_id}.yaml"

    with fcntl_lock(_lock_path(omo_dir)):
        src_group: str | None = None
        src_path: Path | None = None
        for group, candidate in task_roots.items():
            if candidate.exists():
                src_group = group
                src_path = candidate
                break

        if src_path is None:
            if done_path.exists():
                existing_payload = _load_yaml(done_path)
                metadata = existing_payload.get("metadata", {})
                metadata_completed_at = (
                    metadata.get("completed_at") if isinstance(metadata, dict) else None
                )
                if not existing_payload.get("completed_at") and metadata_completed_at:
                    existing_payload["completed_at"] = metadata_completed_at
                    write_yaml_atomic(done_path, existing_payload)
                return existing_payload
            raise ValueError(f"task not found in active/planned/done: {task_id}")

        payload = _load_yaml(src_path)
        payload["status"] = "done"
        payload["completed_at"] = timestamp
        if evidence_paths is not None:
            payload["evidence_paths"] = evidence_paths
        metadata = payload.setdefault("metadata", {})
        if isinstance(metadata, dict):
            metadata["completed_at"] = timestamp
            metadata["completed_via"] = "omo task done"
            metadata["completion_actor"] = actor
            if source_ref:
                metadata["completion_source_ref"] = source_ref

        errors = validate_task_data(payload, group="done")
        if errors:
            raise ValueError("invalid completed task: " + "; ".join(errors))

        write_yaml_atomic(done_path, payload)
        src_path.unlink()

        artifact = {
            "kind": "task_completed",
            "task_id": task_id,
            "source_group": src_group,
            "task_ref_before": f".omo/tasks/{src_group}/{task_id}.yaml",
            "task_ref_after": f".omo/tasks/done/{task_id}.yaml",
            "actor": actor,
            "source_ref": source_ref,
            "completed_at": timestamp,
        }
        artifact_path = (
            _delivery_root(omo_dir)
            / "tasks"
            / f"{task_id}-done-{_timestamp_slug(timestamp)}.yaml"
        )
        write_yaml_atomic(artifact_path, artifact)

        parent_step_id = f"ingress:task-done:{task_id}:{timestamp}"
        details = (
            f"task_id={task_id} actor={actor} from={src_group} "
            f"source_ref={source_ref or '-'} artifact={_workspace_relative(artifact_path)}"
        )
        record_audit(
            action="ingress_complete_task",
            debt_id="",
            actor=actor,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="complete_task",
            target=f".omo/tasks/done/{task_id}.yaml",
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="complete_task",
            target=f".omo/tasks/done/{task_id}.yaml",
            artifact_ref=f"runtime/omo/_delivery/ingress/tasks/{artifact_path.name}",
            source_ref=source_ref,
            created_at=timestamp,
            extra={"task_id": task_id, "source_group": src_group},
        )
        return payload


def update_done_task_evidence_paths(
    omo_dir: Path,
    *,
    task_id: str,
    evidence_paths: list[str],
    actor: str,
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    from omo.omo_ingress import _record_mutation, _record_trail

    timestamp = now or _utc_now()
    task_path = omo_dir / "tasks" / "done" / f"{task_id}.yaml"
    if not task_path.exists():
        raise ValueError(f"done task not found: {task_id}")
    if not isinstance(evidence_paths, list) or not all(
        isinstance(item, str) and item for item in evidence_paths
    ):
        raise ValueError("evidence_paths must be a non-empty list[str]")

    with fcntl_lock(_lock_path(omo_dir)):
        payload = _load_yaml(task_path)
        payload["evidence_paths"] = evidence_paths
        metadata = payload.setdefault("metadata", {})
        metadata["evidence_paths_refreshed_at"] = timestamp
        metadata["evidence_paths_refreshed_by"] = actor
        metadata["evidence_paths_refresh_source_ref"] = source_ref
        write_yaml_atomic(task_path, payload)

        artifact = {
            "kind": "done_task_evidence_paths_updated",
            "task_ref": f".omo/tasks/done/{task_id}.yaml",
            "evidence_paths": evidence_paths,
            "actor": actor,
            "source_ref": source_ref,
            "updated_at": timestamp,
        }
        artifact_path = (
            _delivery_root(omo_dir)
            / "tasks"
            / f"{task_id}-evidence-refresh-{_timestamp_slug(timestamp)}.yaml"
        )
        write_yaml_atomic(artifact_path, artifact)
        parent_step_id = f"ingress:task-evidence-refresh:{task_id}:{timestamp}"
        details = (
            f"task_id={task_id} actor={actor} source_ref={source_ref or '-'} "
            f"artifact={_workspace_relative(artifact_path)}"
        )
        record_audit(
            action="ingress_update_done_task_evidence_paths",
            debt_id="",
            actor=actor,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="update_done_task_evidence_paths",
            target=f".omo/tasks/done/{task_id}.yaml",
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="update_done_task_evidence_paths",
            target=f".omo/tasks/done/{task_id}.yaml",
            artifact_ref=f"runtime/omo/_delivery/ingress/tasks/{artifact_path.name}",
            source_ref=source_ref,
            created_at=timestamp,
            extra={"task_id": task_id},
        )
        return deepcopy(payload)


def update_planned_task_evidence_paths(
    omo_dir: Path,
    *,
    task_id: str,
    evidence_paths: list[str],
    actor: str,
    source_ref: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    from omo.omo_ingress import _record_mutation, _record_trail

    """Add evidence_paths to a planned/active task (未归档, done 前补 evidence).

    解决归档 gap: done 需 evidence, refresh-evidence 只查 done/, planned 无加 evidence 命令.
    """
    timestamp = now or _utc_now()
    task_path: Path | None = None
    for sub in ("planned", "active"):
        candidate = omo_dir / "tasks" / sub / f"{task_id}.yaml"
        if candidate.exists():
            task_path = candidate
            break
    if task_path is None:
        raise ValueError(f"planned/active task not found: {task_id}")
    if not isinstance(evidence_paths, list) or not all(
        isinstance(item, str) and item for item in evidence_paths
    ):
        raise ValueError("evidence_paths must be a non-empty list[str]")

    with fcntl_lock(_lock_path(omo_dir)):
        payload = _load_yaml(task_path)
        payload["evidence_paths"] = evidence_paths
        metadata = payload.setdefault("metadata", {})
        metadata["evidence_paths_refreshed_at"] = timestamp
        metadata["evidence_paths_refreshed_by"] = actor
        metadata["evidence_paths_refresh_source_ref"] = source_ref
        write_yaml_atomic(task_path, payload)

        artifact = {
            "kind": "planned_task_evidence_paths_added",
            "task_ref": str(task_path.relative_to(omo_dir)),
            "evidence_paths": evidence_paths,
            "actor": actor,
            "source_ref": source_ref,
            "updated_at": timestamp,
        }
        artifact_path = (
            _delivery_root(omo_dir)
            / "tasks"
            / f"{task_id}-evidence-add-{_timestamp_slug(timestamp)}.yaml"
        )
        write_yaml_atomic(artifact_path, artifact)
        parent_step_id = f"ingress:task-evidence-add:{task_id}:{timestamp}"
        details = (
            f"task_id={task_id} actor={actor} source_ref={source_ref or '-'} "
            f"artifact={_workspace_relative(artifact_path)}"
        )
        record_audit(
            action="ingress_update_planned_task_evidence_paths",
            debt_id="",
            actor=actor,
            details=details,
            audit_file=_audit_log_path(omo_dir),
        )
        _record_trail(
            omo_dir,
            actor=f"broker:{actor}",
            action="update_planned_task_evidence_paths",
            target=str(task_path.relative_to(omo_dir)),
            parent_step_id=parent_step_id,
        )
        _record_mutation(
            omo_dir,
            actor=actor,
            action="update_planned_task_evidence_paths",
            target=str(task_path.relative_to(omo_dir.parent)),
            artifact_ref=f"runtime/omo/_delivery/ingress/tasks/{artifact_path.name}",
            source_ref=source_ref,
            created_at=timestamp,
            extra={"task_id": task_id},
        )
        return deepcopy(payload)
