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
import sys
from collections.abc import Callable, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

SCHEMA = "orca-codex-supervisor/v1"
IDENTITY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:+-]{0,127}$")
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
Command = tuple[str, ...]
Runner = Callable[[Command, float], tuple[int, str, str]]
GuardRunner = Callable[[Command, float, str], tuple[int, str, str]]


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


def _subprocess_guard_runner(
    command: Command, timeout_seconds: float, agent_id: str
) -> tuple[int, str, str]:
    environment = os.environ.copy()
    environment["AGENT_ID"] = agent_id
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            check=False,
            shell=False,
            text=True,
            timeout=timeout_seconds,
            env=environment,
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
    return isinstance(value, str) and bool(IDENTITY_RE.fullmatch(value))


def _valid_worktree_id(value: str) -> bool:
    if not isinstance(value, str) or "\x00" in value or "::" not in value:
        return False
    repo_id, worktree_path = value.split("::", 1)
    return _valid_identity(repo_id) and worktree_path.startswith("/")


def _path_digest(path: str) -> str:
    return "sha256:" + hashlib.sha256(path.encode("utf-8")).hexdigest()


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


def _clone_guard(
    *,
    workspace_root: str,
    agent_id: str,
    guard_runner: GuardRunner,
) -> tuple[dict[str, str] | None, str | None]:
    root = Path(workspace_root)
    try:
        git_dir = root / ".git"
        if stat.S_ISLNK(os.lstat(git_dir).st_mode) or not stat.S_ISDIR(
            os.lstat(git_dir).st_mode
        ):
            return None, "workspace_not_independent_clone"
    except OSError:
        return None, "workspace_not_independent_clone"
    command = (
        sys.executable,
        str(Path(__file__).with_name("agent-clone.py")),
        "guard",
        "--workspace",
        workspace_root,
        "--require-clone",
        "--json",
    )
    returncode, stdout, _stderr = guard_runner(command, 15.0, agent_id)
    try:
        receipt = json.loads(stdout)
    except (TypeError, json.JSONDecodeError):
        return None, "agent_clone_guard_invalid"
    if (
        returncode != 0
        or not isinstance(receipt, dict)
        or receipt.get("ok") is not True
        or receipt.get("state") != "verified_clone"
        or receipt.get("workspace") != workspace_root
        or receipt.get("clone_root") != workspace_root
        or receipt.get("agent_id") != agent_id
    ):
        return None, "agent_clone_guard_rejected"
    return {
        "clone_agent_id": agent_id,
        "canonical_root_digest": _path_digest(workspace_root),
        "guard_receipt_digest": _digest_payload(receipt),
    }, None


def _worktree_id(result: dict[str, Any], *, workspace_root: str) -> str | None:
    worktree = result.get("worktree")
    worktree_id = worktree.get("id") if isinstance(worktree, dict) else None
    if (
        not isinstance(worktree_id, str)
        or not _valid_worktree_id(worktree_id)
        or worktree.get("path") != workspace_root
    ):
        return None
    _repo_id, id_path = worktree_id.split("::", 1)
    try:
        canonical_id_path = str(Path(id_path).resolve(strict=True))
    except OSError:
        return None
    if canonical_id_path != workspace_root:
        return None
    return worktree_id


def _has_model_output(messages: list[object]) -> bool:
    for message in messages:
        if not isinstance(message, dict) or message.get("role") not in {
            "assistant",
            "model",
        }:
            continue
        if isinstance(message.get("content"), str) and message["content"].strip():
            return True
        blocks = message.get("blocks")
        if not isinstance(blocks, list):
            continue
        for block in blocks:
            if not isinstance(block, dict):
                continue
            for field in ("text", "output", "content"):
                if isinstance(block.get(field), str) and block[field].strip():
                    return True
    return False


