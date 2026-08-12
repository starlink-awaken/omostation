from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[3]
SCRIPT = WORKSPACE / "bin" / "gac" / "orca-worker-start.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("orca_worker_start", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeRunner:
    def __init__(self, responses: list[tuple[int, object, str]]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, command: tuple[str, ...], timeout_seconds: float):
        self.calls.append(command)
        returncode, payload, stderr = self.responses.pop(0)
        stdout = payload if isinstance(payload, str) else json.dumps(payload)
        return returncode, stdout, stderr


def _ok(result: dict) -> dict:
    return {"ok": True, "result": result}


def _success_responses() -> list[tuple[int, object, str]]:
    return [
        (0, "usage: crush\n  -y --yolo  Automatically accept all permissions", ""),
        (0, _ok({"app": {"running": True}, "runtime": {"state": "ready"}}), ""),
        (0, _ok({"terminal": {"handle": "term-1"}}), ""),
        (
            0,
            _ok(
                {
                    "wait": {
                        "handle": "term-1",
                        "condition": "tui-idle",
                        "satisfied": True,
                        "status": "running",
                    }
                }
            ),
            "",
        ),
        (
            0,
            _ok(
                {
                    "terminal": {
                        "handle": "term-1",
                        "connected": True,
                        "writable": True,
                        "preview": "Crush v0.88.1\nY  Yolo mode!",
                    }
                }
            ),
            "",
        ),
        (
            0,
            _ok(
                {
                    "dispatch": {"id": "ctx-1", "status": "dispatched"},
                    "injected": True,
                }
            ),
            "",
        ),
    ]


def test_success_waits_for_crush_tui_before_dispatch_and_uses_valid_yolo_flag() -> None:
    module = _load_module()
    runner = FakeRunner(_success_responses())

    receipt = module.start_crush_worker(
        task_id="task-1",
        worktree="path:/tmp/ws",
        coordinator_handle="term-coordinator",
        run_id="run-1",
        runner=runner,
    )

    assert receipt["ok"] is True
    assert receipt["state"] == "dispatch_injected"
    assert receipt["terminal_handle"] == "term-1"
    assert receipt["dispatch_id"] == "ctx-1"
    assert receipt["input_accepted"] == "unproven"
    assert runner.calls == [
        ("crush", "--help"),
        ("orca", "status", "--json"),
        (
            "orca",
            "terminal",
            "create",
            "--worktree",
            "path:/tmp/ws",
            "--title",
            "crush-task-1",
            "--command",
            "crush --yolo",
            "--json",
        ),
        (
            "orca",
            "terminal",
            "wait",
            "--terminal",
            "term-1",
            "--for",
            "tui-idle",
            "--timeout-ms",
            "60000",
            "--json",
        ),
        ("orca", "terminal", "show", "--terminal", "term-1", "--json"),
        (
            "orca",
            "orchestration",
            "dispatch",
            "--task",
            "task-1",
            "--to",
            "term-1",
            "--from",
            "term-coordinator",
            "--run",
            "run-1",
            "--inject",
            "--json",
        ),
    ]


def test_tui_timeout_fails_closed_without_dispatching() -> None:
    module = _load_module()
    responses = _success_responses()[:3]
    responses.append((1, {"ok": False, "error": {"code": "timeout"}}, ""))
    runner = FakeRunner(responses)

    receipt = module.start_crush_worker(
        task_id="task-1",
        worktree="current",
        coordinator_handle="term-coordinator",
        runner=runner,
    )

    assert receipt == {
        "ok": False,
        "reason": "tui_not_ready",
        "stage": "tui_idle",
        "terminal_handle": "term-1",
        "residual_resources": ["term-1"],
    }
    assert not any("dispatch" in command for command in runner.calls)


def test_shell_fallback_or_non_yolo_tui_is_not_ready() -> None:
    module = _load_module()
    responses = _success_responses()[:4]
    responses.append(
        (
            0,
            _ok(
                {
                    "terminal": {
                        "handle": "term-1",
                        "connected": True,
                        "writable": True,
                        "preview": "Unknown shorthand flag: 'o' in -olo\n%",
                    }
                }
            ),
            "",
        )
    )
    runner = FakeRunner(responses)

    receipt = module.start_crush_worker(
        task_id="task-1",
        worktree="current",
        coordinator_handle="term-coordinator",
        runner=runner,
    )

    assert receipt["ok"] is False
    assert receipt["reason"] == "crush_tui_not_verified"
    assert receipt["stage"] == "process_identity"
    assert receipt["residual_resources"] == ["term-1"]
    assert not any("dispatch" in command for command in runner.calls)


def test_current_crush_must_advertise_long_yolo_flag_before_terminal_creation() -> None:
    module = _load_module()
    runner = FakeRunner([(0, "usage: crush\n  -y  Automatically accept permissions", "")])

    receipt = module.start_crush_worker(
        task_id="task-1",
        worktree="current",
        coordinator_handle="term-coordinator",
        runner=runner,
    )

    assert receipt == {
        "ok": False,
        "reason": "crush_yolo_flag_unsupported",
        "stage": "agent_preflight",
        "residual_resources": [],
    }
    assert runner.calls == [("crush", "--help")]


def test_orca_runtime_must_be_ready_before_terminal_creation() -> None:
    module = _load_module()
    runner = FakeRunner(
        [
            (0, "usage: crush\n  -y --yolo  Automatically accept all permissions", ""),
            (0, _ok({"app": {"running": True}, "runtime": {"state": "starting"}}), ""),
        ]
    )

    receipt = module.start_crush_worker(
        task_id="task-1",
        worktree="current",
        coordinator_handle="term-coordinator",
        runner=runner,
    )

    assert receipt["ok"] is False
    assert receipt["reason"] == "orca_runtime_not_ready"
    assert receipt["residual_resources"] == []
    assert len(runner.calls) == 2


def test_dispatch_failure_is_reported_without_retry() -> None:
    module = _load_module()
    responses = _success_responses()[:5]
    responses.append((1, {"ok": False, "error": {"code": "inject_failed"}}, ""))
    runner = FakeRunner(responses)

    receipt = module.start_crush_worker(
        task_id="task-1",
        worktree="current",
        coordinator_handle="term-coordinator",
        runner=runner,
    )

    assert receipt["ok"] is False
    assert receipt["reason"] == "dispatch_not_injected"
    assert receipt["stage"] == "dispatch"
    assert receipt["terminal_handle"] == "term-1"
    assert receipt["residual_resources"] == ["term-1"]
    assert sum("dispatch" in command for command in runner.calls) == 1


def test_malformed_orca_json_fails_closed() -> None:
    module = _load_module()
    runner = FakeRunner(
        [
            (0, "usage: crush\n  -y --yolo  Automatically accept all permissions", ""),
            (0, "not-json", ""),
        ]
    )

    receipt = module.start_crush_worker(
        task_id="task-1",
        worktree="current",
        coordinator_handle="term-coordinator",
        runner=runner,
    )

    assert receipt["ok"] is False
    assert receipt["reason"] == "orca_response_invalid"
    assert receipt["stage"] == "runtime_preflight"
    assert receipt["residual_resources"] == []
