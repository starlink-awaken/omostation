"""Workspace-owned aggregate replacement for the learning L4 control plane."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Final

from .documents_learning_control import ControlError, plan_decay

SCHEMA: Final = "documents.learning-control-plane.v1"
LEARNING_RELATIVE: Final = "@学习进化"
MODES: Final = ("check", "health", "control-loop", "signals", "bus", "sync", "lessons", "decay", "all")
_CONTROL_SPECIAL: Final = frozenset({"INDEX.md", "kos-index.md", "signals.md"})
_DATE_PREFIX = re.compile(r"^(\d{4}-\d{2}-\d{2})-")


class ControlPlaneError(ValueError):
    """Raised when the learning control-plane owner cannot safely inspect a root."""


def _roots(documents_root: str | Path, workspace_root: str | Path) -> tuple[Path, Path]:
    documents = Path(documents_root).expanduser()
    workspace = Path(workspace_root).expanduser()
    if not documents.is_dir() or documents.is_symlink():
        raise ControlPlaneError("Documents root must be a regular directory")
    if not workspace.is_dir() or workspace.is_symlink():
        raise ControlPlaneError("Workspace root must be a regular directory")
    documents = documents.resolve()
    workspace = workspace.resolve()
    if documents == workspace or documents.is_relative_to(workspace) or workspace.is_relative_to(documents):
        raise ControlPlaneError("Documents and Workspace roots must be disjoint")
    return documents, workspace


def _learning_root(documents: Path) -> Path:
    raw = documents / LEARNING_RELATIVE
    if raw.is_symlink():
        raise ControlPlaneError("learning root must not be a symlink")
    root = raw.resolve()
    if not root.is_relative_to(documents) or not root.is_dir() or root.is_symlink():
        raise ControlPlaneError("learning root must be a regular directory below Documents")
    return root


def _regular_files(root: Path, *, suffix: str | None = None) -> list[Path]:
    files = [path for path in root.rglob("*") if path.is_file() and not path.is_symlink()]
    return sorted(path for path in files if suffix is None or path.suffix == suffix)


def _direct_markdown(root: Path, *, excluded: frozenset[str] = frozenset()) -> list[Path]:
    return sorted(
        path
        for path in root.iterdir()
        if path.is_file() and not path.is_symlink() and path.suffix == ".md" and path.name not in excluded
    )


def _date_age(path: Path, today: date) -> int | None:
    match = _DATE_PREFIX.match(path.name)
    if match:
        try:
            return max(0, (today - date.fromisoformat(match.group(1))).days)
        except ValueError:
            return None
    try:
        return max(0, (today - datetime.fromtimestamp(path.stat().st_mtime).date()).days)
    except OSError:
        return None


def _base(mode: str, *, status: str, summary: dict[str, Any], error: str | None = None) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "mode": mode,
        "status": status,
        "writes_documents": False,
        "summary": summary,
        "error": error,
    }


def _check(learning: Path, mode: str) -> dict[str, Any]:
    controls = _direct_markdown(learning / "_control", excluded=_CONTROL_SPECIAL)
    missing = {"title": 0, "status": 0, "type": 0, "owner": 0}
    for path in controls:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        frontmatter = text.split("---", 2)[1] if text.startswith("---") and "---" in text[3:] else ""
        for field in missing:
            if not re.search(rf"(?m)^\s*{field}\s*:", frontmatter):
                missing[field] += 1
    total_missing = sum(missing.values())
    return _base(
        mode,
        status="attention" if total_missing else "ok",
        summary={"control_file_count": len(controls), "missing_field_count": total_missing, "missing_fields": missing},
    )


def _health(learning: Path, today: date, mode: str) -> dict[str, Any]:
    inbox = [
        path
        for path in (learning / "_inbox").iterdir()
        if path.is_file() and path.suffix == ".md" and path.name != "CLAUDE.md"
    ]
    concepts = _regular_files(learning / "_knowledge" / "50-concepts", suffix=".md")
    lessons = _regular_files(learning / "_knowledge" / "40-lessons" / "lessons", suffix=".md")
    ages = [age for path in lessons if (age := _date_age(path, today)) is not None]
    latest_age = min(ages) if ages else None
    findings = int(bool(inbox)) + int(latest_age is not None and latest_age > 14)
    return _base(
        mode,
        status="attention" if findings else "ok",
        summary={
            "inbox_markdown_count": len(inbox),
            "concept_file_count": len(concepts),
            "lesson_file_count": len(lessons),
            "latest_lesson_age_days": latest_age,
            "finding_count": findings,
        },
    )


def _control_loop(learning: Path, mode: str) -> dict[str, Any]:
    control = learning / "_control"
    required = ("STATE.md", "signals.md", "TIMELINE.md", "INDEX.md", "control-rules.md", "router.md")
    present = sum((control / name).is_file() for name in required)
    kems_rules = learning / "_knowledge" / "10-systems" / "KEMS" / "_control" / "control-rules.md"
    return _base(
        mode,
        status="ok" if present == len(required) and kems_rules.is_file() else "attention",
        summary={
            "required_file_count": len(required),
            "present_file_count": present,
            "kems_control_rules_present": kems_rules.is_file(),
        },
    )


def _signals(learning: Path, mode: str) -> dict[str, Any]:
    path = learning / "_control" / "signals.md"
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return _base(
            mode,
            status="unavailable",
            summary={"signal_count": 0, "real_signal_count": 0, "noise_count": 0},
            error="signals_unavailable",
        )
    total = text.count("message:")
    real = len(re.findall(r"(?m)^\s*real:\s*true\s*$", text))
    return _base(
        mode,
        status="ok",
        summary={"signal_count": total, "real_signal_count": real, "noise_count": max(0, total - real)},
    )


def _sync(documents: Path, mode: str) -> dict[str, Any]:
    path = documents / "@驾驶舱" / "_control" / "SIGNALS.md"
    try:
        text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
    except OSError:
        text = ""
    pending = len(re.findall(r"vault\.upgrade|cockpit\.audit", text))
    return _base(
        mode,
        status="attention" if pending else "ok",
        summary={"cockpit_signal_file_present": path.is_file(), "pending_cross_domain_signal_count": pending},
    )


def _lessons(learning: Path, today: date, mode: str) -> dict[str, Any]:
    paths = _regular_files(learning / "_knowledge" / "40-lessons" / "lessons", suffix=".md")
    ages = [age for path in paths if (age := _date_age(path, today)) is not None]
    latest_age = min(ages) if ages else None
    return _base(
        mode,
        status="attention" if latest_age is None or latest_age > 14 else "ok",
        summary={"lesson_file_count": len(paths), "latest_lesson_age_days": latest_age},
    )


def _decay(documents: Path, workspace: Path, today: date, mode: str) -> dict[str, Any]:
    plan = plan_decay(documents, today=today, workspace_root=workspace)
    candidate_count = int(plan.get("candidate_count", plan.get("decay_candidate_count", 0)))
    orphan_count = int(plan.get("orphan_concept_count", 0))
    payload = _base(
        mode,
        status="attention" if candidate_count or orphan_count else "ok",
        summary={
            "delegated_owner": "documents-learning-decay",
            "candidate_count": candidate_count,
            "inventory_count": int(plan.get("inventory_count", plan.get("concept_file_count", 0))),
            "fingerprint": plan.get("fingerprint"),
        },
    )
    payload["delegated_owner"] = "documents-learning-decay"
    payload["owner_status"] = plan.get("status")
    for field in ("orphan_concept_count", "referenced_concept_count", "staleness_counts"):
        if field in plan:
            payload[field] = plan[field]
    return payload


def inspect_control_plane(
    documents_root: str | Path,
    *,
    workspace_root: str | Path,
    mode: str,
    today: date | None = None,
) -> dict[str, Any]:
    """Run one aggregate-only learning control-plane inspection."""
    if mode not in MODES:
        raise ControlPlaneError("unsupported learning control-plane mode")
    documents, workspace = _roots(documents_root, workspace_root)
    learning = _learning_root(documents)
    checked_on = today or date.today()
    if mode == "all":
        children = {
            child: inspect_control_plane(documents, workspace_root=workspace, mode=child, today=checked_on)
            for child in MODES
            if child != "all"
        }
        attention = [child for child, result in children.items() if result["status"] == "attention"]
        unavailable = [child for child, result in children.items() if result["status"] == "unavailable"]
        return {
            **_base(
                "all",
                status="unavailable" if unavailable else ("attention" if attention else "ok"),
                summary={"mode_count": len(children), "attention_modes": attention, "unavailable_modes": unavailable},
            ),
            "checked_on": checked_on.isoformat(),
            "checks": children,
        }
    if mode == "check":
        result = _check(learning, mode)
    elif mode == "health":
        result = _health(learning, checked_on, mode)
    elif mode == "control-loop":
        result = _control_loop(learning, mode)
    elif mode in {"signals", "bus"}:
        result = _signals(learning, mode)
        if mode == "bus":
            result["summary"] = {**result["summary"], "bus": "documents-learning-signals"}
    elif mode == "sync":
        result = _sync(documents, mode)
    elif mode == "lessons":
        result = _lessons(learning, checked_on, mode)
    else:
        result = _decay(documents, workspace, checked_on, mode)
    result["checked_on"] = checked_on.isoformat()
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=MODES)
    parser.add_argument("--documents-root", type=Path, default=Path.home() / "Documents")
    parser.add_argument("--workspace-root", type=Path, default=Path.cwd())
    parser.add_argument("--today")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        checked_on = date.fromisoformat(args.today) if args.today else date.today()
        payload = inspect_control_plane(
            args.documents_root, workspace_root=args.workspace_root, mode=args.mode, today=checked_on
        )
    except (ControlPlaneError, ControlError, ValueError) as exc:
        payload = _base(args.mode, status="unavailable", summary={}, error="control_plane_unavailable")
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        else:
            print(f"learning-control-plane: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True) if args.json else f"{args.mode}: {payload['status']}")
    return 0 if payload["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
