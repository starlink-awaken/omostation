"""Redacted, deterministic checks for Documents-owned KEMS content metadata."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Literal

from .pipeline import SourceManifest

SCHEMA = "kems.content-checks.v1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_RAW_FIELDS = {"body", "content", "ocr_text", "raw_text", "text"}

Severity = Literal["warning", "error"]


@dataclass(frozen=True)
class ContentRecord:
    """One metadata-only content record; raw document fields are rejected."""

    ref: str
    sha256: str
    metadata: Mapping[str, object]

    def __post_init__(self) -> None:
        if not self.ref.strip():
            raise ValueError("content ref is required")
        if not _SHA256.fullmatch(self.sha256):
            raise ValueError("sha256 must be a lowercase 64-character SHA-256 digest")
        if any(str(key).lower() in _RAW_FIELDS for key in self.metadata):
            raise ValueError("raw content fields are forbidden in KEMS content records")


@dataclass(frozen=True)
class ContentIssue:
    code: str
    severity: Severity
    ref: str
    sha256: str | None = None
    fields: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "code": self.code,
            "severity": self.severity,
            "ref": self.ref,
        }
        if self.sha256 is not None:
            result["sha256"] = self.sha256
        if self.fields:
            result["fields"] = list(self.fields)
        return result


@dataclass(frozen=True)
class ContentCheckReport:
    status: Literal["healthy", "warning", "degraded"]
    record_count: int
    indexed_count: int
    issues: tuple[ContentIssue, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": SCHEMA,
            "status": self.status,
            "record_count": self.record_count,
            "indexed_count": self.indexed_count,
            "issue_count": len(self.issues),
            "issues": [issue.to_dict() for issue in self.issues],
        }


@dataclass(frozen=True)
class SourceConsistencyReport:
    status: Literal["healthy", "degraded"]
    checked_source_count: int
    graph_document_count: int
    duplicate_source_refs: tuple[str, ...] = ()
    missing_graph_refs: tuple[str, ...] = ()
    hash_mismatch_refs: tuple[str, ...] = ()
    unapproved_graph_refs: tuple[str, ...] = ()
    unexpected_graph_refs: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "checked_source_count": self.checked_source_count,
            "graph_document_count": self.graph_document_count,
            "duplicate_source_refs": list(self.duplicate_source_refs),
            "missing_graph_refs": list(self.missing_graph_refs),
            "hash_mismatch_refs": list(self.hash_mismatch_refs),
            "unapproved_graph_refs": list(self.unapproved_graph_refs),
            "unexpected_graph_refs": list(self.unexpected_graph_refs),
        }


def _has_value(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, frozenset, dict)):
        return bool(value)
    return True


def _review_date(value: object) -> date | None:
    if not isinstance(value, str) or not _ISO_DATE.fullmatch(value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def check_content_records(
    records: Iterable[ContentRecord],
    *,
    indexed_refs: Iterable[str],
    as_of: date,
    required_fields: tuple[str, ...] = ("title", "status", "created"),
    allowed_statuses: frozenset[str] = frozenset({"active", "archived", "draft"}),
    warn_after_days: int = 90,
    critical_after_days: int = 180,
) -> ContentCheckReport:
    """Check frontmatter, freshness, and index coverage without retaining content."""
    if warn_after_days < 0 or critical_after_days <= warn_after_days:
        raise ValueError("freshness thresholds must satisfy 0 <= warn < critical")
    if not required_fields or not all(field.strip() for field in required_fields):
        raise ValueError("required_fields must contain non-empty names")

    checked = tuple(records)
    indexed = frozenset(indexed_refs)
    if any(not isinstance(ref, str) or not ref.strip() for ref in indexed):
        raise ValueError("indexed_refs must contain non-empty strings")

    issues: list[ContentIssue] = []
    counts = Counter(record.ref for record in checked)
    for ref in sorted(ref for ref, count in counts.items() if count > 1):
        issues.append(ContentIssue("CONTENT_DUPLICATE_REF", "error", ref))

    records_by_ref = {record.ref: record for record in checked}
    for record in checked:
        missing = tuple(field for field in required_fields if not _has_value(record.metadata.get(field)))
        if missing:
            issues.append(
                ContentIssue(
                    "CONTENT_REQUIRED_FIELD",
                    "error",
                    record.ref,
                    record.sha256,
                    missing,
                )
            )

        status = record.metadata.get("status")
        if _has_value(status) and (not isinstance(status, str) or status not in allowed_statuses):
            issues.append(ContentIssue("CONTENT_INVALID_STATUS", "error", record.ref, record.sha256, ("status",)))

        reviewed = record.metadata.get("last-reviewed")
        if not _has_value(reviewed):
            issues.append(
                ContentIssue("CONTENT_REVIEW_DATE_MISSING", "warning", record.ref, record.sha256, ("last-reviewed",))
            )
            continue
        reviewed_at = _review_date(reviewed)
        if reviewed_at is None or reviewed_at > as_of:
            issues.append(
                ContentIssue("CONTENT_REVIEW_DATE_INVALID", "error", record.ref, record.sha256, ("last-reviewed",))
            )
            continue
        age = (as_of - reviewed_at).days
        if age > critical_after_days:
            issues.append(ContentIssue("CONTENT_CRITICAL_STALE", "error", record.ref, record.sha256))
        elif age > warn_after_days:
            issues.append(ContentIssue("CONTENT_STALE", "warning", record.ref, record.sha256))

    for ref in sorted(set(records_by_ref) - indexed):
        record = records_by_ref[ref]
        issues.append(ContentIssue("CONTENT_INDEX_MISSING", "error", ref, record.sha256))
    for ref in sorted(indexed - set(records_by_ref)):
        issues.append(ContentIssue("CONTENT_INDEX_DANGLING", "error", ref))

    ordered = tuple(sorted(issues, key=lambda issue: (issue.code, issue.ref, issue.fields)))
    if any(issue.severity == "error" for issue in ordered):
        status_value: Literal["healthy", "warning", "degraded"] = "degraded"
    elif ordered:
        status_value = "warning"
    else:
        status_value = "healthy"
    return ContentCheckReport(status_value, len(checked), len(indexed), ordered)


def check_source_consistency(
    sources: Iterable[SourceManifest],
    graph_snapshot: Mapping[str, Iterable[Mapping[str, object]]],
) -> SourceConsistencyReport:
    """Compare immutable source manifests with a redacted GraphStore snapshot."""
    checked = tuple(sources)
    source_counts = Counter(source.source_id for source in checked)
    duplicates = tuple(sorted(ref for ref, count in source_counts.items() if count > 1))
    unique_sources = {source.source_id: source for source in checked}

    documents: dict[str, Mapping[str, object]] = {}
    for document in graph_snapshot.get("document_versions", []):
        document_id = document.get("document_id")
        if isinstance(document_id, str) and document_id:
            documents[document_id] = document

    missing: list[str] = []
    mismatched: list[str] = []
    unapproved: list[str] = []
    for source_id, source in sorted(unique_sources.items()):
        graph_document = documents.get(source_id)
        if source.admitted_to_work_graph:
            if graph_document is None:
                missing.append(source_id)
            elif graph_document.get("source_sha256") != source.content_sha256:
                mismatched.append(source_id)
        elif graph_document is not None:
            unapproved.append(source_id)

    unexpected = sorted(set(documents) - set(unique_sources))
    categories = (duplicates, missing, mismatched, unapproved, tuple(unexpected))
    status: Literal["healthy", "degraded"] = "degraded" if any(categories) else "healthy"
    return SourceConsistencyReport(
        status=status,
        checked_source_count=len(checked),
        graph_document_count=len(documents),
        duplicate_source_refs=duplicates,
        missing_graph_refs=tuple(missing),
        hash_mismatch_refs=tuple(mismatched),
        unapproved_graph_refs=tuple(unapproved),
        unexpected_graph_refs=tuple(unexpected),
    )
