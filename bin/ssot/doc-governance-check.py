#!/usr/bin/env python3
"""Validate document ownership, lifecycle, freshness, and discoverability."""
from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - dependency is supplied by the workspace
    yaml = None


WORKSPACE = Path(__file__).resolve().parents[2]
REGISTRY_PATH = WORKSPACE / ".omo/_truth/registry/document-governance.yaml"
DEFAULT_EXCLUDES = (
    ".git/",
    ".venv/",
    "node_modules/",
    "docs/generated/",
    ".omo/_delivery/",
    "runtime/",
)


def _load_yaml_documents(path: Path) -> dict[str, Any]:
    if yaml is None:
        raise RuntimeError("pyyaml is required")
    documents = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
    merged: dict[str, Any] = {}
    for document in documents:
        if isinstance(document, dict):
            merged.update(document)
    return merged


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"document governance registry not found: {path}")
    registry = _load_yaml_documents(path)
    if not isinstance(registry.get("surfaces"), list):
        raise TypeError("document governance registry must define surfaces")
    return registry


def parse_frontmatter(content: str) -> tuple[dict[str, Any] | None, bool]:
    """Return (metadata, has_frontmatter). Malformed metadata returns (None, True)."""
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, False
    try:
        end = next(index for index in range(1, len(lines)) if lines[index].strip() == "---")
    except StopIteration:
        return None, True
    if yaml is None:
        raise RuntimeError("pyyaml is required")
    try:
        data = yaml.safe_load("\n".join(lines[1:end])) or {}
    except yaml.YAMLError:
        return None, True
    return (data if isinstance(data, dict) else None), True


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _excluded(rel: str, excludes: list[str] | tuple[str, ...] = ()) -> bool:
    return any(rel.startswith(prefix) for prefix in (*DEFAULT_EXCLUDES, *excludes))


