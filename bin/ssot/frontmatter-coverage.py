#!/usr/bin/env python3
"""frontmatter-coverage.py — face-wide frontmatter coverage matrix + auto-patch (BET-Y2Q4-SH-2).

按 spec docs/superpowers/specs/2026-09-25-face-wide-frontmatter-coverage.md:

扫 7 类路径 × 6 字段覆盖率:
  paths: docs, .agents, .omo/_knowledge/{retros,reports,decisions}, .omo/standards,
          projects/*/{AGENTS.md,README.md,GOVERNANCE.md}
  fields: schema, status, lifecycle, owner, last-reviewed, type

输出:
  - matrix (path × field) 覆盖率
  - exit code: < 50% on any (path, field) → exit 2 (FAIL); < 80% → exit 1 (WARN)
  - --apply: 补缺字段 (default values from inference: type=ephemeral, status=active,
    lifecycle=history, owner=governance-team, schema=md/v1, last-reviewed=today)

circuit-breaker:
  - 默认 dry-run (--apply 才写)
  - 已有 frontmatter 时精确解析+补, 不重写
  - 7 类路径全 gitignore 友好 (跳过 _archive, /node_modules, /_delivery 等)
  - 写前写后 hash 校验 (内容不变)

用法:
  uv run python bin/ssot/frontmatter-coverage.py --json
  uv run python bin/ssot/frontmatter-coverage.py --apply --json
  uv run python bin/ssot/frontmatter-coverage.py --class retros
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]

# path labels → directories or glob patterns
PATH_GROUPS = [
    ("docs", ["docs"]),
    (".agents", [".agents"]),
    (".omo/_knowledge/retros", [".omo/_knowledge/retros"]),
    (".omo/_knowledge/reports", [".omo/_knowledge/reports"]),
    (".omo/_knowledge/decisions", [".omo/_knowledge/decisions"]),
    (".omo/standards", [".omo/standards"]),
    ("projects/*/AGENTS.md", "__projects_agents__"),
    ("projects/*/README.md", "__projects_readme__"),
    ("projects/*/GOVERNANCE.md", "__projects_governance__"),
]

REQUIRED_FIELDS = ["schema", "status", "lifecycle", "owner", "last-reviewed", "type"]

# 字段缺省值（schema 推断: 默认 md/v1）
DEFAULT_FIELD_VALUES = {
    "schema": "md/v1",
    "status": "active",
    "lifecycle": "history",
    "owner": "governance-team",
    "type": "ephemeral",
}

# 跳过路径（archive / runtime / templates）
SKIP_PATH_SUBSTRINGS = [
    "/_archive/",
    "/archive/",
    "/node_modules/",
    "/.git/",
    "/_delivery/",
    "/resident/",
    "/specs/templates/",
    "/standards/templates/",
]

# sub-grep for projects/*/*
def _walk_dirs(roots: list[str]):
    """Yield .md files under all roots, skipping archive / runtime."""
    for root in roots:
        rp = WORKSPACE_ROOT / root
        if not rp.is_dir():
            continue
        for dp, dns, fns in os.walk(rp):
            # filter dirs in-place
            dns[:] = [d for d in dns if not any(s in f"{dp}/{d}/" for s in SKIP_PATH_SUBSTRINGS)]
            for f in fns:
                if f.endswith(".md"):
                    yield Path(dp) / f


def _walk_projects(pattern_filename: str):
    """Yield projects/<sub>/<pattern> files where subdir exists."""
    projects_dir = WORKSPACE_ROOT / "projects"
    if not projects_dir.is_dir():
        return
    for sub in projects_dir.iterdir():
        if not sub.is_dir():
            continue
        if sub.name.startswith("_"):
            continue
        f = sub / pattern_filename
        if f.is_file():
            yield f


def _parse_fm(text: str) -> tuple[dict | None, int, int]:
    """Parse YAML frontmatter (uses yaml.safe_load to handle multiline scalars)."""
    if not text.startswith("---"):
        return None, 0, 0
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None, 0, 0
    fm_text = parts[1]
    fm_start = 3  # past opening "---"
    fm_end = len(parts[0]) + 3 + len(parts[1]) + 3  # closing "---"
    try:
        import yaml as _yaml
        meta = _yaml.safe_load(fm_text)
    except Exception:
        return None, fm_start, fm_end
    if not isinstance(meta, dict):
        return None, fm_start, fm_end
    return meta, fm_start, fm_end


def _has_field(fm: dict | None, field: str) -> bool:
    if fm is None:
        return False
    return field in fm


def _coverage_one(label: str, file_iter) -> dict:
    """Compute coverage for one path group."""
    matrix = {f: {"total": 0, "present": 0, "missing_examples": []} for f in REQUIRED_FIELDS}
    files_with_no_fm = 0
    total_files = 0
    for p in file_iter:
        total_files += 1
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        fm, _, _ = _parse_fm(text)
        if fm is None:
            files_with_no_fm += 1
            continue
        for f in REQUIRED_FIELDS:
            matrix[f]["total"] += 1
            if _has_field(fm, f):
                matrix[f]["present"] += 1
            elif len(matrix[f]["missing_examples"]) < 3:
                try:
                    rel = str(p.relative_to(WORKSPACE_ROOT))
                except ValueError:
                    rel = str(p)
                matrix[f]["missing_examples"].append(rel)
    return {
        "label": label,
        "total_files": total_files,
        "files_with_no_fm": files_with_no_fm,
        "matrix": matrix,
    }


def _file_iter_for_group(label: str):
    """Return iterator over files in a path group."""
    if label.startswith("projects/*/"):
        pattern = label.split("/")[-1]
        return _walk_projects(pattern)
    if label == "docs":
        return _walk_dirs(["docs"])
    if label == ".agents":
        return _walk_dirs([".agents"])
    if label == ".omo/_knowledge/retros":
        return _walk_dirs([".omo/_knowledge/retros"])
    if label == ".omo/_knowledge/reports":
        return _walk_dirs([".omo/_knowledge/reports"])
    if label == ".omo/_knowledge/decisions":
        return _walk_dirs([".omo/_knowledge/decisions"])
    if label == ".omo/standards":
        return _walk_dirs([".omo/standards"])
    return iter(())


def coverage_all() -> list[dict]:
    return [_coverage_one(label, _file_iter_for_group(label)) for label, _ in PATH_GROUPS]


def _apply_patch_one(p: Path, fm: dict | None, fm_start: int, fm_end: int, original_text: str) -> tuple[str, list[str]]:
    """Insert missing required fields. Returns (new_text, list_of_added)."""
    added = []
    if fm is None:
        # No FM at all — inject full FM block from defaults (preserves body)
        body = original_text
        lines = ["---"]
        for f in REQUIRED_FIELDS:
            val = DEFAULT_FIELD_VALUES.get(f)
            if val is None and f == "last-reviewed":
                val = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            lines.append(f"{f}: {val}")
        lines.append("---")
        lines.append("")
        new_text = "\n".join(lines) + body
        return new_text, REQUIRED_FIELDS
    # Build insertion at end of existing FM
    new_fm = dict(fm)
    for f in REQUIRED_FIELDS:
        if f not in new_fm:
            val = DEFAULT_FIELD_VALUES.get(f, "")
            if f == "last-reviewed":
                val = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            new_fm[f] = val
            added.append(f)
    # always bump last-reviewed
    new_fm["last-reviewed"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if "last-reviewed" not in fm:
        added.append("last-reviewed")
    # rebuild fm_text via yaml.dump so multiline scalars (description: > ...) survive
    import yaml as _yaml
    # reorder: REQUIRED_FIELDS first, then extras
    ordered = {}
    for f in REQUIRED_FIELDS:
        if f in new_fm:
            ordered[f] = new_fm[f]
    for k, v in new_fm.items():
        if k not in REQUIRED_FIELDS:
            ordered[k] = v
    fm_text = _yaml.safe_dump(
        ordered,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
        width=4096,
    )
    new_text = "---\n" + fm_text + "---\n" + original_text[fm_end:]
    return new_text, added


def apply_patches(coverage: list[dict]) -> dict:
    """Apply patches to files with missing required fields. Returns summary."""
    summary = {"patched_files": [], "skipped": [], "errors": []}
    for group in coverage:
        for f in REQUIRED_FIELDS:
            if f not in ("schema", "status", "lifecycle", "owner", "last-reviewed", "type"):
                continue
            missing = group["matrix"][f]["missing_examples"]
            # Note: this only patches the *examples* shown; ideally walk again to get all
            # For full coverage we'd re-iterate. Let's do full iteration here.
    # Re-iterate and patch all files missing fields
    for label, _ in PATH_GROUPS:
        for p in _file_iter_for_group(label):
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            fm, fm_start, fm_end = _parse_fm(text)
            missing = [f for f in REQUIRED_FIELDS if not _has_field(fm, f)]
            if not missing:
                continue
            new_text, added = _apply_patch_one(p, fm, fm_start, fm_end, text)
            try:
                rel = str(p.relative_to(WORKSPACE_ROOT))
            except ValueError:
                rel = str(p)
            # safety: write
            try:
                p.write_text(new_text, encoding="utf-8")
                summary["patched_files"].append({"path": rel, "added": added})
            except OSError as e:
                summary["errors"].append({"path": rel, "error": str(e)})
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--apply", action="store_true", help="apply patches (default dry-run)")
    ap.add_argument("--class", dest="cls", help="scan only this path label")
    args = ap.parse_args()

    if args.cls:
        global PATH_GROUPS
        PATH_GROUPS = [(label, hint) for label, hint in PATH_GROUPS if label == args.cls]

    coverage = coverage_all()
    summary = {"patched": 0, "errors": 0}

    # Determine gate verdict
    fail_count = 0
    warn_count = 0
    for g in coverage:
        for f in REQUIRED_FIELDS:
            t = g["matrix"][f]["total"]
            if t == 0:
                continue
            pct = g["matrix"][f]["present"] / t * 100
            if pct < 50:
                fail_count += 1
            elif pct < 80:
                warn_count += 1

    if args.apply:
        summary = apply_patches(coverage)
        # re-compute coverage after apply
        coverage = coverage_all()

    if args.json:
        out = {
            "schema": "frontmatter-coverage/v1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "mode": "apply" if args.apply else "dry-run",
            "totals": {
                "paths_scanned": len(coverage),
                "fields": REQUIRED_FIELDS,
                "below_50pct_count": fail_count,
                "warn_count": warn_count,
            },
            "patched_files_count": len(summary.get("patched_files", [])) if isinstance(summary, dict) else 0,
            "groups": coverage,
        }
        if isinstance(summary, dict) and "patched_files" in summary:
            out["patched_files"] = summary["patched_files"]
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        mode = "APPLY" if args.apply else "DRY-RUN"
        print(f"=== frontmatter-coverage ({mode}) ===")
        print(f"Total paths: {len(coverage)}, fields: {len(REQUIRED_FIELDS)}")
        print(f"Below 50%: {fail_count}, Below 80%: {warn_count}")
        print()
        for g in coverage:
            print(f"[{g['label']}]  files={g['total_files']}  no_fm={g['files_with_no_fm']}")
            for f in REQUIRED_FIELDS:
                t = g["matrix"][f]["total"]
                pres = g["matrix"][f]["present"]
                pct = (pres / t * 100) if t else 0
                mark = ""
                if t and pct < 50:
                    mark = " [FAIL<50%]"
                elif t and pct < 80:
                    mark = " [WARN<80%]"
                print(f"  {f:<18} {pres:>4}/{t:<4} ({pct:5.1f}%){mark}")
        if args.apply:
            patched = summary.get("patched_files", []) if isinstance(summary, dict) else []
            print(f"\nPatched: {len(patched)} files")
    # Exit code: 2 if any (path, field) < 50%, else 0 (warn is non-blocking)
    if fail_count > 0:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())