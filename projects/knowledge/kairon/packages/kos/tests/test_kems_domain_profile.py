from __future__ import annotations

import json

import pytest
from kos.kems import (
    DocumentVersion,
    EvidenceSpan,
    GraphEntity,
    GraphStore,
    SourceManifest,
    build_domain_profile,
)


def source(source_id: str = "source-1", **overrides: object) -> SourceManifest:
    values: dict[str, object] = {
        "source_id": source_id,
        "source_type": "documents-domain",
        "source_uri": "vault://private/source",
        "content_sha256": "a" * 64,
        "domain": "official_work",
        "sensitivity": "internal",
        "redaction_status": "verified",
        "connector_version": "documents-v1",
        "captured_at": "2026-08-12T00:00:00Z",
    }
    values.update(overrides)
    return SourceManifest(**values)  # type: ignore[reportArgumentType]


def seeded_store(tmp_path) -> GraphStore:
    store = GraphStore(tmp_path / "graph.sqlite")
    store.put_document_version(
        DocumentVersion(
            "source-1",
            "v1",
            "a" * 64,
            "official_work",
            "raw private source must never enter the profile",
        )
    )
    store.add_evidence(
        EvidenceSpan(
            "evidence-1",
            "source-1",
            "v1",
            "line=1",
            "raw private quote",
            "fixture",
            1.0,
        )
    )
    store.add_entity(
        GraphEntity(
            "entity-1",
            "policy",
            "Policy A",
            "source-1",
            "v1",
            "evidence-1",
            0.99,
        )
    )
    store.db_path.chmod(0o600)
    return store


def build(store: GraphStore, sources: tuple[SourceManifest, ...]):
    return build_domain_profile(
        domain_id="work-health",
        method_ref="documents://work-health/Method.md",
        method_version="v1",
        method_sha256="b" * 64,
        profile_ref="documents://work-health/profiles/Profile.md",
        profile_version="v1",
        profile_sha256="c" * 64,
        sources=sources,
        graph_store=store,
    )


def test_domain_profile_reuses_graph_and_health_without_exposing_raw_content(tmp_path) -> None:
    profile = build(seeded_store(tmp_path), (source(),))

    payload = profile.to_dict()
    encoded = json.dumps(payload, ensure_ascii=False)
    assert profile.status == "healthy"
    assert payload["graph_counts"] == {
        "document_versions": 1,
        "evidence_spans": 1,
        "entities": 1,
        "relations": 0,
    }
    assert payload["sources"] == [{"ref": "source-1", "sha256": "a" * 64}]
    assert payload["database"]["status"] == "healthy"
    assert "raw private" not in encoded
    assert "source_uri" not in encoded
    assert "vault://" not in encoded
    assert len(payload["binding_sha256"]) == 64


def test_domain_profile_degrades_on_hash_mismatch_or_unapproved_graph_source(tmp_path) -> None:
    store = seeded_store(tmp_path)
    store.put_document_version(
        DocumentVersion(
            "source-private",
            "v1",
            "d" * 64,
            "personal",
            "private body",
        )
    )
    store.db_path.chmod(0o600)

    profile = build(
        store,
        (
            source(content_sha256="f" * 64),
            source(
                "source-private",
                content_sha256="d" * 64,
                domain="personal",
                sensitivity="personal",
                redaction_status="pending",
            ),
        ),
    )

    consistency = profile.to_dict()["source_consistency"]
    assert profile.status == "degraded"
    assert consistency["hash_mismatch_refs"] == ["source-1"]
    assert consistency["unapproved_graph_refs"] == ["source-private"]
    assert "private body" not in json.dumps(profile.to_dict())


def test_domain_profile_rejects_non_digest_source_bindings(tmp_path) -> None:
    with pytest.raises(ValueError, match="source source-1 content_sha256"):
        build(seeded_store(tmp_path), (source(content_sha256="z" * 64),))
