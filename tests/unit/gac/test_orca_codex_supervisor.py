from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

WORKSPACE = Path(__file__).resolve().parents[3]
SCRIPT = WORKSPACE / "bin" / "gac" / "orca-codex-supervisor.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("orca_codex_supervisor", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module._subprocess_guard_runner = _guard_runner
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


def _orca_worktree_id(workspace: Path) -> str:
    return f"repo-001::{workspace}"


def _guard_receipt(workspace: str, agent_id: str) -> dict:
    return {
        "ok": True,
        "workspace": workspace,
        "clone_root": workspace,
        "agent_id": agent_id,
        "state": "verified_clone",
    }


def _guard_runner(command: tuple[str, ...], _timeout: float, agent_id: str):
    workspace = command[command.index("--workspace") + 1]
    return 0, json.dumps(_guard_receipt(workspace, agent_id)), ""


def _expected_binding(module, identity: dict[str, str]) -> dict[str, str]:
    workspace = identity["workspace_root"]
    guard = _guard_receipt(workspace, identity["agent_id"])
    return {
        **{
            key: value
            for key, value in identity.items()
            if key not in {"workspace_root", "agent_id"}
        },
        "clone_agent_id": identity["agent_id"],
        "canonical_root_digest": module._path_digest(workspace),
        "guard_receipt_digest": module._digest_payload(guard),
        "orca_worktree_id": _orca_worktree_id(Path(workspace)),
    }


def _collect_clone_args(module, identity: dict[str, str]) -> dict[str, str]:
    workspace = identity["workspace_root"]
    return {
        "canonical_root_digest": module._path_digest(workspace),
        "guard_receipt_digest": module._digest_payload(
            _guard_receipt(workspace, identity["agent_id"])
        ),
        "orca_worktree_id": _orca_worktree_id(Path(workspace)),
    }


def _collect_prefix(workspace: Path) -> list[tuple[int, object, str]]:
    return [
        (
            0,
            _ok(
                {
                    "worktree": {
                        "id": _orca_worktree_id(workspace),
                        "path": str(workspace),
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
                        "handle": "terminal-001",
                        "worktreePath": str(workspace),
                        "connected": True,
                        "writable": True,
                    }
                }
            ),
            "",
        ),
    ]


def _settled_worker_response() -> tuple[int, object, str]:
    return (
        0,
        _ok(
            {
                "dispatch": {
                    "id": "orca-dispatch-001",
                    "task_id": "orca-task-001",
                    "run_id": "orca-run-001",
                    "status": "completed",
                },
                "worker": {
                    "state": "completed",
                    "outcome": "succeeded",
                    "worker_done": {
                        "outcome": "succeeded",
                        "task_id": "orca-task-001",
                        "dispatch_id": "orca-dispatch-001",
                    },
                },
            }
        ),
        "",
    )


def _transcript_response(messages: list[object]) -> tuple[int, object, str]:
    return 0, _ok({"source": "transcript", "transcript": {"messages": messages}}), ""


def _session_not_reported_response() -> tuple[int, object, str]:
    return (
        1,
        {
            "ok": False,
            "error": {
                "code": "transcript_required",
                "message": "Structured output is unavailable: session_not_reported.",
                "data": {"reason": "session_not_reported"},
            },
        },
        "",
    )


def _terminal_fallback_response(
    *, terminal_handle: str = "terminal-001", tail: list[str] | None = None
) -> tuple[int, object, str]:
    return (
        0,
        _ok(
            {
                "source": "terminal",
                "fallbackReason": "session_not_reported",
                "sourceIdentity": "terminal-source-001",
                "status": {"worker": "succeeded", "terminal": "running"},
                "terminal": {
                    "handle": terminal_handle,
                    "status": "running",
                    "truncated": False,
                    "limited": True,
                    "tail": tail
                    or [
                        "• Completed the declared documentation update.",
                        "",
                        "─ Worked for 2m 45s ─",
                    ],
                },
            }
        ),
        "",
    )


def _completed_task_list_response() -> tuple[int, object, str]:
    return (
        0,
        _ok(
            {
                "runId": "orca-run-001",
                "tasks": [
                    {
                        "id": "orca-task-001",
                        "run_id": "orca-run-001",
                        "status": "completed",
                        "result": json.dumps(
                            {
                                "provenance": "worker_report",
                                "outcome": "succeeded",
                                "messageId": "message-001",
                                "reportedBy": "terminal-001",
                                "completedBy": "terminal-001",
                                "filesModified": ["docs/evidence/canary.md"],
                            }
                        ),
                    }
                ],
            }
        ),
        "",
    )


