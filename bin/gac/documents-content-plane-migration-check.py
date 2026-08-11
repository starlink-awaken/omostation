"""Validate Documents runtime/cache migration coverage without mutating content."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY = (
    ROOT / ".omo" / "_truth" / "registry" / "documents-content-plane-migrations.yaml"
)

_KINDS = {"runtime", "cache"}
_DISPOSITIONS = {"content_archive", "delegate", "migrate", "relocate", "retire"}
_STATUSES = {"pending", "in_progress", "blocked", "verified", "retired"}
_TERMINAL_STATUSES = {"verified", "retired"}
_CONFIRMATION_GATES = {
    "none",
    "before_write",
    "before_delete",
    "before_external_config",
}
_EVIDENCE_FIELDS = {
    "verified_at",
    "source_fingerprint",
    "target_fingerprint",
    "consumer_scan",
    "rollback_ref",
}


def _string_list(value: object) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(isinstance(item, str) and item for item in value)
    )


def _safe_globs(value: object) -> bool:
    if not _string_list(value):
        return False
    return all(
        not pattern.startswith("/") and ".." not in Path(pattern).parts
        for pattern in value
    )


def _load_registry(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        return None, [f"registry invalid: {exc}"]
    if not isinstance(raw, dict):
        return None, ["registry must be a mapping"]
    return raw, []


def _validate_registry(
    raw: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, str]], list[str]]:
    errors: list[str] = []
    if raw.get("apiVersion") != "workspace.omostation/v1":
        errors.append("apiVersion must be workspace.omostation/v1")
    if raw.get("kind") != "DocumentsContentPlaneMigrations":
        errors.append("kind must be DocumentsContentPlaneMigrations")
    if not isinstance(raw.get("owner"), str) or not raw["owner"].strip():
        errors.append("owner must be non-empty")

    candidate_kinds = raw.get("candidate_kinds")
    if not _string_list(candidate_kinds) or set(candidate_kinds) != _KINDS:
        errors.append("candidate_kinds must contain runtime and cache exactly once")

    families_raw = raw.get("families")
    if not isinstance(families_raw, list) or not families_raw:
        return [], [], [*errors, "families must be a non-empty list"]

    families: list[dict[str, Any]] = []
    ids: list[str] = []
    for index, item in enumerate(families_raw):
        prefix = f"families[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be a mapping")
            continue
        family_id = item.get("id")
        if not isinstance(family_id, str) or not family_id.strip():
            errors.append(f"{prefix}.id must be non-empty")
            continue
        prefix = f"family {family_id}"
        ids.append(family_id)
        if not _safe_globs(item.get("source_globs")):
            errors.append(
                f"{prefix} source_globs must be safe non-empty relative patterns"
            )
        excludes = item.get("exclude_globs", [])
        if excludes and not _safe_globs(excludes):
            errors.append(f"{prefix} exclude_globs must be safe relative patterns")
        kinds = item.get("artifact_kind")
        if not _string_list(kinds) or not set(kinds).issubset(_KINDS):
            errors.append(f"{prefix} artifact_kind must use runtime/cache")
        if item.get("disposition") not in _DISPOSITIONS:
            errors.append(
                f"{prefix} has unsupported disposition: {item.get('disposition')}"
            )
        if not isinstance(item.get("owner"), str) or not item["owner"].strip():
            errors.append(f"{prefix} owner must be non-empty")
        if (
            not isinstance(item.get("replacement"), str)
            or not item["replacement"].strip()
        ):
            errors.append(f"{prefix} replacement must be non-empty")
        if not _string_list(item.get("consumer_refs")):
            errors.append(f"{prefix} consumer_refs must be a non-empty string list")
        if not isinstance(item.get("rollback"), str) or not item["rollback"].strip():
            errors.append(f"{prefix} rollback must be non-empty")
        if item.get("confirmation_gate") not in _CONFIRMATION_GATES:
            errors.append(
                f"{prefix} has unsupported confirmation_gate: {item.get('confirmation_gate')}"
            )
        status = item.get("status")
        if status not in _STATUSES:
            errors.append(f"{prefix} has unsupported status: {status}")
        elif status in _TERMINAL_STATUSES:
            evidence = item.get("evidence")
            evidence_complete = (
                isinstance(evidence, dict)
                and _EVIDENCE_FIELDS.issubset(evidence)
                and all(
                    isinstance(evidence[field], str) and evidence[field].strip()
                    for field in _EVIDENCE_FIELDS
                )
            )
            if not evidence_complete:
                errors.append(
                    f"{prefix} terminal status requires evidence: {', '.join(sorted(_EVIDENCE_FIELDS))}"
                )
        families.append(item)

    if len(ids) != len(set(ids)):
        errors.append("families contains duplicate ids")

    major_surfaces = raw.get("major_surfaces")
    if not _string_list(major_surfaces):
        errors.append("major_surfaces must be a non-empty string list")
        major_set: set[str] = set()
    else:
        major_set = set(major_surfaces)
        if len(major_set) != len(major_surfaces):
            errors.append("major_surfaces contains duplicate ids")
    flagged_major = {
        item["id"] for item in families if item.get("major_surface") is True
    }
    if major_set != flagged_major:
        errors.append("major_surfaces must equal families marked major_surface")
    unknown_major = sorted(major_set - set(ids))
    if unknown_major:
        errors.append(
            f"major_surfaces references unknown families: {', '.join(unknown_major)}"
        )

    samples_raw = raw.get("coverage_samples")
    samples: list[dict[str, str]] = []
    if not isinstance(samples_raw, list) or not samples_raw:
        errors.append("coverage_samples must be a non-empty list")
    else:
        for index, sample in enumerate(samples_raw):
            if not isinstance(sample, dict):
                errors.append(f"coverage_samples[{index}] must be a mapping")
                continue
            path = sample.get("relative_path")
            kind = sample.get("kind")
            family_id = sample.get("family")
            if (
                not isinstance(path, str)
                or not path
                or path.startswith("/")
                or ".." in Path(path).parts
            ):
                errors.append(
                    f"coverage_samples[{index}].relative_path must be safe and relative"
                )
                continue
            if kind not in _KINDS:
                errors.append(f"coverage_samples[{index}].kind must be runtime/cache")
                continue
            if family_id not in ids:
                errors.append(
                    f"coverage_samples[{index}] references unknown family: {family_id}"
                )
                continue
            samples.append({"relative_path": path, "kind": kind, "family": family_id})
    sampled_families = {sample["family"] for sample in samples}
    missing_samples = sorted(set(ids) - sampled_families)
    if missing_samples:
        errors.append(
            f"families missing coverage samples: {', '.join(missing_samples)}"
        )

    return families, samples, errors


def _matches(candidate: dict[str, str], family: dict[str, Any]) -> bool:
    if candidate["kind"] not in family.get("artifact_kind", []):
        return False
    path = candidate["relative_path"]
    if not any(
        fnmatchcase(path, pattern) for pattern in family.get("source_globs", [])
    ):
        return False
    return not any(
        fnmatchcase(path, pattern) for pattern in family.get("exclude_globs", [])
    )


def _coverage(
    candidates: list[dict[str, str]], families: list[dict[str, Any]]
) -> tuple[dict[str, int], dict[str, int], list[str], list[str]]:
    family_counts = {family["id"]: 0 for family in families}
    kind_counts: Counter[str] = Counter()
    zero_matches: list[str] = []
    multiple_matches: list[str] = []
    seen: set[tuple[str, str]] = set()

    for candidate in candidates:
        path = candidate.get("relative_path")
        kind = candidate.get("kind")
        if not isinstance(path, str) or not path or kind not in _KINDS:
            zero_matches.append(f"invalid candidate: {candidate}")
            continue
        key = (path, kind)
        if key in seen:
            multiple_matches.append(f"duplicate candidate: {path} ({kind})")
            continue
        seen.add(key)
        kind_counts[kind] += 1
        matched = [family["id"] for family in families if _matches(candidate, family)]
        if not matched:
            zero_matches.append(f"zero matches: {path} ({kind})")
        elif len(matched) > 1:
            multiple_matches.append(
                f"multiple matches: {path} ({kind}) -> {', '.join(matched)}"
            )
        else:
            family_counts[matched[0]] += 1
    return (
        family_counts,
        dict(sorted(kind_counts.items())),
        zero_matches,
        multiple_matches,
    )


def check_migrations(
    registry_path: Path,
    *,
    candidates: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Validate registry structure and exact-one coverage for samples or live candidates."""

    raw, errors = _load_registry(registry_path)
    if raw is None:
        return {
            "ok": False,
            "mode": "unavailable",
            "candidate_count": 0,
            "family_counts": {},
            "kind_counts": {},
            "non_terminal_families": [],
            "errors": errors,
        }
    families, samples, validation_errors = _validate_registry(raw)
    errors.extend(validation_errors)

    sample_candidates = [
        {"relative_path": sample["relative_path"], "kind": sample["kind"]}
        for sample in samples
    ]
    _, _, sample_zero, sample_multiple = _coverage(sample_candidates, families)
    errors.extend(f"sample {message}" for message in sample_zero)
    errors.extend(f"sample {message}" for message in sample_multiple)
    for sample in samples:
        matched = [family["id"] for family in families if _matches(sample, family)]
        if matched != [sample["family"]]:
            errors.append(
                f"sample {sample['relative_path']} expected {sample['family']} but matched {', '.join(matched) or 'none'}"
            )

    mode = "live" if candidates is not None else "samples"
    checked = candidates if candidates is not None else sample_candidates
    family_counts, kind_counts, zero_matches, multiple_matches = _coverage(
        checked, families
    )
    non_terminal_families = [
        family["id"]
        for family in families
        if family.get("status") not in _TERMINAL_STATUSES
    ]
    errors.extend(zero_matches[:50])
    errors.extend(multiple_matches[:50])
    if len(zero_matches) > 50:
        errors.append(f"zero matches truncated: {len(zero_matches) - 50} more")
    if len(multiple_matches) > 50:
        errors.append(f"multiple matches truncated: {len(multiple_matches) - 50} more")

    return {
        "ok": not errors,
        "mode": mode,
        "candidate_count": len(checked),
        "family_counts": family_counts,
        "kind_counts": kind_counts,
        "non_terminal_families": non_terminal_families,
        "zero_match_count": len(zero_matches),
        "multiple_match_count": len(multiple_matches),
        "errors": errors,
    }


