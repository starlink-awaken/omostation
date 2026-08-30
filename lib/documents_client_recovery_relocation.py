#!/usr/bin/env python3
"""Relocate inactive client recovery state from Documents, fail closed."""

# ruff: noqa: UP006, UP035, UP045 -- this host tool must parse on Python 3.9.

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import quote

SCHEMA = "documents-client-recovery-relocation/v1"
ERROR_SCHEMA = "documents-client-recovery-relocation-error/v1"
SOURCE_NAMES = (".codex-optimize-log", ".cc-switch-recovery2")
TARGET_PARENT_NAME = "CC_Switch Recovery"
TARGET_NAME = "2026-08-30"
ACTIVE_DATA_NAME = "CC_Switch"
DISK_OVERHEAD_BYTES = 1024 * 1024


class RelocationError(RuntimeError):
    """A stable fail-closed recovery relocation error."""

    def __init__(self, message: str, *, code: str = "RELOCATION_FAILED") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class RelocationPaths:
    documents_root: Path
    source_roots: Tuple[Path, Path]
    target_root: Path
    rollback_receipt: Path

    @property
    def staging_root(self) -> Path:
        return self.target_root.parent / ("." + self.target_root.name + ".staging")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _inside_lexical(path: Path, root: Path) -> bool:
    try:
        Path(os.path.abspath(path)).relative_to(Path(os.path.abspath(root)))
    except ValueError:
        return False
    return True


def _canonical_fingerprint(entries: Sequence[Dict[str, Any]]) -> str:
    payload = [
        {
            "relative_path": item["relative_path"],
            "bytes": item["bytes"],
            "mode": item["mode"],
            "sha256": item["sha256"],
        }
        for item in sorted(entries, key=lambda value: str(value["relative_path"]))
    ]
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _regular_directory(path: Path, label: str) -> None:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise RelocationError(label + " is unavailable", code="SOURCE_ROOT_UNAVAILABLE") from exc
    if not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
        raise RelocationError(label + " boundary must be a regular non-symlink directory", code="SOURCE_BOUNDARY_INVALID")


def _validate_path_boundaries(paths: RelocationPaths) -> None:
    documents = paths.documents_root.expanduser().absolute()
    _regular_directory(documents, "Documents root")
    if len(paths.source_roots) != 2:
        raise RelocationError("source boundary must contain exactly two roots", code="SOURCE_ROOT_SET_INVALID")
    expected = tuple(documents / name for name in SOURCE_NAMES)
    actual = tuple(root.expanduser().absolute() for root in paths.source_roots)
    if actual != expected:
        raise RelocationError("source boundary does not match the exact recovery roots", code="SOURCE_BOUNDARY_INVALID")
    for root in actual:
        _regular_directory(root, "source root")

    home = documents.parent
    application_support = home / "Library" / "Application Support"
    target = paths.target_root.expanduser().absolute()
    expected_target = application_support / TARGET_PARENT_NAME / TARGET_NAME
    active_data = application_support / ACTIVE_DATA_NAME
    if target != expected_target or not _inside_lexical(target, application_support):
        raise RelocationError("target boundary must be the fixed App Support recovery root", code="TARGET_BOUNDARY_INVALID")
    if _inside_lexical(target, active_data) or _inside_lexical(active_data, target):
        raise RelocationError("target boundary overlaps active CC Switch data", code="TARGET_BOUNDARY_INVALID")
    expected_receipt = expected_target.parent / (TARGET_NAME + ".rollback-receipt.json")
    if paths.rollback_receipt.expanduser().absolute() != expected_receipt:
        raise RelocationError("rollback receipt boundary is invalid", code="TARGET_BOUNDARY_INVALID")


def _inventory_once(paths: RelocationPaths) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    for source_root in paths.source_roots:
        root = source_root.expanduser().absolute()
        for current_raw, directory_names, file_names in os.walk(root, followlinks=False):
            current = Path(current_raw)
            for name in sorted(directory_names):
                directory = current / name
                metadata = directory.lstat()
                if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
                    raise RelocationError(
                        "selected recovery node must be a regular non-symlink directory",
                        code="SOURCE_NODE_INVALID",
                    )
            for name in sorted(file_names):
                source = current / name
                try:
                    metadata = source.lstat()
                except OSError as exc:
                    raise RelocationError("source tree changed during inventory", code="SOURCE_DRIFT") from exc
                if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
                    raise RelocationError(
                        "selected recovery node must be a regular non-symlink file",
                        code="SOURCE_NODE_INVALID",
                    )
                relative = Path(root.name) / source.relative_to(root)
                entries.append(
                    {
                        "source": str(source),
                        "relative_path": relative.as_posix(),
                        "node_type": "regular",
                        "bytes": metadata.st_size,
                        "mode": stat.S_IMODE(metadata.st_mode),
                        "sha256": _sha256_file(source),
                    }
                )
    entries.sort(key=lambda item: str(item["relative_path"]))
    if not entries:
        raise RelocationError("source recovery inventory is empty", code="SOURCE_INVENTORY_EMPTY")
    return entries


