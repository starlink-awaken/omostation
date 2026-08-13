#!/usr/bin/env python3
"""Create and observe a manually supervised Codex worker through Orca.

The adapter records transport provenance only.  It deliberately never treats an
Orca ready receipt, TUI idleness, or a terminal handle as evidence that Codex
accepted input or completed model work.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

SCHEMA = "orca-codex-supervisor/v1"
IDENTITY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:+-]{0,127}$")
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
Command = tuple[str, ...]
Runner = Callable[[Command, float], tuple[int, str, str]]


def _subprocess_runner(
    command: Command, timeout_seconds: float
) -> tuple[int, str, str]:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            check=False,
            shell=False,
            text=True,
            timeout=timeout_seconds,
        )
    except FileNotFoundError as exc:
        return 127, "", str(exc)
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else "command timed out"
        return 124, stdout, stderr
    return completed.returncode, completed.stdout, completed.stderr


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def _digest_payload(payload: dict[str, Any]) -> str:
    return (
        "sha256:" + hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    )


def _valid_identity(value: str) -> bool:
    return bool(IDENTITY_RE.fullmatch(value))


def _binding(
    *,
    workflow_run_id: str,
    omo_task_id: str,
    packet_id: str,
    packet_hash: str,
    omo_dispatch_id: str,
    prompt_ref: str,
    prompt_digest: str,
) -> dict[str, str] | None:
    values = {
        "workflow_run_id": workflow_run_id,
        "omo_task_id": omo_task_id,
        "packet_id": packet_id,
        "packet_hash": packet_hash,
        "omo_dispatch_id": omo_dispatch_id,
        "prompt_ref": prompt_ref,
        "prompt_digest": prompt_digest,
    }
    identity_values = (
        workflow_run_id,
        omo_task_id,
        packet_id,
        omo_dispatch_id,
    )
    if (
        not all(_valid_identity(value) for value in identity_values)
        or not SHA256_RE.fullmatch(packet_hash)
        or not SHA256_RE.fullmatch(prompt_digest)
    ):
        return None
    return values


def _read_prompt(
    *, workspace_root: str, prompt_ref: str, prompt_digest: str
) -> tuple[str | None, str | None]:
    raw_ref = Path(prompt_ref)
    if (
        not prompt_ref
        or "\\" in prompt_ref
        or raw_ref.is_absolute()
        or ".." in raw_ref.parts
        or str(PurePosixPath(prompt_ref)) != prompt_ref
    ):
        return None, "prompt_ref_unsafe"
    try:
        root = Path(workspace_root).expanduser().resolve(strict=True)
        if not root.is_dir():
            return None, "prompt_ref_unsafe"
        candidate = root / raw_ref
        cursor = root
        for part in raw_ref.parts:
            cursor /= part
            if cursor.is_symlink():
                return None, "prompt_ref_unsafe"
        resolved = candidate.resolve(strict=True)
        if resolved != candidate or not resolved.is_file():
            return None, "prompt_ref_unsafe"
        metadata = os.stat(resolved)
        if not stat.S_ISREG(metadata.st_mode):
            return None, "prompt_ref_unsafe"
        prompt = resolved.read_text(encoding="utf-8")
    except (OSError, UnicodeError, ValueError):
        return None, "prompt_ref_unsafe"
    observed_digest = "sha256:" + hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    if observed_digest != prompt_digest:
        return None, "prompt_digest_mismatch"
    return prompt, None


def _orca_refs(
    *,
    orca_run_id: str,
    orca_task_id: str,
    orca_dispatch_id: str,
    terminal_handle: str,
) -> dict[str, str] | None:
    values = {
        "run_id": orca_run_id,
        "task_id": orca_task_id,
        "dispatch_id": orca_dispatch_id,
        "terminal_handle": terminal_handle,
    }
    return values if all(_valid_identity(value) for value in values.values()) else None


def _worker_failure_context(
    result: dict[str, Any], *, orca_run_id: str, residual_resources: list[str]
) -> tuple[dict[str, str] | None, list[str]]:
    dispatch_id = result.get("dispatchId")
    task_id = result.get("taskId")
    terminal_handle = result.get("agentTerminalHandle")
    reported_run_id = result.get("runId")
    worker_orca = (
        _orca_refs(
            orca_run_id=reported_run_id,
            orca_task_id=task_id,
            orca_dispatch_id=dispatch_id,
            terminal_handle=terminal_handle,
        )
        if isinstance(reported_run_id, str)
        and isinstance(dispatch_id, str)
        and isinstance(task_id, str)
        and isinstance(terminal_handle, str)
        else None
    )
    resources = list(residual_resources)
    if worker_orca:
        for resource in (
            f"orca:run:{worker_orca['run_id']}",
            f"orca:task:{worker_orca['task_id']}",
            f"orca:dispatch:{worker_orca['dispatch_id']}",
            f"orca:terminal:{worker_orca['terminal_handle']}",
        ):
            if resource not in resources:
                resources.append(resource)
    return worker_orca, resources


def _failure(
    *,
    binding: dict[str, str] | None,
    stage: str,
    reason: str,
    orca: dict[str, str] | None = None,
    residual_resources: list[str] | None = None,
) -> dict[str, Any]:
    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "ok": False,
        "stage": stage,
        "reason": reason,
        "binding": binding or {},
        "residual_resources": (
            residual_resources
            if residual_resources is not None
            else [orca["terminal_handle"]]
            if orca
            else []
        ),
    }
    if orca:
        receipt["orca"] = orca
    return receipt


def _response(
    runner: Runner,
    command: Command,
    *,
    timeout_seconds: float,
    binding: dict[str, str],
    stage: str,
    reason: str,
    orca: dict[str, str] | None = None,
    residual_resources: list[str] | None = None,
    failure_context: Callable[[dict[str, Any]], tuple[dict[str, str] | None, list[str]]]
    | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    returncode, stdout, _stderr = runner(command, timeout_seconds)
    try:
        payload = json.loads(stdout)
    except (TypeError, json.JSONDecodeError):
        return None, _failure(
            binding=binding,
            stage=stage,
            reason="orca_response_invalid",
            orca=orca,
            residual_resources=residual_resources,
        )
    result = payload.get("result") if isinstance(payload, dict) else None
    failure_orca = orca
    failure_resources = residual_resources
    if isinstance(result, dict) and failure_context is not None:
        failure_orca, failure_resources = failure_context(result)
    if (
        returncode != 0
        or not isinstance(payload, dict)
        or payload.get("ok") is not True
        or not isinstance(result, dict)
    ):
        return None, _failure(
            binding=binding,
            stage=stage,
            reason=reason,
            orca=failure_orca,
            residual_resources=failure_resources,
        )
    return result, None


def start_supervised_codex(
    *,
    workflow_run_id: str,
    omo_task_id: str,
    packet_id: str,
    packet_hash: str,
    omo_dispatch_id: str,
    workspace_root: str,
    prompt_ref: str,
    prompt_digest: str,
    idempotency_key: str | None = None,
    codex_executable: str | None = None,
    timeout_ms: int = 60_000,
    runner: Runner = _subprocess_runner,
) -> dict[str, Any]:
    """Create one Orca Codex worker and return only supervised transport facts."""
    binding = _binding(
        workflow_run_id=workflow_run_id,
        omo_task_id=omo_task_id,
        packet_id=packet_id,
        packet_hash=packet_hash,
        omo_dispatch_id=omo_dispatch_id,
        prompt_ref=prompt_ref,
        prompt_digest=prompt_digest,
    )
    if binding is None:
        return _failure(binding=None, stage="input", reason="identity_invalid")
    if idempotency_key is not None and not _valid_identity(idempotency_key):
        return _failure(
            binding=binding, stage="input", reason="idempotency_key_invalid"
        )
    if timeout_ms <= 0:
        return _failure(binding=binding, stage="input", reason="timeout_invalid")
    prompt, prompt_error = _read_prompt(
        workspace_root=workspace_root,
        prompt_ref=prompt_ref,
        prompt_digest=prompt_digest,
    )
    if prompt_error:
        return _failure(binding=binding, stage="input", reason=prompt_error)
    assert prompt is not None
    resolved_codex = codex_executable or shutil.which("codex")
    if not isinstance(resolved_codex, str):
        return _failure(binding=binding, stage="input", reason="codex_not_found")
    codex_path = Path(resolved_codex)
    if not codex_path.is_absolute() or codex_path.name != "codex":
        return _failure(binding=binding, stage="input", reason="codex_path_unsafe")
    try:
        resolved_workspace = str(Path(workspace_root).resolve(strict=True))
    except OSError:
        return _failure(binding=binding, stage="input", reason="workspace_root_unsafe")
    retry_requests: dict[str, str] = {}
    if idempotency_key is not None:
        for stage in ("run-create", "task-create", "worker-start"):
            retry_requests[stage] = hashlib.sha256(
                f"{idempotency_key}\n{stage}".encode()
            ).hexdigest()

    def retry_request(stage: str) -> tuple[str, ...]:
        value = retry_requests.get(stage)
        return ("--retry-request", value) if value is not None else ()

    status, failure = _response(
        runner,
        ("orca", "status", "--json"),
        timeout_seconds=10.0,
        binding=binding,
        stage="status",
        reason="orca_runtime_not_ready",
    )
    if failure:
        return failure
    assert status is not None
    app = status.get("app")
    runtime = status.get("runtime")
    if (
        not isinstance(app, dict)
        or app.get("running") is not True
        or not isinstance(runtime, dict)
        or runtime.get("state") != "ready"
    ):
        return _failure(
            binding=binding, stage="status", reason="orca_runtime_not_ready"
        )

    objective = "supervised-codex:{workflow_run_id}:{omo_task_id}:{packet_id}:{omo_dispatch_id}".format(
        **binding
    )
    created_run, failure = _response(
        runner,
        (
            "orca",
            "orchestration",
            "run-create",
            "--objective",
            objective,
            *retry_request("run-create"),
            "--json",
        ),
        timeout_seconds=30.0,
        binding=binding,
        stage="run_create",
        reason="orca_run_not_created",
    )
    if failure:
        return failure
    assert created_run is not None
    run = created_run.get("run")
    orca_run_id = run.get("id") if isinstance(run, dict) else None
    coordinator_handle = (
        run.get("coordinator_handle") if isinstance(run, dict) else None
    )
    if (
        not isinstance(orca_run_id, str)
        or not _valid_identity(orca_run_id)
        or not isinstance(coordinator_handle, str)
        or not _valid_identity(coordinator_handle)
    ):
        return _failure(
            binding=binding, stage="run_create", reason="orca_response_invalid"
        )
    run_residuals = [f"orca:run:{orca_run_id}"]

    created_task, failure = _response(
        runner,
        (
            "orca",
            "orchestration",
            "task-create",
            "--run",
            orca_run_id,
            "--task-title",
            f"supervised-codex-{omo_task_id}",
            "--spec",
            prompt,
            *retry_request("task-create"),
            "--json",
        ),
        timeout_seconds=30.0,
        binding=binding,
        stage="task_create",
        reason="orca_task_not_created",
        residual_resources=run_residuals,
    )
    if failure:
        return failure
    assert created_task is not None
    task = created_task.get("task")
    orca_task_id = task.get("id") if isinstance(task, dict) else None
    task_run_id = task.get("run_id") if isinstance(task, dict) else None
    if (
        not isinstance(orca_task_id, str)
        or not _valid_identity(orca_task_id)
        or task_run_id != orca_run_id
    ):
        return _failure(
            binding=binding,
            stage="task_create",
            reason="orca_response_invalid",
            residual_resources=run_residuals,
        )
    run_task_residuals = [*run_residuals, f"orca:task:{orca_task_id}"]

    codex_command = shlex.join(
        (
            resolved_codex,
            "--ask-for-approval",
            "on-request",
            "--sandbox",
            "read-only",
            "-C",
            resolved_workspace,
        )
    )
    created_terminal, failure = _response(
        runner,
        (
            "orca",
            "terminal",
            "create",
            "--worktree",
            f"path:{resolved_workspace}",
            "--title",
            f"supervised-codex-{omo_task_id}",
            "--command",
            codex_command,
            "--json",
        ),
        timeout_seconds=30.0,
        binding=binding,
        stage="terminal_create",
        reason="orca_terminal_not_created",
        residual_resources=run_task_residuals,
    )
    if failure:
        return failure
    assert created_terminal is not None
    terminal = created_terminal.get("terminal")
    terminal_handle = terminal.get("handle") if isinstance(terminal, dict) else None
    if not isinstance(terminal_handle, str) or not _valid_identity(terminal_handle):
        return _failure(
            binding=binding,
            stage="terminal_create",
            reason="orca_response_invalid",
            residual_resources=run_task_residuals,
        )
    terminal_residuals = [
        *run_task_residuals,
        f"orca:terminal:{terminal_handle}",
    ]

    waited, failure = _response(
        runner,
        (
            "orca",
            "terminal",
            "wait",
            "--terminal",
            terminal_handle,
            "--for",
            "tui-idle",
            "--timeout-ms",
            str(timeout_ms),
            "--json",
        ),
        timeout_seconds=max(30.0, timeout_ms / 1000.0),
        binding=binding,
        stage="terminal_wait",
        reason="codex_tui_not_idle",
        residual_resources=terminal_residuals,
    )
    if failure:
        return failure
    wait_result = waited.get("wait") if waited else None
    if (
        not isinstance(wait_result, dict)
        or wait_result.get("condition") != "tui-idle"
        or wait_result.get("satisfied") is not True
    ):
        return _failure(
            binding=binding,
            stage="terminal_wait",
            reason="codex_tui_not_idle",
            residual_resources=terminal_residuals,
        )

    shown, failure = _response(
        runner,
        (
            "orca",
            "terminal",
            "show",
            "--terminal",
            terminal_handle,
            "--json",
        ),
        timeout_seconds=10.0,
        binding=binding,
        stage="terminal_show",
        reason="codex_terminal_unverified",
        residual_resources=terminal_residuals,
    )
    if failure:
        return failure
    shown_terminal = shown.get("terminal") if shown else None
    if (
        not isinstance(shown_terminal, dict)
        or shown_terminal.get("handle") != terminal_handle
        or shown_terminal.get("worktreePath") != resolved_workspace
        or shown_terminal.get("connected") is not True
        or shown_terminal.get("writable") is not True
    ):
        return _failure(
            binding=binding,
            stage="terminal_show",
            reason="codex_terminal_unverified",
            residual_resources=terminal_residuals,
        )

    readback, failure = _response(
        runner,
        (
            "orca",
            "terminal",
            "read",
            "--terminal",
            terminal_handle,
            "--cursor",
            "0",
            "--limit",
            "80",
            "--json",
        ),
        timeout_seconds=10.0,
        binding=binding,
        stage="terminal_read",
        reason="codex_launch_unverified",
        residual_resources=terminal_residuals,
    )
    if failure:
        return failure
    read_terminal = readback.get("terminal") if readback else None
    tail = read_terminal.get("tail") if isinstance(read_terminal, dict) else None
    rendered_tail = "\n".join(tail) if isinstance(tail, list) else ""
    if (
        read_terminal is None
        or read_terminal.get("handle") != terminal_handle
        or codex_command not in rendered_tail
        or "--dangerously-bypass-approvals-and-sandbox" in rendered_tail
        or "--approve-for-me" in rendered_tail
    ):
        return _failure(
            binding=binding,
            stage="terminal_read",
            reason="codex_launch_unverified",
            residual_resources=terminal_residuals,
        )

    started_worker, failure = _response(
        runner,
        (
            "orca",
            "orchestration",
            "worker-start",
            "--run",
            orca_run_id,
            "--task",
            orca_task_id,
            "--worktree",
            "current",
            "--terminal",
            terminal_handle,
            "--from",
            coordinator_handle,
            *retry_request("worker-start"),
            "--json",
        ),
        timeout_seconds=max(30.0, timeout_ms / 1000.0),
        binding=binding,
        stage="worker_start",
        reason="orca_worker_not_started",
        residual_resources=terminal_residuals,
        failure_context=lambda result: _worker_failure_context(
            result,
            orca_run_id=orca_run_id,
            residual_resources=terminal_residuals,
        ),
    )
    if failure:
        return failure
    assert started_worker is not None
    orca_dispatch_id = started_worker.get("dispatchId")
    reported_terminal_handle = started_worker.get("agentTerminalHandle")
    worker_orca, worker_residuals = _worker_failure_context(
        started_worker,
        orca_run_id=orca_run_id,
        residual_resources=terminal_residuals,
    )
    if (
        started_worker.get("state") != "ready"
        or started_worker.get("taskId") != orca_task_id
        or started_worker.get("runId") != orca_run_id
        or not isinstance(orca_dispatch_id, str)
        or reported_terminal_handle != terminal_handle
    ):
        return _failure(
            binding=binding,
            stage="worker_start",
            reason="orca_response_invalid",
            orca=worker_orca,
            residual_resources=worker_residuals,
        )
    orca = _orca_refs(
        orca_run_id=orca_run_id,
        orca_task_id=orca_task_id,
        orca_dispatch_id=orca_dispatch_id,
        terminal_handle=terminal_handle,
    )
    if orca is None:
        return _failure(
            binding=binding,
            stage="worker_start",
            reason="orca_response_invalid",
            residual_resources=terminal_residuals,
        )
    receipt = {
        "schema": SCHEMA,
        "ok": True,
        "state": "awaiting_human_action",
        "binding": binding,
        "orca": orca,
        "human_action_required": True,
        "approval": {
            "mode": "manual_click",
            "policy": "on-request",
            "sandbox": "read-only",
            "write_requires_human_click": True,
        },
        "input_accepted": "unproven",
        "model_completion": "unproven",
    }
    if idempotency_key is not None:
        receipt["idempotency"] = {
            "transaction_key_digest": "sha256:"
            + hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest(),
            "stage_retry_requests": retry_requests,
        }
    return receipt


def collect_supervised_codex(
    *,
    workflow_run_id: str,
    omo_task_id: str,
    packet_id: str,
    packet_hash: str,
    omo_dispatch_id: str,
    workspace_root: str,
    prompt_ref: str,
    prompt_digest: str,
    orca_run_id: str,
    orca_task_id: str,
    orca_dispatch_id: str,
    terminal_handle: str,
    runner: Runner = _subprocess_runner,
) -> dict[str, Any]:
    """Collect a settled worker's provenance without retaining transcript content."""
    binding = _binding(
        workflow_run_id=workflow_run_id,
        omo_task_id=omo_task_id,
        packet_id=packet_id,
        packet_hash=packet_hash,
        omo_dispatch_id=omo_dispatch_id,
        prompt_ref=prompt_ref,
        prompt_digest=prompt_digest,
    )
    orca = _orca_refs(
        orca_run_id=orca_run_id,
        orca_task_id=orca_task_id,
        orca_dispatch_id=orca_dispatch_id,
        terminal_handle=terminal_handle,
    )
    if binding is None or orca is None:
        return _failure(
            binding=binding, stage="input", reason="identity_invalid", orca=orca
        )
    _prompt, prompt_error = _read_prompt(
        workspace_root=workspace_root,
        prompt_ref=prompt_ref,
        prompt_digest=prompt_digest,
    )
    if prompt_error:
        return _failure(binding=binding, stage="input", reason=prompt_error, orca=orca)

    shown, failure = _response(
        runner,
        (
            "orca",
            "orchestration",
            "worker-show",
            "--dispatch",
            orca_dispatch_id,
            "--json",
        ),
        timeout_seconds=15.0,
        binding=binding,
        stage="worker_show",
        reason="orca_worker_unavailable",
        orca=orca,
    )
    if failure:
        return failure
    assert shown is not None
    dispatch = shown.get("dispatch")
    worker = shown.get("worker")
    worker_done = worker.get("worker_done") if isinstance(worker, dict) else None
    settled = (
        isinstance(dispatch, dict)
        and isinstance(worker, dict)
        and isinstance(worker_done, dict)
        and dispatch.get("id") == orca_dispatch_id
        and dispatch.get("task_id") == orca_task_id
        and dispatch.get("run_id") == orca_run_id
        and dispatch.get("status") == "completed"
        and worker.get("state") in {"completed", "succeeded"}
        and worker.get("outcome") == "succeeded"
        and worker_done.get("outcome") == "succeeded"
        and worker_done.get("task_id") == orca_task_id
        and worker_done.get("dispatch_id") == orca_dispatch_id
    )
    if not settled:
        return _failure(
            binding=binding,
            stage="worker_show",
            reason="worker_not_settled",
            orca=orca,
        )

    transcript, failure = _response(
        runner,
        (
            "orca",
            "orchestration",
            "worker-read",
            "--dispatch",
            orca_dispatch_id,
            "--source",
            "transcript",
            "--limit",
            "200",
            "--json",
        ),
        timeout_seconds=15.0,
        binding=binding,
        stage="worker_read",
        reason="orca_transcript_unavailable",
        orca=orca,
    )
    if failure:
        return failure
    assert transcript is not None
    transcript_payload = transcript.get("transcript")
    messages = (
        transcript_payload.get("messages")
        if isinstance(transcript_payload, dict)
        else None
    )
    if (
        transcript.get("source") != "transcript"
        or not isinstance(messages, list)
        or not messages
    ):
        return _failure(
            binding=binding,
            stage="worker_read",
            reason="model_output_unproven",
            orca=orca,
        )
    return {
        "schema": SCHEMA,
        "ok": True,
        "state": "settled",
        "binding": binding,
        "orca": orca,
        "human_action_required": True,
        "input_accepted": "unproven",
        "model_completion": "observed",
        "transcript_digest": _digest_payload(transcript),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("start", "collect"):
        command = commands.add_parser(name)
        command.add_argument("--workflow-run-id", required=True)
        command.add_argument("--omo-task-id", required=True)
        command.add_argument("--packet-id", required=True)
        command.add_argument("--packet-hash", required=True)
        command.add_argument("--omo-dispatch-id", required=True)
        command.add_argument("--workspace-root", required=True)
        command.add_argument("--prompt-ref", required=True)
        command.add_argument("--prompt-digest", required=True)
    start = commands.choices["start"]
    start.add_argument("--idempotency-key")
    start.add_argument("--timeout-ms", type=int, default=60_000)
    collect = commands.choices["collect"]
    collect.add_argument("--orca-run-id", required=True)
    collect.add_argument("--orca-task-id", required=True)
    collect.add_argument("--orca-dispatch-id", required=True)
    collect.add_argument("--terminal-handle", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    values = {
        "workflow_run_id": args.workflow_run_id,
        "omo_task_id": args.omo_task_id,
        "packet_id": args.packet_id,
        "packet_hash": args.packet_hash,
        "omo_dispatch_id": args.omo_dispatch_id,
        "workspace_root": args.workspace_root,
        "prompt_ref": args.prompt_ref,
        "prompt_digest": args.prompt_digest,
    }
    if args.command == "start":
        receipt = start_supervised_codex(
            **values,
            idempotency_key=args.idempotency_key,
            timeout_ms=args.timeout_ms,
        )
    else:
        receipt = collect_supervised_codex(
            **values,
            orca_run_id=args.orca_run_id,
            orca_task_id=args.orca_task_id,
            orca_dispatch_id=args.orca_dispatch_id,
            terminal_handle=args.terminal_handle,
        )
    print(_canonical_json(receipt))
    return 0 if receipt["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
