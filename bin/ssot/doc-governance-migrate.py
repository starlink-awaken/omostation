#!/usr/bin/env python3
# ---
# status: active
# lifecycle: contract
# owner: governance-team
# ssot: .omo/_truth/registry/document-governance.yaml
# verifier: pytest tests/test_doc_governance_migrate.py
# ---
"""Apply reviewable document-governance metadata migrations."""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[2]
CHECKER_PATH = WORKSPACE / "bin/ssot/doc-governance-check.py"
SPEC = importlib.util.spec_from_file_location("doc_governance_check", CHECKER_PATH)
if SPEC is None or SPEC.loader is None:  # pragma: no cover - import guard
    raise RuntimeError(f"unable to load checker: {CHECKER_PATH}")
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)


def _date(value: str | None) -> date:
    if value is None:
        return datetime.now(timezone.utc).date()
    return date.fromisoformat(value)


def _default_metadata(
    rel: str,
    surface: dict[str, Any],
    migration_date: date,
) -> dict[str, str]:
    parts = set(PurePosixPath(rel).parts)
    lifecycle = str(surface.get("lifecycle", "contract"))
    status = "active"
    if lifecycle == "history" or parts.intersection(
        {"archive", "audits", "audit", "closeout", "reports", "retrospectives", "reviews"}
    ):
        status = "archived"
        lifecycle = "history"
    elif "proposals" in parts:
        status = "planned"
        lifecycle = "plan"
    elif lifecycle == "ssot":
        status = "active"
    return {
        "status": status,
        "lifecycle": lifecycle,
        "owner": str(surface.get("owner", "governance-team")),
        "last-reviewed": migration_date.isoformat(),
        "review-state": "metadata-only",
        "metadata-migrated-at": migration_date.isoformat(),
    }


def _frontmatter_block(metadata: dict[str, str]) -> str:
    lines = ["---"]
    lines.extend(f"{key}: {value}" for key, value in metadata.items())
    lines.extend(["---", ""])
    return "\n".join(lines)


def _replace_scalar(frontmatter: str, key: str, value: str) -> str:
    pattern = rf"(?m)^{re.escape(key)}:\s*.*$"
    if re.search(pattern, frontmatter):
        return re.sub(pattern, f"{key}: {value}", frontmatter, count=1)
    return frontmatter


def _add_missing_scalars(
    content: str,
    metadata: dict[str, Any] | None,
    defaults: dict[str, str],
    review_state: str,
    migration_date: date,
    normalize_enums: bool,
    enum_migrations: dict[str, dict[str, str]],
) -> tuple[str, bool]:
    if not content.startswith("---\n"):
        return _frontmatter_block(defaults) + content, True
    end = content.find("\n---", 4)
    if end < 0:
        return content, False
    frontmatter = content[4:end]
    current = metadata or {}
    if normalize_enums:
        for field in ("status", "lifecycle"):
            mapping = enum_migrations.get(field, {})
            value = current.get(field)
            if value in mapping:
                frontmatter = _replace_scalar(frontmatter, field, mapping[str(value)])
                current[field] = mapping[str(value)]
    additions: list[str] = []
    if review_state == "content-reviewed":
        if current.get("review-state") != "content-reviewed":
            if "review-state" in current:
                frontmatter = _replace_scalar(
                    frontmatter,
                    "review-state",
                    "content-reviewed",
                )
            else:
                additions.append("review-state: content-reviewed")
            current["review-state"] = "content-reviewed"
        if "content-reviewed-at" not in current:
            additions.append(
                f"content-reviewed-at: {migration_date.isoformat()}"
            )
            current["content-reviewed-at"] = migration_date.isoformat()
    elif current.get("review-state") == "content-reviewed":
        return content, False
    for field, value in defaults.items():
        if field not in current:
            additions.append(f"{field}: {value}")
    if not additions:
        return content, False
    new_frontmatter = frontmatter.rstrip() + "\n" + "\n".join(additions)
    return "---\n" + new_frontmatter + content[end:], True


