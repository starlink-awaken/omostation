from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).parents[2]


def _load_script(relative_path: str, module_name: str):
    path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


registry = _load_script("bin/ssot/scene-card-registry.py", "scene_card_registry_under_test")
connector = _load_script(
    "bin/gac/scene-journey-connector.py",
    "scene_journey_connector_under_test",
)


def _write_scene_card(root: Path, scene_id: str, *, schema: str = "scene-card/v2") -> Path:
    path = root / "docs" / "scene-cards" / f"{scene_id}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                f"schema: {schema}",
                "bet: BET-Y1Q4-T7-08",
                'falsifier: "no useful output"',
                f"scene_id: {scene_id}",
                "lifecycle: assisted",
                f"journey_id: {scene_id}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def test_registry_accepts_current_v2_card_without_legacy_fields(tmp_path: Path) -> None:
    card_path = _write_scene_card(tmp_path, "current-v2")

    assert registry.validate_scene(card_path) == []


def test_registry_reports_legacy_schema_as_warning(tmp_path: Path) -> None:
    card_path = _write_scene_card(tmp_path, "legacy-v1", schema="scene-card/v1")

    assert registry.validate_scene(card_path) == []
    assert any("legacy" in warning for warning in registry.scene_warnings(card_path))


def test_connector_reads_and_writes_only_selected_root(tmp_path: Path) -> None:
    card_path = _write_scene_card(tmp_path, "isolated-scene")
    journey_path = tmp_path / "docs" / "journey-specs" / "isolated-scene.yaml"
    journey_path.parent.mkdir(parents=True, exist_ok=True)
    journey_path.write_text("states: []\ntransitions: []\n", encoding="utf-8")

    assert connector.list_eligible_cards(tmp_path)[0]["path"] == str(card_path)
    state_path = tmp_path / ".omo" / "state" / "scene-journey-map.json"
    assert not state_path.exists()

    result = connector.create_journey("isolated-scene", tmp_path)

    assert result["ok"] is True
    assert state_path.exists()
    assert connector.STATE_FILE != state_path
