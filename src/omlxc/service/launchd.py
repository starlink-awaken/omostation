"""Pure launchd planning and private atomic plist generation."""

from __future__ import annotations

import os
import plistlib
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from uuid import uuid4

from omlxc.adapters.process import (
    BoundedProcessRunner,
    ProcessOutput,
    ProcessOutputLimitError,
    ProcessRunner,
    ProcessSpawnError,
)
from omlxc.config import (
    ConfigError,
    config_identity,
    load_config,
    require_private_config_path,
)

LAUNCHD_LABEL = "com.omlxc.daemon"
LAUNCHCTL = "/bin/launchctl"
LAUNCHCTL_TIMEOUT_SECONDS = 10.0
LAUNCHCTL_OUTPUT_LIMIT = 256 * 1024
LAUNCHCTL_PROCESS_ENV: Mapping[str, str] = MappingProxyType(
    {
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
        "LANG": "C",
        "LC_ALL": "C",
    }
)


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
    config_path: Path
    config_identity: str
    plist_bytes: bytes
    uninstall_preserves: tuple[Path, Path]


@dataclass(frozen=True, slots=True)
class LaunchdWriteResult:
    path: Path
    snapshot_path: Path | None


@dataclass(frozen=True, slots=True)
class LaunchdInstallResult:
    plist_path: Path
    snapshot_path: Path | None


@dataclass(frozen=True, slots=True)
class LaunchdUninstallResult:
    backup_path: Path | None
    preserved_paths: tuple[Path, Path]


class LaunchdFailure(RuntimeError):
    """Sanitized lifecycle failure with a stable public CLI code."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class LaunchdController:
    """Bounded, argv-only controller for the current macOS user domain."""

    def __init__(
        self,
        paths: LaunchdPaths,
        *,
        config_path: Path | None = None,
        uid: int | None = None,
        process_runner: ProcessRunner | None = None,
        timeout_seconds: float = LAUNCHCTL_TIMEOUT_SECONDS,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("launchctl timeout must be positive")
        self.paths = paths
        self._config_path = config_path
        self._uid = os.getuid() if uid is None else uid
        if self._uid < 0:
            raise ValueError("launchd uid must be non-negative")
        self._runner = process_runner or BoundedProcessRunner(
            LAUNCHCTL_OUTPUT_LIMIT,
            env=LAUNCHCTL_PROCESS_ENV,
        )
        self._timeout = timeout_seconds

    @property
    def domain(self) -> str:
        return f"gui/{self._uid}"

    @property
    def service_target(self) -> str:
        return f"{self.domain}/{LAUNCHD_LABEL}"

    async def install(self) -> LaunchdInstallResult:
        _require_private_executable(self.paths.executable)
        if self._config_path is None:
            raise LaunchdFailure("E100", "daemon configuration is required")
        written = write_launchd_plist(build_launchd_plan(self.paths, self._config_path))
        try:
            await self._run((LAUNCHCTL, "bootstrap", self.domain, str(written.path)))
        except BaseException:
            if written.snapshot_path is None:
                written.path.unlink(missing_ok=True)
            else:
                os.replace(written.snapshot_path, written.path)
            raise
        return LaunchdInstallResult(written.path, written.snapshot_path)

    async def uninstall(self) -> LaunchdUninstallResult:
        await self._run(
            (LAUNCHCTL, "bootout", self.service_target),
            allow_not_loaded=True,
        )
        backup = _backup_uninstalled_plist(self.paths.plist_path)
        return LaunchdUninstallResult(
            backup_path=backup,
            preserved_paths=(self.paths.log_directory, self.paths.data_directory),
        )

    async def status(self) -> ProcessOutput:
        return await self._run((LAUNCHCTL, "print", self.service_target), unavailable=True)

    async def start(self) -> ProcessOutput:
        return await self._run((LAUNCHCTL, "bootstrap", self.domain, str(self.paths.plist_path)))

    async def stop(self) -> ProcessOutput:
        return await self._run((LAUNCHCTL, "bootout", self.service_target))

    async def restart(self) -> ProcessOutput:
        return await self._run((LAUNCHCTL, "kickstart", "-k", self.service_target))

    async def _run(
        self,
        argv: tuple[str, ...],
        *,
        unavailable: bool = False,
        allow_not_loaded: bool = False,
    ) -> ProcessOutput:
        try:
            output = await self._runner(argv, self._timeout)
        except TimeoutError:
            raise LaunchdFailure("E305", "launchd operation timed out") from None
        except (ProcessSpawnError, OSError):
            raise LaunchdFailure("E200", "launchctl is unavailable") from None
        except ProcessOutputLimitError:
            raise LaunchdFailure("E900", "launchctl output exceeded its safety limit") from None
        if output.returncode != 0 and not (allow_not_loaded and _is_service_not_loaded(output)):
            code = "E200" if unavailable else "E500"
            raise LaunchdFailure(code, "launchd service is unavailable")
        return output


def build_launchd_plan(paths: LaunchdPaths, config_path: Path) -> LaunchdPlan:
    validated_config = _require_private_config(config_path)
    try:
        identity = config_identity(
            load_config(validated_config, env={}, base_directory=validated_config.parent)
        )
    except ConfigError:
        raise LaunchdFailure("E100", "daemon configuration is invalid") from None
    payload: dict[str, object] = {
        "Label": LAUNCHD_LABEL,
        "ProgramArguments": [str(paths.executable), "--config", str(validated_config)],
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
        config_path=validated_config,
        config_identity=identity,
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


def _require_private_executable(path: Path) -> None:
    try:
        metadata = path.lstat()
    except OSError:
        raise LaunchdFailure("E100", "fixed omlxcd entrypoint is not installed") from None
    if path.is_symlink() or not path.is_file() or metadata.st_uid != os.geteuid():
        raise LaunchdFailure("E700", "fixed omlxcd entrypoint is not trusted")
    if metadata.st_mode & 0o022 or metadata.st_mode & 0o111 == 0:
        raise LaunchdFailure("E700", "fixed omlxcd entrypoint is not trusted")


def _require_private_config(path: Path) -> Path:
    try:
        return require_private_config_path(path)
    except ConfigError as exc:
        code = "E100" if "unavailable" in str(exc) else "E700"
        raise LaunchdFailure(code, str(exc)) from None


def _backup_uninstalled_plist(target: Path) -> Path | None:
    if target.is_symlink():
        raise LaunchdFailure("E700", "refusing launchd plist symlink")
    if not target.exists():
        return None
    backup = target.with_name(f"{target.name}.uninstalled-{uuid4().hex[:12]}")
    os.replace(target, backup)
    os.chmod(backup, 0o600, follow_symlinks=False)
    return backup


def _is_service_not_loaded(output: ProcessOutput) -> bool:
    if output.returncode != 3:
        return False
    detail = f"{output.stdout}\n{output.stderr}".lower()
    return "no such process" in detail
