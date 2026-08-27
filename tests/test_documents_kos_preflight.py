from __future__ import annotations

from pathlib import Path

from lib.documents_kos_preflight import inspect_kos_schedule


def test_kos_preflight_reports_missing_legacy_executable(tmp_path: Path) -> None:
    documents = tmp_path / "Documents"
    workspace = tmp_path / "Workspace"
    documents.mkdir()
    workspace.mkdir()

    result = inspect_kos_schedule(documents, workspace, executable=Path("/usr/local/bin/kos"))

    assert result["schema"] == "documents.kos-preflight.v1"
    assert result["status"] == "findings"
    assert result["summary"]["executable"] == "missing"
    assert result["summary"]["writes_documents"] is False


def test_kos_preflight_rejects_overlapping_roots(tmp_path: Path) -> None:
    documents = tmp_path / "Documents"
    documents.mkdir()

    result = inspect_kos_schedule(documents, documents)

    assert result["status"] == "unavailable"
    assert "must not overlap" in result["errors"][0]
