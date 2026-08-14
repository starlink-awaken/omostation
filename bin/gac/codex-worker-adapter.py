#!/usr/bin/env python3
"""Run Codex exec as a bounded supervised worker."""

# ruff: noqa: UP007, UP045 -- the adapter contract supports Python 3.9.

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import uuid
from collections.abc import Callable, Sequence
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Union

RECEIPT_SCHEMA = "codex-worker-execution/v1"
MIN_CODEX_VERSION = (0, 147, 0)
MAX_TIMEOUT_SECONDS = 3600
VERSION_RE = re.compile(r"^codex-cli (\d+)\.(\d+)\.(\d+)(?:[-+][0-9A-Za-z.-]+)?$")
SECRET_ENV_PARTS = (
    "TOKEN",
    "KEY",
    "SECRET",
    "PASSWORD",
    "CREDENTIAL",
    "PROXY",
    "SSH",
    "AWS",
    "GITHUB",
    "GITLAB",
)
FORBIDDEN_WRITE_PATHS = (
    ".git",
    ".omo/state/system.yaml",
    ".omo/goals/current.yaml",
    "convergence.yaml",
)
WRITE_PATH_RE = re.compile(r"^- You may write to `([^`]+)`$")
APPROVAL_EVENT_TYPES = {
    "apply_patch_approval_request",
    "exec_approval_request",
}
KNOWN_JSONL_EVENT_TYPES = {
    "error",
    "item.completed",
    "item.started",
    "item.updated",
    "message",
    "response.output_item.done",
    "thread.started",
    "turn.completed",
    "turn.failed",
    "turn.started",
}


class AdapterError(RuntimeError):
    """Expose only stable bounded-adapter failure codes."""

    def __init__(self, code: str, *, provider_review: str = "unknown") -> None:
        super().__init__(code)
        self.code = code
        self.provider_review = provider_review


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def receipt_digest(payload: dict[str, Any]) -> str:
    projected = {
        key: value for key, value in payload.items() if key != "receipt_sha256"
    }
    return digest_text(_canonical_json(projected))


def fixed_argv(
    binary: Union[Path, str], workspace_root: Union[Path, str], prompt: str
) -> list[str]:
    return [
        str(binary),
        "exec",
        "--approve-for-me",
        "--ephemeral",
        "--ignore-user-config",
        "--json",
        "--color",
        "never",
        "-C",
        str(workspace_root),
        prompt,
    ]


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _system_temp_roots() -> tuple[Path, ...]:
    candidates = (
        Path(tempfile.gettempdir()),
        Path("/tmp"),
        Path("/private/tmp"),
        Path("/private/var/folders"),
    )
    return tuple(dict.fromkeys(path.resolve() for path in candidates if path.exists()))


def validate_receipt_path(value: Union[Path, str]) -> Path:
    raw = Path(value).expanduser()
    try:
        receipt = raw.resolve(strict=False)
        parent = receipt.parent.resolve(strict=True)
    except OSError as exc:
        raise AdapterError("unsafe_receipt") from exc
    if (
        receipt.exists()
        or not parent.is_dir()
        or not any(_is_within(receipt, root) for root in _system_temp_roots())
    ):
        raise AdapterError("unsafe_receipt")
    return receipt


def validate_workspace(value: Union[Path, str]) -> Path:
    raw = Path(value).expanduser().absolute()
    try:
        if stat.S_ISLNK(os.lstat(raw).st_mode) or not raw.is_dir():
            raise AdapterError("workspace_not_independent_clone")
        root = raw.resolve(strict=True)
        shared_root = (Path.home() / "Workspace").resolve(strict=False)
        if _is_within(root, shared_root):
            raise AdapterError("workspace_not_independent_clone")
        git_dir = root / ".git"
        if not stat.S_ISDIR(os.lstat(git_dir).st_mode):
            raise AdapterError("workspace_not_independent_clone")
        identity = json.loads(
            (git_dir / "agent-clone-identity.json").read_text(encoding="utf-8")
        )
        canonical = Path(identity["canonical_root"]).expanduser().resolve(strict=True)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise AdapterError("workspace_not_independent_clone") from exc
    if (
        identity.get("schema") != "agent-clone-identity/v1"
        or identity.get("ready") is not True
        or canonical != root
    ):
        raise AdapterError("workspace_not_independent_clone")
    return root


