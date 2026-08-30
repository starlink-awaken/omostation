#!/usr/bin/env python3
"""Relocate inactive client recovery state from Documents, fail closed."""

# ruff: noqa: UP006, UP035, UP045 -- this host tool must parse on Python 3.9.

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import stat
import subprocess
import tempfile
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


def _validate_path_boundaries(paths: RelocationPaths, *, require_sources: bool = True) -> None:
    documents = paths.documents_root.expanduser().absolute()
    _regular_directory(documents, "Documents root")
    if len(paths.source_roots) != 2:
        raise RelocationError("source boundary must contain exactly two roots", code="SOURCE_ROOT_SET_INVALID")
    expected = tuple(documents / name for name in SOURCE_NAMES)
    actual = tuple(root.expanduser().absolute() for root in paths.source_roots)
    if actual != expected:
        raise RelocationError("source boundary does not match the exact recovery roots", code="SOURCE_BOUNDARY_INVALID")
    if require_sources:
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
    lsof = shutil.which("lsof")
    if not lsof:
        raise RelocationError("lsof is required for handle inspection", code="HANDLE_INSPECTOR_UNAVAILABLE")
    handles: List[str] = []
    for root in roots:
        completed = subprocess.run(
            [lsof, "+D", str(root)],
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


def _atomic_write_json(path: Path, payload: Dict[str, Any], *, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix="." + path.name + ".",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            os.chmod(temporary, mode)
            json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(str(temporary), str(path))
        temporary = None
        path.chmod(mode)
    finally:
        if temporary is not None:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _source_entries(plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    entries = plan.get("files")
    if not isinstance(entries, list) or not entries:
        raise RelocationError("relocation plan has no source entries", code="PLAN_INVALID")
    if not all(isinstance(item, dict) for item in entries):
        raise RelocationError("relocation plan entries are malformed", code="PLAN_INVALID")
    return [dict(item) for item in entries]


def _entry_at_target(root: Path, source_entry: Dict[str, Any]) -> Dict[str, Any]:
    relative = str(source_entry["relative_path"])
    target = root / relative
    try:
        metadata = target.lstat()
    except OSError as exc:
        raise RelocationError("target verification failed: " + relative, code="TARGET_VERIFY_FAILED") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise RelocationError("target verification failed: " + relative, code="TARGET_VERIFY_FAILED")
    result = {
        "source": str(target),
        "relative_path": relative,
        "node_type": "regular",
        "bytes": metadata.st_size,
        "mode": stat.S_IMODE(metadata.st_mode),
        "sha256": _sha256_file(target),
    }
    for field in ("node_type", "bytes", "mode", "sha256"):
        if result[field] != source_entry[field]:
            raise RelocationError("target verification failed: " + relative, code="TARGET_VERIFY_FAILED")
    return result


def _verify_staging(staging_root: Path, plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    verified = [_entry_at_target(staging_root, item) for item in _source_entries(plan)]
    fingerprint = _canonical_fingerprint(verified)
    if fingerprint != plan.get("source_fingerprint"):
        raise RelocationError("target verification fingerprint mismatch", code="TARGET_VERIFY_FAILED")
    checks = _sqlite_checks(verified)
    if checks != plan.get("sqlite_checks"):
        raise RelocationError("target verification SQLite mismatch", code="TARGET_VERIFY_FAILED")
    return verified


def _completed_manifest(paths: RelocationPaths, plan: Dict[str, Any]) -> Dict[str, Any]:
    files = []
    for item in _source_entries(plan):
        files.append({**item, "target": str(paths.target_root / str(item["relative_path"]))})
    return {
        **plan,
        "status": "completed",
        "files": files,
        "target_fingerprint": plan["source_fingerprint"],
        "manifest_path": str(paths.target_root / "manifest.json"),
        "rollback": "Verify target hashes, require absent source roots, then move each manifest entry back in reverse order.",
    }


def _remove_empty_tree(root: Path) -> None:
    if not root.exists():
        return
    for current_raw, directory_names, _file_names in os.walk(root, topdown=False, followlinks=False):
        current = Path(current_raw)
        for name in directory_names:
            child = current / name
            if child.exists() and not child.is_symlink():
                child.rmdir()
        current.rmdir()


def _remove_empty_source_roots(paths: RelocationPaths) -> None:
    for root in paths.source_roots:
        _remove_empty_tree(root)


def _restore_moves(moved: Sequence[Tuple[Path, Path]]) -> None:
    failures: List[str] = []
    for source, target in reversed(list(moved)):
        try:
            if source.exists() or source.is_symlink():
                raise RelocationError("rollback source collision: " + str(source), code="ROLLBACK_COLLISION")
            if not target.is_file() or target.is_symlink():
                raise RelocationError("rollback target missing: " + str(target), code="ROLLBACK_TARGET_MISSING")
            source.parent.mkdir(parents=True, exist_ok=True)
            os.replace(str(target), str(source))
        except (OSError, RelocationError) as exc:
            failures.append(str(exc))
    if failures:
        raise RelocationError("rollback failed: " + "; ".join(failures), code="ROLLBACK_FAILED")


def apply_relocation(
    paths: RelocationPaths,
    *,
    consumer_receipt: Dict[str, Any],
    source_handles: Optional[Sequence[str]] = None,
    available_bytes: Optional[int] = None,
) -> Dict[str, Any]:
    plan = plan_relocation(
        paths,
        consumer_receipt=consumer_receipt,
        source_handles=source_handles,
        available_bytes=available_bytes,
    )
    return apply_plan(paths, plan)


def apply_plan(paths: RelocationPaths, plan: Dict[str, Any]) -> Dict[str, Any]:
    if plan.get("schema") != SCHEMA or plan.get("status") != "planned":
        raise RelocationError("relocation plan is malformed", code="PLAN_INVALID")
    _validate_path_boundaries(paths)
    _require_targets_absent(paths)
    if inventory_sources(paths) != _source_entries(plan):
        raise RelocationError("source tree changed before apply", code="SOURCE_DRIFT")
    target_device = _nearest_existing(paths.target_root.parent).stat().st_dev
    if any(root.stat().st_dev != target_device for root in paths.source_roots):
        raise RelocationError("source and target must be on the same filesystem", code="CROSS_DEVICE_MOVE")

    moved: List[Tuple[Path, Path]] = []
    published = False
    try:
        paths.staging_root.parent.mkdir(parents=True, exist_ok=True)
        paths.staging_root.mkdir(mode=0o700)
        for item in _source_entries(plan):
            source = Path(str(item["source"]))
            target = paths.staging_root / str(item["relative_path"])
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(str(source), str(target))
            moved.append((source, target))
        _verify_staging(paths.staging_root, plan)
        manifest = _completed_manifest(paths, plan)
        _atomic_write_json(paths.staging_root / "manifest.json", manifest, mode=0o600)
        _fsync_directory(paths.staging_root)
        _remove_empty_source_roots(paths)
        os.replace(str(paths.staging_root), str(paths.target_root))
        published = True
        _fsync_directory(paths.target_root.parent)
        return manifest
    except Exception as exc:
        if published:
            raise RelocationError(
                "relocation published but final durability check failed: " + str(exc),
                code="PUBLISHED_DURABILITY_UNPROVABLE",
            ) from exc
        try:
            _restore_moves(moved)
            _remove_empty_tree(paths.staging_root)
        except RelocationError as rollback_error:
            raise RelocationError(
                "relocation failed: " + str(exc) + "; " + str(rollback_error),
                code="ROLLBACK_FAILED",
            ) from exc
        if isinstance(exc, RelocationError):
            raise
        raise RelocationError("relocation failed: " + str(exc), code="APPLY_FAILED") from exc


def _load_manifest(path: Path) -> Dict[str, Any]:
    try:
        metadata = path.lstat()
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RelocationError("completed manifest is unavailable", code="MANIFEST_INVALID") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode) or not isinstance(payload, dict):
        raise RelocationError("completed manifest is invalid", code="MANIFEST_INVALID")
    if payload.get("schema") != SCHEMA or payload.get("status") != "completed":
        raise RelocationError("completed manifest is invalid", code="MANIFEST_INVALID")
    return payload


def _verify_final_target(paths: RelocationPaths, manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
    if any(root.exists() or root.is_symlink() for root in paths.source_roots):
        raise RelocationError("target verification found a source root", code="SOURCE_RESIDUAL")
    verified = [_entry_at_target(paths.target_root, item) for item in _source_entries(manifest)]
    fingerprint = _canonical_fingerprint(verified)
    if fingerprint != manifest.get("target_fingerprint") or fingerprint != manifest.get("source_fingerprint"):
        raise RelocationError("target verification fingerprint mismatch", code="TARGET_VERIFY_FAILED")
    checks = _sqlite_checks(verified)
    if checks != manifest.get("sqlite_checks"):
        raise RelocationError("target verification SQLite mismatch", code="TARGET_VERIFY_FAILED")
    return verified


def verify_relocation(paths: RelocationPaths, *, consumer_receipt: Dict[str, Any]) -> Dict[str, Any]:
    _validate_path_boundaries(paths, require_sources=False)
    _validate_consumer_receipt(consumer_receipt)
    manifest = _load_manifest(paths.target_root / "manifest.json")
    _verify_final_target(paths, manifest)
    return {
        "schema": SCHEMA,
        "status": "verified",
        "manifest": str(paths.target_root / "manifest.json"),
        "summary": dict(manifest["summary"]),
        "target_fingerprint": manifest["target_fingerprint"],
        "source_roots_absent": True,
        "rollback_available": True,
        "sqlite_checks": list(manifest["sqlite_checks"]),
        "consumer_summary": dict(consumer_receipt["summary"]),
    }


def _restore_rollback_moves(moved: Sequence[Tuple[Path, Path]]) -> None:
    for source, target in reversed(list(moved)):
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(str(source), str(target))


def rollback_relocation(
    paths: RelocationPaths,
    *,
    target_handles: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    _validate_path_boundaries(paths, require_sources=False)
    manifest_path = paths.target_root / "manifest.json"
    manifest = _load_manifest(manifest_path)
    if any(root.exists() or root.is_symlink() for root in paths.source_roots):
        raise RelocationError("source collision prevents rollback", code="ROLLBACK_COLLISION")
    _verify_final_target(paths, manifest)
    handles = list(target_handles) if target_handles is not None else _open_handles((paths.target_root,))
    if handles:
        raise RelocationError("target recovery state has an open handle", code="TARGET_HANDLE_OPEN")

    moved: List[Tuple[Path, Path]] = []
    try:
        for item in reversed(_source_entries(manifest)):
            target = paths.target_root / str(item["relative_path"])
            source = Path(str(item["source"]))
            if source.exists() or source.is_symlink():
                raise RelocationError("source collision prevents rollback", code="ROLLBACK_COLLISION")
            source.parent.mkdir(parents=True, exist_ok=True)
            os.replace(str(target), str(source))
            moved.append((source, target))
        restored = inventory_sources(paths)
        if _canonical_fingerprint(restored) != manifest.get("source_fingerprint"):
            raise RelocationError("restored source verification failed", code="ROLLBACK_VERIFY_FAILED")
        completed_manifest = paths.target_root.parent / (TARGET_NAME + ".completed-manifest.json")
        if completed_manifest.exists() or completed_manifest.is_symlink():
            raise RelocationError("rollback manifest archive collision", code="ROLLBACK_COLLISION")
        manifest_sha256 = _sha256_file(manifest_path)
        os.replace(str(manifest_path), str(completed_manifest))
        _remove_empty_tree(paths.target_root)
        receipt = {
            "schema": SCHEMA,
            "status": "rolled_back",
            "summary": dict(manifest["summary"]),
            "source_fingerprint": manifest["source_fingerprint"],
            "completed_manifest": str(completed_manifest),
            "completed_manifest_sha256": "sha256:" + manifest_sha256,
            "permanent_deletion": False,
        }
        _atomic_write_json(paths.rollback_receipt, receipt, mode=0o600)
        return receipt
    except Exception as exc:
        try:
            _restore_rollback_moves(moved)
        except OSError as restore_error:
            raise RelocationError(
                "rollback failed and target restoration failed: " + str(restore_error),
                code="ROLLBACK_FAILED",
            ) from exc
        if isinstance(exc, RelocationError):
            raise
        raise RelocationError("rollback failed: " + str(exc), code="ROLLBACK_FAILED") from exc


DEFAULT_DOCUMENTS_ROOT = Path.home() / "Documents"
DEFAULT_SOURCE_RELATIVES = SOURCE_NAMES
DEFAULT_TARGET_ROOT = (
    Path.home() / "Library" / "Application Support" / TARGET_PARENT_NAME / TARGET_NAME
)
DEFAULT_ROLLBACK_RECEIPT = DEFAULT_TARGET_ROOT.parent / (TARGET_NAME + ".rollback-receipt.json")


def _load_json_mapping(path: Path, label: str) -> Dict[str, Any]:
    try:
        metadata = path.lstat()
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RelocationError(label + " is unavailable or malformed", code="CONSUMER_RECEIPT_INVALID") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode) or not isinstance(payload, dict):
        raise RelocationError(label + " must be a regular JSON object", code="CONSUMER_RECEIPT_INVALID")
    return payload


def _cli_paths(args: argparse.Namespace) -> RelocationPaths:
    documents = args.documents_root.expanduser().absolute()
    relative_values: Sequence[str] = args.source_relative or DEFAULT_SOURCE_RELATIVES
    sources = tuple(documents / value for value in relative_values)
    if len(sources) != 2:
        raise RelocationError("exactly two source roots are required", code="SOURCE_ROOT_SET_INVALID")
    return RelocationPaths(
        documents_root=documents,
        source_roots=(sources[0], sources[1]),
        target_root=args.target_root.expanduser().absolute(),
        rollback_receipt=args.rollback_receipt.expanduser().absolute(),
    )


def _cli_consumer_receipt(args: argparse.Namespace) -> Dict[str, Any]:
    if args.consumer_receipt is None:
        raise RelocationError("consumer receipt is required", code="CONSUMER_RECEIPT_REQUIRED")
    return _load_json_mapping(args.consumer_receipt.expanduser().absolute(), "consumer receipt")


def _execute_cli(args: argparse.Namespace) -> Dict[str, Any]:
    paths = _cli_paths(args)
    if args.command == "plan":
        return plan_relocation(paths, consumer_receipt=_cli_consumer_receipt(args))
    if args.command == "apply":
        return apply_relocation(paths, consumer_receipt=_cli_consumer_receipt(args))
    if args.command == "verify":
        return verify_relocation(paths, consumer_receipt=_cli_consumer_receipt(args))
    if args.command == "rollback":
        return rollback_relocation(paths)
    raise RelocationError("unknown command", code="COMMAND_INVALID")


def _error_payload(command: str, error: Exception) -> Dict[str, Any]:
    code = error.code if isinstance(error, RelocationError) else "RELOCATION_FAILED"
    return {
        "schema": ERROR_SCHEMA,
        "status": "error",
        "code": code,
        "command": command,
        "error": str(error),
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "apply", "verify", "rollback"))
    parser.add_argument("--documents-root", type=Path, default=DEFAULT_DOCUMENTS_ROOT)
    parser.add_argument("--source-relative", action="append")
    parser.add_argument("--target-root", type=Path, default=DEFAULT_TARGET_ROOT)
    parser.add_argument("--rollback-receipt", type=Path, default=DEFAULT_ROLLBACK_RECEIPT)
    parser.add_argument("--consumer-receipt", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        payload = _execute_cli(args)
    except (OSError, RelocationError) as exc:
        print(json.dumps(_error_payload(args.command, exc), ensure_ascii=False, indent=2, sort_keys=True))
        return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2 if args.json else None, sort_keys=True))
    return 0