def migrate_file(
    path: Path,
    root: Path,
    registry: dict[str, Any],
    migration_date: date,
    review_state: str,
    normalize_enums: bool,
) -> tuple[bool, str]:
    rel = path.relative_to(root).as_posix()
    surface = CHECKER.match_surface(rel, registry)
    if surface is None or surface.get("metadata") != "frontmatter":
        return False, "unmatched"
    content = path.read_text(encoding="utf-8", errors="replace")
    metadata, _ = CHECKER.parse_frontmatter(content)
    defaults = _default_metadata(rel, surface, migration_date)
    if review_state == "content-reviewed":
        defaults["review-state"] = "content-reviewed"
        defaults.pop("metadata-migrated-at", None)
        defaults["content-reviewed-at"] = migration_date.isoformat()
    enum_migrations = (
        registry.get("metadata", {}).get("enum_migrations", {})
        if isinstance(registry.get("metadata", {}), dict)
        else {}
    )
    updated, changed = _add_missing_scalars(
        content,
        metadata,
        defaults,
        review_state,
        migration_date,
        normalize_enums,
        enum_migrations,
    )
    if changed:
        path.write_text(updated, encoding="utf-8")
    return changed, str(surface.get("id", "unmatched"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Migrate governed documents into the review-state frontmatter contract"
    )
    parser.add_argument("--scope", choices=("tracked", "workspace"), default="tracked")
    parser.add_argument("--files", nargs="*", default=None)
    parser.add_argument(
        "--all",
        action="store_true",
        help="include governed files without current metadata warnings",
    )
    parser.add_argument("--date", dest="migration_date")
    parser.add_argument(
        "--review-state",
        choices=("metadata-only", "content-reviewed"),
        default="metadata-only",
    )
    parser.add_argument(
        "--normalize-enums",
        action="store_true",
        help="apply explicit registry enum migrations while adding metadata",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    migration_date = _date(args.migration_date)
    registry = CHECKER.load_registry(
        WORKSPACE / ".omo/_truth/registry/document-governance.yaml"
    )
    if args.files or args.all:
        files = CHECKER.collect_markdown_files(
            WORKSPACE,
            scope=args.scope,
            paths=args.files,
        )
    else:
        current = CHECKER.run(
            root=WORKSPACE,
            scope=args.scope,
            paths=None,
            strict=False,
            no_new_warnings=False,
        )
        eligible = {
            finding["path"]
            for finding in current["findings"]
            if finding["rule"] in {"missing_frontmatter", "invalid_metadata"}
        }
        files = [
            WORKSPACE / path
            for path in sorted(eligible)
            if (WORKSPACE / path).is_file()
        ]
    changed = 0
    surfaces: dict[str, int] = {}
    for path in files:
        rel = path.relative_to(WORKSPACE).as_posix()
        surface = CHECKER.match_surface(rel, registry)
        if surface is None or surface.get("metadata") != "frontmatter":
            continue
        if args.dry_run:
            content = path.read_text(encoding="utf-8", errors="replace")
            metadata, _ = CHECKER.parse_frontmatter(content)
            defaults = _default_metadata(rel, surface, migration_date)
            if args.review_state == "content-reviewed":
                defaults["review-state"] = "content-reviewed"
                defaults.pop("metadata-migrated-at", None)
                defaults["content-reviewed-at"] = migration_date.isoformat()
            enum_migrations = registry.get("metadata", {}).get("enum_migrations", {})
            _, file_changed = _add_missing_scalars(
                content,
                metadata,
                defaults,
                args.review_state,
                migration_date,
                args.normalize_enums,
                enum_migrations,
            )
            surface_id = str(surface.get("id", "unmatched"))
        else:
            file_changed, surface_id = migrate_file(
                path,
                WORKSPACE,
                registry,
                migration_date,
                args.review_state,
                args.normalize_enums,
            )
        if file_changed:
            changed += 1
            surfaces[surface_id] = surfaces.get(surface_id, 0) + 1
    mode = "dry-run" if args.dry_run else "updated"
    print(f"doc-governance-migrate: {mode} {changed} files")
    for surface_id, count in sorted(surfaces.items()):
        print(f"  {surface_id}: {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