def _default_codex_resolver() -> Optional[Path]:
    found = shutil.which("codex")
    if found is None:
        return None
    try:
        resolved = Path(found).resolve(strict=True)
        if not stat.S_ISREG(os.stat(resolved).st_mode):
            return None
    except OSError:
        return None
    return resolved


def _default_version_reader(binary: Path) -> str:
    try:
        completed = subprocess.run(
            [str(binary), "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
            env=_scrubbed_environment(),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AdapterError("codex_unavailable") from exc
    if completed.returncode != 0:
        raise AdapterError("codex_unavailable")
    return completed.stdout.strip()


def _validate_version(value: str) -> str:
    match = VERSION_RE.fullmatch(value)
    if match is None or tuple(int(part) for part in match.groups()) < MIN_CODEX_VERSION:
        raise AdapterError("codex_identity_invalid")
    return value


def _scrubbed_environment() -> dict[str, str]:
    return {
        name: value
        for name, value in os.environ.items()
        if not any(part in name.upper() for part in SECRET_ENV_PARTS)
        and name != "GIT_CONFIG_COUNT"
        and not name.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_"))
    }


def _final_assistant_message(stdout: str) -> str:
    final: Optional[str] = None
    if not stdout.strip():
        raise AdapterError("worker_output_invalid")
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise AdapterError("worker_output_invalid") from exc
        if not isinstance(event, dict):
            raise AdapterError("worker_output_invalid")
        if event.get("type") == "item.completed":
            item = event.get("item")
            if isinstance(item, dict) and item.get("type") in {
                "agent_message",
                "message",
            }:
                text = item.get("text")
                if isinstance(text, str) and text:
                    final = text
        elif event.get("type") in {"message", "response.output_item.done"}:
            message = event.get("message", event.get("item"))
            if isinstance(message, dict) and message.get("role") == "assistant":
                text = message.get("text")
                if isinstance(text, str) and text:
                    final = text
    if final is None:
        raise AdapterError("worker_output_invalid")
    return final


def _provider_review(stdout: str, *, timed_out: bool = False) -> str:
    approval_observed = False
    unknown_observed = False
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            unknown_observed = True
            continue
        if not isinstance(event, dict):
            unknown_observed = True
            continue
        event_type = event.get("type")
        if event_type in APPROVAL_EVENT_TYPES:
            approval_observed = True
        elif event_type not in KNOWN_JSONL_EVENT_TYPES:
            unknown_observed = True
    if approval_observed:
        return "human_required"
    if timed_out:
        return "timed_out"
    if unknown_observed:
        return "unknown"
    return "completed_without_observed_escalation"


def _timeout_output(exc: subprocess.TimeoutExpired) -> str:
    output = exc.output
    if isinstance(output, bytes):
        return output.decode("utf-8", errors="replace")
    return output if isinstance(output, str) else ""


def _run_git(
    root: Path,
    arguments: Sequence[str],
    *,
    input_bytes: bytes | None = None,
    timeout: int = 30,
) -> subprocess.CompletedProcess[bytes]:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), *arguments],
            check=False,
            capture_output=True,
            input=input_bytes,
            timeout=timeout,
            env=_scrubbed_environment(),
        )
    except subprocess.TimeoutExpired as exc:
        raise AdapterError("git_status_timeout") from exc
    except OSError as exc:
        raise AdapterError("git_status_failed") from exc
    if completed.returncode != 0:
        raise AdapterError("git_status_failed")
    return completed


def _default_changed_paths_reader(root: Path) -> list[str]:
    tracked = _run_git(
        root, ["diff", "--name-only", "-z", "--no-renames", "HEAD"]
    ).stdout
    untracked = _run_git(
        root, ["ls-files", "--others", "--exclude-standard", "-z"]
    ).stdout
    return sorted(
        {
            value.decode("utf-8", errors="strict")
            for value in (tracked + untracked).split(b"\0")
            if value
        }
    )


def _path_state(root: Path, relative: str) -> tuple[str, str]:
    path = root / relative
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return ("missing", "")
    except OSError as exc:
        raise AdapterError("delta_audit_failed") from exc
    if stat.S_ISLNK(metadata.st_mode):
        return ("symlink", os.readlink(path))
    if stat.S_ISREG(metadata.st_mode):
        digest = hashlib.sha256()
        try:
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
        except OSError as exc:
            raise AdapterError("delta_audit_failed") from exc
        return (f"file:{metadata.st_mode & 0o777:o}", digest.hexdigest())
    if stat.S_ISDIR(metadata.st_mode):
        try:
            head = _run_git(path, ["rev-parse", "HEAD"]).stdout
            status = _run_git(
                path, ["status", "--porcelain=v2", "-z", "--untracked-files=all"]
            ).stdout
        except AdapterError:
            return ("directory", "")
        return ("git-directory", digest_text((head + status).hex()))
    return (f"special:{stat.S_IFMT(metadata.st_mode)}", "")


