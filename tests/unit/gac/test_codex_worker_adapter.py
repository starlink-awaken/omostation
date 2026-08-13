"""Contract tests for the bounded Codex exec worker adapter."""

from __future__ import annotations

import importlib.util
import json
import os
import signal
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

SCRIPT = Path(__file__).parents[3] / "bin/gac/codex-worker-adapter.py"
WORKERS = Path(__file__).parents[3] / ".omo/_truth/registry/workers.yaml"
SPEC = importlib.util.spec_from_file_location("codex_worker_adapter", SCRIPT)
assert SPEC and SPEC.loader
adapter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(adapter)


def clone_root(tmp_path: Path) -> Path:
    root = tmp_path / "clone"
    git_dir = root / ".git"
    git_dir.mkdir(parents=True)
    (git_dir / "agent-clone-identity.json").write_text(
        json.dumps(
            {
                "schema": "agent-clone-identity/v1",
                "canonical_root": str(root),
                "ready": True,
            }
        ),
        encoding="utf-8",
    )
    return root


def real_clone_root(tmp_path: Path) -> Path:
    root = tmp_path / "real-clone"
    root.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "-b", "task", str(root)], check=True)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.name", "Test Worker"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "worker@example.invalid"],
        check=True,
    )
    (root / "README.md").write_text("baseline\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "README.md"], check=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-q", "-m", "baseline"], check=True
    )
    (root / ".git/agent-clone-identity.json").write_text(
        json.dumps(
            {
                "schema": "agent-clone-identity/v1",
                "canonical_root": str(root),
                "ready": True,
            }
        ),
        encoding="utf-8",
    )
    return root


def write_prompt(*paths: str) -> str:
    constraints = "\n".join(f"- You may write to `{path}`" for path in paths)
    return f"# Worker Prompt Contract\n\n## Constraints\n\n{constraints}\n\n## Required deliverables\n"


def jsonl(message: str = "final answer") -> str:
    return "\n".join(
        [
            json.dumps({"type": "thread.started", "thread_id": "secret"}),
            json.dumps(
                {
                    "type": "item.completed",
                    "item": {"type": "agent_message", "text": "earlier"},
                }
            ),
            json.dumps(
                {
                    "type": "item.completed",
                    "item": {"type": "agent_message", "text": message},
                }
            ),
        ]
    )


class FakeProcess:
    def __init__(
        self, *, stdout: str | None = None, stderr: str = "", returncode: int = 0
    ) -> None:
        self.pid = 43210
        self.stdout = jsonl() if stdout is None else stdout
        self.stderr = stderr
        self.returncode = returncode
        self.wait_calls: list[float | None] = []

    def communicate(self, timeout: float | None = None) -> tuple[str, str]:
        return self.stdout, self.stderr

    def wait(self, timeout: float | None = None) -> int:
        self.wait_calls.append(timeout)
        return self.returncode


class HungProcess(FakeProcess):
    def communicate(self, timeout: float | None = None) -> tuple[str, str]:
        raise subprocess.TimeoutExpired("codex", timeout)

    def wait(self, timeout: float | None = None) -> int:
        self.wait_calls.append(timeout)
        if len(self.wait_calls) == 1:
            raise subprocess.TimeoutExpired("codex", timeout)
        return self.returncode


class PartialHungProcess(HungProcess):
    def communicate(self, timeout: float | None = None) -> tuple[str, str]:
        raise subprocess.TimeoutExpired("codex", timeout, output=self.stdout)


def run_success(tmp_path: Path, **overrides):
    arguments = {
        "workspace_root": real_clone_root(tmp_path),
        "prompt": write_prompt("allowed.txt"),
        "execute": True,
        "popen_factory": lambda *_args, **_kwargs: FakeProcess(),
        "codex_resolver": lambda: Path("/usr/local/bin/codex"),
        "version_reader": lambda _binary: "codex-cli 0.147.0",
    }
    arguments.update(overrides)
    return adapter.run_worker(**arguments)


