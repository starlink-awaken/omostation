#!/usr/bin/env python3
"""Auto-fix document frontmatter based on document-governance.yaml rules.

Usage:
    python3 bin/ssot/doc-governance-autofix.py [--dry-run] [--paths <path>...]

Adds missing frontmatter fields (status, lifecycle, owner, last-reviewed) to
documents governed by the document-governance.yaml registry.
"""

from __future__ import annotations

import argparse
import fnmatch
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None

WORKSPACE = Path(__file__).resolve().parents[2]
REGISTRY_PATH = WORKSPACE / ".omo/_truth/registry/document-governance.yaml"
TODAY = datetime.now(UTC).date().isoformat()

DEFAULT_EXCLUDES = (
    ".git/",
    ".venv/",
    "node_modules/",
    "docs/generated/",
    ".omo/_delivery/",
    "runtime/",
    "docs/superpowers/specs/templates/",
)


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    if yaml is None:
        raise RuntimeError("pyyaml is required")
    documents = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
    merged: dict[str, Any] = {}
    for document in documents:
        if isinstance(document, dict):
            merged.update(document)
    return merged


def parse_frontmatter(content: str) -> tuple[dict[str, Any] | None, bool, int]:
    """Return (metadata, has_frontmatter, end_line_idx).

    end_line_idx is the index of the closing --- (or -1 if no frontmatter).
    """
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, False, -1
    try:
        end = next(index for index in range(1, len(lines)) if lines[index].strip() == "---")
    except StopIteration:
        return None, True, -1
    try:
        data = yaml.safe_load("\n".join(lines[1:end])) or {}
    except yaml.YAMLError:
        return None, True, end
    return (data if isinstance(data, dict) else None), True, end


def match_surface(rel: str, registry: dict[str, Any]) -> dict[str, Any] | None:
    """Find the surface configuration that matches a relative path."""
    for surface in registry.get("surfaces", []):
        patterns = surface.get("patterns", [])
        excludes = surface.get("excludes", [])
        for pattern in patterns:
            if fnmatch.fnmatch(rel, pattern):
                if any(fnmatch.fnmatch(rel, ex) for ex in excludes):
                    continue
                return surface
    return None


def collect_markdown_files(
    root: Path,
    scope: str = "tracked",
    paths: list[str] | None = None,
) -> list[Path]:
    if paths:
        return [Path(p).resolve() for p in paths]
    if scope == "tracked":
        result = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            capture_output=True,
            text=True,
            cwd=root,
            check=True,
        )
        return [root / p for p in result.stdout.splitlines() if p.endswith(".md")]
    return sorted(root.rglob("**/*.md"))


def _excluded(rel: str) -> bool:
    return any(rel.startswith(prefix) for prefix in DEFAULT_EXCLUDES)


def fix_file(path: Path, root: Path, registry: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    """Fix frontmatter for a single file. Returns a report dict."""
    rel = path.relative_to(root).as_posix()
    surface = match_surface(rel, registry)

    if surface is None:
        return {"path": rel, "status": "skipped", "reason": "no_surface_match"}

    if _excluded(rel):
        return {"path": rel, "status": "skipped", "reason": "excluded"}

    content = path.read_text(encoding="utf-8")
    metadata, has_frontmatter, end_idx = parse_frontmatter(content)

    required = surface.get("required_frontmatter", ["status", "lifecycle", "owner", "last-reviewed"])
    valid_statuses = registry.get("metadata", {}).get("valid_statuses", ["active"])
    valid_lifecycles = registry.get("metadata", {}).get("valid_lifecycles", ["ssot"])
    default_owner = surface.get("owner", "governance-team")
    default_lifecycle = surface.get("lifecycle", "ssot")

    actions: list[str] = []

    if not has_frontmatter:
        # Add full frontmatter
        status = "active" if "active" in valid_statuses else valid_statuses[0]
        fm = f"---\nstatus: {status}\nlifecycle: {default_lifecycle}\nowner: {default_owner}\nlast-reviewed: {TODAY}\n---\n\n"
        if dry_run:
            actions.append(f"add_full_frontmatter(status={status}, lifecycle={default_lifecycle})")
        else:
            path.write_text(fm + content, encoding="utf-8")
            actions.append(f"added_full_frontmatter(status={status}, lifecycle={default_lifecycle})")
    elif metadata is not None:
        # Has frontmatter, check for missing/invalid fields
        modifications: list[str] = []

        if "status" not in metadata:
            modifications.append("status: active")
            actions.append("add_status")

        if "lifecycle" not in metadata:
            modifications.append(f"lifecycle: {default_lifecycle}")
            actions.append(f"add_lifecycle({default_lifecycle})")
        elif metadata.get("lifecycle") not in valid_lifecycles:
            modifications.append(f"lifecycle: {default_lifecycle}")
            actions.append(f"fix_lifecycle({metadata.get('lifecycle')} -> {default_lifecycle})")

        if "owner" not in metadata:
            modifications.append(f"owner: {default_owner}")
            actions.append(f"add_owner({default_owner})")

        if "last-reviewed" not in metadata:
            modifications.append(f"last-reviewed: {TODAY}")
            actions.append("add_last-reviewed")

        if modifications and not dry_run:
            lines = content.splitlines()
            # Insert modifications before closing ---
            for mod in modifications:
                lines.insert(end_idx, mod)
            path.write_text("\n".join(lines), encoding="utf-8")

    if not actions:
        return {"path": rel, "status": "ok", "reason": "no_fix_needed"}

    return {
        "path": rel,
        "status": "fixed" if not dry_run else "would_fix",
        "actions": actions,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Auto-fix document frontmatter")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be fixed without writing")
    parser.add_argument("--paths", nargs="*", help="Specific files to fix (default: all tracked)")
    parser.add_argument("--scope", default="tracked", choices=["tracked", "all"])
    args = parser.parse_args()

    if yaml is None:
        print("ERROR: pyyaml is required", file=sys.stderr)
        return 1

    registry = load_registry()
    files = collect_markdown_files(WORKSPACE, scope=args.scope, paths=args.paths)

    reports = []
    fixed = 0
    skipped = 0
    ok = 0

    for path in files:
        if not path.exists():
            continue
        try:
            report = fix_file(path, WORKSPACE, registry, args.dry_run)
        except Exception as e:
            report = {"path": str(path), "status": "error", "reason": str(e)}

        reports.append(report)
        if report["status"] in ("fixed", "would_fix"):
            fixed += 1
        elif report["status"] == "skipped":
            skipped += 1
        else:
            ok += 1

    # Print summary
    mode = "DRY RUN" if args.dry_run else "APPLIED"
    print(f"[{mode}] Document frontmatter auto-fix report")
    print(f"  Files scanned: {len(files)}")
    print(f"  Fixed: {fixed}")
    print(f"  Skipped: {skipped}")
    print(f"  Already OK: {ok}")

    if fixed > 0:
        print("\nFixed files:")
        for r in reports:
            if r["status"] in ("fixed", "would_fix"):
                print(f"  {r['path']}: {', '.join(r.get('actions', []))}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