def _workspace_fingerprint(
    root: Path,
    changed_paths_reader: Callable[[Path], list[str]],
) -> dict[str, Any]:
    head, branch = _git_identity(root)
    changed = changed_paths_reader(root)
    index = _run_git(root, ["write-tree"]).stdout.decode().strip()
    return {
        "branch": branch,
        "changed_paths": changed,
        "head": head,
        "index": index,
        "states": {path: _path_state(root, path) for path in changed},
    }


def _fingerprint_digest(fingerprint: dict[str, Any]) -> str:
    return f"sha256:{digest_text(_canonical_json(fingerprint))}"


def _patch_digest(patch: bytes) -> str:
    return f"sha256:{hashlib.sha256(patch).hexdigest()}"


def _expected_post_fingerprint(
    baseline_fingerprint: dict[str, Any],
    changed: Sequence[str],
    expected_worker_states: dict[str, tuple[str, str]],
) -> dict[str, Any]:
    expected_paths = sorted(set(baseline_fingerprint["changed_paths"]) | set(changed))
    expected_states = dict(baseline_fingerprint["states"])
    expected_states.update(expected_worker_states)
    return {
        **baseline_fingerprint,
        "changed_paths": expected_paths,
        "states": {path: expected_states[path] for path in expected_paths},
    }


def _git_identity(root: Path) -> tuple[str, str]:
    head = _run_git(root, ["rev-parse", "HEAD"]).stdout.decode().strip()
    branch = _run_git(root, ["symbolic-ref", "--quiet", "--short", "HEAD"])
    return head, branch.stdout.decode().strip()


def _parse_write_paths(prompt: str) -> list[str]:
    lines = prompt.splitlines()
    try:
        start = lines.index("## Constraints") + 1
    except ValueError as exc:
        raise AdapterError("prompt_contract_invalid") from exc
    allowed: list[str] = []
    no_writes = False
    for line in lines[start:]:
        if line.startswith("## "):
            break
        if line == "- No repository writes are permitted.":
            no_writes = True
            continue
        match = WRITE_PATH_RE.fullmatch(line)
        if match is None:
            continue
        raw = match.group(1)
        path = Path(raw)
        if (
            not raw
            or path.is_absolute()
            or ".." in path.parts
            or path.parts[0] == ".git"
        ):
            raise AdapterError("prompt_contract_invalid")
        normalized = path.as_posix().rstrip("/")
        if normalized in {"", "."}:
            raise AdapterError("prompt_contract_invalid")
        allowed.append(normalized + ("/" if raw.endswith("/") else ""))
    if no_writes and allowed:
        raise AdapterError("prompt_contract_invalid")
    if not no_writes and not allowed:
        raise AdapterError("prompt_contract_invalid")
    return list(dict.fromkeys(allowed))


def _tree_file_snapshot(root: Path) -> dict[str, tuple[int, int, int, str]]:
    snapshot: dict[str, tuple[int, int, int, str]] = {}
    for directory, names, files in os.walk(root, followlinks=False):
        relative_directory = Path(directory).relative_to(root)
        if relative_directory == Path(".") and ".git" in names:
            names.remove(".git")
        for name in [*names, *files]:
            path = Path(directory) / name
            relative = path.relative_to(root).as_posix()
            try:
                metadata = path.lstat()
            except OSError as exc:
                raise AdapterError("delta_audit_failed") from exc
            if stat.S_ISDIR(metadata.st_mode):
                continue
            target = os.readlink(path) if stat.S_ISLNK(metadata.st_mode) else ""
            snapshot[relative] = (
                stat.S_IFMT(metadata.st_mode),
                metadata.st_size,
                metadata.st_mtime_ns,
                target,
            )
    return snapshot