def _has_terminal_model_output(lines: list[object]) -> bool:
    if not lines or not all(isinstance(line, str) for line in lines):
        return False
    completion_seen = any(
        "Worked for " in line and line.lstrip().startswith(("─", "━")) for line in lines
    )
    tool_prefixes = (
        "• Ran ",
        "• Edited ",
        "• Read ",
        "• Explored ",
        "• Searched ",
        "• Called ",
    )
    model_output_seen = any(
        line.startswith("• ") and not line.startswith(tool_prefixes) for line in lines
    )
    return completion_seen and model_output_seen


def _session_not_reported(payload: object) -> bool:
    if not isinstance(payload, dict) or payload.get("ok") is not False:
        return False
    error = payload.get("error")
    data = error.get("data") if isinstance(error, dict) else None
    return (
        isinstance(error, dict)
        and error.get("code") == "transcript_required"
        and isinstance(data, dict)
        and data.get("reason") == "session_not_reported"
    )


def _task_completion(
    result: dict[str, Any],
    *,
    orca_run_id: str,
    orca_task_id: str,
    terminal_handle: str,
) -> dict[str, Any] | None:
    if result.get("runId") not in {None, orca_run_id}:
        return None
    tasks = result.get("tasks")
    if not isinstance(tasks, list):
        return None
    matching = [
        task
        for task in tasks
        if isinstance(task, dict) and task.get("id") == orca_task_id
    ]
    if len(matching) != 1:
        return None
    task = matching[0]
    if task.get("status") != "completed" or task.get("run_id") not in {
        None,
        orca_run_id,
    }:
        return None
    raw_completion = task.get("result")
    try:
        completion = json.loads(raw_completion)
    except (TypeError, json.JSONDecodeError):
        return None
    files_modified = (
        completion.get("filesModified") if isinstance(completion, dict) else None
    )
    if (
        not isinstance(completion, dict)
        or completion.get("provenance") != "worker_report"
        or completion.get("outcome") != "succeeded"
        or completion.get("reportedBy") != terminal_handle
        or completion.get("completedBy") != terminal_handle
        or not _valid_identity(completion.get("messageId"))
        or not isinstance(files_modified, list)
        or not files_modified
        or not all(isinstance(path, str) and path for path in files_modified)
    ):
        return None
    return completion


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
    result: dict[str, Any],
    *,
    terminal_handle: str,
    residual_resources: list[str],
) -> tuple[dict[str, str] | None, list[str]]:
    dispatch_id = result.get("dispatchId")
    task_id = result.get("taskId")
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


def _has_worker_effect(
    effects: object, *, kind: str, terminal_handle: str, **expected: str
) -> bool:
    return isinstance(effects, list) and any(
        isinstance(effect, dict)
        and effect.get("kind") == kind
        and effect.get("id") == terminal_handle
        and all(effect.get(field) == value for field, value in expected.items())
        for effect in effects
    )


