from __future__ import annotations

from pathlib import Path

from omo.omo_dashboard import _load_json


def test_load_json_accepts_multi_document_yaml(tmp_path: Path) -> None:
    payload = tmp_path / "dashboard.yaml"
    payload.write_text(
        "---\nstatus: active\nowner: governance\n---\n---\n"
        "current_phase: 42\n"
        "health_score: 98.0\n",
        encoding="utf-8",
    )

    result = _load_json(payload)

    assert result["status"] == "active"
    assert result["current_phase"] == 42
    assert result["health_score"] == 98.0