@contextmanager
def _execution_clone(root: Path):
    try:
        with tempfile.TemporaryDirectory(prefix="codex-worker-") as directory:
            execution_root = Path(directory) / "workspace"
            copied = subprocess.run(
                ["/bin/cp", "-cR", str(root), str(execution_root)],
                check=False,
                capture_output=True,
                timeout=120,
                env=_scrubbed_environment(),
            )
            if copied.returncode != 0:
                raise AdapterError("execution_clone_failed")
            yield execution_root
    except subprocess.TimeoutExpired as exc:
        raise AdapterError("execution_clone_failed") from exc


def _path_allowed(path: str, allowed: Sequence[str]) -> bool:
    if any(
        path == forbidden or path.startswith(f"{forbidden}/")
        for forbidden in FORBIDDEN_WRITE_PATHS
    ):
        return False
    return any(
        path == item.rstrip("/") or (item.endswith("/") and path.startswith(item))
        for item in allowed
    )


def _execution_delta(
    execution_root: Path,
    *,
    baseline_head: str,
    baseline_branch: str,
    pristine_snapshot: dict[str, tuple[int, int, int, str]],
    allowed: Sequence[str],
) -> tuple[list[str], bytes, dict[str, tuple[str, str]]]:
    if _git_identity(execution_root) != (baseline_head, baseline_branch):
        raise AdapterError("worker_commit_forbidden")
    _run_git(execution_root, ["add", "-A"])
    changed_raw = _run_git(
        execution_root,
        ["diff", "--cached", "--name-only", "-z", "--no-renames", "HEAD"],
    ).stdout
    changed = sorted(
        value.decode("utf-8", errors="strict")
        for value in changed_raw.split(b"\0")
        if value
    )
    for path in changed:
        head_mode = _run_git(execution_root, ["ls-tree", "HEAD", "--", path]).stdout
        index_mode = _run_git(execution_root, ["ls-files", "-s", "--", path]).stdout
        if head_mode.startswith(b"160000 ") or index_mode.startswith(b"160000 "):
            raise AdapterError("worker_gitlink_forbidden")
    current_snapshot = _tree_file_snapshot(execution_root)
    metadata_delta = {
        path
        for path in pristine_snapshot.keys() | current_snapshot.keys()
        if pristine_snapshot.get(path) != current_snapshot.get(path)
    }
    ignored_delta = metadata_delta - set(changed)
    ignored_delta -= {
        path for path in ignored_delta if Path(path).parts[0] in {".subtrees", ".venv"}
    }
    if ignored_delta:
        raise AdapterError("ignored_write_forbidden")
    for path in changed:
        if not _path_allowed(path, allowed):
            raise AdapterError("write_scope_violation")
        candidate = execution_root / path
        if candidate.is_symlink():
            raise AdapterError("worker_symlink_forbidden")
    patch = _run_git(
        execution_root, ["diff", "--cached", "--binary", "HEAD"], timeout=120
    ).stdout
    return changed, patch, {path: _path_state(execution_root, path) for path in changed}


def _prepare_execution_baseline(root: Path) -> tuple[str, str]:
    _run_git(root, ["add", "-A"])
    _run_git(
        root,
        [
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "user.name=OMO Codex Worker",
            "-c",
            "user.email=codex-worker@example.invalid",
            "commit",
            "--allow-empty",
            "--quiet",
            "-m",
            "ephemeral worker baseline",
        ],
        timeout=120,
    )
    return _git_identity(root)


def _apply_delta(
    root: Path,
    patch: bytes,
    *,
    baseline_fingerprint: dict[str, Any],
    changed: Sequence[str],
    expected_worker_states: dict[str, tuple[str, str]],
    changed_paths_reader: Callable[[Path], list[str]],
) -> None:
    if not patch:
        if _workspace_fingerprint(root, changed_paths_reader) != baseline_fingerprint:
            raise AdapterError("workspace_changed_during_execution")
        return
    _run_git(root, ["apply", "--check", "--whitespace=nowarn", "-"], input_bytes=patch)
    applied = False
    try:
        _run_git(root, ["apply", "--whitespace=nowarn", "-"], input_bytes=patch)
        applied = True
        expected = _expected_post_fingerprint(
            baseline_fingerprint, changed, expected_worker_states
        )
        if _workspace_fingerprint(root, changed_paths_reader) != expected:
            raise AdapterError("delta_apply_unconfirmed")
    except (AdapterError, OSError) as exc:
        if applied:
            try:
                _run_git(
                    root,
                    ["apply", "--reverse", "--check", "--whitespace=nowarn", "-"],
                    input_bytes=patch,
                )
                _run_git(
                    root,
                    ["apply", "--reverse", "--whitespace=nowarn", "-"],
                    input_bytes=patch,
                )
            except AdapterError as rollback_exc:
                raise AdapterError("rollback_unconfirmed") from rollback_exc
            if (
                _workspace_fingerprint(root, changed_paths_reader)
                != baseline_fingerprint
            ):
                raise AdapterError("rollback_unconfirmed") from exc
        if isinstance(exc, AdapterError):
            raise
        raise AdapterError("delta_apply_unconfirmed") from exc


