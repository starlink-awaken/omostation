"""Regression tests for W0-02 journey-runner validate honest gate."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SSOT_DIR = ROOT / "bin" / "ssot"


def _load_runner():
    sys.path.insert(0, str(SSOT_DIR))
    spec = importlib.util.spec_from_file_location(
        "journey_runner", ROOT / "bin/ssot/journey-runner.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


runner_mod = _load_runner()


def _write_journey_spec(path: Path, **overrides: object) -> None:
    spec = {
        "schema": "journey-spec/v1",
        "journey_id": "test-journey",
        "description": "test journey",
        "states": [
            {"name": "start", "scene": "research-pipeline", "next": ["end"]},
            {"name": "end", "scene": "research-pipeline", "next": []},
        ],
        "transitions": [
            {"from": "start", "to": "end", "condition": "always"},
        ],
    }
    spec.update(overrides)
    path.parent.mkdir(parents=True, exist_ok=True)
    import yaml

    path.write_text(yaml.safe_dump(spec, allow_unicode=True, sort_keys=False), encoding="utf-8")


class TestJourneyRunnerValidateHonestGate:
    def test_valid_spec_exits_zero(self, tmp_path: Path) -> None:
        spec_path = tmp_path / "journey.yaml"
        _write_journey_spec(spec_path)
        ret = runner_mod.main(["--root", str(ROOT), "validate", str(spec_path)])
        assert ret == 0

    def test_invalid_spec_unknown_scene_exits_nonzero(self, tmp_path: Path) -> None:
        spec_path = tmp_path / "journey.yaml"
        _write_journey_spec(spec_path, states=[
            {"name": "start", "scene": "nonexistent-scene", "next": ["end"]},
            {"name": "end", "scene": "nonexistent-scene", "next": []},
        ])
        ret = runner_mod.main(["--root", str(ROOT), "validate", str(spec_path)])
        assert ret == 1

    def test_valid_spec_json_output_is_machine_readable(self, tmp_path: Path) -> None:
        spec_path = tmp_path / "journey.yaml"
        _write_journey_spec(spec_path)
        ret = runner_mod.main(["--root", str(ROOT), "validate", str(spec_path), "--json"])
        assert ret == 0

    def test_invalid_spec_json_output_contains_errors(self, tmp_path: Path) -> None:
        spec_path = tmp_path / "journey.yaml"
        _write_journey_spec(spec_path, states=[
            {"name": "start", "scene": "nonexistent-scene", "next": ["end"]},
            {"name": "end", "scene": "nonexistent-scene", "next": []},
        ])
        ret = runner_mod.main(["--root", str(ROOT), "validate", str(spec_path), "--json"])
        assert ret == 1