def inventory_sources(paths: RelocationPaths) -> List[Dict[str, Any]]:
    _validate_path_boundaries(paths)
    first = _inventory_once(paths)
    second = _inventory_once(paths)
    if first != second:
        raise RelocationError("source tree changed during inventory", code="SOURCE_DRIFT")
    return first


def _validate_consumer_receipt(receipt: Dict[str, Any]) -> None:
    if receipt.get("schema") != "documents.consumer-audit.v1":
        raise RelocationError("consumer receipt schema is invalid", code="CONSUMER_RECEIPT_INVALID")
    if receipt.get("status") != "ok":
        raise RelocationError("consumer receipt status is not ok", code="CONSUMER_RECEIPT_UNHEALTHY")
    summary = receipt.get("summary")
    if not isinstance(summary, dict):
        raise RelocationError("consumer receipt summary is missing", code="CONSUMER_RECEIPT_INVALID")
    for field in ("forbidden_executors", "unmatched"):
        if summary.get(field) != 0:
            raise RelocationError(
                "consumer receipt " + field + " must equal zero",
                code="CONSUMER_RECEIPT_UNHEALTHY",
            )


def _open_handles(roots: Sequence[Path]) -> List[str]:
    handles: List[str] = []
    for root in roots:
        completed = subprocess.run(
            ["/usr/sbin/lsof", "+D", str(root)],
            check=False,
            capture_output=True,
            text=True,
        )
        lines = [line for line in completed.stdout.splitlines() if line.strip()]
        if len(lines) > 1:
            handles.extend(lines[1:])
    return handles


def _nearest_existing(path: Path) -> Path:
    candidate = path.expanduser().absolute()
    while not candidate.exists():
        parent = candidate.parent
        if parent == candidate:
            raise RelocationError("target has no existing ancestor", code="TARGET_BOUNDARY_INVALID")
        candidate = parent
    return candidate


def _available_bytes(target_parent: Path) -> int:
    return int(shutil.disk_usage(_nearest_existing(target_parent)).free)


def _sqlite_checks(entries: Iterable[Dict[str, Any]]) -> List[Dict[str, str]]:
    checks: List[Dict[str, str]] = []
    for item in entries:
        source = Path(str(item["source"]))
        if int(item["bytes"]) == 0:
            continue
        with source.open("rb") as stream:
            header = stream.read(16)
        if header != b"SQLite format 3\x00":
            continue
        uri = "file:" + quote(str(source)) + "?mode=ro&immutable=1"
        try:
            connection = sqlite3.connect(uri, uri=True)
            try:
                rows = [str(row[0]) for row in connection.execute("PRAGMA quick_check")]
            finally:
                connection.close()
        except sqlite3.Error as exc:
            raise RelocationError("SQLite quick_check failed: " + str(item["relative_path"]), code="SQLITE_CORRUPT") from exc
        if rows != ["ok"]:
            raise RelocationError("SQLite quick_check failed: " + str(item["relative_path"]), code="SQLITE_CORRUPT")
        checks.append({"relative_path": str(item["relative_path"]), "status": "ok"})
    return checks


def _require_targets_absent(paths: RelocationPaths) -> None:
    for target in (paths.target_root, paths.staging_root, paths.rollback_receipt):
        if target.exists() or target.is_symlink():
            raise RelocationError("target collision: " + str(target), code="TARGET_COLLISION")


def plan_relocation(
    paths: RelocationPaths,
    *,
    consumer_receipt: Dict[str, Any],
    source_handles: Optional[Sequence[str]] = None,
    available_bytes: Optional[int] = None,
) -> Dict[str, Any]:
    files = inventory_sources(paths)
    _validate_consumer_receipt(consumer_receipt)
    handles = list(source_handles) if source_handles is not None else _open_handles(paths.source_roots)
    if handles:
        raise RelocationError("source recovery state has an open handle", code="SOURCE_HANDLE_OPEN")
    total = sum(int(item["bytes"]) for item in files)
    free = available_bytes if available_bytes is not None else _available_bytes(paths.target_root.parent)
    if free < total + DISK_OVERHEAD_BYTES:
        raise RelocationError("insufficient disk space for staged recovery relocation", code="INSUFFICIENT_DISK")
    _require_targets_absent(paths)
    sqlite_checks = _sqlite_checks(files)
    return {
        "schema": SCHEMA,
        "status": "planned",
        "documents_root": str(paths.documents_root.expanduser().absolute()),
        "source_roots": [str(root.expanduser().absolute()) for root in paths.source_roots],
        "target_root": str(paths.target_root.expanduser().absolute()),
        "staging_root": str(paths.staging_root.expanduser().absolute()),
        "rollback_receipt": str(paths.rollback_receipt.expanduser().absolute()),
        "files": files,
        "summary": {"files": len(files), "bytes": total},
        "source_fingerprint": _canonical_fingerprint(files),
        "sqlite_checks": sqlite_checks,
        "consumer_summary": dict(consumer_receipt["summary"]),
        "permanent_deletion": False,
    }
