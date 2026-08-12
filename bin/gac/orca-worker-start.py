#!/usr/bin/env python3
"""Fail-closed Orca adapter for starting a supervised Crush worker.

The adapter deliberately distinguishes a submitted dispatch from proven model
input acceptance.  Orca 1.4.180 exposes a durable ``injected`` receipt, but no
separate acknowledgement from the TUI input widget.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Callable, Sequence
from typing import Any

Command = tuple[str, ...]
Runner = Callable[[Command, float], tuple[int, str, str]]


def _subprocess_runner(command: Command, timeout_seconds: float) -> tuple[int, str, str]:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )
    except FileNotFoundError as exc:
        return 127, "", str(exc)
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return 124, stdout, stderr or "command timed out"
    return completed.returncode, completed.stdout, completed.stderr


def _failure(
    reason: str,
    stage: str,
    *,
    terminal_handle: str | None = None,
) -> dict[str, Any]:
    receipt: dict[str, Any] = {
        "ok": False,
        "reason": reason,
        "stage": stage,
        "residual_resources": [terminal_handle] if terminal_handle else [],
    }
    if terminal_handle:
        receipt["terminal_handle"] = terminal_handle
    return receipt


def _parse_orca_response(
    returncode: int,
    stdout: str,
    *,
    stage: str,
    terminal_handle: str | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    try:
        payload = json.loads(stdout)
    except (json.JSONDecodeError, TypeError):
        return None, _failure(
            "orca_response_invalid", stage, terminal_handle=terminal_handle
        )
    if not isinstance(payload, dict):
        return None, _failure(
            "orca_response_invalid", stage, terminal_handle=terminal_handle
        )
    if returncode != 0 or payload.get("ok") is not True:
        return None, _failure(
            {
                "runtime_preflight": "orca_runtime_not_ready",
                "terminal_create": "terminal_not_created",
                "tui_idle": "tui_not_ready",
                "process_identity": "crush_tui_not_verified",
                "dispatch": "dispatch_not_injected",
            }.get(stage, "orca_command_failed"),
            stage,
            terminal_handle=terminal_handle,
        )
    result = payload.get("result")
    if not isinstance(result, dict):
        return None, _failure(
            "orca_response_invalid", stage, terminal_handle=terminal_handle
        )
    return result, None


def start_crush_worker(
    *,
    task_id: str,
    worktree: str,
    coordinator_handle: str,
    run_id: str | None = None,
    timeout_ms: int = 60_000,
    runner: Runner = _subprocess_runner,
) -> dict[str, Any]:
    """Start Crush, verify its ready TUI, then inject exactly one Orca dispatch."""
    help_rc, help_stdout, _help_stderr = runner(("crush", "--help"), 10.0)
    if help_rc != 0 or "--yolo" not in help_stdout:
        return _failure("crush_yolo_flag_unsupported", "agent_preflight")

    status_rc, status_stdout, _status_stderr = runner(
        ("orca", "status", "--json"), 10.0
    )
    status, failure = _parse_orca_response(
        status_rc, status_stdout, stage="runtime_preflight"
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
        return _failure("orca_runtime_not_ready", "runtime_preflight")

    title = f"crush-{task_id}"
    create_command = (
        "orca",
        "terminal",
        "create",
        "--worktree",
        worktree,
        "--title",
        title,
        "--command",
        "crush --yolo",
        "--json",
    )
    create_rc, create_stdout, _create_stderr = runner(create_command, 30.0)
    created, failure = _parse_orca_response(
        create_rc, create_stdout, stage="terminal_create"
    )
    if failure:
        return failure
    assert created is not None
    terminal = created.get("terminal")
    handle = terminal.get("handle") if isinstance(terminal, dict) else None
    if not isinstance(handle, str) or not handle:
        return _failure("orca_response_invalid", "terminal_create")

    wait_command = (
        "orca",
        "terminal",
        "wait",
        "--terminal",
        handle,
        "--for",
        "tui-idle",
        "--timeout-ms",
        str(timeout_ms),
        "--json",
    )
    wait_rc, wait_stdout, _wait_stderr = runner(
        wait_command, max(10.0, timeout_ms / 1000 + 5.0)
    )
    waited, failure = _parse_orca_response(
        wait_rc, wait_stdout, stage="tui_idle", terminal_handle=handle
    )
    if failure:
        return failure
    assert waited is not None
    wait_receipt = waited.get("wait")
    if (
        not isinstance(wait_receipt, dict)
        or wait_receipt.get("satisfied") is not True
        or wait_receipt.get("condition") != "tui-idle"
        or wait_receipt.get("status") != "running"
    ):
        return _failure("tui_not_ready", "tui_idle", terminal_handle=handle)

    show_command = (
        "orca",
        "terminal",
        "show",
        "--terminal",
        handle,
        "--json",
    )
    show_rc, show_stdout, _show_stderr = runner(show_command, 10.0)
    shown, failure = _parse_orca_response(
        show_rc, show_stdout, stage="process_identity", terminal_handle=handle
    )
    if failure:
        return failure
    assert shown is not None
    shown_terminal = shown.get("terminal")
    preview = shown_terminal.get("preview") if isinstance(shown_terminal, dict) else None
    if (
        not isinstance(shown_terminal, dict)
        or shown_terminal.get("connected") is not True
        or shown_terminal.get("writable") is not True
        or not isinstance(preview, str)
        or "yolo mode!" not in preview.lower()
    ):
        return _failure(
            "crush_tui_not_verified", "process_identity", terminal_handle=handle
        )

    dispatch_parts: list[str] = [
        "orca",
        "orchestration",
        "dispatch",
        "--task",
        task_id,
        "--to",
        handle,
        "--from",
        coordinator_handle,
    ]
    if run_id:
        dispatch_parts.extend(("--run", run_id))
    dispatch_parts.extend(("--inject", "--json"))
    dispatch_command = tuple(dispatch_parts)
    dispatch_rc, dispatch_stdout, _dispatch_stderr = runner(dispatch_command, 30.0)
    dispatched, failure = _parse_orca_response(
        dispatch_rc, dispatch_stdout, stage="dispatch", terminal_handle=handle
    )
    if failure:
        return failure
    assert dispatched is not None
    dispatch = dispatched.get("dispatch")
    if (
        dispatched.get("injected") is not True
        or not isinstance(dispatch, dict)
        or dispatch.get("status") != "dispatched"
        or not isinstance(dispatch.get("id"), str)
    ):
        return _failure("dispatch_not_injected", "dispatch", terminal_handle=handle)

    return {
        "ok": True,
        "state": "dispatch_injected",
        "terminal_handle": handle,
        "dispatch_id": dispatch["id"],
        "task_id": task_id,
        "input_accepted": "unproven",
        "residual_resources": [handle],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Start a supervised Crush worker only after its Orca TUI is ready."
    )
    parser.add_argument("--task", required=True, dest="task_id")
    parser.add_argument("--worktree", required=True)
    parser.add_argument("--coordinator-handle", required=True)
    parser.add_argument("--run")
    parser.add_argument("--timeout-ms", type=int, default=60_000)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.timeout_ms <= 0:
        _parser().error("--timeout-ms must be positive")
    receipt = start_crush_worker(
        task_id=args.task_id,
        worktree=args.worktree,
        coordinator_handle=args.coordinator_handle,
        run_id=args.run,
        timeout_ms=args.timeout_ms,
    )
    json.dump(receipt, sys.stdout, ensure_ascii=False, sort_keys=True)
    sys.stdout.write("\n")
    return 0 if receipt["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
