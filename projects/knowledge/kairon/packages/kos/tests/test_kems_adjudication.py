from __future__ import annotations

import pytest
from kos.kems import AdjudicationStore
from kos.kems.annotation_schema import annotation_schema


def item(sample_id: str = "sample-1") -> dict[str, object]:
    return {
        "sample_id": sample_id,
        "source_sha256": "a" * 64,
        "source_ref": "vault://redacted/sample-1",
        "scenario_id": "oa-notice",
        "split": "test",
        "annotation_status": "pending",
    }


def test_queue_is_idempotent_and_adjudication_is_auditable(tmp_path) -> None:
    store = AdjudicationStore(tmp_path / "adjudication.sqlite")

    assert store.ingest_queue([item()]) == 1
    assert store.ingest_queue([item()]) == 0
    assert store.list_items(status="pending")[0]["annotation_status"] == "pending"

    claimed = store.claim("sample-1", annotator="reviewer-1")
    assert claimed["annotation_status"] == "reviewed"
    assert store.claim("sample-1", annotator="reviewer-1")["annotator"] == "reviewer-1"
    store.submit_annotation(
        "sample-1",
        labels={"category": "notice", "priority": "normal"},
        annotation_version="ann-1",
        annotator="reviewer-1",
    )
    with pytest.raises(ValueError, match="already submitted"):
        store.submit_annotation(
            "sample-1",
            labels={"category": "notice", "priority": "normal"},
            annotation_version="ann-1",
            annotator="reviewer-1",
        )
    second_claim = store.claim("sample-1", annotator="reviewer-2")
    assert second_claim["claimed_annotators"] == ["reviewer-1", "reviewer-2"]
    with pytest.raises(ValueError, match="two independent annotator slots"):
        store.claim("sample-1", annotator="reviewer-3")
    second = store.submit_annotation(
        "sample-1",
        labels={"category": "notice", "priority": "normal"},
        annotation_version="ann-1",
        annotator="reviewer-2",
    )
    assert second["annotation_count"] == 2
    assert second["annotation_conflict"] is False
    result = store.adjudicate(
        "sample-1",
        labels={"category": "notice", "priority": "normal"},
        annotation_version="ann-2",
        adjudicator="reviewer-3",
    )

    assert result["annotation_status"] == "adjudicated"
    assert result["labels"] == {"category": "notice", "priority": "normal"}
    assert result["adjudicator"] == "reviewer-3"
    assert len(store.adjudicated_items()) == 1


def test_queue_rejects_raw_content_and_invalid_refs(tmp_path) -> None:
    store = AdjudicationStore(tmp_path / "adjudication.sqlite")

    with pytest.raises(ValueError, match="raw content"):
        store.ingest_queue([item() | {"text": "private"}])
    with pytest.raises(ValueError, match="vault://redacted"):
        store.ingest_queue([item() | {"source_ref": "file:///private/source"}])


def test_adjudication_rejects_raw_labels_and_unknown_samples(tmp_path) -> None:
    store = AdjudicationStore(tmp_path / "adjudication.sqlite")
    store.ingest_queue([item()])

    with pytest.raises(ValueError, match="raw content"):
        store.submit_annotation("sample-1", labels={"text": "private"}, annotation_version="ann-1", annotator="r")
    with pytest.raises(KeyError):
        store.adjudicate("missing", labels={"category": "notice"}, annotation_version="ann-1", annotator="r")


def test_conflicting_annotations_require_external_adjudicator(tmp_path) -> None:
    store = AdjudicationStore(tmp_path / "adjudication.sqlite")
    store.ingest_queue([item()])
    store.claim("sample-1", annotator="a")
    store.claim("sample-1", annotator="b")
    store.submit_annotation("sample-1", labels={"priority": "high"}, annotation_version="ann-1", annotator="a")
    conflict = store.submit_annotation(
        "sample-1", labels={"priority": "low"}, annotation_version="ann-1", annotator="b"
    )
    assert conflict["annotation_status"] == "conflict"
    assert conflict["annotation_conflict"] is True
    with pytest.raises(ValueError, match="independent from annotators"):
        store.adjudicate("sample-1", labels={"priority": "high"}, annotation_version="ann-2", annotator="a")
    final = store.adjudicate(
        "sample-1", labels={"priority": "high"}, annotation_version="ann-2", annotator="adjudicator"
    )
    assert final["annotation_status"] == "adjudicated"
    assert final["adjudicator"] == "adjudicator"