def _identity(
    tmp_path: Path, prompt: str = "Update the declared documentation fixture."
) -> dict[str, str]:
    (tmp_path / "prompts").mkdir(exist_ok=True)
    (tmp_path / ".git").mkdir(exist_ok=True)
    prompt_path = tmp_path / "prompts" / "dogfood.md"
    prompt_path.write_text(prompt, encoding="utf-8")
    return {
        "workflow_run_id": "wf-001",
        "omo_task_id": "OMO-TASK-001",
        "packet_id": "packet-001",
        "packet_hash": "sha256:" + "a" * 64,
        "omo_dispatch_id": "omo-dispatch-001",
        "workspace_root": str(tmp_path),
        "prompt_ref": "prompts/dogfood.md",
        "prompt_digest": "sha256:" + hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "agent_id": "agent-001",
    }


def _start_responses(workspace: Path) -> list[tuple[int, object, str]]:
    return [
        (
            0,
            _ok(
                {
                    "worktree": {
                        "id": _orca_worktree_id(workspace),
                        "path": str(workspace),
                    }
                }
            ),
            "",
        ),
        (0, _ok({"app": {"running": True}, "runtime": {"state": "ready"}}), ""),
        (
            0,
            _ok(
                {
                    "terminal": {
                        "handle": "coordinator-001",
                        "worktreePath": str(workspace),
                        "connected": True,
                        "writable": True,
                    }
                }
            ),
            "",
        ),
        (
            0,
            _ok(
                {
                    "run": {
                        "id": "orca-run-001",
                        "coordinator_handle": "coordinator-001",
                    }
                }
            ),
            "",
        ),
        (
            0,
            _ok({"task": {"id": "orca-task-001", "run_id": "orca-run-001"}}),
            "",
        ),
        (
            0,
            _ok(
                {
                    "terminal": {
                        "handle": "terminal-001",
                        "worktreePath": str(workspace),
                        "connected": True,
                        "writable": True,
                    }
                }
            ),
            "",
        ),
        (
            0,
            _ok({"wait": {"condition": "tui-idle", "satisfied": True}}),
            "",
        ),
        (
            0,
            _ok(
                {
                    "terminal": {
                        "handle": "terminal-001",
                        "worktreePath": str(workspace),
                        "connected": True,
                        "writable": True,
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
                        "handle": "terminal-001",
                        "tail": [
                            (
                                "env AGENT_ID=agent-001 /opt/homebrew/bin/codex --ask-for-approval "
                                f"on-request --sandbox read-only -C {workspace}"
                            )
                        ],
                    }
                }
            ),
            "",
        ),
        (
            0,
            _ok(
                {
                    "state": "ready",
                    "stage": "input_accepted",
                    "dispatchId": "orca-dispatch-001",
                    "taskId": "orca-task-001",
                    "runId": "orca-run-001",
                    "effects": [
                        {
                            "kind": "terminal",
                            "role": "agent",
                            "action": "reused",
                            "id": "terminal-001",
                        },
                        {
                            "kind": "dispatch_input",
                            "role": "agent",
                            "id": "terminal-001",
                            "state": "accepted",
                        },
                    ],
                    "mutation": {"requestId": "worker-request-001"},
                }
            ),
            "",
        ),
    ]


def _run_residuals() -> list[str]:
    return ["orca:terminal:coordinator-001", "orca:run:orca-run-001"]


def _run_task_residuals() -> list[str]:
    return [
        "orca:terminal:coordinator-001",
        "orca:run:orca-run-001",
        "orca:task:orca-task-001",
    ]


