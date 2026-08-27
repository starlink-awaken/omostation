from __future__ import annotations

from pathlib import Path

from lib.bos_neural_mesh_owner import inspect_bos_owner


def test_bos_owner_uses_workspace_state_and_never_invokes_connectors(tmp_path: Path) -> None:
    documents = tmp_path / "Documents"
    workspace = tmp_path / "Workspace"
    documents.mkdir()
    workspace.mkdir()

    result = inspect_bos_owner(documents, workspace)

    assert result["schema"] == "documents.bos-neural-mesh-owner.v1"
    assert result["state_db"] == str(workspace / "runtime/bos-neural-mesh-state.sqlite")
    assert Path(result["state_db"]).is_relative_to(workspace)
    assert result["invoked"] is False
    assert result["connector_invocations"] == 0


def test_bos_owner_reports_legacy_runner_and_state_as_retirement_findings(tmp_path: Path) -> None:
    documents = tmp_path / "Documents"
    workspace = tmp_path / "Workspace"
    documents.mkdir()
    workspace.mkdir()
    legacy_runner = documents / "@公共/_runtime/bos-neural-mesh-runner.py"
    legacy_db = documents / "@公共/_runtime/bos-neural-mesh-state.sqlite"
    legacy_runner.parent.mkdir(parents=True)
    legacy_runner.write_text("legacy\n", encoding="utf-8")
    legacy_db.write_bytes(b"sqlite-placeholder")

    result = inspect_bos_owner(documents, workspace)

    assert result["status"] == "findings"
    assert result["legacy_runner"] == "present"
    assert result["legacy_state_db"] == "present"
    assert "legacy BOS runner" in result["findings"][0]


def test_bos_owner_rejects_overlapping_roots(tmp_path: Path) -> None:
    documents = tmp_path / "Documents"
    documents.mkdir()

    result = inspect_bos_owner(documents, documents)

    assert result["status"] == "unavailable"
    assert "must not overlap" in result["errors"][0]
