#!/usr/bin/env python3
"""Move audited Documents runtime files into a recoverable Workspace quarantine."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "documents-runtime-quarantine/v1"
ROLLBACK_SCHEMA = "documents-runtime-quarantine-rollback/v1"
_EXECUTION_MODES = {"content-reference"}
_ALLOWED_KINDS = frozenset({"runtime", "cache"})


class QuarantineError(RuntimeError):
    """Raised when a physical quarantine cannot be proved safe."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _inside_lexical(path: Path, root: Path) -> bool:
    try:
        Path(os.path.abspath(path)).relative_to(Path(os.path.abspath(root)))
    except ValueError:
        return False
    return True


def _canonical_digest(entries: list[dict[str, Any]]) -> str:
    payload = [
        {
            "relative_path": entry["relative_path"],
            "bytes": entry["bytes"],
            "mode": entry["mode"],
            "sha256": entry["sha256"],
        }
        for entry in sorted(entries, key=lambda item: item["relative_path"])
    ]
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _normalize_relative_paths(values: list[str]) -> tuple[str, ...]:
    normalized: set[str] = set()
    for raw in values:
        candidate = Path(raw)
        if not raw or candidate.is_absolute() or any(part in {"", ".", ".."} for part in candidate.parts):
            raise QuarantineError(f"exact include path is unsafe: {raw}")
        value = candidate.as_posix()
        if value in normalized:
            raise QuarantineError(f"exact include path is duplicated: {value}")
        normalized.add(value)
    if not normalized:
        raise QuarantineError("exact include paths are empty")
    return tuple(sorted(normalized))


def _validate_consumer_receipt(receipt: dict[str, Any]) -> None:
    if receipt.get("schema") != "documents.consumer-audit.v1":
        raise QuarantineError("consumer receipt schema is not documents.consumer-audit.v1")
    if receipt.get("status") != "ok":
        raise QuarantineError("consumer receipt status is not ok")
    summary = receipt.get("summary")
    if not isinstance(summary, dict):
        raise QuarantineError("consumer receipt summary is missing")
    for field in ("forbidden_executors", "unmatched"):
        if summary.get(field) != 0:
            raise QuarantineError(f"consumer receipt {field} must equal zero")
    for item in receipt.get("consumers", []):
        if not isinstance(item, dict):
            continue
        if item.get("family") in {"public-runtime", "cockpit-runtime"} and item.get("execution_mode") not in _EXECUTION_MODES:
            raise QuarantineError("public/cockpit runtime consumer is not content-reference")


def _entry_from_source(source: Path, relative_path: str) -> dict[str, Any]:
    try:
        info = source.lstat()
    except OSError as exc:
        raise QuarantineError(f"source cannot be inspected: {source}") from exc
    if stat.S_ISLNK(info.st_mode):
        link_target = os.readlink(source)
        return {
            "source": str(source),
            "relative_path": relative_path,
            "node_type": "symlink",
            "link_target": link_target,
            "bytes": 0,
            "mode": stat.S_IMODE(info.st_mode),
            "sha256": hashlib.sha256(os.fsencode(link_target)).hexdigest(),
        }
    if not stat.S_ISREG(info.st_mode):
        raise QuarantineError(f"selected source is not a regular non-symlink file: {source}")
    return {
        "source": str(source),
        "relative_path": relative_path,
        "node_type": "regular",
        "bytes": info.st_size,
        "mode": stat.S_IMODE(info.st_mode),
        "sha256": _sha256(source),
    }


def _scope_snapshot(source_root: Path, excluded: set[str]) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    try:
        paths = sorted(source_root.rglob("*"), key=lambda path: path.relative_to(source_root).as_posix())
    except OSError as exc:
        raise QuarantineError(f"source scope cannot be enumerated: {source_root}") from exc
    for path in paths:
        relative = path.relative_to(source_root).as_posix()
        if relative in excluded:
            continue
        try:
            info = path.lstat()
        except OSError as exc:
            raise QuarantineError(f"source scope node cannot be inspected: {path}") from exc
        if stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode):
            continue
        entries.append(_entry_from_source(path, relative))
    return {
        "files": len(entries),
        "bytes": sum(item["bytes"] for item in entries),
        "fingerprint": _canonical_digest(entries),
        "entries": entries,
    }