def test_start_binds_omo_and_orca_identities_without_claiming_input_or_completion(
    tmp_path: Path,
) -> None:
    module = _load_module()
    runner = FakeRunner(_start_responses(tmp_path))
    identity = _identity(tmp_path)

    receipt = module.start_supervised_codex(
        **identity,
        codex_executable="/opt/homebrew/bin/codex",
        runner=runner,
    )

    assert receipt == {
        "schema": "orca-codex-supervisor/v1",
        "ok": True,
        "state": "awaiting_human_action",
        "binding": {
            **_expected_binding(module, identity),
        },
        "orca": {
            "run_id": "orca-run-001",
            "task_id": "orca-task-001",
            "dispatch_id": "orca-dispatch-001",
            "terminal_handle": "terminal-001",
        },
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
    assert runner.calls == [
        (
            "orca",
            "worktree",
            "show",
            "--worktree",
            f"path:{tmp_path}",
            "--json",
        ),
        ("orca", "status", "--json"),
        (
            "orca",
            "terminal",
            "create",
            "--worktree",
            f"id:{_orca_worktree_id(tmp_path)}",
            "--title",
            "supervised-coordinator-OMO-TASK-001",
            "--json",
        ),
        (
            "orca",
            "orchestration",
            "run-create",
            "--objective",
            "supervised-codex:wf-001:OMO-TASK-001:packet-001:omo-dispatch-001",
            "--from",
            "coordinator-001",
            "--json",
        ),
        (
            "orca",
            "orchestration",
            "task-create",
            "--run",
            "orca-run-001",
            "--task-title",
            "supervised-codex-OMO-TASK-001",
            "--spec",
            "Update the declared documentation fixture.",
            "--json",
        ),
        (
            "orca",
            "terminal",
            "create",
            "--worktree",
            f"id:{_orca_worktree_id(tmp_path)}",
            "--title",
            "supervised-codex-OMO-TASK-001",
            "--command",
            f"env AGENT_ID=agent-001 /opt/homebrew/bin/codex --ask-for-approval on-request --sandbox read-only -C {tmp_path}",
            "--json",
        ),
        (
            "orca",
            "terminal",
            "wait",
            "--terminal",
            "terminal-001",
            "--for",
            "tui-idle",
            "--timeout-ms",
            "60000",
            "--json",
        ),
        (
            "orca",
            "terminal",
            "show",
            "--terminal",
            "terminal-001",
            "--json",
        ),
        (
            "orca",
            "terminal",
            "read",
            "--terminal",
            "terminal-001",
            "--cursor",
            "0",
            "--limit",
            "80",
            "--json",
        ),
        (
            "orca",
            "orchestration",
            "worker-start",
            "--run",
            "orca-run-001",
            "--task",
            "orca-task-001",
            "--worktree",
            f"id:{_orca_worktree_id(tmp_path)}",
            "--terminal",
            "terminal-001",
            "--from",
            "coordinator-001",
            "--json",
        ),
    ]


def test_start_derives_one_stable_retry_request_per_orca_mutation(
    tmp_path: Path,
) -> None:
    module = _load_module()
    responses = _start_responses(tmp_path)
    worker_request_id = hashlib.sha256(b"retry-request-001\nworker-start").hexdigest()
    responses[-1][1]["result"]["mutation"]["requestId"] = worker_request_id
    runner = FakeRunner(responses)

    receipt = module.start_supervised_codex(
        **_identity(tmp_path),
        idempotency_key="retry-request-001",
        codex_executable="/opt/homebrew/bin/codex",
        runner=runner,
    )

    assert receipt["ok"] is True
    stage_ids = receipt["idempotency"]["stage_retry_requests"]
    assert receipt["idempotency"]["transaction_key_digest"] == (
        "sha256:" + hashlib.sha256(b"retry-request-001").hexdigest()
    )
    assert set(stage_ids) == {"run-create", "task-create", "worker-start"}
    assert len(set(stage_ids.values())) == 3
    for command, stage in zip(
        (runner.calls[3], runner.calls[4], runner.calls[-1]),
        ("run-create", "task-create", "worker-start"),
        strict=True,
    ):
        assert command[-3:] == ("--retry-request", stage_ids[stage], "--json")
    assert worker_request_id == stage_ids["worker-start"]


def test_start_rejects_worker_start_receipt_without_bound_terminal_effect(
    tmp_path: Path,
) -> None:
    module = _load_module()
    responses = _start_responses(tmp_path)
    result = responses[-1][1]["result"]
    result["effects"][0]["id"] = "wrong-terminal"

    receipt = module.start_supervised_codex(
        **_identity(tmp_path),
        codex_executable="/opt/homebrew/bin/codex",
        runner=FakeRunner(responses),
    )

    assert receipt["ok"] is False
    assert receipt["stage"] == "worker_start"
    assert receipt["reason"] == "orca_response_invalid"
    assert "orca:dispatch:orca-dispatch-001" in receipt["residual_resources"]


def test_start_fails_closed_on_unbound_worker_receipt_without_cleanup(
    tmp_path: Path,
) -> None:
    module = _load_module()
    responses = _start_responses(tmp_path)
    responses[-1] = (
        0,
        _ok(
            {
                "state": "ready",
                "dispatchId": "orca-dispatch-001",
                "taskId": "wrong-task",
                "runId": "orca-run-001",
                "agentTerminalHandle": "terminal-001",
            }
        ),
        "",
    )
    runner = FakeRunner(responses)
    identity = _identity(tmp_path)

    receipt = module.start_supervised_codex(
        **identity,
        codex_executable="/opt/homebrew/bin/codex",
        runner=runner,
    )

    assert receipt == {
        "schema": "orca-codex-supervisor/v1",
        "ok": False,
        "stage": "worker_start",
        "reason": "orca_response_invalid",
        "binding": {
            **_expected_binding(module, identity),
        },
        "orca": {
            "run_id": "orca-run-001",
            "task_id": "wrong-task",
            "dispatch_id": "orca-dispatch-001",
            "terminal_handle": "terminal-001",
        },
        "residual_resources": [
            "orca:terminal:coordinator-001",
            "orca:run:orca-run-001",
            "orca:task:orca-task-001",
            "orca:terminal:terminal-001",
            "orca:task:wrong-task",
            "orca:dispatch:orca-dispatch-001",
        ],
    }
    assert not any("worker-stop" in command for command in runner.calls)


def test_start_rejects_orca_codex_profile_bypass_before_dispatch(
    tmp_path: Path,
) -> None:
    module = _load_module()
    responses = _start_responses(tmp_path)
    responses[-2] = (
        0,
        _ok(
            {
                "terminal": {
                    "handle": "terminal-001",
                    "tail": ["codex --dangerously-bypass-approvals-and-sandbox"],
                }
            }
        ),
        "",
    )
    runner = FakeRunner(responses[:-1])

    receipt = module.start_supervised_codex(
        **_identity(tmp_path),
        codex_executable="/opt/homebrew/bin/codex",
        runner=runner,
    )

    assert receipt["ok"] is False
    assert receipt["stage"] == "terminal_read"
    assert receipt["reason"] == "codex_launch_unverified"
    assert receipt["residual_resources"] == [
        "orca:terminal:coordinator-001",
        "orca:run:orca-run-001",
        "orca:task:orca-task-001",
        "orca:terminal:terminal-001",
    ]
    assert not any("worker-start" in command for command in runner.calls)


def test_start_rejects_non_json_status_before_orca_mutations(tmp_path: Path) -> None:
    module = _load_module()
    runner = FakeRunner(
        [
            (
                0,
                _ok(
                    {
                        "worktree": {
                            "id": _orca_worktree_id(tmp_path),
                            "path": str(tmp_path),
                        }
                    }
                ),
                "",
            ),
            (0, "not-json", "runtime detail that must not leak"),
        ]
    )
    identity = _identity(tmp_path)

    receipt = module.start_supervised_codex(**identity, runner=runner)

    assert receipt == {
        "schema": "orca-codex-supervisor/v1",
        "ok": False,
        "stage": "status",
        "reason": "orca_response_invalid",
        "binding": _expected_binding(module, identity),
        "residual_resources": [],
    }
    assert runner.calls == [
        ("orca", "worktree", "show", "--worktree", f"path:{tmp_path}", "--json"),
        ("orca", "status", "--json"),
    ]


def test_start_rejects_worktree_id_with_nonmatching_suffix_path(tmp_path: Path) -> None:
    module = _load_module()
    responses = _start_responses(tmp_path)
    responses[0][1]["result"]["worktree"]["id"] = f"repo-001::{tmp_path}/other"
    runner = FakeRunner(responses)

    receipt = module.start_supervised_codex(**_identity(tmp_path), runner=runner)

    assert receipt["ok"] is False
    assert receipt["stage"] == "worktree_show"
    assert receipt["reason"] == "orca_worktree_unavailable"
    assert runner.calls == [
        ("orca", "worktree", "show", "--worktree", f"path:{tmp_path}", "--json")
    ]


def test_start_rejects_clone_guard_before_any_orca_call(tmp_path: Path) -> None:
    module = _load_module()
    guard_calls: list[tuple[str, ...]] = []

    def rejected_guard(command: tuple[str, ...], _timeout: float, _agent_id: str):
        guard_calls.append(command)
        return 1, json.dumps({"ok": False, "reason": "clone_identity_required"}), ""

    runner = FakeRunner([])
    receipt = module.start_supervised_codex(
        **_identity(tmp_path), runner=runner, guard_runner=rejected_guard
    )

    assert receipt["ok"] is False
    assert receipt["stage"] == "input"
    assert receipt["reason"] == "agent_clone_guard_rejected"
    assert runner.calls == []
    assert guard_calls[0][-2:] == ("--require-clone", "--json")


def test_start_rejects_linked_gitdir_before_clone_guard_or_orca(tmp_path: Path) -> None:
    module = _load_module()
    identity = _identity(tmp_path)
    git_dir = tmp_path / ".git"
    git_dir.rmdir()
    git_dir.write_text("gitdir: /shared/worktrees/x\n", encoding="utf-8")
    guard_called = False

    def guard_should_not_run(*_args):
        nonlocal guard_called
        guard_called = True
        return 0, "{}", ""

    runner = FakeRunner([])
    receipt = module.start_supervised_codex(
        **identity, runner=runner, guard_runner=guard_should_not_run
    )

    assert receipt["reason"] == "workspace_not_independent_clone"
    assert guard_called is False
    assert runner.calls == []


@pytest.mark.parametrize(
    ("task_response", "reason"),
    [
        (
            (1, {"ok": False, "error": {"code": "task_create_failed"}}, ""),
            "orca_task_not_created",
        ),
        (
            (
                0,
                _ok({"task": {"id": "orca-task-001", "run_id": "wrong-run"}}),
                "",
            ),
            "orca_response_invalid",
        ),
    ],
    ids=["task-create-failed", "task-create-bad-schema"],
)
def test_task_create_failure_preserves_created_run(
    tmp_path: Path, task_response: tuple[int, object, str], reason: str
) -> None:
    module = _load_module()
    runner = FakeRunner(_start_responses(tmp_path)[:4] + [task_response])

    receipt = module.start_supervised_codex(**_identity(tmp_path), runner=runner)

    assert receipt["ok"] is False
    assert receipt["stage"] == "task_create"
    assert receipt["reason"] == reason
    assert receipt["residual_resources"] == _run_residuals()
    assert len(runner.calls) == 5


@pytest.mark.parametrize(
    ("worker_response", "reason", "residual_resources"),
    [
        (
            (1, {"ok": False, "error": {"code": "worker_failed"}}, ""),
            "orca_worker_not_started",
            _run_task_residuals(),
        ),
        ((0, "not-json", ""), "orca_response_invalid", _run_task_residuals()),
        (
            (
                7,
                _ok(
                    {
                        "state": "ready",
                        "dispatchId": "orca-dispatch-001",
                        "taskId": "orca-task-001",
                        "runId": "orca-run-001",
                        "agentTerminalHandle": "terminal-001",
                    }
                ),
                "nonzero",
            ),
            "orca_worker_not_started",
            [
                *_run_task_residuals(),
                "orca:dispatch:orca-dispatch-001",
                "orca:terminal:terminal-001",
            ],
        ),
        (
            (124, {"ok": False, "error": {"code": "timeout"}}, "timed out"),
            "orca_worker_not_started",
            _run_task_residuals(),
        ),
    ],
    ids=["worker-failed", "worker-non-json", "worker-nonzero", "worker-timeout"],
)
def test_worker_start_failure_preserves_created_run_and_task(
    tmp_path: Path,
    worker_response: tuple[int, object, str],
    reason: str,
    residual_resources: list[str],
) -> None:
    module = _load_module()
    runner = FakeRunner(_start_responses(tmp_path)[:-1] + [worker_response])

    receipt = module.start_supervised_codex(**_identity(tmp_path), runner=runner)

    assert receipt["ok"] is False
    assert receipt["stage"] == "worker_start"
    assert receipt["reason"] == reason
    expected = [*_run_task_residuals(), "orca:terminal:terminal-001"]
    if "orca:dispatch:orca-dispatch-001" in residual_resources:
        expected.append("orca:dispatch:orca-dispatch-001")
    assert receipt["residual_resources"] == expected
    assert len(runner.calls) == 10


def test_collect_returns_only_digest_after_succeeded_worker_done_and_transcript(
    tmp_path: Path,
) -> None:
    module = _load_module()
    runner = FakeRunner(
        _collect_prefix(tmp_path)
        + [
            (
                0,
                _ok(
                    {
                        "dispatch": {
                            "id": "orca-dispatch-001",
                            "task_id": "orca-task-001",
                            "run_id": "orca-run-001",
                            "status": "completed",
                        },
                        "worker": {
                            "state": "completed",
                            "outcome": "succeeded",
                            "worker_done": {
                                "outcome": "succeeded",
                                "task_id": "orca-task-001",
                                "dispatch_id": "orca-dispatch-001",
                            },
                        },
                    }
                ),
                "",
            ),
            (
                0,
                _ok(
                    {
                        "source": "transcript",
                        "transcript": {
                            "messages": [
                                {
                                    "role": "assistant",
                                    "blocks": [
                                        {"type": "text", "text": "private result"}
                                    ],
                                }
                            ]
                        },
                    }
                ),
                "",
            ),
        ]
    )
    identity = _identity(tmp_path)

    receipt = module.collect_supervised_codex(
        **identity,
        orca_run_id="orca-run-001",
        orca_task_id="orca-task-001",
        orca_dispatch_id="orca-dispatch-001",
        terminal_handle="terminal-001",
        **_collect_clone_args(module, identity),
        runner=runner,
    )

    assert receipt["ok"] is True
    assert receipt["state"] == "settled"
    assert receipt["model_completion"] == "observed"
    assert receipt["transcript_digest"].startswith("sha256:")
    assert "private result" not in json.dumps(receipt)
    assert runner.calls == [
        ("orca", "worktree", "show", "--worktree", f"path:{tmp_path}", "--json"),
        ("orca", "terminal", "show", "--terminal", "terminal-001", "--json"),
        (
            "orca",
            "orchestration",
            "worker-show",
            "--dispatch",
            "orca-dispatch-001",
            "--json",
        ),
        (
            "orca",
            "orchestration",
            "worker-read",
            "--dispatch",
            "orca-dispatch-001",
            "--source",
            "transcript",
            "--limit",
            "200",
            "--json",
        ),
    ]


def test_collect_uses_bounded_terminal_evidence_when_session_was_not_reported(
    tmp_path: Path,
) -> None:
    module = _load_module()
    runner = FakeRunner(
        _collect_prefix(tmp_path)
        + [
            (
                0,
                _ok(
                    {
                        "dispatch": {
                            "id": "orca-dispatch-001",
                            "task_id": "orca-task-001",
                            "run_id": "orca-run-001",
                            "status": "completed",
                        },
                        "worker": {
                            "dispatch_id": "orca-dispatch-001",
                            "agent_terminal_handle": "terminal-001",
                            "state": "succeeded",
                            "stage": "settled",
                        },
                    }
                ),
                "",
            ),
            _session_not_reported_response(),
            _completed_task_list_response(),
            _terminal_fallback_response(),
        ]
    )
    identity = _identity(tmp_path)

    receipt = module.collect_supervised_codex(
        **identity,
        orca_run_id="orca-run-001",
        orca_task_id="orca-task-001",
        orca_dispatch_id="orca-dispatch-001",
        terminal_handle="terminal-001",
        **_collect_clone_args(module, identity),
        runner=runner,
    )

    assert receipt["ok"] is True
    assert receipt["state"] == "settled"
    assert receipt["model_completion"] == "observed"
    assert receipt["model_output_source"] == "bounded_terminal_fallback"
    assert receipt["fallback_reason"] == "session_not_reported"
    assert receipt["model_output_digest"].startswith("sha256:")
    assert receipt["completion_receipt_digest"].startswith("sha256:")
    assert receipt["source_identity_digest"].startswith("sha256:")
    serialized = json.dumps(receipt)
    assert "Completed the declared documentation update" not in serialized
    assert "terminal-source-001" not in serialized
    assert runner.calls[-3:] == [
        (
            "orca",
            "orchestration",
            "worker-read",
            "--dispatch",
            "orca-dispatch-001",
            "--source",
            "transcript",
            "--limit",
            "200",
            "--json",
        ),
        (
            "orca",
            "orchestration",
            "task-list",
            "--run",
            "orca-run-001",
            "--json",
        ),
        (
            "orca",
            "orchestration",
            "worker-read",
            "--dispatch",
            "orca-dispatch-001",
            "--source",
            "auto",
            "--limit",
            "200",
            "--json",
        ),
    ]


@pytest.mark.parametrize(
    "terminal_response",
    [
        _terminal_fallback_response(terminal_handle="different-terminal"),
        _terminal_fallback_response(tail=["• Ran a command", "no completion sentinel"]),
    ],
    ids=["terminal-drift", "model-output-unproven"],
)
def test_collect_terminal_fallback_fails_closed_without_bound_model_output(
    tmp_path: Path, terminal_response: tuple[int, object, str]
) -> None:
    module = _load_module()
    identity = _identity(tmp_path)
    runner = FakeRunner(
        _collect_prefix(tmp_path)
        + [
            (
                0,
                _ok(
                    {
                        "dispatch": {
                            "id": "orca-dispatch-001",
                            "task_id": "orca-task-001",
                            "run_id": "orca-run-001",
                            "status": "completed",
                        },
                        "worker": {
                            "dispatch_id": "orca-dispatch-001",
                            "agent_terminal_handle": "terminal-001",
                            "state": "succeeded",
                            "stage": "settled",
                        },
                    }
                ),
                "",
            ),
            _session_not_reported_response(),
            _completed_task_list_response(),
            terminal_response,
        ]
    )

    receipt = module.collect_supervised_codex(
        **identity,
        **_collect_clone_args(module, identity),
        orca_run_id="orca-run-001",
        orca_task_id="orca-task-001",
        orca_dispatch_id="orca-dispatch-001",
        terminal_handle="terminal-001",
        runner=runner,
    )

    assert receipt["ok"] is False
    assert receipt["stage"] == "worker_read"
    assert receipt["reason"] == "model_output_unproven"


def test_collect_keeps_active_worker_unmanaged_and_does_not_read_transcript(
    tmp_path: Path,
) -> None:
    module = _load_module()
    runner = FakeRunner(
        _collect_prefix(tmp_path)
        + [
            (
                0,
                _ok(
                    {
                        "dispatch": {
                            "id": "orca-dispatch-001",
                            "task_id": "orca-task-001",
                            "run_id": "orca-run-001",
                            "status": "dispatched",
                        },
                        "worker": {"state": "ready", "outcome": None},
                    }
                ),
                "",
            )
        ]
    )
    identity = _identity(tmp_path)

    receipt = module.collect_supervised_codex(
        **identity,
        orca_run_id="orca-run-001",
        orca_task_id="orca-task-001",
        orca_dispatch_id="orca-dispatch-001",
        terminal_handle="terminal-001",
        **_collect_clone_args(module, identity),
        runner=runner,
    )

    assert receipt == {
        "schema": "orca-codex-supervisor/v1",
        "ok": False,
        "stage": "worker_show",
        "reason": "worker_not_settled",
        "binding": _expected_binding(module, identity),
        "orca": {
            "run_id": "orca-run-001",
            "task_id": "orca-task-001",
            "dispatch_id": "orca-dispatch-001",
            "terminal_handle": "terminal-001",
        },
        "residual_resources": ["terminal-001"],
    }
    assert len(runner.calls) == 3


def test_collect_rejects_orca_worktree_id_drift_before_terminal_or_worker_read(
    tmp_path: Path,
) -> None:
    module = _load_module()
    identity = _identity(tmp_path)
    runner = FakeRunner(
        [
            (
                0,
                _ok(
                    {
                        "worktree": {
                            "id": f"repo-002::{tmp_path}",
                            "path": str(tmp_path),
                        }
                    }
                ),
                "",
            )
        ]
    )

    receipt = module.collect_supervised_codex(
        **identity,
        **_collect_clone_args(module, identity),
        orca_run_id="orca-run-001",
        orca_task_id="orca-task-001",
        orca_dispatch_id="orca-dispatch-001",
        terminal_handle="terminal-001",
        runner=runner,
    )

    assert receipt["ok"] is False
    assert receipt["stage"] == "worktree_show"
    assert receipt["reason"] == "orca_worktree_drift"
    assert runner.calls == [
        ("orca", "worktree", "show", "--worktree", f"path:{tmp_path}", "--json")
    ]


def test_collect_rejects_matching_worktree_id_with_nonmatching_suffix_path(
    tmp_path: Path,
) -> None:
    module = _load_module()
    identity = _identity(tmp_path)
    bad_worktree_id = f"repo-001::{tmp_path}/other"
    runner = FakeRunner(
        [
            (
                0,
                _ok(
                    {
                        "worktree": {
                            "id": bad_worktree_id,
                            "path": str(tmp_path),
                        }
                    }
                ),
                "",
            )
        ]
    )
    clone_args = _collect_clone_args(module, identity)
    clone_args["orca_worktree_id"] = bad_worktree_id

    receipt = module.collect_supervised_codex(
        **identity,
        **clone_args,
        orca_run_id="orca-run-001",
        orca_task_id="orca-task-001",
        orca_dispatch_id="orca-dispatch-001",
        terminal_handle="terminal-001",
        runner=runner,
    )

    assert receipt["ok"] is False
    assert receipt["stage"] == "worktree_show"
    assert receipt["reason"] == "orca_worktree_drift"
    assert len(runner.calls) == 1


def test_collect_rejects_terminal_drift_before_worker_read(tmp_path: Path) -> None:
    module = _load_module()
    identity = _identity(tmp_path)
    prefix = _collect_prefix(tmp_path)
    prefix[-1][1]["result"]["terminal"]["writable"] = False
    runner = FakeRunner(prefix)

    receipt = module.collect_supervised_codex(
        **identity,
        **_collect_clone_args(module, identity),
        orca_run_id="orca-run-001",
        orca_task_id="orca-task-001",
        orca_dispatch_id="orca-dispatch-001",
        terminal_handle="terminal-001",
        runner=runner,
    )

    assert receipt["ok"] is False
    assert receipt["stage"] == "terminal_show"
    assert receipt["reason"] == "orca_terminal_drift"
    assert len(runner.calls) == 2


@pytest.mark.parametrize(
    "messages",
    [
        [{}],
        [{"role": "user", "blocks": [{"type": "text", "text": "request"}]}],
        [{"role": "system", "blocks": [{"type": "text", "text": "notice"}]}],
        [{"role": "assistant", "blocks": [{"type": "text", "text": "   "}]}],
    ],
    ids=["empty-object", "user-only", "system-only", "empty-assistant-output"],
)
def test_collect_rejects_transcript_without_explicit_nonempty_model_output(
    tmp_path: Path, messages: list[object]
) -> None:
    module = _load_module()
    identity = _identity(tmp_path)
    runner = FakeRunner(
        _collect_prefix(tmp_path)
        + [_settled_worker_response(), _transcript_response(messages)]
    )

    receipt = module.collect_supervised_codex(
        **identity,
        **_collect_clone_args(module, identity),
        orca_run_id="orca-run-001",
        orca_task_id="orca-task-001",
        orca_dispatch_id="orca-dispatch-001",
        terminal_handle="terminal-001",
        runner=runner,
    )

    assert receipt["ok"] is False
    assert receipt["stage"] == "worker_read"
    assert receipt["reason"] == "model_output_unproven"


def test_start_rejects_prompt_digest_drift_before_orca_calls(tmp_path: Path) -> None:
    module = _load_module()
    runner = FakeRunner([])
    identity = _identity(tmp_path)
    identity["prompt_digest"] = "sha256:" + "b" * 64

    receipt = module.start_supervised_codex(**identity, runner=runner)

    assert receipt["ok"] is False
    assert receipt["stage"] == "input"
    assert receipt["reason"] == "prompt_digest_mismatch"
    assert runner.calls == []


def test_start_rejects_non_sha256_packet_hash_before_orca_calls(tmp_path: Path) -> None:
    module = _load_module()
    runner = FakeRunner([])
    identity = _identity(tmp_path)
    identity["packet_hash"] = "not-a-sha256"

    receipt = module.start_supervised_codex(**identity, runner=runner)

    assert receipt == {
        "schema": "orca-codex-supervisor/v1",
        "ok": False,
        "stage": "input",
        "reason": "identity_invalid",
        "binding": {},
        "residual_resources": [],
    }
    assert runner.calls == []


def test_start_rejects_symlink_prompt_ref_before_orca_calls(tmp_path: Path) -> None:
    module = _load_module()
    outside = tmp_path.parent / "outside-prompt.md"
    outside.write_text("outside", encoding="utf-8")
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "dogfood.md").symlink_to(outside)
    identity = {
        "workflow_run_id": "wf-001",
        "omo_task_id": "OMO-TASK-001",
        "packet_id": "packet-001",
        "packet_hash": "sha256:" + "a" * 64,
        "omo_dispatch_id": "omo-dispatch-001",
        "workspace_root": str(tmp_path),
        "prompt_ref": "prompts/dogfood.md",
        "prompt_digest": "sha256:" + hashlib.sha256(b"outside").hexdigest(),
        "agent_id": "agent-001",
    }
    runner = FakeRunner([])

    receipt = module.start_supervised_codex(**identity, runner=runner)

    assert receipt["ok"] is False
    assert receipt["stage"] == "input"
    assert receipt["reason"] == "prompt_ref_unsafe"
    assert runner.calls == []


