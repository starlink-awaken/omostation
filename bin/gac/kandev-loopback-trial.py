#!/usr/bin/env python3
"""Run a deliberately narrow, loopback-only Kandev Phase-0 smoke trial.

This is a control-plane lifecycle check, not a Kandev task runner.  It never
creates tasks, invokes an agent/model, configures MCP, or writes a workspace.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import urllib.request
import uuid
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$")
DEFAULT_TIMEOUT_SECONDS = 300.0
MAX_TIMEOUT_SECONDS = 600.0
CLEANUP_GRACE_SECONDS = 15.0
MAX_CLEANUP_GRACE_SECONDS = 60.0


class TrialError(RuntimeError):
    """A safe, user-actionable rejection of the bounded trial."""


def validate_package_version(version: str) -> str:
    """Accept only an exact npm package version; aliases and ranges are unsafe."""
    if not VERSION_RE.fullmatch(version):
        raise TrialError("package version must be an exact pinned semver, never latest or a range")
    return version


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def validate_trial_home(home: Path | str, *, workspace_root: Path | str, user_home: Path | str) -> Path:
    """Require a caller-created, empty, isolated directory outside user/workspace state."""
    resolved = Path(home).expanduser().resolve()
    workspace = Path(workspace_root).expanduser().resolve()
    user = Path(user_home).expanduser().resolve()
    if not resolved.exists() or not resolved.is_dir():
        raise TrialError("trial home must be an explicit existing directory")
    if _is_within(resolved, workspace) or _is_within(resolved, user):
        raise TrialError("trial home must be outside the Workspace and user home")
    if any(resolved.iterdir()):
        raise TrialError("trial home must be empty before a smoke trial")
    return resolved


def build_command(package_version: str, port: int) -> list[str]:
    """Construct an argv-only command; shell interpolation is never allowed."""
    validate_package_version(package_version)
    if not 1 <= port <= 65535:
        raise TrialError("port must be in the range 1..65535")
    return ["npx", "-y", f"kandev@{package_version}", "--headless", "--port", str(port)]


def resolve_npx() -> str:
    """Resolve the only external executable before constructing a child PATH."""
    candidate = shutil.which("npx")
    if not candidate:
        raise TrialError("npx is unavailable; refusing to search an inherited PATH")
    resolved = Path(candidate).absolute()
    if not resolved.is_file() or not os.access(resolved, os.X_OK):
        raise TrialError("resolved npx is not executable")
    return str(resolved)


def _controlled_path(npx_path: str) -> str:
    """Keep the executable directory and system paths, never a user-agent PATH."""
    paths = [str(Path(npx_path).absolute().parent), "/usr/bin", "/bin", "/usr/sbin", "/sbin", "/opt/homebrew/bin"]
    return ":".join(dict.fromkeys(paths))


def assert_loopback_listener(listener_output: str, port: int) -> None:
    """Reject wildcard and non-loopback listeners from a deliberately small parser."""
    marker = f":{port}"
    lines = [line.strip() for line in listener_output.splitlines() if marker in line]
    if not lines:
        raise TrialError("listener probe found no listener on the requested port")
    for line in lines:
        lowered = line.lower()
        if f"127.0.0.1:{port}" in lowered or f"[::1]:{port}" in lowered:
            continue
        raise TrialError("listener is not bound exclusively to loopback")


def _default_health_probe(
    port: int,
    opener_factory: Callable[..., Any] = urllib.request.build_opener,
) -> bool:
    """Probe loopback directly; do not consult parent proxy configuration."""
    try:
        opener = opener_factory(urllib.request.ProxyHandler({}))
        with opener.open(f"http://127.0.0.1:{port}/health", timeout=1.0) as response:
            return 200 <= response.status < 400
    except OSError:
        return False


def _default_listener_probe(port: int) -> str:
    try:
        completed = subprocess.run(
            ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise TrialError("listener probe unavailable; refusing to trust the trial") from exc
    return completed.stdout


def _listener_released(port: int) -> bool:
    return f":{port}" not in _default_listener_probe(port)


def _default_process_tree_probe() -> str:
    """Return the complete local PID/PPID/PGID table without invoking a shell."""
    try:
        completed = subprocess.run(
            ["ps", "-axo", "pid=,ppid=,pgid=,stat="],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise TrialError("process-tree probe unavailable; refusing to trust cleanup") from exc
    return completed.stdout


def _default_marker_probe(marker: str) -> dict[int, tuple[int, int]]:
    """Find only processes bearing this exact trial marker; never persist ps output."""
    try:
        completed = subprocess.run(
            ["ps", "eww", "-axo", "pid=,ppid=,pgid=,command="],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise TrialError("marker probe unavailable; refusing to trust cleanup") from exc
    found: dict[int, tuple[int, int]] = {}
    token = re.compile(rf"(?<!\S){re.escape(marker)}(?!\S)")
    for line in completed.stdout.splitlines():
        fields = line.split(maxsplit=3)
        if len(fields) != 4 or not all(field.isdigit() for field in fields[:3]) or not token.search(fields[3]):
            continue
        found[int(fields[0])] = (int(fields[1]), int(fields[2]))
    return found


def _parse_process_tree(output: str) -> dict[int, tuple[int, int]]:
    tree: dict[int, tuple[int, int]] = {}
    for line in output.splitlines():
        fields = line.split()
        if len(fields) not in (3, 4) or not all(field.isdigit() for field in fields[:3]):
            continue
        if len(fields) == 4 and fields[3].startswith("Z"):
            continue
        pid, parent, group = (int(field) for field in fields[:3])
        tree[pid] = (parent, group)
    return tree


def _owned_processes(root_pid: int, output: str) -> dict[int, tuple[int, int]]:
    """Return only the launcher and descendants visible in a single snapshot."""
    tree = _parse_process_tree(output)
    owned = {root_pid} if root_pid in tree else set()
    changed = True
    while changed:
        changed = False
        for pid, (parent, _group) in tree.items():
            if parent in owned and pid not in owned:
                owned.add(pid)
                changed = True
    return {pid: tree[pid] for pid in owned}


def _minimal_environment(home: Path, npx_path: str, trial_marker: str) -> dict[str, str]:
    """Build an allowlisted child environment; credentials never cross the boundary."""
    cache = home / ".npm-cache"
    config = home / ".xdg-config"
    runtime_tmp = home / ".tmp"
    xdg_cache = home / ".xdg-cache"
    for directory in (cache, config, runtime_tmp, xdg_cache):
        directory.mkdir(mode=0o700, exist_ok=True)
    locale = os.environ.get("LC_ALL") or os.environ.get("LANG") or "C.UTF-8"
    return {
        "HOME": str(home),
        "KANDEV_HOME_DIR": str(home),
        "KANDEV_NO_BROWSER": "1",
        "KANDEV_SERVER_HOST": "127.0.0.1",
        "OMO_KANDEV_TRIAL_ID": trial_marker.removeprefix("OMO_KANDEV_TRIAL_ID="),
        "LANG": locale,
        "NPM_CONFIG_CACHE": str(cache),
        "NPM_CONFIG_AUDIT": "false",
        "NPM_CONFIG_FUND": "false",
        "NPM_CONFIG_UPDATE_NOTIFIER": "false",
        "NPM_CONFIG_USERCONFIG": str(home / ".npmrc"),
        "PATH": _controlled_path(npx_path),
        "TMPDIR": str(runtime_tmp),
        "XDG_CACHE_HOME": str(xdg_cache),
        "XDG_CONFIG_HOME": str(config),
    }


def validate_receipt_path(
    receipt_path: Path | str, *, workspace_root: Path | str, user_home: Path | str, trial_home: Path | str
) -> Path:
    """Keep receipts out of mutable workspace, user config, and trial state."""
    receipt = Path(receipt_path).expanduser().resolve()
    workspace = Path(workspace_root).expanduser().resolve()
    user = Path(user_home).expanduser().resolve()
    home = Path(trial_home).expanduser().resolve()
    safe_tmp = Path(tempfile.gettempdir()).resolve()
    if (
        _is_within(receipt, workspace)
        or _is_within(receipt, user)
        or _is_within(receipt, home)
        or not _is_within(receipt, safe_tmp)
        or not receipt.parent.is_dir()
        or receipt.exists()
    ):
        raise TrialError("receipt path must be outside Workspace, user home, and trial home")
    return receipt


def _default_group_terminator(group_id: int, value: signal.Signals) -> None:
    """Signal one owned process group; callers first derive it from a tree snapshot."""
    try:
        os.killpg(group_id, value)
    except ProcessLookupError:
        return


def _default_listener_owner_probe(listener_output: str, owned: dict[int, tuple[int, int]]) -> bool:
    """Require lsof's listener PID to be in the launcher's captured descendant snapshot."""
    for line in listener_output.splitlines()[1:]:  # first line is lsof's header
        fields = line.split()
        if len(fields) < 2 or not fields[1].isdigit():
            continue
        if int(fields[1]) in owned:
            return True
    return False


def _wait_for_owned_exit(
    owned_pids: set[int],
    process_tree_probe: Callable[[], str],
    *,
    monotonic: Callable[[], float],
    sleeper: Callable[[float], None],
    timeout_seconds: float,
) -> bool:
    deadline = monotonic() + timeout_seconds
    while True:
        live = set(_parse_process_tree(process_tree_probe())).intersection(owned_pids)
        if not live:
            return True
        if monotonic() >= deadline:
            return False
        sleeper(0.05)


def _reap(
    process: Any,
    group_terminator: Callable[[int, signal.Signals], None],
    process_tree_probe: Callable[[], str] = _default_process_tree_probe,
    *,
    owned_snapshot: dict[int, tuple[int, int]] | None = None,
    trial_marker: str | None = None,
    marker_probe: Callable[[str], dict[int, tuple[int, int]]] = _default_marker_probe,
    monotonic: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
    timeout_seconds: float = 15.0,
) -> bool:
    """Reap root first, then prove every captured descendant was removed."""
    if process is None:
        return True
    try:
        owned = dict(owned_snapshot or _owned_processes(process.pid, process_tree_probe()))
        if trial_marker:
            owned.update(marker_probe(trial_marker))
        # A missing root means it is already gone; never broaden this to
        # arbitrary groups.  The normal path snapshots root+all descendants.
        if not owned:
            return False
        root_group = owned.get(process.pid, (0, 0))[1]
        groups = sorted({group for _parent, group in owned.values() if group != root_group})
        if root_group:
            groups.append(root_group)
        for group in groups:
            group_terminator(group, signal.SIGTERM)
        if root_group:
            try:
                process.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                group_terminator(root_group, signal.SIGKILL)
                process.wait(timeout=timeout_seconds)
        descendants = set(owned).difference({process.pid})
        if _wait_for_owned_exit(
            descendants, process_tree_probe, monotonic=monotonic, sleeper=sleeper, timeout_seconds=timeout_seconds
        ) and not (trial_marker and marker_probe(trial_marker)):
            return True
        for group in groups:
            group_terminator(group, signal.SIGKILL)
        return _wait_for_owned_exit(
            descendants, process_tree_probe, monotonic=monotonic, sleeper=sleeper, timeout_seconds=timeout_seconds
        ) and not (trial_marker and marker_probe(trial_marker))
    except (OSError, TrialError, subprocess.SubprocessError):
        return False


def _home_digest(home: Path) -> str:
    return hashlib.sha256(str(home).encode("utf-8")).hexdigest()


def _write_receipt(path: Path, receipt: dict[str, Any]) -> None:
    path.write_text(json.dumps(receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")


def _failure_code(error: BaseException) -> str:
    message = str(error).lower()
    if "health" in message or "timed out" in message:
        return "health_unavailable"
    if "listener" in message:
        return "listener_rejected"
    if "home" in message:
        return "home_rejected"
    if "version" in message:
        return "version_rejected"
    return "trial_failed"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _merge_owned_snapshot(
    snapshot: dict[int, tuple[int, int]], root_pid: int, process_tree_probe: Callable[[], str], trial_marker: str,
    marker_probe: Callable[[str], dict[int, tuple[int, int]]],
) -> None:
    snapshot.update(_owned_processes(root_pid, process_tree_probe()))
    snapshot.update(marker_probe(trial_marker))


def run_smoke(
    *,
    package_version: str,
    home: Path | str,
    port: int,
    receipt_path: Path | str,
    workspace_root: Path | str,
    user_home: Path | str,
    startup_timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    cleanup_timeout_seconds: float = CLEANUP_GRACE_SECONDS,
    popen_factory: Callable[..., Any] = subprocess.Popen,
    health_probe: Callable[[int], bool] = _default_health_probe,
    listener_probe: Callable[[int], str] = _default_listener_probe,
    listener_released_probe: Callable[[int], bool] = _listener_released,
    group_terminator: Callable[[int, signal.Signals], None] = _default_group_terminator,
    listener_owner_probe: Callable[[str, Any], bool] = _default_listener_owner_probe,
    process_tree_probe: Callable[[], str] = _default_process_tree_probe,
    monotonic: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
    npx_resolver: Callable[[], str] = resolve_npx,
    marker_factory: Callable[[], str] = lambda: str(uuid.uuid4()),
    marker_probe: Callable[[str], dict[int, tuple[int, int]]] = _default_marker_probe,
) -> dict[str, Any]:
    """Execute one bounded lifecycle test and always write a redacted receipt."""
    if not 0 < startup_timeout_seconds <= MAX_TIMEOUT_SECONDS:
        raise TrialError(f"startup timeout must be greater than zero and at most {int(MAX_TIMEOUT_SECONDS)} seconds")
    if not 0 < cleanup_timeout_seconds <= MAX_CLEANUP_GRACE_SECONDS:
        raise TrialError(f"cleanup timeout must be greater than zero and at most {int(MAX_CLEANUP_GRACE_SECONDS)} seconds")

    receipt_file: Path | None = None
    process: Any | None = None
    owned_snapshot: dict[int, tuple[int, int]] | None = None
    trial_home: Path | None = None
    error: TrialError | None = None
    trial_marker = f"OMO_KANDEV_TRIAL_ID={marker_factory()}"
    started_at = _utc_now()
    started_monotonic = monotonic()
    receipt: dict[str, Any] = {
        "assertions": {
            "agent_spawned": False,
            "model_called": False,
            "task_created": False,
            "workspace_written": False,
        },
        "checks": {
            "child_reaped": False,
            "health": False,
            "listener_loopback": False,
            "listener_released": False,
            "owned_processes_released": False,
        },
        "control_plane": {"headless": True, "host": "127.0.0.1", "port": port},
        "home_digest": "unavailable",
        "outcome": "failed",
        "package": {"name": "kandev", "version": package_version},
        "schema_version": 1,
        "started_at": started_at,
    }

    try:
        version = validate_package_version(package_version)
        command = build_command(version, port)
        npx_path = npx_resolver()
        command[0] = npx_path
        trial_home = validate_trial_home(home, workspace_root=workspace_root, user_home=user_home)
        receipt_file = validate_receipt_path(
            receipt_path, workspace_root=workspace_root, user_home=user_home, trial_home=trial_home
        )
        receipt["home_digest"] = _home_digest(trial_home)
        if listener_probe(port).strip():
            raise TrialError("listener already active before trial startup")
        environment = _minimal_environment(trial_home, npx_path, trial_marker)
        try:
            process = popen_factory(
                command,
                cwd=str(trial_home),
                env=environment,
                shell=False,
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            owned_snapshot = {}
            _merge_owned_snapshot(owned_snapshot, process.pid, process_tree_probe, trial_marker, marker_probe)
        except OSError as exc:
            raise TrialError("trial process failed to start") from exc

        deadline = monotonic() + startup_timeout_seconds
        while True:
            # Preserve the last trustworthy descendant set even if the
            # launcher exits after it has moved the backend to another PGID.
            _merge_owned_snapshot(owned_snapshot, process.pid, process_tree_probe, trial_marker, marker_probe)
            if health_probe(port):
                receipt["checks"]["health"] = True
                break
            if process.poll() is not None:
                raise TrialError("trial process exited before health became ready")
            if monotonic() >= deadline:
                raise TrialError("health check timed out")
            sleeper(0.1)
        listener_output = listener_probe(port)
        assert_loopback_listener(listener_output, port)
        _merge_owned_snapshot(owned_snapshot, process.pid, process_tree_probe, trial_marker, marker_probe)
        if not listener_owner_probe(listener_output, owned_snapshot):
            raise TrialError("listener does not belong to this trial process group")
        receipt["checks"]["listener_loopback"] = True
        receipt["outcome"] = "succeeded"
    except TrialError as exc:
        error = exc
    except Exception as exc:  # noqa: BLE001 - fail closed without persisting dependency error text
        error = TrialError("trial execution failed")
        error.__cause__ = exc
    finally:
        receipt["checks"]["child_reaped"] = _reap(
            process,
            group_terminator,
            process_tree_probe,
            owned_snapshot=owned_snapshot,
            trial_marker=trial_marker,
            marker_probe=marker_probe,
            monotonic=monotonic,
            sleeper=sleeper,
            timeout_seconds=cleanup_timeout_seconds,
        )
        receipt["checks"]["owned_processes_released"] = receipt["checks"]["child_reaped"]
        if receipt["checks"]["child_reaped"]:
            try:
                receipt["checks"]["listener_released"] = listener_released_probe(port)
            except (OSError, TrialError, subprocess.SubprocessError):
                receipt["checks"]["listener_released"] = False
        if not receipt["checks"]["listener_released"]:
            receipt["checks"]["child_reaped"] = False
            receipt["checks"]["owned_processes_released"] = False
            if error is None:
                error = TrialError("listener remained active after cleanup")
            receipt["outcome"] = "failed"
        if not receipt["checks"]["listener_released"]:
            receipt["failure_code"] = "cleanup_unconfirmed"
        elif error is not None:
            receipt["failure_code"] = _failure_code(error)
        receipt["completed_at"] = _utc_now()
        receipt["duration_seconds"] = round(max(0.0, monotonic() - started_monotonic), 3)
        # A rejected receipt destination must never become a write into a
        # workspace/user directory merely because cleanup entered ``finally``.
        if receipt_file is not None:
            _write_receipt(receipt_file, receipt)

    if error is not None:
        raise error
    return receipt


def _plan(args: argparse.Namespace) -> dict[str, Any]:
    home = validate_trial_home(args.home, workspace_root=args.workspace_root, user_home=args.user_home)
    command = build_command(args.package_version, args.port)
    command[0] = resolve_npx()
    return {
        "assertions": {"agent_spawned": False, "model_called": False, "task_created": False, "workspace_written": False},
        "command": command,
        "home_digest": _home_digest(home),
        "mode": "dry-run",
        "required_environment": {
            "KANDEV_HOME_DIR": "<isolated-home>",
            "KANDEV_NO_BROWSER": "1",
            "KANDEV_SERVER_HOST": "127.0.0.1",
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    command = parser.add_subparsers(dest="command", required=True)
    smoke = command.add_parser("run-smoke", help="print a plan unless --execute is explicitly supplied")
    smoke.add_argument("--execute", action="store_true", help="start the isolated, bounded local smoke trial")
    smoke.add_argument("--package-version", required=True, help="exact Kandev npm version; latest/ranges are rejected")
    smoke.add_argument("--home", required=True, help="empty, explicit directory outside Workspace and user home")
    smoke.add_argument("--port", required=True, type=int, help="local trial port")
    smoke.add_argument("--receipt", help="required with --execute; canonical redacted JSON output path")
    smoke.add_argument("--workspace-root", default=Path.cwd(), help=argparse.SUPPRESS)
    smoke.add_argument("--user-home", default=Path.home(), help=argparse.SUPPRESS)
    smoke.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    smoke.add_argument("--cleanup-timeout-seconds", type=float, default=CLEANUP_GRACE_SECONDS)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if not args.execute:
            print(json.dumps(_plan(args), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            return 0
        if not args.receipt:
            raise TrialError("--receipt is required with --execute")
        result = run_smoke(
            package_version=args.package_version,
            home=args.home,
            port=args.port,
            receipt_path=args.receipt,
            workspace_root=args.workspace_root,
            user_home=args.user_home,
            startup_timeout_seconds=args.timeout_seconds,
            cleanup_timeout_seconds=args.cleanup_timeout_seconds,
        )
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 0
    except TrialError as exc:
        print(f"kandev trial rejected: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