def build_plan(
    *,
    documents_root: Path,
    source_root: Path,
    target_root: Path,
    inventory: list[dict[str, Any]],
    consumer_receipt: dict[str, Any],
    now: str,
    selected_kinds: set[str] | None = None,
    exact_relative_paths: list[str] | None = None,
) -> dict[str, Any]:
    documents = documents_root.expanduser().resolve()
    source_lexical = source_root.expanduser().absolute()
    try:
        source_info = source_lexical.lstat()
    except OSError as exc:
        raise QuarantineError("Documents source does not exist or cannot be inspected") from exc
    source_is_file = stat.S_ISREG(source_info.st_mode)
    source_is_directory = stat.S_ISDIR(source_info.st_mode)
    source = source_lexical.resolve()
    target = target_root.expanduser().resolve()
    if not documents.is_dir() or not (source_is_file or source_is_directory):
        raise QuarantineError("Documents root must be a directory and source must be a regular file or directory")
    if not _inside(source, documents):
        raise QuarantineError("source root must be below Documents root")
    if _inside(target, documents) or _inside(documents, target):
        raise QuarantineError("Documents and quarantine roots must be disjoint")
    _validate_consumer_receipt(consumer_receipt)

    kinds = {"runtime"} if selected_kinds is None else set(selected_kinds)
    if not kinds or not kinds.issubset(_ALLOWED_KINDS):
        raise QuarantineError("selected artifact kinds must be a non-empty subset of runtime|cache")
    exact = _normalize_relative_paths(exact_relative_paths) if exact_relative_paths is not None else None
    if exact is not None and not source_is_directory:
        raise QuarantineError("exact selection requires a directory source root")

    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in inventory:
        if item.get("kind") not in kinds:
            continue
        relative = item.get("relative_path")
        path_value = item.get("path")
        if not isinstance(relative, str) or not relative or not isinstance(path_value, str):
            raise QuarantineError("L4 runtime inventory entry is malformed")
        relative_path = Path(relative)
        if relative_path.is_absolute() or ".." in relative_path.parts or relative in seen:
            raise QuarantineError(f"runtime inventory path is unsafe or duplicated: {relative}")
        source_file = Path(path_value).expanduser().absolute()
        if source_is_file:
            if source_file != source_lexical or relative != source_lexical.name:
                raise QuarantineError(f"runtime inventory path mismatch: {relative}")
        else:
            if not _inside_lexical(source_file, source):
                raise QuarantineError(f"runtime inventory escapes source root: {relative}")
            if source_file.relative_to(source.absolute()).as_posix() != relative:
                raise QuarantineError(f"runtime inventory path mismatch: {relative}")
        entries.append(_entry_from_source(source_file, relative))
        seen.add(relative)
    if not entries:
        raise QuarantineError("L4 inventory selected no runtime files")
    if exact is not None and set(seen) != set(exact):
        raise QuarantineError("exact selection did not match every expected relative path")

    summary = {"files": len(entries), "bytes": sum(entry["bytes"] for entry in entries)}
    plan = {
        "schema": SCHEMA,
        "status": "planned",
        "planned_at": now,
        "documents_root": str(documents),
        "source_root": str(source),
        "target_root": str(target),
        "files": entries,
        "summary": summary,
        "source_fingerprint": _canonical_digest(entries),
        "consumer_summary": consumer_receipt["summary"],
        "permanent_deletion": False,
    }
    if exact is not None:
        plan.update(
            {
                "selection_mode": "exact",
                "selected_kinds": sorted(kinds),
                "expected_relative_paths": list(exact),
                "non_target_guard": _scope_snapshot(source, set(exact)),
            }
        )
    return plan


def _validate_non_target_guard(plan: dict[str, Any]) -> None:
    guard = plan.get("non_target_guard")
    if guard is None:
        return
    expected = plan.get("expected_relative_paths")
    if (
        not isinstance(guard, dict)
        or not isinstance(expected, list)
        or not all(isinstance(item, str) for item in expected)
    ):
        raise QuarantineError("exact non-target guard is malformed")
    current = _scope_snapshot(Path(str(plan["source_root"])), set(expected))
    if current != guard:
        raise QuarantineError("non-target source scope changed")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _restore(moved: list[tuple[Path, Path]]) -> None:
    failures: list[str] = []
    for source, target in reversed(moved):
        try:
            if not os.path.lexists(target) or os.path.lexists(source):
                raise QuarantineError("rollback boundary changed")
            source.parent.mkdir(parents=True, exist_ok=True)
            os.replace(target, source)
        except (OSError, QuarantineError) as exc:
            failures.append(f"{target} -> {source}: {exc}")
    if failures:
        raise QuarantineError("rollback failed: " + "; ".join(failures))


def apply_plan(plan: dict[str, Any]) -> dict[str, Any]:
    if plan.get("schema") != SCHEMA or plan.get("status") != "planned":
        raise QuarantineError("plan is not a planned documents runtime quarantine")
    target_root = Path(str(plan["target_root"])).expanduser().resolve()
    manifest_path = target_root / "manifest.json"
    if manifest_path.exists() or manifest_path.is_symlink():
        raise QuarantineError(f"manifest collision: {manifest_path}")
    if target_root.exists() and (not target_root.is_dir() or target_root.is_symlink()):
        raise QuarantineError(f"quarantine target is not a regular directory: {target_root}")
    if target_root.exists() and any(target_root.iterdir()):
        raise QuarantineError(f"target collision: quarantine target is not empty: {target_root}")

    entries = plan.get("files")
    if not isinstance(entries, list) or not entries:
        raise QuarantineError("plan contains no files")
    _validate_non_target_guard(plan)
    moved: list[tuple[Path, Path]] = []
    try:
        target_root.mkdir(parents=True, exist_ok=True)
        for item in entries:
            source = Path(str(item["source"])).expanduser().absolute()
            relative = Path(str(item["relative_path"]))
            target = target_root / relative
            if target.exists() or target.is_symlink():
                raise QuarantineError(f"target collision: {target}")
            current = _entry_from_source(source, relative.as_posix())
            compare_fields = ("node_type", "bytes", "mode", "sha256")
            if current["node_type"] == "symlink":
                compare_fields += ("link_target",)
            for field in compare_fields:
                if current[field] != item[field]:
                    raise QuarantineError(f"source changed before move: {source}")
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(source, target)
            moved.append((source, target))

        verified: list[dict[str, Any]] = []
        for item in entries:
            target = target_root / Path(str(item["relative_path"]))
            if item.get("node_type") == "symlink":
                link_target = os.readlink(target) if target.is_symlink() else None
                valid_target = link_target == item.get("link_target") and hashlib.sha256(
                    os.fsencode(link_target or "")
                ).hexdigest() == item["sha256"]
            else:
                valid_target = target.is_file() and not target.is_symlink() and _sha256(target) == item["sha256"]
            if not valid_target:
                raise QuarantineError(f"target verification failed: {target}")
            if os.path.lexists(item["source"]):
                raise QuarantineError(f"source remains after move: {item['source']}")
            verified.append({**item, "target": str(target)})

        _validate_non_target_guard(plan)

        manifest = {
            **plan,
            "status": "completed",
            "completed_at": plan["planned_at"],
            "files": verified,
            "target_fingerprint": _canonical_digest(verified),
            "rollback": "Move each manifest target back to its recorded source path after rechecking target hashes and source absence.",
        }
        _write_json(manifest_path, manifest)
        return manifest
    except Exception as exc:
        try:
            _restore(moved)
        except QuarantineError as rollback_error:
            raise QuarantineError(f"quarantine failed: {exc}; {rollback_error}") from exc
        if isinstance(exc, QuarantineError):
            raise
        raise QuarantineError(f"quarantine failed: {exc}") from exc


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise QuarantineError(f"manifest cannot be loaded: {path}") from exc
    if not isinstance(payload, dict):
        raise QuarantineError("manifest must be a JSON object")
    return payload


def _compare_entry(current: dict[str, Any], expected: dict[str, Any], *, label: str) -> None:
    fields = ("node_type", "bytes", "mode", "sha256")
    if expected.get("node_type") == "symlink":
        fields += ("link_target",)
    if any(current.get(field) != expected.get(field) for field in fields):
        raise QuarantineError(f"{label} does not match manifest")


def verify_completed_manifest(manifest_path: Path) -> dict[str, Any]:
    manifest_path = manifest_path.expanduser().resolve()
    manifest = _load_json_object(manifest_path)
    if manifest.get("schema") != SCHEMA or manifest.get("status") != "completed":
        raise QuarantineError("manifest is not a completed documents runtime quarantine")
    if manifest.get("permanent_deletion") is not False:
        raise QuarantineError("manifest must record permanent deletion false")
    documents_root = Path(str(manifest.get("documents_root", ""))).expanduser().resolve()
    target_root = Path(str(manifest.get("target_root", ""))).expanduser().resolve()
    source_root = Path(str(manifest.get("source_root", ""))).expanduser().absolute()
    if not documents_root.is_dir() or not _inside_lexical(source_root, documents_root):
        raise QuarantineError("manifest source boundary is outside Documents")
    if _inside(target_root, documents_root) or _inside(documents_root, target_root):
        raise QuarantineError("manifest target boundary overlaps Documents")
    if manifest_path != target_root / "manifest.json":
        raise QuarantineError("manifest path does not match target root")
    entries = manifest.get("files")
    if not isinstance(entries, list) or not entries:
        raise QuarantineError("completed manifest contains no files")

    expected_relatives: set[str] = set()
    target_entries: list[dict[str, Any]] = []
    for item in entries:
        if not isinstance(item, dict) or not isinstance(item.get("relative_path"), str):
            raise QuarantineError("completed manifest file entry is malformed")
        relative = _normalize_relative_paths([item["relative_path"]])[0]
        if relative in expected_relatives:
            raise QuarantineError("completed manifest relative path is duplicated")
        expected_relatives.add(relative)
        source_value = item.get("source")
        if not isinstance(source_value, str) or not source_value:
            raise QuarantineError("completed manifest source path is malformed")
        source = Path(source_value).expanduser().absolute()
        expected_source = (source_root / relative).absolute()
        single_file_source = source == source_root and relative == source_root.name
        if source != expected_source and not single_file_source:
            raise QuarantineError("manifest source boundary does not match source root")
        if not _inside_lexical(source, documents_root):
            raise QuarantineError("manifest source boundary is outside Documents")
        target = target_root / relative
        current = _entry_from_source(target, relative)
        _compare_entry(current, item, label=f"target {relative}")
        if os.path.lexists(source):
            raise QuarantineError(f"source remains after completed quarantine: {source}")
        target_entries.append(current)

    actual = _scope_snapshot(target_root, {"manifest.json", "rollback.json"})
    if {item["relative_path"] for item in actual["entries"]} != expected_relatives:
        raise QuarantineError("target inventory contains unexpected or missing entries")
    target_fingerprint = _canonical_digest(target_entries)
    if (
        manifest.get("source_fingerprint") != target_fingerprint
        or manifest.get("target_fingerprint") != target_fingerprint
    ):
        raise QuarantineError("manifest source/target fingerprint mismatch")
    _validate_non_target_guard(manifest)
    return {
        "schema": SCHEMA,
        "status": "verified",
        "manifest": str(manifest_path),
        "summary": manifest.get("summary"),
        "source_fingerprint": manifest.get("source_fingerprint"),
        "target_fingerprint": target_fingerprint,
        "source_root": str(source_root),
        "sources_absent": True,
        "non_target_fingerprint": (manifest.get("non_target_guard") or {}).get("fingerprint"),
        "rollback_available": True,
        "permanent_deletion": False,
    }


def rollback_completed_manifest(manifest_path: Path, *, now: str) -> dict[str, Any]:
    manifest_path = manifest_path.expanduser().resolve()
    verification = verify_completed_manifest(manifest_path)
    manifest = _load_json_object(manifest_path)
    target_root = Path(str(manifest["target_root"])).expanduser().resolve()
    entries = manifest["files"]
    for item in entries:
        source = Path(str(item["source"])).expanduser().absolute()
        if os.path.lexists(source):
            raise QuarantineError(f"rollback source collision: {source}")

    restored: list[tuple[Path, Path]] = []
    try:
        for item in reversed(entries):
            source = Path(str(item["source"])).expanduser().absolute()
            target = target_root / str(item["relative_path"])
            source.parent.mkdir(parents=True, exist_ok=True)
            os.replace(target, source)
            restored.append((target, source))
        for item in entries:
            source = Path(str(item["source"])).expanduser().absolute()
            current = _entry_from_source(source, str(item["relative_path"]))
            _compare_entry(current, item, label=f"restored source {source}")
            if os.path.lexists(target_root / str(item["relative_path"])):
                raise QuarantineError(f"rollback target remains: {item['relative_path']}")
        _validate_non_target_guard(manifest)
    except Exception as exc:
        try:
            _restore(restored)
        except QuarantineError as restore_error:
            raise QuarantineError(f"rollback failed: {exc}; {restore_error}") from exc
        if isinstance(exc, QuarantineError):
            raise
        raise QuarantineError(f"rollback failed: {exc}") from exc

    receipt = {
        "schema": ROLLBACK_SCHEMA,
        "status": "rolled_back",
        "rolled_back_at": now,
        "manifest": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "summary": manifest["summary"],
        "source_fingerprint": verification["source_fingerprint"],
        "permanent_deletion": False,
    }
    _write_json(target_root / "rollback.json", receipt)
    return receipt


def _load_l4_inventory(source_root: Path) -> list[dict[str, Any]]:
    l4_src = ROOT / "projects" / "l4-kernel" / "src"
    if str(l4_src) not in sys.path:
        sys.path.insert(0, str(l4_src))
    try:
        from l4_kernel.content_plane import audit_content_plane, classify_artifact
    except ImportError as exc:
        raise QuarantineError("L4 content-plane auditor is unavailable") from exc
    if source_root.is_file() and not source_root.is_symlink():
        relative = source_root.name
        before = _entry_from_source(source_root, relative)
        artifact = classify_artifact(source_root.parent, source_root)
        after = _entry_from_source(source_root, relative)
        stable_fields = ("node_type", "bytes", "mode", "sha256", "link_target")
        if any(before.get(field) != after.get(field) for field in stable_fields):
            raise QuarantineError("scoped L4 audit was not stable: single-file source changed during audit")
        return [artifact.to_dict()]
    report = audit_content_plane(source_root)
    if report.stability_attempts != 1:
        raise QuarantineError(f"scoped L4 audit was not stable: attempts={report.stability_attempts}")
    if any(item.kind == "invalid_archive" for item in report.artifacts):
        raise QuarantineError("scoped L4 audit found invalid archive artifacts")
    return [item.to_dict() for item in report.artifacts]


def _load_exact_inventory(documents_root: Path, source_root: Path, relative_paths: list[str]) -> list[dict[str, Any]]:
    l4_src = ROOT / "projects" / "l4-kernel" / "src"
    if str(l4_src) not in sys.path:
        sys.path.insert(0, str(l4_src))
    try:
        from l4_kernel.content_plane import classify_artifact
    except ImportError as exc:
        raise QuarantineError("L4 content-plane auditor is unavailable") from exc
    documents = documents_root.expanduser().resolve()
    source = source_root.expanduser().resolve()
    exact = _normalize_relative_paths(relative_paths)
    inventory: list[dict[str, Any]] = []
    for relative in exact:
        path = (source / relative).absolute()
        if not _inside_lexical(path, source):
            raise QuarantineError(f"exact include escapes source root: {relative}")
        before = _entry_from_source(path, relative)
        artifact = classify_artifact(documents, path).to_dict()
        after = _entry_from_source(path, relative)
        stable_fields = ("node_type", "bytes", "mode", "sha256", "link_target")
        if any(before.get(field) != after.get(field) for field in stable_fields):
            raise QuarantineError(f"exact source changed during classification: {relative}")
        artifact["relative_path"] = relative
        inventory.append(artifact)
    return inventory


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--documents-root", type=Path, default=Path.home() / "Documents")
    parser.add_argument("--source-relative", default="@公共")
    parser.add_argument("--target-root", type=Path)
    parser.add_argument("--consumer-receipt", type=Path)
    parser.add_argument("--include-relative", action="append", default=[])
    parser.add_argument("--artifact-kind", action="append", choices=sorted(_ALLOWED_KINDS), default=[])
    parser.add_argument("--now", default="2026-08-29T00:00:00Z")
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--apply", action="store_true")
    actions.add_argument("--verify-manifest", type=Path)
    actions.add_argument("--rollback-manifest", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.verify_manifest is not None:
            result = verify_completed_manifest(args.verify_manifest)
        elif args.rollback_manifest is not None:
            result = rollback_completed_manifest(args.rollback_manifest, now=args.now)
        else:
            if args.target_root is None or args.consumer_receipt is None:
                raise QuarantineError("target root and consumer receipt are required for plan/apply")
            if bool(args.include_relative) != bool(args.artifact_kind):
                raise QuarantineError("exact include paths and artifact kinds must be supplied together")
            documents_root = args.documents_root.expanduser().resolve()
            source_root = (documents_root / Path(args.source_relative)).expanduser().absolute()
            receipt_path = args.consumer_receipt.expanduser().resolve()
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            if not isinstance(receipt, dict):
                raise QuarantineError("consumer receipt must be a JSON object")
            inventory = (
                _load_exact_inventory(documents_root, source_root, args.include_relative)
                if args.include_relative
                else _load_l4_inventory(source_root)
            )
            plan = build_plan(
                documents_root=documents_root,
                source_root=source_root,
                target_root=args.target_root,
                inventory=inventory,
                consumer_receipt=receipt,
                now=args.now,
                selected_kinds=set(args.artifact_kind) if args.artifact_kind else None,
                exact_relative_paths=args.include_relative or None,
            )
            result = apply_plan(plan) if args.apply else plan
    except (OSError, UnicodeError, ValueError, QuarantineError) as exc:
        payload = {"schema": SCHEMA, "status": "failed", "error": str(exc)}
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True) if args.json else f"documents runtime quarantine: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True) if args.json else f"documents runtime quarantine: {result['status']} {result['summary']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