def _audit_candidates(
    documents_root: Path,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    l4_src = ROOT / "projects" / "l4-kernel" / "src"
    if str(l4_src) not in sys.path:
        sys.path.insert(0, str(l4_src))
    from l4_kernel.content_plane import (
        audit_content_plane,  # type: ignore[import-not-found]
    )

    report = audit_content_plane(documents_root)
    candidates = [
        {"relative_path": item.relative_path, "kind": item.kind}
        for item in report.artifacts
        if item.kind in _KINDS
    ]
    return candidates, {
        "artifact_count": len(report.artifacts),
        "counts": report.counts,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--documents-root", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        if args.documents_root:
            documents_root = args.documents_root.resolve()
            candidates, audit = _audit_candidates(documents_root)
            report = check_migrations(args.registry.resolve(), candidates=candidates)
            report["audit"] = audit
            if audit["artifact_count"] == 0 and any(documents_root.iterdir()):
                report["ok"] = False
                report["errors"].append(
                    f"audit returned zero artifacts for non-empty Documents root: {documents_root}"
                )
            if not candidates and report["non_terminal_families"]:
                report["ok"] = False
                report["errors"].append(
                    "audit returned zero migration candidates while non-terminal "
                    "families remain: " + ", ".join(report["non_terminal_families"])
                )
        else:
            report = check_migrations(args.registry.resolve())
    except Exception as exc:  # noqa: BLE001 - stable CLI boundary for owner/audit failures
        report = {
            "ok": False,
            "mode": "unavailable",
            "candidate_count": 0,
            "family_counts": {},
            "kind_counts": {},
            "non_terminal_families": [],
            "errors": [f"migration check unavailable: {exc}"],
        }
    if args.json:
        print(json.dumps(report, ensure_ascii=False))
    else:
        print(
            "documents migrations: ok"
            if report["ok"]
            else "documents migrations: failed"
        )
        print(f"mode={report['mode']} candidates={report['candidate_count']}")
        for error in report["errors"]:
            print(f"- {error}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
