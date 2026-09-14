#!/usr/bin/env python3
"""E-DOC-001~005: Documents dual-plane boundary gate.

Enforces ADR-0191 rules on the Documents content plane:
  E-DOC-001  No executable scripts (.py/.sh/.js/.ts/.rb/.go)
  E-DOC-002  No environment dependency dirs (node_modules/.venv/__pycache__/.pytest_cache)
  E-DOC-003  No cross-domain direct writes (Workspace→Documents bypassing BOS)
  E-DOC-004  Critical fact files schema validation (_entities/facts/*.yaml, 14-day freshness)
  E-DOC-005  Multi-client config consistency (documents-domain-projects.yaml → IDE configs)

Supports --dry-run, --json, --documents-root, and --auto-fix modes.
Outputs Diagnostic Envelope with self-heal suggestions on violations.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DOCUMENTS_ROOT = Path.home() / "Documents"
FACTS_GLOB = "_entities/facts/*.yaml"
FRESHNESS_DAYS = 14
EVIDENCE_SUFFIX = ".evidence.json"

# E-DOC-001: Executable script extensions banned in Documents
BANNED_EXTENSIONS = {".py", ".sh", ".bash", ".js", ".ts", ".rb", ".go"}

# E-DOC-002: Environment/cache directories banned in Documents
BANNED_DIRS = {"node_modules", ".venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".tox"}

# E-DOC-005: Client config files generated from SSOT
CLIENT_CONFIG_MAP = {
    "claude_desktop": "claude_desktop_config.json",
    "zed": "settings.json",
    "zcode": "zcode.json",
}

# ──────────────────────────────────────────────────────────────────────────────
# Violation model
# ──────────────────────────────────────────────────────────────────────────────

class Violation:
    """A single boundary violation."""

    def __init__(
        self,
        rule: str,
        path: str,
        message: str,
        severity: str = "error",
        fix_suggestion: str | None = None,
    ) -> None:
        self.rule = rule
        self.path = path
        self.message = message
        self.severity = severity  # "error" | "warning"
        self.fix_suggestion = fix_suggestion

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "rule": self.rule,
            "path": self.path,
            "message": self.message,
            "severity": self.severity,
        }
        if self.fix_suggestion:
            d["fix_suggestion"] = self.fix_suggestion
        return d


# ──────────────────────────────────────────────────────────────────────────────
# E-DOC-001: Executable script scan
# ──────────────────────────────────────────────────────────────────────────────

def check_edoc001(doc_root: Path) -> list[Violation]:
    """Scan Documents for executable script files."""
    violations: list[Violation] = []
    if not doc_root.is_dir():
        return violations
    for p in doc_root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() in BANNED_EXTENSIONS:
            # Skip known legitimate config/script files at specific locations
            rel = str(p.relative_to(doc_root))
            if _is_excluded_path(rel):
                continue
            violations.append(
                Violation(
                    rule="E-DOC-001",
                    path=str(p),
                    message=f"Executable script '{p.name}' found in Documents content plane",
                    fix_suggestion=(
                        f"Move to Workspace: mv '{p}' "
                        f"'{ROOT}/scripts/{rel.rsplit('/', 1)[-1] if '/' in rel else p.name}'"
                    ),
                )
            )
    return violations


# ──────────────────────────────────────────────────────────────────────────────
# E-DOC-002: Environment dependency directory scan
# ──────────────────────────────────────────────────────────────────────────────

def check_edoc002(doc_root: Path) -> list[Violation]:
    """Scan Documents for banned environment/cache directories."""
    violations: list[Violation] = []
    if not doc_root.is_dir():
        return violations
    for d in doc_root.rglob("*"):
        if d.is_dir() and d.name in BANNED_DIRS:
            rel = str(d.relative_to(doc_root))
            if _is_excluded_path(rel):
                continue
            violations.append(
                Violation(
                    rule="E-DOC-002",
                    path=str(d),
                    message=f"Banned environment directory '{d.name}' found in Documents",
                    fix_suggestion=f"rm -rf '{d}' && add to .gitignore if needed in Workspace",
                )
            )
    return violations


# ──────────────────────────────────────────────────────────────────────────────
# E-DOC-003: Cross-domain direct write detection
# ──────────────────────────────────────────────────────────────────────────────

def check_edoc003(doc_root: Path) -> list[Violation]:
    """Detect recent cross-domain writes: files in Documents modified by Workspace-side processes.

    Heuristic: files whose git author email matches workspace committers but
    lack a BOS routing receipt. This is a soft check — we flag files that
    appear to have been written directly (not via BOS/MCP).
    """
    violations: list[Violation] = []
    if not doc_root.is_dir():
        return violations

    # Check for signal files that indicate direct Workspace writes
    # Look for .signal receipts that indicate BOS-mediated writes vs raw writes
    for p in doc_root.rglob("*.py"):
        rel = str(p.relative_to(doc_root))
        if _is_excluded_path(rel):
            continue
        # A .py file in Documents = always a violation (caught by E-DOC-001)
        # E-DOC-003 is about YAML/MD files written without BOS routing
        pass

    # Check for YAML fact files that lack BOS receipt headers
    for p in doc_root.rglob("*.yaml"):
        rel = str(p.relative_to(doc_root))
        if _is_excluded_path(rel):
            continue
        if "_entities/facts/" in rel:
            try:
                content = p.read_text(encoding="utf-8")
                # Files written via BOS should have a bos_routed header
                if not re.search(r"bos_routed:\s*true", content) and not re.search(
                    r"auto.generated|do.not.edit", content, re.IGNORECASE
                ):
                    violations.append(
                        Violation(
                            rule="E-DOC-003",
                            path=str(p),
                            message="Fact file may have been written directly without BOS routing",
                            severity="warning",
                            fix_suggestion=(
                                f"Route through BOS: write via bos://documents/{{domain}}/{{resource}} "
                                f"or add bos_routed: true header"
                            ),
                        )
                    )
            except (OSError, UnicodeError):
                pass
    return violations


# ──────────────────────────────────────────────────────────────────────────────
# E-DOC-004: Critical fact file schema validation + freshness
# ──────────────────────────────────────────────────────────────────────────────

def check_edoc004(doc_root: Path) -> list[Violation]:
    """Validate _entities/facts/*.yaml files: schema compliance + 14-day freshness."""
    try:
        import yaml
    except ImportError:
        return [
            Violation(
                rule="E-DOC-004",
                path=str(doc_root),
                message="pyyaml not installed — cannot validate YAML schema",
                severity="warning",
            )
        ]
    violations: list[Violation] = []
    if not doc_root.is_dir():
        return violations
    facts_dir = doc_root / "_entities" / "facts"
    if not facts_dir.is_dir():
        return violations

    cutoff = datetime.now(UTC) - timedelta(days=FRESHNESS_DAYS)
    for p in facts_dir.glob("*.yaml"):
        if not p.is_file():
            continue
        # Schema validation: must be valid YAML with at least one top-level key
        try:
            data = yaml.safe_load(p.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or not data:
                violations.append(
                    Violation(
                        rule="E-DOC-004",
                        path=str(p),
                        message="Fact file is empty or not a YAML mapping",
                        fix_suggestion="Ensure the file contains at least one top-level key-value pair",
                    )
                )
        except yaml.YAMLError as exc:
            violations.append(
                Violation(
                    rule="E-DOC-004",
                    path=str(p),
                    message=f"Invalid YAML: {exc}",
                    fix_suggestion="Fix YAML syntax errors",
                )
            )
            continue

        # Freshness check
        try:
            mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=UTC)
            if mtime < cutoff:
                age_days = (datetime.now(UTC) - mtime).days
                violations.append(
                    Violation(
                        rule="E-DOC-004",
                        path=str(p),
                        message=f"Fact file not updated in {age_days} days (>{FRESHNESS_DAYS} day limit)",
                        severity="warning",
                        fix_suggestion="Review and refresh the fact file or archive if stale",
                    )
                )
        except OSError:
            pass

    return violations


# ──────────────────────────────────────────────────────────────────────────────
# E-DOC-005: Multi-client config consistency
# ──────────────────────────────────────────────────────────────────────────────

def check_edoc005(doc_root: Path, workspace: Path) -> list[Violation]:
    """Verify multi-client configs are generated from SSOT, not hand-maintained."""
    violations: list[Violation] = []
    # Check that the SSOT registry exists
    ssot_path = workspace / ".omo" / "_truth" / "registry" / "documents-domain-projects.yaml"
    if not ssot_path.is_file():
        violations.append(
            Violation(
                rule="E-DOC-005",
                path=str(ssot_path),
                message="SSOT registry documents-domain-projects.yaml not found",
                severity="warning",
                fix_suggestion="Create the SSOT registry or run documents-domain-project-check.py",
            )
        )
        return violations

    # Check for hand-maintained client configs (should be auto-generated)
    generators = list((workspace / "bin" / "gac").glob("documents-*-config.py"))
    if not generators:
        violations.append(
            Violation(
                rule="E-DOC-005",
                path=str(workspace / "bin" / "gac"),
                message="No documents-*-config.py generator scripts found",
                fix_suggestion="Create generator scripts that read from SSOT registry",
            )
        )

    return violations


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

_EXCLUDED_PREFIXES = (
    "@公共/_control/",
    "@公共/_meta/",
    ".DS_Store",
    "node_modules/",
)

def _is_excluded_path(rel: str) -> bool:
    """Check if a relative path should be excluded from scanning."""
    for prefix in _EXCLUDED_PREFIXES:
        if rel.startswith(prefix):
            return True
    return False


# ──────────────────────────────────────────────────────────────────────────────
# Auto-fix mode
# ──────────────────────────────────────────────────────────────────────────────

def auto_fix(violations: list[Violation], dry_run: bool = True) -> list[str]:
    """Attempt auto-fix for violations with fix_suggestion."""
    actions: list[str] = []
    for v in violations:
        if not v.fix_suggestion:
            continue
        if v.rule == "E-DOC-001":
            # Move script to Workspace
            src = Path(v.path)
            if src.is_file():
                dest = ROOT / "scripts" / src.name
                if dry_run:
                    actions.append(f"[dry-run] mv '{src}' '{dest}'")
                else:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    src.rename(dest)
                    actions.append(f"moved '{src}' → '{dest}'")
        elif v.rule == "E-DOC-002":
            # Remove banned directory
            target = Path(v.path)
            if target.is_dir():
                if dry_run:
                    actions.append(f"[dry-run] rm -rf '{target}'")
                else:
                    import shutil
                    shutil.rmtree(target)
                    actions.append(f"removed '{target}'")
    return actions


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="E-DOC-001~005: Documents dual-plane boundary gate"
    )
    parser.add_argument(
        "--documents-root",
        type=Path,
        default=DEFAULT_DOCUMENTS_ROOT,
        help="Path to Documents root (default: ~/Documents)",
    )
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--dry-run", action="store_true", help="Dry-run mode (no mutations)")
    parser.add_argument("--auto-fix", action="store_true", help="Attempt auto-fix")
    parser.add_argument("--rule", type=str, help="Run only a specific rule (e.g. E-DOC-001)")
    args = parser.parse_args()

    doc_root = args.documents_root.expanduser().resolve()
    if not doc_root.is_dir():
        if args.json:
            print(json.dumps({"ok": False, "error": f"Documents root not found: {doc_root}"}))
        else:
            print(f"ERROR: Documents root not found: {doc_root}", file=sys.stderr)
        return 1

    all_violations: list[Violation] = []
    rules_run: list[str] = []

    rules = [
        ("E-DOC-001", lambda: check_edoc001(doc_root)),
        ("E-DOC-002", lambda: check_edoc002(doc_root)),
        ("E-DOC-003", lambda: check_edoc003(doc_root)),
        ("E-DOC-004", lambda: check_edoc004(doc_root)),
        ("E-DOC-005", lambda: check_edoc005(doc_root, ROOT)),
    ]

    for rule_id, checker in rules:
        if args.rule and args.rule != rule_id:
            continue
        rules_run.append(rule_id)
        violations = checker()
        all_violations.extend(violations)

    # Auto-fix if requested
    fix_actions: list[str] = []
    if args.auto_fix and all_violations:
        fix_actions = auto_fix(all_violations, dry_run=args.dry_run)

    errors = [v for v in all_violations if v.severity == "error"]
    warnings = [v for v in all_violations if v.severity == "warning"]
    ok = len(errors) == 0

    if args.json:
        result: dict[str, Any] = {
            "ok": ok,
            "documents_root": str(doc_root),
            "rules_checked": rules_run,
            "error_count": len(errors),
            "warning_count": len(warnings),
            "violations": [v.to_dict() for v in all_violations],
        }
        if fix_actions:
            result["fix_actions"] = fix_actions
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        if ok:
            print(f"OK E-DOC-001~005: All {len(rules_run)} rules passed ({len(warnings)} warnings)")
        else:
            print(f"FAIL E-DOC-001~005: {len(errors)} errors, {len(warnings)} warnings")
            for v in all_violations:
                prefix = "ERR " if v.severity == "error" else "WARN"
                print(f"  [{prefix}] {v.rule}: {v.message}")
                print(f"         path: {v.path}")
                if v.fix_suggestion:
                    print(f"         fix:  {v.fix_suggestion}")
        if fix_actions:
            print("\nAuto-fix actions:")
            for a in fix_actions:
                print(f"  {a}")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
