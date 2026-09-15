from __future__ import annotations

import json
from datetime import date

import pytest
from kos.kems import ContentRecord, check_content_records


def record(ref: str, **metadata: object) -> ContentRecord:
    values: dict[str, object] = {
        "title": ref,
        "status": "active",
        "created": "2026-01-01",
        "last-reviewed": "2026-08-10",
        "tags": ["kems"],
    }
    values.update(metadata)
    return ContentRecord(ref=ref, sha256="a" * 64, metadata=values)


def test_content_checks_accept_complete_metadata_and_exact_index() -> None:
    report = check_content_records(
        [record("cards/one.md"), record("cards/two.md")],
        indexed_refs={"cards/one.md", "cards/two.md"},
        as_of=date(2026, 8, 12),
        warn_after_days=7,
        critical_after_days=14,
    )

    assert report.status == "healthy"
    assert report.to_dict() == {
        "schema_version": "kems.content-checks.v1",
        "status": "healthy",
        "record_count": 2,
        "indexed_count": 2,
        "issue_count": 0,
        "issues": [],
    }


def test_content_checks_fail_closed_on_contract_freshness_and_index_drift() -> None:
    report = check_content_records(
        [
            record("cards/missing.md", title=""),
            record("cards/stale.md", status="invented", **{"last-reviewed": "2026-06-01"}),
        ],
        indexed_refs={"cards/stale.md", "cards/ghost.md"},
        as_of=date(2026, 8, 12),
        required_fields=("title", "status", "created"),
        allowed_statuses=frozenset({"active", "archived", "draft"}),
        warn_after_days=7,
        critical_after_days=14,
    )

    payload = report.to_dict()
    assert report.status == "degraded"
    assert {issue["code"] for issue in payload["issues"]} == {
        "CONTENT_CRITICAL_STALE",
        "CONTENT_INDEX_DANGLING",
        "CONTENT_INDEX_MISSING",
        "CONTENT_INVALID_STATUS",
        "CONTENT_REQUIRED_FIELD",
    }
    assert "cards/stale.md" in json.dumps(payload)
    assert "invented" not in json.dumps(payload)


def test_content_records_reject_raw_content_and_invalid_identity() -> None:
    with pytest.raises(ValueError, match="raw content fields"):
        ContentRecord(
            ref="cards/private.md",
            sha256="a" * 64,
            metadata={"title": "private", "content": "raw private body"},
        )
    with pytest.raises(ValueError, match="64-character SHA-256"):
        ContentRecord(ref="cards/invalid.md", sha256="not-a-hash", metadata={})