def _default_group_terminator(pid: int, value: signal.Signals) -> None:
    try:
        os.killpg(pid, value)
    except ProcessLookupError:
        return


def _default_group_probe(pid: int) -> bool:
    try:
        os.killpg(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _terminate_surviving_group(
    pid: int,
    group_probe: Callable[[int], bool],
    group_terminator: Callable[[int, signal.Signals], None],
) -> bool:
    group_terminator(pid, signal.SIGTERM)
    if not group_probe(pid):
        return True
    group_terminator(pid, signal.SIGKILL)
    return not group_probe(pid)


def _terminate_timed_out_process(
    process: Any,
    group_probe: Callable[[int], bool],
    group_terminator: Callable[[int, signal.Signals], None],
) -> bool:
    group_terminator(process.pid, signal.SIGTERM)
    parent_reaped = False
    try:
        process.wait(timeout=2)
        parent_reaped = True
    except subprocess.TimeoutExpired:
        pass
    if not parent_reaped or group_probe(process.pid):
        group_terminator(process.pid, signal.SIGKILL)
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            return False
    return not group_probe(process.pid)


def _write_receipt(path: Path, payload: dict[str, Any]) -> None:
    with path.open("x", encoding="utf-8") as handle:
        handle.write(_canonical_json(payload) + "\n")


def _stage_receipt(path: Path, payload: dict[str, Any]) -> Path:
    staged = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
    try:
        _write_receipt(staged, payload)
    except OSError:
        staged.unlink(missing_ok=True)
        raise
    return staged


def _publish_receipt(staged: Path, destination: Path) -> None:
    os.link(staged, destination)
    staged.unlink(missing_ok=True)


def run_worker(
    *,
    workspace_root: Union[Path, str],
    prompt: str,
    execute: bool = False,
    expect_exact: Optional[str] = None,
    receipt_path: Optional[Union[Path, str]] = None,
    timeout_seconds: int = 900,
    popen_factory: Callable[..., Any] = subprocess.Popen,
    codex_resolver: Callable[[], Optional[Path]] = _default_codex_resolver,
    version_reader: Callable[[Path], str] = _default_version_reader,
    changed_paths_reader: Callable[[Path], list[str]] = _default_changed_paths_reader,
    group_probe: Callable[[int], bool] = _default_group_probe,
    group_terminator: Callable[[int, signal.Signals], None] = _default_group_terminator,
) -> dict[str, Any]:
    """Execute exactly one bounded Codex invocation."""
    if not execute:
        return {
            "command": fixed_argv("codex", Path(workspace_root), prompt),
            "mode": "dry-run",
        }
    if not 1 <= timeout_seconds <= MAX_TIMEOUT_SECONDS:
        raise AdapterError("worker_timeout")
    root = validate_workspace(workspace_root)
    receipt_file = (
        validate_receipt_path(receipt_path) if receipt_path is not None else None
    )
    binary = codex_resolver()
    if binary is None:
        raise AdapterError("codex_unavailable")
    version = _validate_version(version_reader(binary))
    allowed_write_paths = _parse_write_paths(prompt)
    baseline_fingerprint = _workspace_fingerprint(root, changed_paths_reader)
    started_at = _utc_now()
    with _execution_clone(root) as execution_root:
        execution_head, execution_branch = _prepare_execution_baseline(execution_root)
        pristine_snapshot = _tree_file_snapshot(execution_root)
        try:
            process = popen_factory(
                fixed_argv(binary, execution_root, prompt),
                cwd=str(execution_root),
                env=_scrubbed_environment(),
                shell=False,
                start_new_session=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except OSError as exc:
            raise AdapterError("codex_unavailable") from exc
        try:
            stdout, _stderr = process.communicate(timeout=timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            provider_review = _provider_review(_timeout_output(exc), timed_out=True)
            if not _terminate_timed_out_process(process, group_probe, group_terminator):
                raise AdapterError("cleanup_unconfirmed") from exc
            raise AdapterError(
                "worker_timeout", provider_review=provider_review
            ) from exc
        if group_probe(process.pid):
            if not _terminate_surviving_group(
                process.pid, group_probe, group_terminator
            ):
                raise AdapterError("cleanup_unconfirmed")
            raise AdapterError("process_leaked")
        if process.returncode != 0:
            raise AdapterError("worker_nonzero")
        output = _final_assistant_message(stdout)
        provider_review = _provider_review(stdout)
        if provider_review == "human_required":
            raise AdapterError(
                "human_approval_required", provider_review=provider_review
            )
        if expect_exact is not None and output != expect_exact:
            raise AdapterError("marker_mismatch")
        changed_paths, patch, worker_states = _execution_delta(
            execution_root,
            baseline_head=execution_head,
            baseline_branch=execution_branch,
            pristine_snapshot=pristine_snapshot,
            allowed=allowed_write_paths,
        )
        if _workspace_fingerprint(root, changed_paths_reader) != baseline_fingerprint:
            raise AdapterError("workspace_changed_during_execution")
    receipt: Optional[dict[str, Any]] = None
    staged_receipt: Path | None = None
    if receipt_file is not None:
        expected_post = _expected_post_fingerprint(
            baseline_fingerprint, changed_paths, worker_states
        )
        receipt = {
            "baseline_digest": _fingerprint_digest(baseline_fingerprint),
            "boundaries": {
                "approval": "approve-for-me",
                "config": "ignore-user-config",
                "ephemeral": True,
                "sandbox": "workspace-write",
            },
            "changed_paths": changed_paths,
            "codex_version": version,
            "completed_at": _utc_now(),
            "exit_code": process.returncode,
            "output_sha256": digest_text(output),
            "patch_digest": _patch_digest(patch),
            "post_digest": _fingerprint_digest(expected_post),
            "readiness": "model_output_observed",
            "schema": RECEIPT_SCHEMA,
            "started_at": started_at,
            "status": "succeeded",
            "supervision": {
                "controller_approval": "granted",
                "provider_review": provider_review,
            },
            "worker": "codex",
        }
        receipt["receipt_sha256"] = receipt_digest(receipt)
        try:
            staged_receipt = _stage_receipt(receipt_file, receipt)
        except OSError as exc:
            raise AdapterError("receipt_write_failed") from exc
    try:
        _apply_delta(
            root,
            patch,
            baseline_fingerprint=baseline_fingerprint,
            changed=changed_paths,
            expected_worker_states=worker_states,
            changed_paths_reader=changed_paths_reader,
        )
        if receipt_file is not None and staged_receipt is not None:
            try:
                _publish_receipt(staged_receipt, receipt_file)
            except OSError as exc:
                if patch:
                    try:
                        _run_git(
                            root,
                            [
                                "apply",
                                "--reverse",
                                "--check",
                                "--whitespace=nowarn",
                                "-",
                            ],
                            input_bytes=patch,
                        )
                        _run_git(
                            root,
                            ["apply", "--reverse", "--whitespace=nowarn", "-"],
                            input_bytes=patch,
                        )
                    except AdapterError as rollback_exc:
                        raise AdapterError("rollback_unconfirmed") from rollback_exc
                if (
                    _workspace_fingerprint(root, changed_paths_reader)
                    != baseline_fingerprint
                ):
                    raise AdapterError("rollback_unconfirmed") from exc
                raise AdapterError("receipt_write_failed") from exc
    finally:
        if staged_receipt is not None:
            staged_receipt.unlink(missing_ok=True)
    return {"output": output, "receipt": receipt}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="dry-run by default")
    run.add_argument("--execute", action="store_true")
    run.add_argument("--workspace-root", required=True)
    run.add_argument("--prompt", required=True)
    run.add_argument("--expect-exact")
    run.add_argument("--receipt")
    run.add_argument("--timeout-seconds", type=int, default=900)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run_worker(
            workspace_root=args.workspace_root,
            prompt=args.prompt,
            execute=args.execute,
            expect_exact=args.expect_exact,
            receipt_path=args.receipt,
            timeout_seconds=args.timeout_seconds,
        )
    except AdapterError as exc:
        print(
            _canonical_json(
                {
                    "error_code": exc.code,
                    "provider_review": exc.provider_review,
                    "status": "failed",
                }
            ),
            file=sys.stderr,
        )
        return 2
    if args.execute:
        sys.stdout.write(result["output"])
    else:
        print(_canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
