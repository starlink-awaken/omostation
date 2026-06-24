from __future__ import annotations

from pathlib import Path

from omo.omo_mesh_event_handler import _write_to_omo_state


def test_write_to_omo_state_accepts_existing_multi_document_yaml(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    state_path = tmp_path / "Workspace" / ".omo" / "state" / "mesh_node_states.yaml"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        "---\nstatus: active\nowner: runtime\n---\n---\n"
        "schema_version: 1\n"
        "nodes:\n"
        "  node-a:\n"
        "    status: old\n",
        encoding="utf-8",
    )

    _write_to_omo_state("node-a", {"status": "healthy"})

    content = state_path.read_text(encoding="utf-8")
    assert "node-a" in content
    assert "healthy" in content
