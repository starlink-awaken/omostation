"""Domain-level KEMS profile bound to Documents method/profile hashes."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Literal

from .content_checks import SourceConsistencyReport, check_source_consistency
from .graph_store import GraphStore
from .health import inspect_sqlite_database
from .pipeline import SourceManifest

SCHEMA = "kems.domain-profile.v1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_GRAPH_TABLES = (
    "document_versions",
    "evidence_spans",
    "entities",
    "relations",
    "extraction_runs",
    "review_decisions",
)
_PROFILE_COUNTS = ("document_versions", "evidence_spans", "entities", "relations")


@dataclass(frozen=True)
class DomainProfile:
    domain_id: str
    method_ref: str
    method_version: str
    method_sha256: str
    profile_ref: str
    profile_version: str
    profile_sha256: str
    source_bindings: tuple[tuple[str, str], ...]
    graph_counts: Mapping[str, int]
    database: Mapping[str, object]
    source_consistency: SourceConsistencyReport
    binding_sha256: str
    status: Literal["healthy", "degraded"]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": SCHEMA,
            "domain_id": self.domain_id,
            "status": self.status,
            "method": {
                "ref": self.method_ref,
                "version": self.method_version,
                "sha256": self.method_sha256,
            },
            "profile": {
                "ref": self.profile_ref,
                "version": self.profile_version,
                "sha256": self.profile_sha256,
            },
            "sources": [{"ref": source_ref, "sha256": sha256} for source_ref, sha256 in self.source_bindings],
            "graph_counts": dict(self.graph_counts),
            "database": dict(self.database),
            "source_consistency": self.source_consistency.to_dict(),
            "binding_sha256": self.binding_sha256,
        }


def _required(value: str, field: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field} is required")
    return stripped


def _digest(value: str, field: str) -> str:
    if not _SHA256.fullmatch(value):
        raise ValueError(f"{field} must be a lowercase 64-character SHA-256 digest")
    return value


def _binding_digest(payload: Mapping[str, object]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_domain_profile(
    *,
    domain_id: str,
    method_ref: str,
    method_version: str,
    method_sha256: str,
    profile_ref: str,
    profile_version: str,
    profile_sha256: str,
    sources: Iterable[SourceManifest],
    graph_store: GraphStore,
) -> DomainProfile:
    """Build a safe profile from existing GraphStore and health contracts."""
    domain_id = _required(domain_id, "domain_id")
    method_ref = _required(method_ref, "method_ref")
    method_version = _required(method_version, "method_version")
    method_sha256 = _digest(method_sha256, "method_sha256")
    profile_ref = _required(profile_ref, "profile_ref")
    profile_version = _required(profile_version, "profile_version")
    profile_sha256 = _digest(profile_sha256, "profile_sha256")
    checked_sources = tuple(sources)
    for source in checked_sources:
        _digest(source.content_sha256, f"source {source.source_id} content_sha256")

    health = inspect_sqlite_database("kems-graph", graph_store.db_path, expected_tables=_GRAPH_TABLES)
    if health.status == "missing":
        snapshot: dict[str, list[dict[str, object]]] = {table: [] for table in _PROFILE_COUNTS}
    else:
        snapshot = graph_store.export_snapshot(include_text=False)
    consistency = check_source_consistency(checked_sources, snapshot)

    source_bindings = tuple(sorted((source.source_id, source.content_sha256) for source in checked_sources))
    graph_counts = {table: len(snapshot.get(table, [])) for table in _PROFILE_COUNTS}
    database = {
        "status": health.status,
        "integrity": health.integrity,
        "private_mode": health.private_mode,
        "tables": list(health.tables),
        "row_counts": dict(health.row_counts),
        "missing_tables": list(health.missing_tables),
        "size_bytes": health.size_bytes,
    }
    binding = {
        "schema_version": SCHEMA,
        "domain_id": domain_id,
        "method": {
            "ref": method_ref,
            "version": method_version,
            "sha256": method_sha256,
        },
        "profile": {
            "ref": profile_ref,
            "version": profile_version,
            "sha256": profile_sha256,
        },
        "sources": [{"ref": source_ref, "sha256": sha256} for source_ref, sha256 in source_bindings],
    }
    status: Literal["healthy", "degraded"] = (
        "healthy" if health.status == "healthy" and consistency.status == "healthy" else "degraded"
    )
    return DomainProfile(
        domain_id=domain_id,
        method_ref=method_ref,
        method_version=method_version,
        method_sha256=method_sha256,
        profile_ref=profile_ref,
        profile_version=profile_version,
        profile_sha256=profile_sha256,
        source_bindings=source_bindings,
        graph_counts=graph_counts,
        database=database,
        source_consistency=consistency,
        binding_sha256=_binding_digest(binding),
        status=status,
    )