def test_annotation_requires_a_claim(tmp_path) -> None:
    store = AdjudicationStore(tmp_path / "adjudication.sqlite")
    store.ingest_queue([item()])
    with pytest.raises(ValueError, match="must claim"):
        store.submit_annotation(
            "sample-1", labels={"priority": "normal"}, annotation_version="ann-1", annotator="unassigned"
        )


def private_item() -> dict[str, object]:
    return item("private-sample") | {"scenario_id": "private-source-review-v1", "split": "shadow"}


def private_labels() -> dict[str, object]:
    return {
        "source_kind": "email",
        "document_type": "request",
        "actionability": "follow_up",
        "priority": "normal",
        "has_deadline": True,
        "has_owner": False,
        "requires_omo_task": True,
    }


def test_private_source_review_enforces_versioned_label_contract(tmp_path) -> None:
    store = AdjudicationStore(tmp_path / "adjudication.sqlite")
    store.ingest_queue([private_item()])
    store.claim("private-sample", annotator="reviewer-a")

    with pytest.raises(ValueError, match="schema mismatch"):
        store.submit_annotation(
            "private-sample",
            labels={"priority": "normal"},
            annotation_version="private-source-review-v1.0",
            annotator="reviewer-a",
        )
    with pytest.raises(ValueError, match="unsupported fields"):
        store.submit_annotation(
            "private-sample",
            labels=private_labels() | {"note": "free text"},
            annotation_version="private-source-review-v1.0",
            annotator="reviewer-a",
        )

    store.submit_annotation(
        "private-sample",
        labels=private_labels(),
        annotation_version="private-source-review-v1.0",
        annotator="reviewer-a",
    )
    store.claim("private-sample", annotator="reviewer-b")
    store.submit_annotation(
        "private-sample",
        labels=private_labels(),
        annotation_version="private-source-review-v1.0",
        annotator="reviewer-b",
    )
    result = store.adjudicate(
        "private-sample",
        labels=private_labels(),
        annotation_version="private-source-review-v1.0",
        adjudicator="reviewer-c",
    )
    assert result["annotation_status"] == "adjudicated"


def test_private_source_review_schema_is_versioned_and_public() -> None:
    schema = annotation_schema("private-source-review-v1")

    assert schema["schema_version"] == "private-source-review-v1.0"
    assert [field["name"] for field in schema["fields"]] == [
        "source_kind",
        "document_type",
        "actionability",
        "priority",
        "has_deadline",
        "has_owner",
        "requires_omo_task",
    ]


def test_engineering_delivery_review_has_a_strict_label_contract(tmp_path) -> None:
    scenario = "engineering-delivery-review-v1"
    labels = {
        "delivery_quality": "complete",
        "evidence_sufficiency": "sufficient",
        "workflow_alignment": "aligned",
        "requires_follow_up": False,
    }
    schema = annotation_schema(scenario)
    assert schema["schema_version"] == "engineering-delivery-review-v1.0"
    assert [field["name"] for field in schema["fields"]] == [
        "delivery_quality",
        "evidence_sufficiency",
        "workflow_alignment",
        "requires_follow_up",
    ]

    store = AdjudicationStore(tmp_path / "adjudication.sqlite")
    store.ingest_queue([item("engineering-sample") | {"scenario_id": scenario, "split": "shadow"}])
    store.claim("engineering-sample", annotator="reviewer-a")
    with pytest.raises(ValueError, match="schema mismatch"):
        store.submit_annotation(
            "engineering-sample",
            labels=labels | {"note": "free text"},
            annotation_version="engineering-delivery-review-v1.0",
            annotator="reviewer-a",
        )
    store.submit_annotation(
        "engineering-sample",
        labels=labels,
        annotation_version="engineering-delivery-review-v1.0",
        annotator="reviewer-a",
    )
