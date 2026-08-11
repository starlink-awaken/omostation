"""Private, recoverable TOML serialization and atomic persistence."""

from __future__ import annotations

import os
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


class AtomicWriteError(OSError):
    """Raised when an atomic write fails without damaging the target."""


@dataclass(frozen=True, slots=True)
class AtomicWriteResult:
    target_path: Path
    snapshot_path: Path | None


def render_toml(config: AppConfig) -> str:
    payload = config.model_dump(mode="json", exclude_none=True)
    return tomlkit.dumps(payload)


def write_config_atomic(
    target: Path,
    content: str,
    *,
    write: WriteFunction = os.write,
    replace: ReplaceFunction = os.replace,
) -> AtomicWriteResult:
    target = target.expanduser()
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
    )
    temporary_path = Path(temporary_name)
    snapshot_path: Path | None = None
    stage = "write"
    try:
        os.fchmod(file_descriptor, 0o600)
        _write_all(file_descriptor, content.encode("utf-8"), write)
        os.fsync(file_descriptor)
        os.close(file_descriptor)
        file_descriptor = -1
        if target.exists():
            stage = "snapshot"
            snapshot_path = _write_snapshot(target, write)
        stage = "replace"
        replace(str(temporary_path), str(target))
        os.chmod(target, 0o600)
        _fsync_directory(target.parent)
        return AtomicWriteResult(target_path=target, snapshot_path=snapshot_path)
    except OSError as exc:
        raise AtomicWriteError(f"atomic write failed during {stage}") from exc
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


def _fsync_directory(directory: Path) -> None:
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
