"""Pure launchd planning and private atomic plist generation."""

from __future__ import annotations

import os
import plistlib
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class LaunchdPaths:
    home: Path
    executable: Path
    plist_path: Path
    log_directory: Path
    data_directory: Path

    @classmethod
    def for_home(cls, home: Path) -> LaunchdPaths:
        resolved = home.expanduser().resolve()
        return cls(
            home=resolved,
            executable=resolved / ".local/bin/omlxcd",
            plist_path=resolved / "Library/LaunchAgents/com.omlxc.daemon.plist",
            log_directory=resolved / "Library/Logs/omlxc",
            data_directory=resolved / "Library/Application Support/omlxc",
        )


@dataclass(frozen=True, slots=True)
class LaunchdPlan:
    paths: LaunchdPaths
    plist_bytes: bytes
    uninstall_preserves: tuple[Path, Path]


@dataclass(frozen=True, slots=True)
class LaunchdWriteResult:
    path: Path
    snapshot_path: Path | None


def build_launchd_plan(paths: LaunchdPaths) -> LaunchdPlan:
    payload: dict[str, object] = {
        "Label": "com.omlxc.daemon",
        "ProgramArguments": [str(paths.executable)],
        "RunAtLoad": True,
        "KeepAlive": True,
        "ProcessType": "Background",
        "StandardOutPath": str(paths.log_directory / "daemon.log"),
        "StandardErrorPath": str(paths.log_directory / "daemon-error.log"),
        "EnvironmentVariables": {
            "HOME": str(paths.home),
            "PATH": f"{paths.home}/.local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
        },
    }
    return LaunchdPlan(
        paths=paths,
        plist_bytes=plistlib.dumps(payload, fmt=plistlib.FMT_XML, sort_keys=True),
        uninstall_preserves=(paths.log_directory, paths.data_directory),
    )


def write_launchd_plist(plan: LaunchdPlan) -> LaunchdWriteResult:
    target = plan.paths.plist_path
    for directory in (plan.paths.log_directory, plan.paths.data_directory):
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(directory, 0o700, follow_symlinks=False)
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(target.parent, 0o700, follow_symlinks=False)
    snapshot_path: Path | None = None
    if target.is_symlink():
        raise RuntimeError("refusing launchd plist symlink")
    if target.exists():
        snapshot_path = target.with_name(f"{target.name}.snapshot")
        _atomic_write(snapshot_path, target.read_bytes())
    _atomic_write(target, plan.plist_bytes)
    return LaunchdWriteResult(path=target, snapshot_path=snapshot_path)


def _atomic_write(target: Path, payload: bytes) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    temporary_path = Path(temporary)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, target)
        os.chmod(target, 0o600, follow_symlinks=False)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise
