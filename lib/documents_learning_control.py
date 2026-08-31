"""Workspace-owned, human-gated learning content operations."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Final

SCHEMA: Final = "documents.learning-content-control.v1"
CONCEPTS_RELATIVE: Final = "@学习进化/_knowledge/50-concepts"
INBOX_RELATIVE: Final = "@学习进化/_inbox"
_EXCLUDED_CONCEPT_NAMES: Final = frozenset({"README.md", "INDEX.md", "_index.md"})
_EXCLUDED_INBOX_NAMES: Final = frozenset({".DS_Store", "CLAUDE.md", "inbox-router.sh"})
_STATUS = re.compile(r"^\s*status\s*:\s*(.*?)\s*$", re.IGNORECASE)
_REVIEWED = re.compile(r"^\s*last-reviewed\s*[:：]\s*['\"]?(\d{4}-\d{2}-\d{2})['\"]?\s*$", re.IGNORECASE)
_STALE_SINCE = re.compile(r"^\s*stale_since\s*:", re.IGNORECASE)


class ControlError(ValueError):
    """A guarded learning operation cannot proceed safely."""


def _resolved_root(path: str | Path, *, label: str) -> Path:
    raw = Path(path).expanduser()
    if not raw.is_dir() or raw.is_symlink():
        raise ControlError(f"{label} must be a regular directory")
    return raw.resolve()


def _validate_roots(documents_root: str | Path, workspace_root: str | Path | None = None) -> tuple[Path, Path | None]:
    documents = _resolved_root(documents_root, label="Documents root")
    if workspace_root is None:
        return documents, None
    workspace = _resolved_root(workspace_root, label="Workspace root")
    if documents == workspace or documents.is_relative_to(workspace) or workspace.is_relative_to(documents):
        raise ControlError("Documents and Workspace roots must be disjoint")
    return documents, workspace


def _resolve_child(documents: Path, relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts or candidate == Path("."):
        raise ControlError("content scope must be relative and non-traversing")
    raw = documents / candidate
    if raw.is_symlink():
        raise ControlError("content scope must not be a symlink")
    resolved = raw.resolve()
    if not resolved.is_relative_to(documents) or not resolved.is_dir() or resolved.is_symlink():
        raise ControlError("content scope must be a regular directory below Documents")
    return resolved


def _sha256_bytes(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()


def _mode(path: Path) -> str:
    return oct(os.stat(path, follow_symlinks=False).st_mode & 0o7777)


def _inventory(documents: Path, paths: list[Path]) -> tuple[list[dict[str, Any]], str]:
    entries: list[dict[str, Any]] = []
    for path in sorted(paths):
        try:
            content = path.read_bytes()
            stat = path.stat()
        except OSError as exc:
            raise ControlError("content inventory became unreadable") from exc
        relative = path.relative_to(documents).as_posix()
        digest = _sha256_bytes(content)
        mode = _mode(path)
        entries.append(
            {
                "relative_path": relative,
                "sha256": digest,
                "bytes": len(content),
                "mode": mode,
                "_fingerprint_line": f"{relative}\0{mode}\0{stat.st_size}\0{digest}\n",
            }
        )
    fingerprint = (
        "sha256:" + hashlib.sha256("".join(entry.pop("_fingerprint_line") for entry in entries).encode()).hexdigest()
    )
    return entries, fingerprint


def _concept_files(root: Path) -> list[Path]:
    return [
        path
        for path in sorted(root.rglob("*.md"))
        if path.is_file()
        and not path.is_symlink()
        and path.name not in _EXCLUDED_CONCEPT_NAMES
        and not path.name.startswith("_ontology")
    ]


def _inbox_files(root: Path) -> list[Path]:
    return [
        path
        for path in sorted(root.iterdir())
        if path.is_file() and not path.is_symlink() and path.name not in _EXCLUDED_INBOX_NAMES
    ]


def _frontmatter(path: Path) -> tuple[list[str], int, int] | None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    except (OSError, UnicodeError) as exc:
        raise ControlError("concept file is unreadable") from exc
    if not lines or lines[0].strip() != "---":
        return None
    for end in range(1, len(lines)):
        if lines[end].strip() == "---":
            return lines, 0, end
    return None


def _frontmatter_value(lines: list[str], start: int, end: int, pattern: re.Pattern[str]) -> str | None:
    for line in lines[start + 1 : end]:
        match = pattern.match(line.rstrip("\r\n"))
        if match:
            return match.group(1).strip(" '\"")
    return None


def _last_reviewed(path: Path, lines: list[str], start: int, end: int) -> date:
    value = _frontmatter_value(lines, start, end, _REVIEWED)
    if value:
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).date()
    except OSError as exc:
        raise ControlError("concept timestamp is unavailable") from exc


def _insert_stale_since(path: Path, checked_on: date) -> str:
    parsed = _frontmatter(path)
    if parsed is None:
        raise ControlError("candidate concept has no valid frontmatter")
    lines, start, end = parsed
    if any(_STALE_SINCE.match(line.rstrip("\r\n")) for line in lines[start + 1 : end]):
        raise ControlError("candidate concept already has stale_since")
    status_index = next((index for index in range(start + 1, end) if _STATUS.match(lines[index].rstrip("\r\n"))), None)
    if status_index is None:
        raise ControlError("candidate concept has no status field")
    newline = "\r\n" if lines[status_index].endswith("\r\n") else "\n"
    lines.insert(status_index + 1, f"stale_since: {checked_on.isoformat()}{newline}")
    return "".join(lines)


def _concept_candidate(
    documents: Path, path: Path, texts: dict[Path, str], checked_on: date, stale_days: int
) -> dict[str, Any] | None:
    parsed = _frontmatter(path)
    if parsed is None:
        return None
    lines, start, end = parsed
    status = _frontmatter_value(lines, start, end, _STATUS)
    if not status or not status.lower().startswith("draft"):
        return None
    if any(_STALE_SINCE.match(line.rstrip("\r\n")) for line in lines[start + 1 : end]):
        return None
    references = sum(1 for other, text in texts.items() if other != path and path.name in text)
    if references:
        return None
    age_days = (checked_on - _last_reviewed(path, lines, start, end)).days
    if age_days < stale_days:
        return None
    content = path.read_bytes()
    return {
        "relative_path": path.relative_to(documents).as_posix(),
        "sha256": _sha256_bytes(content),
        "bytes": len(content),
        "mode": _mode(path),
        "action": "insert_stale_since",
        "stale_since": checked_on.isoformat(),
    }


def plan_decay(
    documents_root: str | Path,
    *,
    today: date | None = None,
    stale_days: int = 14,
    domain_relative: str = CONCEPTS_RELATIVE,
    workspace_root: str | Path | None = None,
) -> dict[str, Any]:
    """Build a deterministic mark-stale plan without mutating either root."""
    documents, _ = _validate_roots(documents_root, workspace_root)
    if stale_days <= 0:
        raise ControlError("stale_days must be positive")
    checked_on = today or date.today()
    root = _resolve_child(documents, domain_relative)
    paths = _concept_files(root)
    texts = {path: path.read_text(encoding="utf-8", errors="replace") for path in paths}
    inventory, fingerprint = _inventory(documents, paths)
    candidates = [
        candidate for path in paths if (candidate := _concept_candidate(documents, path, texts, checked_on, stale_days))
    ]
    return {
        "schema": SCHEMA,
        "operation": "decay-mark-stale",
        "mode": "dry-run",
        "status": "planned",
        "checked_on": checked_on.isoformat(),
        "stale_days": stale_days,
        "scope": domain_relative,
        "fingerprint": fingerprint,
        "inventory_count": len(inventory),
        "candidate_count": len(candidates),
        "candidates": candidates,
        "error": None,
    }


_INBOX_RULES: Final = (
    (re.compile(r"灵感|洞察|MCP|趋势|未来", re.IGNORECASE), "@学习进化/_archive/灵感顿悟/", "internal"),
    (
        re.compile(r"lesson|教训|经验|复盘|反思|retro", re.IGNORECASE),
        "@学习进化/_knowledge/40-lessons/lessons/",
        "internal",
    ),
    (re.compile(r"pattern|模式|template|模板", re.IGNORECASE), "@学习进化/_knowledge/40-lessons/patterns/", "internal"),
    (re.compile(r"概念|概念卡片|concept", re.IGNORECASE), "@学习进化/_knowledge/50-concepts/", "internal"),
    (re.compile(r"政务|公文|卫健委|医保|分级诊疗", re.IGNORECASE), "@学习进化/_storage/资料库/政务/", "internal"),
    (re.compile(r"书籍|书评|读书", re.IGNORECASE), "@学习进化/_storage/资料库/书籍/", "internal"),
    (re.compile(r"报告|白皮书|调研", re.IGNORECASE), "@学习进化/_storage/资料库/报告/", "internal"),
    (re.compile(r"技巧|订阅|工具|框架", re.IGNORECASE), "@学习进化/_storage/知识订阅/", "internal"),
    (re.compile(r"工作|借调|国转", re.IGNORECASE), "@工作文档/", "deferred_external"),
    (re.compile(r"家庭|生活|育儿|健康|医疗", re.IGNORECASE), "@家庭生活/", "deferred_external"),
    (re.compile(r"创意|创作|小说|文章|作品", re.IGNORECASE), "@创意创作/", "deferred_external"),
)


def _inbox_target(path: Path) -> tuple[str, str]:
    try:
        head = "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[:5])
    except OSError as exc:
        raise ControlError("inbox file is unreadable") from exc
    for pattern, target, disposition in _INBOX_RULES:
        if pattern.search(head):
            return target, disposition
    return "@学习进化/_inbox/_stale/", "internal"


def plan_inbox(
    documents_root: str | Path,
    *,
    inbox_relative: str = INBOX_RELATIVE,
    workspace_root: str | Path | None = None,
) -> dict[str, Any]:
    """Build a deterministic inbox routing plan without moving files."""
    documents, _ = _validate_roots(documents_root, workspace_root)
    root = _resolve_child(documents, inbox_relative)
    paths = _inbox_files(root)
    inventory, fingerprint = _inventory(documents, paths)
    candidates: list[dict[str, Any]] = []
    if len(paths) != len(inventory):  # pragma: no cover - _inventory is one-to-one by contract
        raise ControlError("inbox inventory is inconsistent")
    for path, entry in zip(paths, inventory):
        target, disposition = _inbox_target(path)
        candidates.append(
            {
                "relative_path": entry["relative_path"],
                "sha256": entry["sha256"],
                "bytes": entry["bytes"],
                "mode": entry["mode"],
                "action": "move" if disposition == "internal" else "defer",
                "disposition": disposition,
                "target_relative": target,
            }
        )
    return {
        "schema": SCHEMA,
        "operation": "inbox-route",
        "mode": "dry-run",
        "status": "planned",
        "scope": inbox_relative,
        "fingerprint": fingerprint,
        "inventory_count": len(inventory),
        "candidate_count": len(candidates),
        "candidates": candidates,
        "deferred_external_count": sum(item["disposition"] == "deferred_external" for item in candidates),
        "error": None,
    }


def _atomic_write(path: Path, content: str, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    except BaseException:
        try:
            temporary_path.unlink()
        except OSError:
            pass
        raise


def _write_manifest(path: Path, payload: dict[str, Any]) -> None:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(encoded, encoding="utf-8")
    os.replace(temporary, path)


def _rollback_root(workspace: Path, operation: str) -> Path:
    root = (
        workspace
        / "runtime"
        / "quarantine"
        / f"documents-learning-control-{operation}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"  # noqa: UP017
    )
    root.mkdir(parents=True, exist_ok=False)
    return root


def _current_fingerprint(documents: Path, relative_paths: list[str]) -> str:
    _, fingerprint = _inventory(documents, [documents / relative for relative in relative_paths])
    return fingerprint


def _require_plan(plan: dict[str, Any], expected_fingerprint: str) -> None:
    if plan.get("schema") != SCHEMA or plan.get("status") != "planned":
        raise ControlError("plan schema or status is invalid")
    if plan.get("fingerprint") != expected_fingerprint:
        raise ControlError("expected fingerprint does not match plan")


def _apply_decay(plan: dict[str, Any], documents: Path, workspace: Path) -> dict[str, Any]:
    candidates = plan["candidates"]
    rollback = _rollback_root(workspace, "decay")
    entries: list[dict[str, Any]] = []
    for candidate in candidates:
        source = documents / candidate["relative_path"]
        content = source.read_bytes()
        if _sha256_bytes(content) != candidate["sha256"] or _mode(source) != candidate["mode"]:
            raise ControlError("source changed after plan; refusing decay apply")
        backup = rollback / "originals" / candidate["relative_path"]
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_bytes(content)
        os.chmod(backup, int(candidate["mode"], 8))
        entries.append({**candidate, "backup_relative": backup.relative_to(rollback).as_posix()})
    manifest = {"schema": SCHEMA, "operation": "decay-mark-stale", "status": "prepared", "entries": entries}
    manifest_path = rollback / "manifest.json"
    _write_manifest(manifest_path, manifest)
    applied: list[dict[str, Any]] = []
    try:
        for entry in entries:
            source = documents / entry["relative_path"]
            updated = _insert_stale_since(source, date.fromisoformat(entry["stale_since"]))
            _atomic_write(source, updated, int(entry["mode"], 8))
            applied.append(entry)
    except (OSError, ControlError) as exc:
        for entry in reversed(applied):
            backup = rollback / entry["backup_relative"]
            _atomic_write(documents / entry["relative_path"], backup.read_text(encoding="utf-8"), int(entry["mode"], 8))
        manifest["status"] = "rolled_back"
        _write_manifest(manifest_path, manifest)
        raise ControlError(f"decay mutation failed and rolled back: {exc}") from exc
    manifest["status"] = "completed"
    _write_manifest(manifest_path, manifest)
    return {
        **plan,
        "mode": "apply",
        "status": "applied",
        "rollback_manifest": str(manifest_path),
        "manifest_sha256": _sha256_bytes(manifest_path.read_bytes()),
    }


def _apply_inbox(plan: dict[str, Any], documents: Path, workspace: Path) -> dict[str, Any]:
    movable = [entry for entry in plan["candidates"] if entry["disposition"] == "internal"]
    destinations = [(documents / entry["target_relative"] / Path(entry["relative_path"]).name) for entry in movable]
    if any(destination.exists() or destination.is_symlink() for destination in destinations):
        raise ControlError("inbox target collision detected before mutation")
    rollback = _rollback_root(workspace, "inbox")
    entries: list[dict[str, Any]] = []
    for entry in movable:
        source = documents / entry["relative_path"]
        if _sha256_bytes(source.read_bytes()) != entry["sha256"] or _mode(source) != entry["mode"]:
            raise ControlError("source changed after plan; refusing inbox apply")
        entries.append(
            {**entry, "target_path": (Path(entry["target_relative"]) / Path(entry["relative_path"]).name).as_posix()}
        )
    manifest = {"schema": SCHEMA, "operation": "inbox-route", "status": "prepared", "entries": entries}
    manifest_path = rollback / "manifest.json"
    _write_manifest(manifest_path, manifest)
    moved: list[dict[str, Any]] = []
    try:
        for entry in entries:
            source = documents / entry["relative_path"]
            target = documents / entry["target_path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            source.rename(target)
            moved.append(entry)
    except (OSError, ControlError) as exc:
        for entry in reversed(moved):
            (documents / entry["target_path"]).rename(documents / entry["relative_path"])
        manifest["status"] = "rolled_back"
        _write_manifest(manifest_path, manifest)
        raise ControlError(f"inbox mutation failed and rolled back: {exc}") from exc
    manifest["status"] = "completed"
    _write_manifest(manifest_path, manifest)
    return {
        **plan,
        "mode": "apply",
        "status": "applied",
        "moved_count": len(moved),
        "rollback_manifest": str(manifest_path),
        "manifest_sha256": _sha256_bytes(manifest_path.read_bytes()),
    }


def apply_plan(
    plan: dict[str, Any],
    *,
    documents_root: str | Path,
    workspace_root: str | Path,
    expected_fingerprint: str,
) -> dict[str, Any]:
    """Apply a previously reviewed plan only when its source fingerprint is unchanged."""
    workspace = _resolved_root(workspace_root, label="Workspace root")
    documents = _resolved_root(documents_root, label="Documents root")
    _validate_roots(documents, workspace)
    scope = plan.get("scope")
    if not isinstance(scope, str):
        raise ControlError("plan scope is invalid")
    operation = plan.get("operation")
    if operation == "decay-mark-stale":
        fresh = plan_decay(
            documents,
            today=date.fromisoformat(plan["checked_on"]),
            stale_days=int(plan["stale_days"]),
            domain_relative=scope,
        )
    elif operation == "inbox-route":
        fresh = plan_inbox(documents, inbox_relative=scope)
    else:
        raise ControlError("unsupported learning operation")
    _require_plan(plan, expected_fingerprint)
    if fresh["fingerprint"] != expected_fingerprint or fresh["candidates"] != plan["candidates"]:
        raise ControlError("source fingerprint or candidate set changed after plan")
    if operation == "decay-mark-stale":
        return _apply_decay(plan, documents, workspace)
    return _apply_inbox(plan, documents, workspace)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="documents-domain-owner-job learning-control")
    sub = parser.add_subparsers(dest="domain", required=True)
    decay = sub.add_parser("decay")
    decay_sub = decay.add_subparsers(dest="decay_command", required=True)
    decay_cmd = decay_sub.add_parser("mark-stale")
    decay_cmd.add_argument("--documents-root", type=Path, default=Path.home() / "Documents")
    decay_cmd.add_argument("--workspace-root", type=Path, default=Path.cwd())
    decay_cmd.add_argument("--days", type=int, default=14)
    decay_cmd.add_argument("--today")
    inbox = sub.add_parser("inbox")
    inbox_sub = inbox.add_subparsers(dest="inbox_command", required=True)
    inbox_cmd = inbox_sub.add_parser("route")
    inbox_cmd.add_argument("--documents-root", type=Path, default=Path.home() / "Documents")
    inbox_cmd.add_argument("--workspace-root", type=Path, default=Path.cwd())
    for command in (decay_cmd, inbox_cmd):
        mode = command.add_mutually_exclusive_group()
        mode.add_argument("--dry-run", action="store_true")
        mode.add_argument("--apply", action="store_true")
        command.add_argument("--expected-fingerprint")
        command.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.domain == "decay":
            today = date.fromisoformat(args.today) if args.today else date.today()
            plan = plan_decay(
                args.documents_root, today=today, stale_days=args.days, workspace_root=args.workspace_root
            )
        else:
            plan = plan_inbox(args.documents_root, workspace_root=args.workspace_root)
        if args.apply:
            if not args.expected_fingerprint:
                raise ControlError("--apply requires --expected-fingerprint from a prior dry-run")
            result = apply_plan(
                plan,
                documents_root=args.documents_root,
                workspace_root=args.workspace_root,
                expected_fingerprint=args.expected_fingerprint,
            )
        else:
            result = plan
    except (ControlError, OSError, ValueError) as exc:
        result = {
            "schema": SCHEMA,
            "status": "blocked",
            "mode": "apply" if getattr(args, "apply", False) else "dry-run",
            "error": str(exc),
        }
        if getattr(args, "json", False):
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        else:
            print(f"learning-control: {exc}", file=os.sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print(f"{result['operation']}: {result['status']} candidates={result.get('candidate_count', 0)}")
    return 0
