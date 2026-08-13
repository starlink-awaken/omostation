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


def _identity(
    tmp_path: Path, prompt: str = "Update the declared documentation fixture."
) -> dict[str, str]:
    (tmp_path / "prompts").mkdir(exist_ok=True)
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
    }


def _start_responses() -> list[tuple[int, object, str]]:
    return [
        (0, _ok({"app": {"running": True}, "runtime": {"state": "ready"}}), ""),
        (0, _ok({"run": {"id": "orca-run-001"}}), ""),
        (
            0,
            _ok({"task": {"id": "orca-task-001", "run_id": "orca-run-001"}}),
            "",
        ),
        (
            0,
            _ok(
                {
                    "state": "ready",
                    "dispatchId": "orca-dispatch-001",
                    "taskId": "orca-task-001",
                    "runId": "orca-run-001",
                    "agentTerminalHandle": "terminal-001",
                }
            ),
            "",
        ),
    ]


def _run_residuals() -> list[str]:
    return ["orca:run:orca-run-001"]


def _run_task_residuals() -> list[str]:
    return ["orca:run:orca-run-001", "orca:task:orca-task-001"]


def test_start_binds_omo_and_orca_identities_without_claiming_input_or_completion(
    tmp_path: Path,
) -> None:
    module = _load_module()
    runner = FakeRunner(_start_responses())
    identity = _identity(tmp_path)

    receipt = module.start_supervised_codex(**identity, runner=runner)

    assert receipt == {
        "schema": "orca-codex-supervisor/v1",
        "ok": True,
        "state": "awaiting_human_action",
        "binding": {
            key: value for key, value in identity.items() if key != "workspace_root"
        },
        "orca": {
            "run_id": "orca-run-001",
            "task_id": "orca-task-001",
            "dispatch_id": "orca-dispatch-001",
            "terminal_handle": "terminal-001",
        },
        "human_action_required": True,
        "input_accepted": "unproven",
        "model_completion": "unproven",
    }
    assert runner.calls == [
        ("orca", "status", "--json"),
        (
            "orca",
            "orchestration",
            "run-create",
            "--objective",
            "supervised-codex:wf-001:OMO-TASK-001:packet-001:omo-dispatch-001",
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
            "orchestration",
            "worker-start",
            "--run",
            "orca-run-001",
            "--task",
            "orca-task-001",
            "--worktree",
            "current",
            "--agent",
            "codex",
            "--json",
        ),
    ]


def test_start_derives_one_stable_retry_request_per_orca_mutation(
    tmp_path: Path,
) -> None:
    module = _load_module()
    runner = FakeRunner(_start_responses())

    receipt = module.start_supervised_codex(
        **_identity(tmp_path),
        idempotency_key="retry-request-001",
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
        runner.calls[1:],
        ("run-create", "task-create", "worker-start"),
        strict=True,
    ):
        assert command[-3:] == ("--retry-request", stage_ids[stage], "--json")


def test_start_fails_closed_on_unbound_worker_receipt_without_cleanup(
    tmp_path: Path,
) -> None:
    module = _load_module()
    responses = _start_responses()
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

    receipt = module.start_supervised_codex(**identity, runner=runner)

    assert receipt == {
        "schema": "orca-codex-supervisor/v1",
        "ok": False,
        "stage": "worker_start",
        "reason": "orca_response_invalid",
        "binding": {
            key: value for key, value in identity.items() if key != "workspace_root"
        },
        "orca": {
            "run_id": "orca-run-001",
            "task_id": "wrong-task",
            "dispatch_id": "orca-dispatch-001",
            "terminal_handle": "terminal-001",
        },
        "residual_resources": [
            "orca:run:orca-run-001",
            "orca:task:orca-task-001",
            "orca:task:wrong-task",
            "orca:dispatch:orca-dispatch-001",
            "orca:terminal:terminal-001",
        ],
    }
    assert not any("worker-stop" in command for command in runner.calls)


def test_start_rejects_non_json_status_before_orca_mutations(tmp_path: Path) -> None:
    module = _load_module()
    runner = FakeRunner([(0, "not-json", "runtime detail that must not leak")])
    identity = _identity(tmp_path)

    receipt = module.start_supervised_codex(**identity, runner=runner)

    assert receipt == {
        "schema": "orca-codex-supervisor/v1",
        "ok": False,
        "stage": "status",
        "reason": "orca_response_invalid",
        "binding": {
            key: value for key, value in identity.items() if key != "workspace_root"
        },
        "residual_resources": [],
    }
    assert runner.calls == [("orca", "status", "--json")]


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
    runner = FakeRunner(_start_responses()[:2] + [task_response])

    receipt = module.start_supervised_codex(**_identity(tmp_path), runner=runner)

    assert receipt["ok"] is False
    assert receipt["stage"] == "task_create"
    assert receipt["reason"] == reason
    assert receipt["residual_resources"] == _run_residuals()
    assert len(runner.calls) == 3


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
    runner = FakeRunner(_start_responses()[:3] + [worker_response])

    receipt = module.start_supervised_codex(**_identity(tmp_path), runner=runner)

    assert receipt["ok"] is False
    assert receipt["stage"] == "worker_start"
    assert receipt["reason"] == reason
    assert receipt["residual_resources"] == residual_resources
    assert len(runner.calls) == 4


def test_collect_returns_only_digest_after_succeeded_worker_done_and_transcript(
    tmp_path: Path,
) -> None:
    module = _load_module()
    runner = FakeRunner(
        [
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
        runner=runner,
    )

    assert receipt["ok"] is True
    assert receipt["state"] == "settled"
    assert receipt["model_completion"] == "observed"
    assert receipt["transcript_digest"].startswith("sha256:")
    assert "private result" not in json.dumps(receipt)
    assert runner.calls == [
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


def test_collect_keeps_active_worker_unmanaged_and_does_not_read_transcript(
    tmp_path: Path,
) -> None:
    module = _load_module()
    runner = FakeRunner(
        [
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
        runner=runner,
    )

    assert receipt == {
        "schema": "orca-codex-supervisor/v1",
        "ok": False,
        "stage": "worker_show",
        "reason": "worker_not_settled",
        "binding": {
            key: value for key, value in identity.items() if key != "workspace_root"
        },
        "orca": {
            "run_id": "orca-run-001",
            "task_id": "orca-task-001",
            "dispatch_id": "orca-dispatch-001",
            "terminal_handle": "terminal-001",
        },
        "residual_resources": ["terminal-001"],
    }
    assert len(runner.calls) == 1


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
    }
    runner = FakeRunner([])

    receipt = module.start_supervised_codex(**identity, runner=runner)

    assert receipt["ok"] is False
    assert receipt["stage"] == "input"
    assert receipt["reason"] == "prompt_ref_unsafe"
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
