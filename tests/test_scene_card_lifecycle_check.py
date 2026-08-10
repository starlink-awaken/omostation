"""Regression tests for W0-02 honest-gate fix.

Validates that invalid scene cards and failed validators cause the
canonical scene-card-check / journey-validate commands to exit nonzero
with deterministic machine-readable evidence.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_lifecycle():
    spec = importlib.util.spec_from_file_location(
        "scene_card_lifecycle", ROOT / "bin/ssot/scene-card-lifecycle.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


lifecycle_mod = _load_lifecycle()


def _write_scene_card(path: Path, **overrides: object) -> None:
    card = {
        "schema": "scene-card/v2",
        "scene_type": "external_resource",
        "lifecycle": "shadow",
        "activation": "preview",
        "scene_id": "test-scene",
        "journey_id": "test-journey",
        "goal": "test goal",
        "trigger": "test trigger",
        "input_contract": "test input",
        "result_contract": "test result",
        "outcome_metric": "test_metric",
        "consumer": "test-consumer",
        "approver": "test-approver",
        "owner": "test-owner",
        "failure_cost": "test failure",
        "data_classification": "internal",
        "data_scope": "test-scope",
        "operator": "test-operator",
        "permission_ref": "permission://test/scene",
        "rollback_plan": "test-rollback",
        "sample_refs": ["sample://test/1"],
        "demand_evidence_refs": ["evidence://test/demand"],
        "activation_evidence_refs": ["evidence://test/approval"],
        "required_capabilities": ["test.capability"],
        "bet": "BET-TEST-01",
        "falsifier": "test falsifier",
        "approval_state": "confirmed",
        "activation_blockers": [],
    }
    card.update(overrides)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\ntitle: Test Scene Card\nstatus: active\n---\n"
        + json.dumps(card, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


class TestSceneCardLifecycleHonestGate:
    def test_check_preflight_error_is_json_and_nonzero(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        card_path = tmp_path / "scene-card.yaml"
        _write_scene_card(card_path, scene_type="internal_pipeline")
        ret = lifecycle_mod.main(["--root", str(tmp_path), "check", "--scene-card", str(card_path)])
        assert ret == 2
        output = json.loads(capsys.readouterr().out)
        assert output["ready"] is False
        assert output["error_type"] in {"FileNotFoundError", "PreflightInputError"}

    def test_valid_card_validate_exits_zero(self, tmp_path: Path) -> None:
        card_path = tmp_path / "scene-card.yaml"
        _write_scene_card(card_path)
        ret = lifecycle_mod.main(["--root", str(tmp_path), "validate", "--scene-card", str(card_path)])
        assert ret == 0

    def test_invalid_card_missing_bet_validate_exits_nonzero(self, tmp_path: Path) -> None:
        card_path = tmp_path / "scene-card.yaml"
        _write_scene_card(card_path, bet="")
        ret = lifecycle_mod.main(["--root", str(tmp_path), "validate", "--scene-card", str(card_path)])
        assert ret == 1

    def test_invalid_card_with_blockers_check_exits_nonzero(self, tmp_path: Path) -> None:
        card_path = tmp_path / "scene-card.yaml"
        _write_scene_card(card_path, activation_blockers=["blocker1"])
        ret = lifecycle_mod.main(["--root", str(tmp_path), "check", "--scene-card", str(card_path)])
        assert ret == 1

    def test_validate_failing_card_missing_falsifier_exits_nonzero(self, tmp_path: Path) -> None:
        card_path = tmp_path / "scene-card.yaml"
        _write_scene_card(card_path, falsifier="")
        ret = lifecycle_mod.main(["--root", str(tmp_path), "validate", "--scene-card", str(card_path)])
        assert ret == 1

    def test_valid_card_check_exits_zero_with_trial_log(self, tmp_path: Path) -> None:
        card_path = tmp_path / "scene-card.yaml"
        _write_scene_card(card_path)
        trial_log = tmp_path / ".omo" / "_knowledge" / "workflow-mesh" / "external-scene-trials.jsonl"
        trial_log.parent.mkdir(parents=True, exist_ok=True)
        trial_log.write_text("{}", encoding="utf-8")
        ret = lifecycle_mod.main(["--root", str(tmp_path), "check", "--scene-card", str(card_path)])
        assert ret == 0