def _ready_worker_orca(
    result: dict[str, Any],
    *,
    orca_run_id: str,
    orca_task_id: str,
    terminal_handle: str,
    expected_request_id: str | None,
) -> dict[str, str] | None:
    reported_run_id = result.get("runId")
    reported_task_id = result.get("taskId")
    dispatch_id = result.get("dispatchId")
    mutation = result.get("mutation")
    if not all(
        isinstance(value, str)
        for value in (reported_run_id, reported_task_id, dispatch_id)
    ):
        return None
    orca = _orca_refs(
        orca_run_id=reported_run_id,
        orca_task_id=reported_task_id,
        orca_dispatch_id=dispatch_id,
        terminal_handle=terminal_handle,
    )
    if (
        orca is None
        or orca["run_id"] != orca_run_id
        or orca["task_id"] != orca_task_id
        or result.get("state") != "ready"
        or result.get("stage") != "input_accepted"
        or not isinstance(mutation, dict)
        or not isinstance(mutation.get("requestId"), str)
        or not _valid_identity(mutation["requestId"])
        or (
            expected_request_id is not None
            and mutation["requestId"] != expected_request_id
        )
        or not _has_worker_effect(
            result.get("effects"),
            kind="terminal",
            terminal_handle=terminal_handle,
            role="agent",
            action="reused",
        )
        or not _has_worker_effect(
            result.get("effects"),
            kind="dispatch_input",
            terminal_handle=terminal_handle,
            role="agent",
            state="accepted",
        )
    ):
        return None
    return orca


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
    agent_id: str,
    idempotency_key: str | None = None,
    codex_executable: str | None = None,
    timeout_ms: int = 60_000,
    runner: Runner = _subprocess_runner,
    guard_runner: GuardRunner | None = None,
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
    if not _valid_identity(agent_id):
        return _failure(binding=binding, stage="input", reason="agent_id_invalid")
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
    clone_binding, clone_error = _clone_guard(
        workspace_root=resolved_workspace,
        agent_id=agent_id,
        guard_runner=guard_runner or _subprocess_guard_runner,
    )
    if clone_error:
        return _failure(binding=binding, stage="input", reason=clone_error)
    assert clone_binding is not None
    binding.update(clone_binding)
    retry_requests: dict[str, str] = {}
    if idempotency_key is not None:
        for stage in ("run-create", "task-create", "worker-start"):
            retry_requests[stage] = hashlib.sha256(
                f"{idempotency_key}\n{stage}".encode()
            ).hexdigest()

    def retry_request(stage: str) -> tuple[str, ...]:
        value = retry_requests.get(stage)
        return ("--retry-request", value) if value is not None else ()

    shown_worktree, failure = _response(
        runner,
        (
            "orca",
            "worktree",
            "show",
            "--worktree",
            f"path:{resolved_workspace}",
            "--json",
        ),
        timeout_seconds=15.0,
        binding=binding,
        stage="worktree_show",
        reason="orca_worktree_unavailable",
    )
    if failure:
        return failure
    assert shown_worktree is not None
    orca_worktree_id = _worktree_id(shown_worktree, workspace_root=resolved_workspace)
    if orca_worktree_id is None:
        return _failure(
            binding=binding, stage="worktree_show", reason="orca_worktree_unavailable"
        )
    binding["orca_worktree_id"] = orca_worktree_id

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
            "env",
            f"AGENT_ID={agent_id}",
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
            f"id:{orca_worktree_id}",
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
            f"id:{orca_worktree_id}",
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
            terminal_handle=terminal_handle,
            residual_resources=terminal_residuals,
        ),
    )
    if failure:
        return failure
    assert started_worker is not None
    worker_orca, worker_residuals = _worker_failure_context(
        started_worker,
        terminal_handle=terminal_handle,
        residual_resources=terminal_residuals,
    )
    orca = _ready_worker_orca(
        started_worker,
        orca_run_id=orca_run_id,
        orca_task_id=orca_task_id,
        terminal_handle=terminal_handle,
        expected_request_id=retry_requests.get("worker-start"),
    )
    if orca is None:
        return _failure(
            binding=binding,
            stage="worker_start",
            reason="orca_response_invalid",
            orca=worker_orca,
            residual_resources=worker_residuals,
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
    agent_id: str,
    canonical_root_digest: str,
    guard_receipt_digest: str,
    orca_worktree_id: str,
    orca_run_id: str,
    orca_task_id: str,
    orca_dispatch_id: str,
    terminal_handle: str,
    runner: Runner = _subprocess_runner,
    guard_runner: GuardRunner | None = None,
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
    if (
        not _valid_identity(agent_id)
        or not SHA256_RE.fullmatch(canonical_root_digest)
        or not SHA256_RE.fullmatch(guard_receipt_digest)
        or not _valid_worktree_id(orca_worktree_id)
    ):
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

    try:
        resolved_workspace = str(Path(workspace_root).resolve(strict=True))
    except OSError:
        return _failure(
            binding=binding, stage="input", reason="workspace_root_unsafe", orca=orca
        )
    clone_binding, clone_error = _clone_guard(
        workspace_root=resolved_workspace,
        agent_id=agent_id,
        guard_runner=guard_runner or _subprocess_guard_runner,
    )
    if clone_error:
        return _failure(binding=binding, stage="input", reason=clone_error, orca=orca)
    assert clone_binding is not None
    if (
        clone_binding["canonical_root_digest"] != canonical_root_digest
        or clone_binding["guard_receipt_digest"] != guard_receipt_digest
    ):
        return _failure(
            binding=binding, stage="input", reason="clone_guard_drift", orca=orca
        )
    binding.update(clone_binding)
    binding["orca_worktree_id"] = orca_worktree_id

    shown_worktree, failure = _response(
        runner,
        (
            "orca",
            "worktree",
            "show",
            "--worktree",
            f"path:{resolved_workspace}",
            "--json",
        ),
        timeout_seconds=15.0,
        binding=binding,
        stage="worktree_show",
        reason="orca_worktree_unavailable",
        orca=orca,
    )
    if failure:
        return failure
    assert shown_worktree is not None
    if (
        _worktree_id(shown_worktree, workspace_root=resolved_workspace)
        != orca_worktree_id
    ):
        return _failure(
            binding=binding,
            stage="worktree_show",
            reason="orca_worktree_drift",
            orca=orca,
        )

    shown_terminal, failure = _response(
        runner,
        ("orca", "terminal", "show", "--terminal", terminal_handle, "--json"),
        timeout_seconds=10.0,
        binding=binding,
        stage="terminal_show",
        reason="orca_terminal_unavailable",
        orca=orca,
    )
    if failure:
        return failure
    terminal = shown_terminal.get("terminal") if shown_terminal else None
    if (
        not isinstance(terminal, dict)
        or terminal.get("handle") != terminal_handle
        or terminal.get("worktreePath") != resolved_workspace
        or terminal.get("connected") is not True
        or terminal.get("writable") is not True
    ):
        return _failure(
            binding=binding,
            stage="terminal_show",
            reason="orca_terminal_drift",
            orca=orca,
        )

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
    dispatch_settled = (
        isinstance(dispatch, dict)
        and isinstance(worker, dict)
        and dispatch.get("id") == orca_dispatch_id
        and dispatch.get("task_id") == orca_task_id
        and dispatch.get("run_id") == orca_run_id
        and dispatch.get("status") == "completed"
    )
    legacy_worker_settled = (
        isinstance(worker, dict)
        and isinstance(worker_done, dict)
        and worker.get("state") in {"completed", "succeeded"}
        and worker.get("outcome") == "succeeded"
        and worker_done.get("outcome") == "succeeded"
        and worker_done.get("task_id") == orca_task_id
        and worker_done.get("dispatch_id") == orca_dispatch_id
    )
    current_worker_settled = (
        isinstance(worker, dict)
        and worker.get("dispatch_id") == orca_dispatch_id
        and worker.get("agent_terminal_handle") == terminal_handle
        and worker.get("state") in {"completed", "succeeded"}
        and worker.get("stage") == "settled"
    )
    if not dispatch_settled or not (legacy_worker_settled or current_worker_settled):
        return _failure(
            binding=binding,
            stage="worker_show",
            reason="worker_not_settled",
            orca=orca,
        )

    transcript_command = (
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
    )
    returncode, stdout, _stderr = runner(transcript_command, 15.0)
    try:
        transcript_payload_raw = json.loads(stdout)
    except (TypeError, json.JSONDecodeError):
        transcript_payload_raw = None
    transcript = (
        transcript_payload_raw.get("result")
        if isinstance(transcript_payload_raw, dict)
        and transcript_payload_raw.get("ok") is True
        else None
    )
    if returncode == 0 and isinstance(transcript, dict):
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
            or not _has_model_output(messages)
        ):
            return _failure(
                binding=binding,
                stage="worker_read",
                reason="model_output_unproven",
                orca=orca,
            )
        output_digest = _digest_payload(transcript)
        return {
            "schema": SCHEMA,
            "ok": True,
            "state": "settled",
            "binding": binding,
            "orca": orca,
            "human_action_required": True,
            "input_accepted": "unproven",
            "model_completion": "observed",
            "model_output_source": "structured_transcript",
            "model_output_digest": output_digest,
            "transcript_digest": output_digest,
        }
    if not _session_not_reported(transcript_payload_raw):
        return _failure(
            binding=binding,
            stage="worker_read",
            reason="orca_transcript_unavailable",
            orca=orca,
        )

    task_list, failure = _response(
        runner,
        (
            "orca",
            "orchestration",
            "task-list",
            "--run",
            orca_run_id,
            "--json",
        ),
        timeout_seconds=15.0,
        binding=binding,
        stage="worker_read",
        reason="worker_completion_unproven",
        orca=orca,
    )
    if failure:
        return failure
    assert task_list is not None
    completion = _task_completion(
        task_list,
        orca_run_id=orca_run_id,
        orca_task_id=orca_task_id,
        terminal_handle=terminal_handle,
    )
    if completion is None:
        return _failure(
            binding=binding,
            stage="worker_read",
            reason="worker_completion_unproven",
            orca=orca,
        )

    terminal_output, failure = _response(
        runner,
        (
            "orca",
            "orchestration",
            "worker-read",
            "--dispatch",
            orca_dispatch_id,
            "--source",
            "auto",
            "--limit",
            "200",
            "--json",
        ),
        timeout_seconds=15.0,
        binding=binding,
        stage="worker_read",
        reason="model_output_unproven",
        orca=orca,
    )
    if failure:
        return failure
    assert terminal_output is not None
    terminal_evidence = terminal_output.get("terminal")
    source_identity = terminal_output.get("sourceIdentity")
    status = terminal_output.get("status")
    tail = (
        terminal_evidence.get("tail") if isinstance(terminal_evidence, dict) else None
    )
    if (
        terminal_output.get("source") != "terminal"
        or terminal_output.get("fallbackReason") != "session_not_reported"
        or not _valid_identity(source_identity)
        or not isinstance(status, dict)
        or status.get("worker") != "succeeded"
        or not isinstance(terminal_evidence, dict)
        or terminal_evidence.get("handle") != terminal_handle
        or terminal_evidence.get("truncated") is not False
        or not isinstance(tail, list)
        or not _has_terminal_model_output(tail)
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
        "model_output_source": "bounded_terminal_fallback",
        "fallback_reason": "session_not_reported",
        "model_output_digest": _digest_payload(terminal_output),
        "completion_receipt_digest": _digest_payload(completion),
        "source_identity_digest": "sha256:"
        + hashlib.sha256(source_identity.encode("utf-8")).hexdigest(),
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
    start.add_argument("--agent-id", required=True)
    start.add_argument("--idempotency-key")
    start.add_argument("--timeout-ms", type=int, default=60_000)
    collect = commands.choices["collect"]
    collect.add_argument("--agent-id", required=True)
    collect.add_argument("--canonical-root-digest", required=True)
    collect.add_argument("--guard-receipt-digest", required=True)
    collect.add_argument("--orca-worktree-id", required=True)
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
            agent_id=args.agent_id,
            idempotency_key=args.idempotency_key,
            timeout_ms=args.timeout_ms,
        )
    else:
        receipt = collect_supervised_codex(
            **values,
            agent_id=args.agent_id,
            canonical_root_digest=args.canonical_root_digest,
            guard_receipt_digest=args.guard_receipt_digest,
            orca_worktree_id=args.orca_worktree_id,
            orca_run_id=args.orca_run_id,
            orca_task_id=args.orca_task_id,
            orca_dispatch_id=args.orca_dispatch_id,
            terminal_handle=args.terminal_handle,
        )
    print(_canonical_json(receipt))
    return 0 if receipt["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