def collect_markdown_files(
    root: Path,
    scope: str = "tracked",
    paths: list[str] | None = None,
) -> list[Path]:
    if paths:
        candidates = [root / path for path in paths]
    elif scope == "tracked":
        result = subprocess.run(
            ["git", "ls-files", "--", "*.md", "*.markdown"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        candidates = [root / line.strip() for line in result.stdout.splitlines() if line.strip()]
    elif scope == "workspace":
        candidates = list(root.rglob("*.md")) + list(root.rglob("*.markdown"))
    else:
        raise ValueError(f"unsupported scope: {scope}")

    files = {
        path.resolve()
        for path in candidates
        if path.is_file() and not _excluded(_relative(path, root))
    }
    return sorted(files, key=lambda path: _relative(path, root))


def _matches(rel: str, pattern: str) -> bool:
    if fnmatch.fnmatchcase(rel, pattern) or PurePosixPath(rel).match(pattern):
        return True
    # Python's glob implementations treat `**/` as requiring at least one
    # directory. Governance patterns must also match files directly below the
    # declared root, such as `.omo/_knowledge/README.md`.
    if "/**/" in pattern:
        prefix, suffix = pattern.split("/**/", 1)
        if rel.startswith(prefix + "/"):
            return fnmatch.fnmatchcase(rel[len(prefix) + 1 :], suffix)
    return False


def match_surface(rel: str, registry: dict[str, Any]) -> dict[str, Any] | None:
    for surface in registry.get("surfaces", []):
        patterns = surface.get("patterns", [])
        excludes = surface.get("excludes", [])
        if any(_matches(rel, pattern) for pattern in patterns) and not any(
            _matches(rel, pattern) for pattern in excludes
        ):
            return surface
    return None


def _finding(
    *,
    path: str,
    rule: str,
    surface: dict[str, Any] | None,
    severity: str,
    workflow: str,
    evidence: str,
    message: str,
    line: int | None = None,
) -> dict[str, Any]:
    return {
        "path": path,
        "rule": rule,
        "owner": (surface or {}).get("owner", "governance-team"),
        "severity": severity,
        "workflow": workflow,
        "evidence": evidence,
        "message": message,
        **({"line": line} if line is not None else {}),
    }


def _severity(registry: dict[str, Any], rule: str, surface: dict[str, Any] | None) -> str:
    overrides = (surface or {}).get("rules", {})
    if isinstance(overrides, dict) and rule in overrides:
        return str(overrides[rule])
    return str((registry.get("rules", {}).get(rule) or {}).get("severity", "warning"))


def validate_registry(
    registry: dict[str, Any],
    root: Path,
    registry_path: Path = REGISTRY_PATH,
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    metadata = registry.get("metadata", {})
    valid_statuses = set(metadata.get("valid_statuses", []))
    valid_lifecycles = set(metadata.get("valid_lifecycles", []))
    for index, surface in enumerate(registry.get("surfaces", []), start=1):
        surface_id = str(surface.get("id", ""))
        surface_name = surface_id or f"surface[{index}]"
        if not surface_id or surface_id in seen_ids:
            findings.append(
                _finding(
                    path=_relative(registry_path, root)
                    if registry_path.is_relative_to(root)
                    else str(registry_path),
                    rule="registry-integrity",
                    surface=None,
                    severity="error",
                    workflow="project-doc-change",
                    evidence=surface_name,
                    message="surface ids must be present and unique",
                )
            )
        seen_ids.add(surface_id)
        for field in ("patterns", "owner", "lifecycle", "ssot", "verifier"):
            if not surface.get(field):
                findings.append(
                    _finding(
                        path=_relative(registry_path, root)
                        if registry_path.is_relative_to(root)
                        else str(registry_path),
                        rule="registry-integrity",
                        surface=None,
                        severity="error",
                        workflow="project-doc-change",
                        evidence=surface_name,
                        message=f"{surface_name} is missing required field {field}",
                    )
                )
        if surface.get("lifecycle") not in valid_lifecycles:
            findings.append(
                _finding(
                    path=_relative(registry_path, root)
                    if registry_path.is_relative_to(root)
                    else str(registry_path),
                    rule="registry-integrity",
                    surface=None,
                    severity="error",
                    workflow="project-doc-change",
                    evidence=f"{surface_name}.lifecycle",
                    message=f"lifecycle must be one of {sorted(valid_lifecycles)}",
                )
            )
        for field in ("ssot", "verifier"):
            target = root / str(surface.get(field, ""))
            if not target.exists():
                findings.append(
                    _finding(
                        path=_relative(registry_path, root)
                        if registry_path.is_relative_to(root)
                        else str(registry_path),
                        rule="registry-integrity",
                        surface=None,
                        severity="error",
                        workflow="project-doc-change",
                        evidence=f"{surface_name}.{field}={surface.get(field)}",
                        message=f"registered {field} path does not exist",
                    )
                )
    if not valid_statuses or not valid_lifecycles:
        findings.append(
            _finding(
                path=str(REGISTRY_PATH.relative_to(root)),
                rule="registry-integrity",
                surface=None,
                severity="error",
                workflow="project-doc-change",
                evidence="metadata.valid_statuses/valid_lifecycles",
                message="registry must declare lifecycle enums",
            )
        )
    return findings


def _warning_bucket(
    finding: dict[str, Any],
    registry: dict[str, Any],
) -> str:
    surface = match_surface(str(finding["path"]), registry)
    surface_id = str(surface.get("id")) if surface else "unmatched"
    return f"{finding['rule']}:{surface_id}"


def evaluate_warning_baseline(
    findings: list[dict[str, Any]],
    registry: dict[str, Any],
    today: date,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Compare warning counts with expiring, registry-owned exception budgets."""
    config = registry.get("warning_exceptions")
    baseline: dict[str, Any] = {
        "configured": isinstance(config, dict),
        "policy": (config or {}).get("policy", "none"),
        "observed": {},
        "budgets": {},
        "expired": [],
        "unbaselined": [],
        "over_budget": [],
        "ok": False,
    }
    registry_findings: list[dict[str, Any]] = []
    if not isinstance(config, dict):
        registry_findings.append(
            _finding(
                path=".omo/_truth/registry/document-governance.yaml",
                rule="warning_exception_registry",
                surface=None,
                severity="error",
                workflow="governance-state-mutation",
                evidence="warning_exceptions",
                message="registry must define warning exception budgets",
            )
        )
        return baseline, registry_findings

    entries = config.get("entries")
    if not isinstance(entries, list) or not entries:
        registry_findings.append(
            _finding(
                path=".omo/_truth/registry/document-governance.yaml",
                rule="warning_exception_registry",
                surface=None,
                severity="error",
                workflow="governance-state-mutation",
                evidence="warning_exceptions.entries",
                message="warning exception registry must define entries",
            )
        )
        return baseline, registry_findings

    entry_ids: set[str] = set()
    entries_by_bucket: dict[str, dict[str, Any]] = {}
    valid_rules = set(registry.get("rules", {}))
    valid_surfaces = {
        str(surface.get("id"))
        for surface in registry.get("surfaces", [])
        if surface.get("id")
    }
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            registry_findings.append(
                _finding(
                    path=".omo/_truth/registry/document-governance.yaml",
                    rule="warning_exception_registry",
                    surface=None,
                    severity="error",
                    workflow="governance-state-mutation",
                    evidence=f"entries[{index}]",
                    message="warning exception entries must be mappings",
                )
            )
            continue
        entry_id = str(entry.get("id", ""))
        rule = str(entry.get("rule", ""))
        surface = str(entry.get("surface", ""))
        bucket = f"{rule}:{surface}"
        if not entry_id or entry_id in entry_ids:
            registry_findings.append(
                _finding(
                    path=".omo/_truth/registry/document-governance.yaml",
                    rule="warning_exception_registry",
                    surface=None,
                    severity="error",
                    workflow="governance-state-mutation",
                    evidence=entry_id or f"entries[{index}]",
                    message="warning exception ids must be present and unique",
                )
            )
        entry_ids.add(entry_id)
        try:
            max_findings = int(entry["max_findings"])
        except (KeyError, TypeError, ValueError):
            max_findings = -1
        try:
            expires = date.fromisoformat(str(entry["expires"]))
        except (KeyError, TypeError, ValueError):
            expires = None
        if (
            not rule
            or rule not in valid_rules
            or not surface
            or surface not in valid_surfaces
            or max_findings < 0
            or expires is None
            or not entry.get("owner")
            or not entry.get("reason")
        ):
            registry_findings.append(
                _finding(
                    path=".omo/_truth/registry/document-governance.yaml",
                    rule="warning_exception_registry",
                    surface=None,
                    severity="error",
                    workflow="governance-state-mutation",
                    evidence=entry_id or f"entries[{index}]",
                    message="exception entries require rule, surface, non-negative max_findings, and YYYY-MM-DD expires",
                )
            )
            continue
        if bucket in entries_by_bucket:
            registry_findings.append(
                _finding(
                    path=".omo/_truth/registry/document-governance.yaml",
                    rule="warning_exception_registry",
                    surface=None,
                    severity="error",
                    workflow="governance-state-mutation",
                    evidence=bucket,
                    message="only one exception budget may exist for each rule/surface bucket",
                )
            )
        entries_by_bucket[bucket] = entry
        baseline["budgets"][bucket] = {
            "id": entry_id,
            "max_findings": max_findings,
            "expires": expires.isoformat(),
        }
        if expires < today:
            baseline["expired"].append(entry_id)

    warning_counts: dict[str, int] = {}
    for finding in findings:
        if finding["severity"] != "warning":
            continue
        bucket = _warning_bucket(finding, registry)
        warning_counts[bucket] = warning_counts.get(bucket, 0) + 1
    baseline["observed"] = dict(sorted(warning_counts.items()))
    for bucket, count in warning_counts.items():
        entry = entries_by_bucket.get(bucket)
        if entry is None:
            baseline["unbaselined"].append({"bucket": bucket, "count": count})
        elif count > int(entry["max_findings"]):
            baseline["over_budget"].append(
                {
                    "bucket": bucket,
                    "count": count,
                    "max_findings": int(entry["max_findings"]),
                    "exception": entry["id"],
                }
            )

    baseline["ok"] = not (
        registry_findings
        or baseline["expired"]
        or baseline["unbaselined"]
        or baseline["over_budget"]
    )
    return baseline, registry_findings


def _baseline_violation_findings(
    baseline: dict[str, Any],
) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    for entry_id in baseline["expired"]:
        violations.append(
            _finding(
                path=".omo/_truth/registry/document-governance.yaml",
                rule="expired_warning_exception",
                surface=None,
                severity="error",
                workflow="governance-state-mutation",
                evidence=entry_id,
                message="warning exception has expired and must be renewed or removed",
            )
        )
    for item in baseline["unbaselined"]:
        violations.append(
            _finding(
                path=".omo/_truth/registry/document-governance.yaml",
                rule="unbaselined_warning",
                surface=None,
                severity="error",
                workflow="project-doc-change",
                evidence=f"{item['bucket']} count={item['count']}",
                message="warning bucket is not covered by an exception budget",
            )
        )
    for item in baseline["over_budget"]:
        violations.append(
            _finding(
                path=".omo/_truth/registry/document-governance.yaml",
                rule="warning_budget_exceeded",
                surface=None,
                severity="error",
                workflow="project-doc-change",
                evidence=(
                    f"{item['bucket']} count={item['count']} "
                    f"max={item['max_findings']}"
                ),
                message=f"warning exception {item['exception']} has been exceeded",
            )
        )
    return violations


def _is_discoverable(rel: str, surface: dict[str, Any], index_text: str) -> bool:
    if rel == surface.get("index"):
        return True
    if rel in index_text or Path(rel).name in index_text:
        return True
    if surface.get("discoverability") == "directory-index":
        parent = PurePosixPath(rel).parent.as_posix()
        return parent != "." and f"{parent}/" in index_text
    return True


def check_file(
    path: Path,
    root: Path,
    registry: dict[str, Any],
    index_cache: dict[Path, str],
    today: date,
) -> list[dict[str, Any]]:
    rel = _relative(path, root)
    surface = match_surface(rel, registry)
    if surface is None:
        return []

    workflow = str(surface.get("workflow", "project-doc-change"))
    findings: list[dict[str, Any]] = []
    content = path.read_text(encoding="utf-8", errors="replace")
    metadata, has_frontmatter = parse_frontmatter(content)
    if surface.get("metadata") == "frontmatter":
        required = surface.get(
            "required_frontmatter",
            registry.get("metadata", {}).get("required_frontmatter", []),
        )
        if not has_frontmatter:
            findings.append(
                _finding(
                    path=rel,
                    rule="missing_frontmatter",
                    surface=surface,
                    severity=_severity(registry, "missing_frontmatter", surface),
                    workflow=workflow,
                    evidence="file does not start with YAML frontmatter",
                    message=f"frontmatter is required for surface {surface['id']}",
                    line=1,
                )
            )
            metadata = {}
        elif metadata is None:
            findings.append(
                _finding(
                    path=rel,
                    rule="malformed_frontmatter",
                    surface=surface,
                    severity=_severity(registry, "malformed_frontmatter", surface),
                    workflow=workflow,
                    evidence="frontmatter cannot be parsed as a mapping",
                    message="frontmatter must be valid YAML mapping",
                    line=1,
                )
            )
            metadata = {}
        missing = [field for field in required if field not in metadata]
        if missing:
            findings.append(
                _finding(
                    path=rel,
                    rule="missing_frontmatter",
                    surface=surface,
                    severity=_severity(registry, "missing_frontmatter", surface),
                    workflow=workflow,
                    evidence=", ".join(missing),
                    message=f"missing required frontmatter fields: {', '.join(missing)}",
                    line=1,
                )
            )

        valid_statuses = set(registry.get("metadata", {}).get("valid_statuses", []))
        valid_lifecycles = set(registry.get("metadata", {}).get("valid_lifecycles", []))
        if "status" in metadata and metadata.get("status") not in valid_statuses:
            findings.append(
                _finding(
                    path=rel,
                    rule="invalid_metadata",
                    surface=surface,
                    severity=_severity(registry, "invalid_metadata", surface),
                    workflow=workflow,
                    evidence=f"status={metadata.get('status')!r}",
                    message=f"status must be one of {sorted(valid_statuses)}",
                    line=1,
                )
            )
        if "lifecycle" in metadata and metadata.get("lifecycle") not in valid_lifecycles:
            findings.append(
                _finding(
                    path=rel,
                    rule="invalid_metadata",
                    surface=surface,
                    severity=_severity(registry, "invalid_metadata", surface),
                    workflow=workflow,
                    evidence=f"lifecycle={metadata.get('lifecycle')!r}",
                    message=f"lifecycle must be one of {sorted(valid_lifecycles)}",
                    line=1,
                )
            )
        reviewed = metadata.get("last-reviewed")
        if reviewed:
            try:
                reviewed_date = date.fromisoformat(str(reviewed))
            except ValueError:
                reviewed_date = None
                findings.append(
                    _finding(
                        path=rel,
                        rule="invalid_metadata",
                        surface=surface,
                        severity=_severity(registry, "invalid_metadata", surface),
                        workflow=workflow,
                        evidence=f"last-reviewed={reviewed!r}",
                        message="last-reviewed must use YYYY-MM-DD",
                        line=1,
                    )
                )
            if reviewed_date and reviewed_date > today:
                findings.append(
                    _finding(
                        path=rel,
                        rule="invalid_metadata",
                        surface=surface,
                        severity=_severity(registry, "invalid_metadata", surface),
                        workflow=workflow,
                        evidence=f"last-reviewed={reviewed_date.isoformat()}",
                        message="last-reviewed cannot be in the future",
                        line=1,
                    )
                )
            elif reviewed_date and (today - reviewed_date).days > int(surface.get("review_days", 0)):
                findings.append(
                    _finding(
                        path=rel,
                        rule="stale_review",
                        surface=surface,
                        severity=_severity(registry, "stale_review", surface),
                        workflow=workflow,
                        evidence=f"age={(today - reviewed_date).days}d threshold={surface.get('review_days')}d",
                        message="document review date is outside the registered SLA",
                        line=1,
                    )
                )

    discoverability = surface.get("discoverability")
    if discoverability:
        index_path = root / str(surface.get("index", ""))
        if not index_path.is_file():
            findings.append(
                _finding(
                    path=rel,
                    rule="missing_index",
                    surface=surface,
                    severity=_severity(registry, "missing_index", surface),
                    workflow=workflow,
                    evidence=str(surface.get("index")),
                    message="registered discoverability index does not exist",
                )
            )
        else:
            index_text = index_cache.setdefault(index_path, index_path.read_text(encoding="utf-8", errors="replace"))
            if not _is_discoverable(rel, surface, index_text):
                findings.append(
                    _finding(
                        path=rel,
                        rule="orphan_document",
                        surface=surface,
                        severity=_severity(registry, "orphan_document", surface),
                        workflow=workflow,
                        evidence=f"index={surface.get('index')}",
                        message="document is not discoverable from its registered index",
                    )
                )
    return findings


def run(
    *,
    root: Path = WORKSPACE,
    scope: str = "tracked",
    paths: list[str] | None = None,
    strict: bool = False,
    no_new_warnings: bool = False,
    today: date | None = None,
) -> dict[str, Any]:
    registry_path = REGISTRY_PATH
    if REGISTRY_PATH.is_relative_to(WORKSPACE):
        registry_path = root / REGISTRY_PATH.relative_to(WORKSPACE)
    registry = load_registry(registry_path)
    files = collect_markdown_files(root, scope=scope, paths=paths)
    findings = validate_registry(registry, root, registry_path)
    index_cache: dict[Path, str] = {}
    for path in files:
        findings.extend(
            check_file(
                path,
                root,
                registry,
                index_cache,
                today or datetime.now(timezone.utc).date(),
            )
        )
    baseline, registry_findings = evaluate_warning_baseline(
        findings,
        registry,
        today or datetime.now(timezone.utc).date(),
    )
    findings.extend(registry_findings)
    baseline_violations = _baseline_violation_findings(baseline)
    if no_new_warnings:
        findings.extend(baseline_violations)
    blocking = [
        finding
        for finding in findings
        if finding["severity"] == "error" or strict
    ]
    return {
        "ok": not blocking,
        "scope": scope,
        "strict": strict,
        "no_new_warnings": no_new_warnings,
        "files_scanned": len(files),
        "surfaces": len(registry.get("surfaces", [])),
        "findings": findings,
        "warning_baseline": {
            **baseline,
            "mode": "no-new-warnings" if no_new_warnings else "advisory",
            "violations": baseline_violations,
        },
        "summary": {
            "errors": sum(f["severity"] == "error" for f in findings),
            "warnings": sum(f["severity"] == "warning" for f in findings),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Document governance ownership/lifecycle checker")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument("--strict", action="store_true", help="treat warnings as blocking")
    parser.add_argument(
        "--no-new-warnings",
        action="store_true",
        help="block unbaselined or over-budget warnings while preserving baseline grace",
    )
    parser.add_argument("--scope", choices=("tracked", "workspace"), default="tracked")
    parser.add_argument("--files", nargs="*", default=None, help="check only these workspace-relative files")
    args = parser.parse_args(argv)
    try:
        result = run(
            scope=args.scope,
            paths=args.files,
            strict=args.strict,
            no_new_warnings=args.no_new_warnings,
        )
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        result = {
            "ok": False,
            "scope": args.scope,
            "strict": args.strict,
            "no_new_warnings": args.no_new_warnings,
            "files_scanned": 0,
            "surfaces": 0,
            "findings": [
                {
                    "path": str(REGISTRY_PATH.relative_to(WORKSPACE)),
                    "rule": "registry-integrity",
                    "owner": "governance-team",
                    "severity": "error",
                    "workflow": "project-doc-change",
                    "evidence": str(exc),
                    "message": "unable to load document governance registry",
                }
            ],
            "warning_baseline": {
                "configured": False,
                "mode": "no-new-warnings" if args.no_new_warnings else "advisory",
                "ok": False,
                "violations": [],
            },
            "summary": {"errors": 1, "warnings": 0},
        }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if result["ok"]:
            print(
                f"doc-governance-check: PASS ({result['files_scanned']} files, "
                f"{result['summary']['warnings']} warnings)"
            )
        else:
            print(
                f"doc-governance-check: FAIL ({result['summary']['errors']} errors, "
                f"{result['summary']['warnings']} warnings)"
            )
            for finding in result["findings"]:
                print(
                    f"{finding['path']}: {finding['rule']} [{finding['severity']}] "
                    f"{finding['message']} (evidence: {finding['evidence']})"
                )
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
