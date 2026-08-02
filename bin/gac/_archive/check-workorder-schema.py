#!/usr/bin/env python3
"""check-workorder-schema: enforce the workorder authoring standard.

Reads every yaml under `.omo/tasks/{planned,active}/` and verifies
the required fields defined in
`.omo/standards/workorder-authoring-standard.md` are present.

Status:
  - exit 0 = all good
  - exit 1 = one or more new tasks missing required fields

Skipped:
  - tasks in `closed/`, `archived/`, `done/` (historical)
  - tasks with `status: archived` or `status: closed`
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

WORKSPACE = Path(__file__).resolve().parents[2]
TASKS_ROOT = WORKSPACE / ".omo" / "tasks"
SCOPES = ("planned", "active")

REQUIRED_FIELDS = (
    "id",
    "title",
    "description",
    "track",
    "task_type",
    "appetite",
    "授权范围",
    "需人类拍板项",
    "熔断条件",
    "验收标准",
    "evidence_required",
    "risk_level",
    "allowed_operation_level",
    "human_approval_required",
    "status",
    "priority",
    "source_docs",
)


def _collect_tasks() -> list[Path]:
    files: list[Path] = []
    for scope in SCOPES:
        d = TASKS_ROOT / scope
        if d.is_dir():
            files.extend(sorted(d.glob("*.yaml")))
    return files


def _check(path: Path) -> list[str]:
    missing: list[str] = []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        return [f"yaml parse error: {exc}"]
    if data.get("status") in {"archived", "closed"}:
        return []  # exempt
    for f in REQUIRED_FIELDS:
        if f not in data:
            missing.append(f)
    # Cross-check: 验收标准 / acceptance_criteria must be non-empty list.
    acc = data.get("验收标准") or data.get("acceptance_criteria") or []
    if isinstance(acc, list) and len(acc) == 0:
        missing.append("验收标准(non-empty)")
    return missing


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit 1 on any non-conforming workorder (default: warn-only).",
    )
    args = parser.parse_args(argv)

    tasks = _collect_tasks()
    findings: list[dict] = []
    summary = {"scanned": 0, "ok": 0, "non_conforming": 0}
    for path in tasks:
        summary["scanned"] += 1
        missing = _check(path)
        if not missing:
            summary["ok"] += 1
            continue
        summary["non_conforming"] += 1
        findings.append({
            "path": str(path.relative_to(WORKSPACE)),
            "missing_fields": missing,
        })

    # Default: warn-only (exit 0). The standard is new (2026-07-28) and
    # existing workorders pre-date it; blocking them all on day one
    # would penalise the very history the gate is meant to protect.
    # Promote to strict after the grace period by passing --strict
    # in the CI definition (a G2 follow-up).
    ok = not findings or not args.strict
    report = {
        "ok": ok,
        "mode": "strict" if args.strict else "warn",
        "summary": summary,
        "findings": findings,
    }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"check-workorder-schema: {'PASS' if ok else 'FAIL'} (mode={report['mode']})")
        print(
            f"  scanned={summary['scanned']} ok={summary['ok']} "
            f"non_conforming={summary['non_conforming']}"
        )
        for f in findings[:20]:
            print(f"  - {f['path']}: missing {f['missing_fields']}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