def test_dry_run_is_default_and_returns_only_fixed_command(tmp_path: Path):
    root = clone_root(tmp_path)

    result = adapter.run_worker(workspace_root=root, prompt="do work")

    assert result == {
        "command": [
            "codex",
            "exec",
            "--approve-for-me",
            "--ephemeral",
            "--ignore-user-config",
            "--json",
            "--color",
            "never",
            "-C",
            str(root),
            "do work",
        ],
        "mode": "dry-run",
    }


def test_execute_uses_exact_argv_no_shell_and_scrubbed_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    root = real_clone_root(tmp_path)
    captured: dict[str, object] = {}
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    monkeypatch.setenv("HTTPS_PROXY", "http://secret")
    monkeypatch.setenv("SSH_AUTH_SOCK", "/tmp/secret")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setenv("GITHUB_TOKEN", "secret")
    monkeypatch.setenv("CODEX_HOME", "/safe/codex-home")

    def start(argv, **kwargs):
        captured["argv"] = argv
        captured.update(kwargs)
        return FakeProcess()

    adapter.run_worker(
        workspace_root=root,
        prompt=write_prompt("allowed.txt"),
        execute=True,
        popen_factory=start,
        codex_resolver=lambda: Path("/opt/codex/bin/codex"),
        version_reader=lambda _binary: "codex-cli 0.147.0",
        group_probe=lambda _pid: False,
    )

    argv = captured["argv"]
    assert (
        argv[: argv.index("-C")]
        == adapter.fixed_argv(
            Path("/opt/codex/bin/codex"), root, write_prompt("allowed.txt")
        )[: argv.index("-C")]
    )
    execution_root = Path(argv[argv.index("-C") + 1])
    assert execution_root != root
    assert argv[-1] == write_prompt("allowed.txt")
    assert captured["shell"] is False
    assert captured["start_new_session"] is True
    assert captured["text"] is True
    env = captured["env"]
    assert env["CODEX_HOME"] == "/safe/codex-home"
    for name in (
        "OPENAI_API_KEY",
        "HTTPS_PROXY",
        "SSH_AUTH_SOCK",
        "AWS_SECRET_ACCESS_KEY",
        "GITHUB_TOKEN",
    ):
        assert name not in env