def test_start_accepts_plus_sign_in_dispatch_id(tmp_path: Path) -> None:
    """Realistic omo_dispatch_id with +0000 suffix must pass identity validation."""
    module = _load_module()
    runner = FakeRunner(_start_responses(tmp_path))
    identity = _identity(tmp_path)
    identity["omo_dispatch_id"] = "ctx_1d58fa0dd44d+0000"

    receipt = module.start_supervised_codex(
        **identity,
        codex_executable="/opt/homebrew/bin/codex",
        runner=runner,
    )

    assert receipt["ok"] is True
    assert receipt["binding"]["omo_dispatch_id"] == "ctx_1d58fa0dd44d+0000"
    assert len(runner.calls) > 0  # identity passed validation, reached runner


@pytest.mark.parametrize(
    "bad_char",
    [" ", "\t", "\n", "\r", "/", "\\", ";", "|", "&", "$", "`", "'", '"', "(", ")"],
    ids=[
        "space",
        "tab",
        "newline",
        "carriage-return",
        "slash",
        "backslash",
        "semicolon",
        "pipe",
        "ampersand",
        "dollar",
        "backtick",
        "single-quote",
        "double-quote",
        "lparen",
        "rparen",
    ],
)
def test_start_rejects_shell_dangerous_chars_in_dispatch_id(
    tmp_path: Path, bad_char: str
) -> None:
    """Shell-dangerous / path-traversal chars in dispatch ID must still be rejected."""
    module = _load_module()
    runner = FakeRunner([])
    identity = _identity(tmp_path)
    identity["omo_dispatch_id"] = f"ctx_abc{bad_char}def"

    receipt = module.start_supervised_codex(**identity, runner=runner)

    assert receipt["ok"] is False
    assert receipt["reason"] == "identity_invalid"
    assert runner.calls == []


def test_start_rejects_nul_prompt_ref_before_orca_calls(tmp_path: Path) -> None:
    module = _load_module()
    identity = _identity(tmp_path)
    identity["prompt_ref"] = "prompts/\x00dogfood.md"
    runner = FakeRunner([])

    receipt = module.start_supervised_codex(**identity, runner=runner)

    assert receipt["ok"] is False
    assert receipt["stage"] == "input"
    assert receipt["reason"] == "prompt_ref_unsafe"
    assert runner.calls == []
