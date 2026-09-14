from __future__ import annotations

import json
from pathlib import Path

from scripts.kems_adjudication_cli import main


def _item() -> dict[str, object]:
    return {
        "sample_id": "sample-1",
        "source_sha256": "a" * 64,
        "source_ref": "vault://redacted/sample-1",
        "scenario_id": "private-source-review-v1",
        "split": "shadow",
        "annotation_status": "pending",
    }


def _labels() -> dict[str, object]:
    return {
        "source_kind": "email",
        "document_type": "request",
        "actionability": "follow_up",
        "priority": "normal",
        "has_deadline": True,
        "has_owner": False,
        "requires_omo_task": True,
    }


def _seed(database: Path, tmp_path: Path) -> Path:
    from kos.kems import AdjudicationStore

    store = AdjudicationStore(database)
    store.ingest_queue([_item()])
    labels_path = tmp_path / "labels.json"
    labels_path.write_text(json.dumps(_labels()), encoding="utf-8")
    return labels_path


def test_cli_completes_two_person_adjudication_without_raw_text(tmp_path: Path, capsys) -> None:
    database = tmp_path / "adjudication.sqlite"
    labels_path = _seed(database, tmp_path)

    assert main(["--database", str(database), "claim", "--sample-id", "sample-1", "--annotator", "a"]) == 0
    assert main(["--database", str(database), "claim", "--sample-id", "sample-1", "--annotator", "b"]) == 0
    assert (
        main(
            [
                "--database",
                str(database),
                "annotate",
                "--sample-id",
                "sample-1",
                "--annotator",
                "a",
                "--annotation-version",
                "private-source-review-v1.0",
                "--labels-file",
                str(labels_path),
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "--database",
                str(database),
                "annotate",
                "--sample-id",
                "sample-1",
                "--annotator",
                "b",
                "--annotation-version",
                "private-source-review-v1.0",
                "--labels-file",
                str(labels_path),
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "--database",
                str(database),
                "adjudicate",
                "--sample-id",
                "sample-1",
                "--adjudicator",
                "reviewer",
                "--annotation-version",
                "private-source-review-v1.0",
                "--labels-file",
                str(labels_path),
            ]
        )
        == 0
    )

    assert main(["--database", str(database), "list", "--status", "adjudicated"]) == 0
    output = capsys.readouterr().out
    assert '"annotation_status": "adjudicated"' in output
    assert "raw_text" not in output
    assert "source_ref" in output


def test_cli_rejects_annotation_without_claim(tmp_path: Path, capsys) -> None:
    database = tmp_path / "adjudication.sqlite"
    labels_path = _seed(database, tmp_path)

    assert (
        main(
            [
                "--database",
                str(database),
                "annotate",
                "--sample-id",
                "sample-1",
                "--annotator",
                "unassigned",
                "--annotation-version",
                "private-source-review-v1.0",
                "--labels-file",
                str(labels_path),
            ]
        )
        == 1
    )
    assert "must claim" in capsys.readouterr().out