@pytest.mark.parametrize(
    "version",
    [
        "codex 0.147.0",
        "codex-cli dev",
        "codex-cli 0.146.9",
        "",
        "codex-cli 0.147.0 extra",
    ],
)
def test_invalid_or_unsupported_codex_version_fails_before_launch(
    tmp_path: Path, version: str
):
    called = False

    def start(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("must not launch")

    with pytest.raises(adapter.AdapterError, match="codex_identity_invalid"):
        adapter.run_worker(
            workspace_root=clone_root(tmp_path),
            prompt="x",
            execute=True,
            popen_factory=start,
            codex_resolver=lambda: Path("/usr/local/bin/codex"),
            version_reader=lambda _binary: version,
        )

    assert called is False


def test_missing_or_non_regular_codex_is_unavailable(tmp_path: Path):
    with pytest.raises(adapter.AdapterError, match="codex_unavailable"):
        adapter.run_worker(
            workspace_root=clone_root(tmp_path),
            prompt="x",
            execute=True,
            codex_resolver=lambda: None,
        )


@pytest.mark.parametrize(
    "case", ["missing_identity", "linked_git", "identity_mismatch", "not_ready"]
)
def test_non_independent_workspace_is_rejected_before_launch(tmp_path: Path, case: str):
    root = clone_root(tmp_path)
    identity = root / ".git/agent-clone-identity.json"
    if case == "missing_identity":
        identity.unlink()
    elif case == "linked_git":
        identity.unlink()
        (root / ".git").rmdir()
        (root / ".git").write_text("gitdir: /shared/worktrees/x\n", encoding="utf-8")
    else:
        payload = json.loads(identity.read_text(encoding="utf-8"))
        payload["canonical_root" if case == "identity_mismatch" else "ready"] = (
            str(tmp_path / "other") if case == "identity_mismatch" else False
        )
        identity.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(adapter.AdapterError, match="workspace_not_independent_clone"):
        adapter.run_worker(workspace_root=root, prompt="x", execute=True)


def test_symlink_workspace_is_rejected(tmp_path: Path):
    root = clone_root(tmp_path)
    link = tmp_path / "linked"
    link.symlink_to(root, target_is_directory=True)

    with pytest.raises(adapter.AdapterError, match="workspace_not_independent_clone"):
        adapter.run_worker(workspace_root=link, prompt="x", execute=True)


def test_jsonl_projects_only_last_assistant_message(tmp_path: Path):
    result = run_success(
        tmp_path,
        popen_factory=lambda *_args, **_kwargs: FakeProcess(stdout=jsonl("safe final")),
    )

    assert result["output"] == "safe final"


def test_unknown_jsonl_event_keeps_provider_review_unknown(tmp_path: Path) -> None:
    receipt = tmp_path / "receipt.json"
    stdout = "\n".join(
        [
            json.dumps({"type": "future.provider.event", "detail": "secret"}),
            jsonl("safe final"),
        ]
    )

    result = run_success(
        tmp_path,
        receipt_path=receipt,
        popen_factory=lambda *_args, **_kwargs: FakeProcess(stdout=stdout),
    )

    assert result["receipt"]["supervision"]["provider_review"] == "unknown"
    assert "future.provider.event" not in receipt.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "approval_event_type", ["exec_approval_request", "apply_patch_approval_request"]
)
def test_observed_approval_event_fails_closed_without_receipt_or_patch(
    tmp_path: Path, approval_event_type: str
) -> None:
    root = real_clone_root(tmp_path)
    receipt = tmp_path / "receipt.json"
    stdout = "\n".join(
        [
            json.dumps({"type": approval_event_type, "command": "secret"}),
            jsonl("safe final"),
        ]
    )

    def start(argv, **_kwargs):
        execution_root = Path(argv[argv.index("-C") + 1])
        (execution_root / "allowed.txt").write_text("candidate\n", encoding="utf-8")
        return FakeProcess(stdout=stdout)

    with pytest.raises(adapter.AdapterError, match="human_approval_required") as raised:
        adapter.run_worker(
            workspace_root=root,
            prompt=write_prompt("allowed.txt"),
            execute=True,
            receipt_path=receipt,
            popen_factory=start,
            codex_resolver=lambda: Path("/usr/local/bin/codex"),
            version_reader=lambda _binary: "codex-cli 0.147.0",
            group_probe=lambda _pid: False,
        )

    assert raised.value.provider_review == "human_required"
    assert not receipt.exists()
    assert not (root / "allowed.txt").exists()
    assert (
        subprocess.run(
            ["git", "-C", str(root), "status", "--short"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        == ""
    )


@pytest.mark.parametrize(
    ("stdout", "returncode", "error"),
    [
        (jsonl(), 7, "worker_nonzero"),
        ("", 0, "worker_output_invalid"),
        ("not-json\n", 0, "worker_output_invalid"),
        (
            json.dumps(
                {"type": "item.completed", "item": {"type": "command_execution"}}
            ),
            0,
            "worker_output_invalid",
        ),
    ],
)
def test_nonzero_empty_or_malformed_output_fails_closed(
    tmp_path: Path, stdout: str, returncode: int, error: str
):
    with pytest.raises(adapter.AdapterError, match=error):
        run_success(
            tmp_path,
            popen_factory=lambda *_args, **_kwargs: FakeProcess(
                stdout=stdout, returncode=returncode
            ),
        )


def test_exact_marker_must_match_final_message(tmp_path: Path):
    with pytest.raises(adapter.AdapterError, match="marker_mismatch"):
        run_success(tmp_path, expect_exact="expected")


def test_timeout_sends_term_then_kill_and_waits_after_each(tmp_path: Path):
    process = HungProcess()
    signals: list[tuple[int, signal.Signals]] = []

    with pytest.raises(adapter.AdapterError, match="worker_timeout"):
        run_success(
            tmp_path,
            popen_factory=lambda *_args, **_kwargs: process,
            group_terminator=lambda pid, value: signals.append((pid, value)),
            timeout_seconds=1,
        )

    assert signals == [(process.pid, signal.SIGTERM), (process.pid, signal.SIGKILL)]
    assert len(process.wait_calls) == 2


@pytest.mark.parametrize(
    ("partial_stdout", "provider_review"),
    [
        (json.dumps({"type": "turn.started"}), "timed_out"),
        (
            json.dumps(
                {"type": "apply_patch_approval_request", "path": "/private/secret"}
            ),
            "human_required",
        ),
    ],
)
def test_timeout_classifies_partial_jsonl_without_receipt_or_patch_application(
    tmp_path: Path, partial_stdout: str, provider_review: str
) -> None:
    root = real_clone_root(tmp_path)
    receipt = tmp_path / "receipt.json"
    process = PartialHungProcess(stdout=partial_stdout)

    def start(argv, **_kwargs):
        execution_root = Path(argv[argv.index("-C") + 1])
        (execution_root / "allowed.txt").write_text("candidate\n", encoding="utf-8")
        return process

    with pytest.raises(adapter.AdapterError, match="worker_timeout") as raised:
        adapter.run_worker(
            workspace_root=root,
            prompt=write_prompt("allowed.txt"),
            execute=True,
            receipt_path=receipt,
            popen_factory=start,
            codex_resolver=lambda: Path("/usr/local/bin/codex"),
            version_reader=lambda _binary: "codex-cli 0.147.0",
            group_terminator=lambda *_args: None,
            group_probe=lambda _pid: False,
            timeout_seconds=1,
        )

    assert raised.value.provider_review == provider_review
    assert not receipt.exists()
    assert not (root / "allowed.txt").exists()


def test_timeout_parent_exit_does_not_hide_surviving_process_group(tmp_path: Path):
    process = HungProcess()
    process.wait = lambda timeout=None: process.returncode
    signals: list[tuple[int, signal.Signals]] = []
    probe_results = iter([True, False])

    with pytest.raises(adapter.AdapterError, match="worker_timeout"):
        run_success(
            tmp_path,
            popen_factory=lambda *_args, **_kwargs: process,
            group_probe=lambda _pid: next(probe_results),
            group_terminator=lambda pid, value: signals.append((pid, value)),
            timeout_seconds=1,
        )

    assert signals == [
        (process.pid, signal.SIGTERM),
        (process.pid, signal.SIGKILL),
    ]


def test_unconfirmed_timeout_cleanup_has_stable_failure(tmp_path: Path):
    process = HungProcess()
    process.wait = lambda timeout=None: (_ for _ in ()).throw(
        subprocess.TimeoutExpired("codex", timeout)
    )

    with pytest.raises(adapter.AdapterError, match="cleanup_unconfirmed"):
        run_success(
            tmp_path,
            popen_factory=lambda *_args, **_kwargs: process,
            group_terminator=lambda *_args: None,
            timeout_seconds=1,
        )


def test_git_status_failure_is_not_reported_as_no_changed_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        adapter.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=7, stdout=""),
    )

    with pytest.raises(adapter.AdapterError) as raised:
        adapter._default_changed_paths_reader(tmp_path)

    assert raised.value.code == "git_status_failed"


