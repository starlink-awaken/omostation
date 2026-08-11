"""Private, recoverable TOML serialization and atomic persistence."""

from __future__ import annotations

import json
import os
import stat
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import tomlkit

from .schema import AppConfig

WriteFunction = Callable[[int, bytes], int]
ReplaceFunction = Callable[[str, str], None]
ChmodFunction = Callable[[str, int], None]
DirectoryFsyncFunction = Callable[[Path], None]


class AtomicWriteError(OSError):
    """Raised when an atomic write fails without damaging the target."""

    def __init__(self, stage: str, cause: OSError) -> None:
        super().__init__(f"atomic write failed during {stage}")
        self.stage = stage
        self.cause = cause


class AtomicRollbackError(AtomicWriteError):
    """Raised when both the write transaction and its rollback fail."""

    def __init__(
        self,
        *,
        operation_stage: str,
        operation_error: OSError,
        rollback_stage: str,
        rollback_error: OSError,
    ) -> None:
        super().__init__(operation_stage, operation_error)
        self.args = (
            f"atomic write failed during {operation_stage}; "
            f"rollback failed during {rollback_stage}",
        )
        self.operation_stage = operation_stage
        self.operation_error = operation_error
        self.rollback_stage = rollback_stage
        self.rollback_error = rollback_error


@dataclass(frozen=True, slots=True)
class AtomicWriteResult:
    target_path: Path
    snapshot_path: Path | None


def render_toml(config: AppConfig) -> str:
    payload = config.model_dump(mode="json", exclude_none=True)
    legacy_extensions = payload.pop("legacy_extensions", {})
    if legacy_extensions:
        payload["legacy_extensions_json"] = json.dumps(
            legacy_extensions,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    return tomlkit.dumps(payload)


def write_config_atomic(
    target: Path,
    content: str,
    *,
    write: WriteFunction = os.write,
    replace: ReplaceFunction = os.replace,
    chmod: ChmodFunction = os.chmod,
    fsync_directory: DirectoryFsyncFunction | None = None,
) -> AtomicWriteResult:
    target = target.expanduser()
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory_sync = fsync_directory or _fsync_directory
    original_exists = target.exists()
    original_mode = stat.S_IMODE(target.stat().st_mode) if original_exists else None
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
    )
    temporary_path = Path(temporary_name)
    snapshot_path: Path | None = None
    stage = "chmod"
    replace_started = False
    try:
        chmod(str(temporary_path), 0o600)
        stage = "write"
        _write_all(file_descriptor, content.encode("utf-8"), write)
        stage = "file_fsync"
        os.fsync(file_descriptor)
        os.close(file_descriptor)
        file_descriptor = -1
        if original_exists:
            stage = "snapshot"
            snapshot_path = _write_snapshot(target, write)
        stage = "replace"
        replace_started = True
        replace(str(temporary_path), str(target))
        stage = "directory_fsync"
        directory_sync(target.parent)
        return AtomicWriteResult(target_path=target, snapshot_path=snapshot_path)
    except OSError as operation_error:
        if replace_started and not _target_matches_original(
            target,
            snapshot_path=snapshot_path,
            original_exists=original_exists,
            original_mode=original_mode,
        ):
            try:
                _rollback_target(
                    target,
                    snapshot_path=snapshot_path,
                    original_exists=original_exists,
                    original_mode=original_mode,
                    write=write,
                    replace=replace,
                    fsync_directory=directory_sync,
                )
            except _RollbackFailure as rollback_failure:
                raise AtomicRollbackError(
                    operation_stage=stage,
                    operation_error=operation_error,
                    rollback_stage=rollback_failure.stage,
                    rollback_error=rollback_failure.cause,
                ) from rollback_failure.cause
        raise AtomicWriteError(stage, operation_error) from operation_error
    finally:
        if file_descriptor >= 0:
            os.close(file_descriptor)
        temporary_path.unlink(missing_ok=True)


def _write_all(file_descriptor: int, payload: bytes, write: WriteFunction) -> None:
    position = 0
    while position < len(payload):
        written = write(file_descriptor, payload[position:])
        if written <= 0:
            raise OSError("write returned no progress")
        position += written


def _write_snapshot(target: Path, write: WriteFunction) -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    snapshot = target.with_name(f"{target.name}.snapshot-{timestamp}-{uuid4().hex[:8]}")
    descriptor = os.open(snapshot, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        _write_all(descriptor, target.read_bytes(), write)
        os.fsync(descriptor)
    except OSError:
        snapshot.unlink(missing_ok=True)
        raise
    finally:
        os.close(descriptor)
    return snapshot


class _RollbackFailure(Exception):
    def __init__(self, stage: str, cause: OSError) -> None:
        super().__init__(stage)
        self.stage = stage
        self.cause = cause


def _target_matches_original(
    target: Path,
    *,
    snapshot_path: Path | None,
    original_exists: bool,
    original_mode: int | None,
) -> bool:
    if not original_exists:
        return not target.exists()
    if snapshot_path is None or original_mode is None or not target.exists():
        return False
    try:
        return (
            target.read_bytes() == snapshot_path.read_bytes()
            and stat.S_IMODE(target.stat().st_mode) == original_mode
        )
    except OSError:
        return False


def _rollback_target(
    target: Path,
    *,
    snapshot_path: Path | None,
    original_exists: bool,
    original_mode: int | None,
    write: WriteFunction,
    replace: ReplaceFunction,
    fsync_directory: DirectoryFsyncFunction,
) -> None:
    if not original_exists:
        try:
            target.unlink(missing_ok=True)
        except OSError as exc:
            raise _RollbackFailure("unlink", exc) from exc
        try:
            fsync_directory(target.parent)
        except OSError as exc:
            raise _RollbackFailure("directory_fsync", exc) from exc
        return
    if snapshot_path is None or original_mode is None:
        raise _RollbackFailure("prepare", OSError("durable snapshot unavailable"))

    rollback_descriptor, rollback_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".rollback", dir=target.parent
    )
    rollback_path = Path(rollback_name)
    stage = "chmod"
    try:
        os.fchmod(rollback_descriptor, original_mode)
        stage = "write"
        _write_all(rollback_descriptor, snapshot_path.read_bytes(), write)
        stage = "file_fsync"
        os.fsync(rollback_descriptor)
        os.close(rollback_descriptor)
        rollback_descriptor = -1
        stage = "replace"
        replace(str(rollback_path), str(target))
        stage = "directory_fsync"
        fsync_directory(target.parent)
    except OSError as exc:
        raise _RollbackFailure(stage, exc) from exc
    finally:
        if rollback_descriptor >= 0:
            os.close(rollback_descriptor)
        rollback_path.unlink(missing_ok=True)


def _fsync_directory(directory: Path) -> None:
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