def test_git_status_timeout_is_not_reported_as_no_changed_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    def time_out(*_args, **_kwargs):
        raise subprocess.TimeoutExpired("git status", 10)

    monkeypatch.setattr(adapter.subprocess, "run", time_out)

    with pytest.raises(adapter.AdapterError) as raised:
        adapter._default_changed_paths_reader(tmp_path)

    assert raised.value.code == "git_status_timeout"


def test_surviving_process_group_after_parent_exit_fails_closed(tmp_path: Path):
    process = FakeProcess()
    signals: list[tuple[int, signal.Signals]] = []
    probe_results = iter([True, False])

    with pytest.raises(adapter.AdapterError) as raised:
        run_success(
            tmp_path,
            popen_factory=lambda *_args, **_kwargs: process,
            group_probe=lambda _pid: next(probe_results),
            group_terminator=lambda pid, value: signals.append((pid, value)),
        )

    assert raised.value.code == "process_leaked"
    assert signals == [(process.pid, signal.SIGTERM)]


def test_receipt_is_exclusive_temp_only_canonical_and_redacted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    receipt = Path(os.getenv("TMPDIR", "/tmp")) / f"codex-receipt-{tmp_path.name}.json"
    monkeypatch.setenv("PRIVATE_TOKEN", "receipt-secret")
    try:
        result = run_success(tmp_path, receipt_path=receipt)
        raw = receipt.read_text(encoding="utf-8")
        payload = json.loads(raw)

        assert (
            raw
            == json.dumps(
                payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
            + "\n"
        )
        assert payload["schema"] == "codex-worker-execution/v1"
        assert payload["worker"] == "codex"
        assert payload["status"] == "succeeded"
        assert payload["changed_paths"] == []
        assert payload["output_sha256"] == adapter.digest_text("final answer")
        assert payload["supervision"] == {
            "controller_approval": "granted",
            "provider_review": "completed_without_observed_escalation",
        }
        assert payload["readiness"] == "model_output_observed"
        assert payload["baseline_digest"].startswith("sha256:")
        assert payload["post_digest"].startswith("sha256:")
        assert payload["patch_digest"].startswith("sha256:")
        assert payload["baseline_digest"] == payload["post_digest"]
        assert payload["receipt_sha256"] == adapter.receipt_digest(payload)
        assert result["receipt"] == payload
        for secret in (
            "allowed.txt",
            "final answer",
            "receipt-secret",
            "secret",
            "thread_id",
        ):
            assert secret not in raw

        with pytest.raises(adapter.AdapterError, match="unsafe_receipt"):
            run_success(tmp_path / "again", receipt_path=receipt)
    finally:
        receipt.unlink(missing_ok=True)


def test_receipt_outside_system_temp_is_rejected(tmp_path: Path):
    receipt = Path.cwd() / f"unsafe-codex-receipt-{tmp_path.name}.json"
    try:
        with pytest.raises(adapter.AdapterError, match="unsafe_receipt"):
            run_success(tmp_path, receipt_path=receipt)
    finally:
        receipt.unlink(missing_ok=True)


def test_receipt_write_failure_is_stable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    receipt = (
        Path(os.getenv("TMPDIR", "/tmp")) / f"codex-receipt-fail-{tmp_path.name}.json"
    )
    monkeypatch.setattr(
        adapter,
        "_write_receipt",
        lambda *_args: (_ for _ in ()).throw(OSError("secret")),
    )

    with pytest.raises(adapter.AdapterError, match="receipt_write_failed"):
        run_success(tmp_path, receipt_path=receipt)


def test_partial_staged_receipt_is_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt = tmp_path / "receipt.json"

    def partial_write(path: Path, _payload) -> None:
        path.write_text("partial", encoding="utf-8")
        raise OSError("write failed")

    monkeypatch.setattr(adapter, "_write_receipt", partial_write)

    with pytest.raises(OSError, match="write failed"):
        adapter._stage_receipt(receipt, {"status": "candidate"})

    assert list(tmp_path.iterdir()) == []


def test_cli_exposes_only_bounded_options_and_emits_final_message(
    monkeypatch: pytest.MonkeyPatch, capsys
):
    monkeypatch.setattr(
        adapter, "run_worker", lambda **_kwargs: {"output": "final\n", "receipt": None}
    )

    assert (
        adapter.main(
            ["run", "--execute", "--workspace-root", "/clone", "--prompt", "x"]
        )
        == 0
    )
    assert capsys.readouterr().out == "final\n"
    with pytest.raises(SystemExit):
        adapter.build_parser().parse_args(
            [
                "run",
                "--workspace-root",
                "/clone",
                "--prompt",
                "x",
                "--model",
                "dangerous",
            ]
        )


def test_cli_failure_emits_only_safe_provider_review(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    monkeypatch.setattr(
        adapter,
        "run_worker",
        lambda **_kwargs: (_ for _ in ()).throw(
            adapter.AdapterError("worker_timeout", provider_review="human_required")
        ),
    )

    assert (
        adapter.main(
            ["run", "--execute", "--workspace-root", "/clone", "--prompt", "secret"]
        )
        == 2
    )
    assert json.loads(capsys.readouterr().err) == {
        "error_code": "worker_timeout",
        "provider_review": "human_required",
        "status": "failed",
    }


def test_codex_worker_registry_admits_only_the_interactive_orca_supervisor() -> None:
    registry = list(yaml.safe_load_all(WORKERS.read_text(encoding="utf-8")))[-1]
    codex = next(worker for worker in registry["workers"] if worker["id"] == "codex")

    assert codex["enabled"] is True
    assert codex["admission_state"] == "admitted"
    assert codex["provider_ref"] == "codex"
    assert codex["require_explicit_capabilities"] is True
    assert codex["allowed_operation_level"] == "L1"
    assert codex["write_scope"] == {
        "mode": "task_declared_only",
        "forbidden_paths": [
            ".omo/state/system.yaml",
            ".omo/goals/current.yaml",
            "convergence.yaml",
        ],
    }
    assert codex["transports"] == {
        "cli_prompt": {
            "command": (
                '/usr/bin/python3 "{workspace_root}/bin/gac/'
                'orca-codex-supervisor.py" start'
            )
        }
    }
    assert codex["supervision"] == {
        "controller_approval": "required",
        "provider_review": "manual_click_required",
        "waiting_state": "awaiting_human_action",
        "readiness_evidence": "settled_worker_done_and_transcript_digest",
        "transport_ack_is_readiness": False,
        "controller_direct_start_required": True,
    }


def test_execution_clone_applies_only_declared_worker_delta(tmp_path: Path) -> None:
    root = real_clone_root(tmp_path)
    (root / "preexisting.txt").write_text("keep me\n", encoding="utf-8")
    receipt = tmp_path / "codex-worker-receipt.json"

    def start(argv, **_kwargs):
        execution_root = Path(argv[argv.index("-C") + 1])
        assert execution_root != root
        (execution_root / "allowed.txt").write_text("worker result\n", encoding="utf-8")
        return FakeProcess(stdout=jsonl("done"))

    result = adapter.run_worker(
        workspace_root=root,
        prompt=write_prompt("allowed.txt"),
        execute=True,
        receipt_path=receipt,
        popen_factory=start,
        codex_resolver=lambda: Path("/usr/local/bin/codex"),
        version_reader=lambda _binary: "codex-cli 0.147.0",
        group_probe=lambda _pid: False,
    )

    assert (root / "allowed.txt").read_text(encoding="utf-8") == "worker result\n"
    assert (root / "preexisting.txt").read_text(encoding="utf-8") == "keep me\n"
    payload = result["receipt"]
    assert payload["changed_paths"] == ["allowed.txt"]
    assert payload["baseline_digest"] != payload["post_digest"]
    assert payload["patch_digest"] != f"sha256:{adapter.digest_text('')}"
    assert "worker result" not in receipt.read_text(encoding="utf-8")


def test_out_of_scope_execution_is_discarded_without_touching_clone(
    tmp_path: Path,
) -> None:
    root = real_clone_root(tmp_path)

    def start(argv, **_kwargs):
        execution_root = Path(argv[argv.index("-C") + 1])
        (execution_root / "forbidden.txt").write_text(
            "must not land\n", encoding="utf-8"
        )
        return FakeProcess(stdout=jsonl("done"))

    with pytest.raises(adapter.AdapterError, match="write_scope_violation"):
        adapter.run_worker(
            workspace_root=root,
            prompt=write_prompt("allowed.txt"),
            execute=True,
            popen_factory=start,
            codex_resolver=lambda: Path("/usr/local/bin/codex"),
            version_reader=lambda _binary: "codex-cli 0.147.0",
            group_probe=lambda _pid: False,
        )

    assert not (root / "forbidden.txt").exists()
    assert (
        subprocess.run(
            ["git", "-C", str(root), "status", "--short"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        == ""
    )


def test_execution_commit_or_ignored_write_is_discarded(
    tmp_path: Path,
) -> None:
    for case in ("commit", "ignored"):
        root = real_clone_root(tmp_path / case)
        baseline = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

        def start(argv, _case=case, **_kwargs):
            execution_root = Path(argv[argv.index("-C") + 1])
            if _case == "commit":
                (execution_root / "allowed.txt").write_text(
                    "commit\n", encoding="utf-8"
                )
                subprocess.run(
                    ["git", "-C", str(execution_root), "add", "allowed.txt"],
                    check=True,
                )
                subprocess.run(
                    [
                        "git",
                        "-C",
                        str(execution_root),
                        "-c",
                        "user.name=Worker",
                        "-c",
                        "user.email=worker@example.invalid",
                        "commit",
                        "-q",
                        "-m",
                        "must not land",
                    ],
                    check=True,
                )
            else:
                (execution_root / ".gitignore").write_text(
                    "ignored/\n", encoding="utf-8"
                )
                (execution_root / "ignored").mkdir()
                (execution_root / "ignored/secret.txt").write_text(
                    "ignored\n", encoding="utf-8"
                )
            return FakeProcess(stdout=jsonl("done"))

        with pytest.raises(
            adapter.AdapterError,
            match="worker_commit_forbidden|ignored_write_forbidden",
        ):
            adapter.run_worker(
                workspace_root=root,
                prompt=write_prompt("allowed.txt", ".gitignore"),
                execute=True,
                popen_factory=start,
                codex_resolver=lambda: Path("/usr/local/bin/codex"),
                version_reader=lambda _binary: "codex-cli 0.147.0",
                group_probe=lambda _pid: False,
            )

        assert (
            subprocess.run(
                ["git", "-C", str(root), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            == baseline
        )
        assert not (root / "allowed.txt").exists()
        assert not (root / "ignored").exists()


def test_receipt_publish_failure_rolls_back_applied_patch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = real_clone_root(tmp_path)
    receipt = tmp_path / "receipt.json"

    def start(argv, **_kwargs):
        execution_root = Path(argv[argv.index("-C") + 1])
        (execution_root / "allowed.txt").write_text("candidate\n", encoding="utf-8")
        return FakeProcess(stdout=jsonl("done"))

    monkeypatch.setattr(
        adapter,
        "_publish_receipt",
        lambda *_args: (_ for _ in ()).throw(OSError("publish failed")),
    )

    with pytest.raises(adapter.AdapterError, match="receipt_write_failed"):
        adapter.run_worker(
            workspace_root=root,
            prompt=write_prompt("allowed.txt"),
            execute=True,
            receipt_path=receipt,
            popen_factory=start,
            codex_resolver=lambda: Path("/usr/local/bin/codex"),
            version_reader=lambda _binary: "codex-cli 0.147.0",
            group_probe=lambda _pid: False,
        )

    assert not (root / "allowed.txt").exists()
    assert not receipt.exists()
    assert (
        subprocess.run(
            ["git", "-C", str(root), "status", "--short"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        == ""
    )


def test_delta_failure_removes_staged_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = real_clone_root(tmp_path)
    receipt = tmp_path / "receipt.json"
    monkeypatch.setattr(
        adapter,
        "_apply_delta",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            adapter.AdapterError("delta_apply_unconfirmed")
        ),
    )

    with pytest.raises(adapter.AdapterError, match="delta_apply_unconfirmed"):
        adapter.run_worker(
            workspace_root=root,
            prompt=write_prompt("allowed.txt"),
            execute=True,
            receipt_path=receipt,
            popen_factory=lambda *_args, **_kwargs: FakeProcess(stdout=jsonl("done")),
            codex_resolver=lambda: Path("/usr/local/bin/codex"),
            version_reader=lambda _binary: "codex-cli 0.147.0",
            group_probe=lambda _pid: False,
        )

    assert not receipt.exists()
    assert not list(tmp_path.glob(".receipt.json.*.tmp"))


def test_no_delta_rechecks_original_clone_before_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = real_clone_root(tmp_path)
    original_apply = adapter._apply_delta

    def mutate_then_apply(*args, **kwargs) -> None:
        (root / "README.md").write_text("concurrent\n", encoding="utf-8")
        original_apply(*args, **kwargs)

    monkeypatch.setattr(adapter, "_apply_delta", mutate_then_apply)

    with pytest.raises(
        adapter.AdapterError, match="workspace_changed_during_execution"
    ):
        adapter.run_worker(
            workspace_root=root,
            prompt=write_prompt("allowed.txt"),
            execute=True,
            popen_factory=lambda *_args, **_kwargs: FakeProcess(stdout=jsonl("done")),
            codex_resolver=lambda: Path("/usr/local/bin/codex"),
            version_reader=lambda _binary: "codex-cli 0.147.0",
            group_probe=lambda _pid: False,
        )

    assert (root / "README.md").read_text(encoding="utf-8") == "concurrent\n"


def test_same_path_concurrent_mutation_blocks_apply_without_overwrite(
    tmp_path: Path,
) -> None:
    root = real_clone_root(tmp_path)
    allowed = root / "README.md"

    def start(argv, **_kwargs):
        execution_root = Path(argv[argv.index("-C") + 1])
        (execution_root / "README.md").write_text("worker\n", encoding="utf-8")
        allowed.write_text("concurrent\n", encoding="utf-8")
        return FakeProcess(stdout=jsonl("done"))

    with pytest.raises(
        adapter.AdapterError, match="workspace_changed_during_execution"
    ):
        adapter.run_worker(
            workspace_root=root,
            prompt=write_prompt("README.md"),
            execute=True,
            popen_factory=start,
            codex_resolver=lambda: Path("/usr/local/bin/codex"),
            version_reader=lambda _binary: "codex-cli 0.147.0",
            group_probe=lambda _pid: False,
        )

    assert allowed.read_text(encoding="utf-8") == "concurrent\n"


def test_real_initialized_submodule_gitlink_change_is_rejected(
    tmp_path: Path,
) -> None:
    child = tmp_path / "child"
    child.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(child)], check=True)
    subprocess.run(
        ["git", "-C", str(child), "config", "user.name", "Child"], check=True
    )
    subprocess.run(
        ["git", "-C", str(child), "config", "user.email", "child@example.invalid"],
        check=True,
    )
    (child / "child.txt").write_text("one\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(child), "add", "child.txt"], check=True)
    subprocess.run(["git", "-C", str(child), "commit", "-q", "-m", "one"], check=True)
    root = real_clone_root(tmp_path / "parent")
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "-c",
            "protocol.file.allow=always",
            "submodule",
            "add",
            "-q",
            str(child),
            "vendor/child",
        ],
        check=True,
    )
    subprocess.run(["git", "-C", str(root), "commit", "-qam", "submodule"], check=True)

    def start(argv, **_kwargs):
        execution_root = Path(argv[argv.index("-C") + 1])
        (execution_root / "vendor/child").mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "-C", str(execution_root), "rm", "-q", "vendor/child"], check=True
        )
        return FakeProcess(stdout=jsonl("done"))

    with pytest.raises(adapter.AdapterError, match="worker_gitlink_forbidden"):
        adapter.run_worker(
            workspace_root=root,
            prompt=write_prompt("vendor/child"),
            execute=True,
            popen_factory=start,
            codex_resolver=lambda: Path("/usr/local/bin/codex"),
            version_reader=lambda _binary: "codex-cli 0.147.0",
            group_probe=lambda _pid: False,
        )

    assert subprocess.run(
        ["git", "-C", str(root), "ls-files", "-s", "vendor/child"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.startswith("160000 ")


def test_shared_workspace_root_has_direct_rejection_regression() -> None:
    with pytest.raises(adapter.AdapterError, match="workspace_not_independent_clone"):
        adapter.validate_workspace(Path.home() / "Workspace")
