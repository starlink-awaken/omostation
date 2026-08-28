"""Regression tests for W0-02 honest-gate fix.

Validates that invalid scene cards and failed validators cause the
canonical scene-card-check / journey-validate commands to exit nonzero
with deterministic machine-readable evidence.

BET-Y1Q3-T4-03: the Make aggregate gate must reflect blockers in its
exit code — run the real `make scene-card-check` target from a
controlled cwd, not just the per-card Python validator.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_lifecycle():
    spec = importlib.util.spec_from_file_location("scene_card_lifecycle", ROOT / "bin/ssot/scene-card-lifecycle.py")
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
        "---\ntitle: Test Scene Card\nstatus: active\n---\n" + json.dumps(card, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


class TestSceneCardLifecycleHonestGate:
    def test_check_preflight_error_is_json_and_nonzero(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
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


class TestSceneCardMakeAggregateGate:
    """BET-Y1Q3-T4-03: make 聚合门退出码必须如实反映 blockers (spec §3).

    从真实 Make 入口运行 (make -f <ROOT>/Makefile scene-card-check)，受控
    cwd 自带 docs/scene-cards 测试卡 + bin symlink + trial log，不触碰真实
    runtime 数据面。
    """

    def _mk_env(self, tmp_path: Path, *cards: tuple[str, dict[str, object]]) -> None:
        (tmp_path / "bin").symlink_to(ROOT / "bin")
        trial_log = tmp_path / ".omo" / "_knowledge" / "workflow-mesh" / "external-scene-trials.jsonl"
        trial_log.parent.mkdir(parents=True, exist_ok=True)
        trial_log.write_text("{}", encoding="utf-8")
        for name, overrides in cards:
            _write_scene_card(tmp_path / "docs" / "scene-cards" / f"{name}.yaml", **overrides)

    def _run_make(self, cwd: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["make", "-f", str(ROOT / "Makefile"), "scene-card-check"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=120,
        )

    def test_mixed_cards_exit_nonzero(self, tmp_path: Path) -> None:
        self._mk_env(
            tmp_path,
            ("ready-card", {}),
            ("blocked-card", {"activation_blockers": ["blocker1"]}),
        )
        proc = self._run_make(tmp_path)
        assert "ready=1 with-blockers=1" in proc.stdout
        assert proc.returncode != 0  # 旧实现 false-green (exit 0) 必须在此 RED

    def test_all_ready_exit_zero(self, tmp_path: Path) -> None:
        self._mk_env(tmp_path, ("ready-card", {}))
        proc = self._run_make(tmp_path)
        assert "ready=1 with-blockers=0" in proc.stdout
        assert proc.returncode == 0

    def test_no_cards_exit_zero(self, tmp_path: Path) -> None:
        """无卡片 = vacuous ready, 必须退出零 (spec 回滚条款边界)."""
        (tmp_path / "bin").symlink_to(ROOT / "bin")
        proc = self._run_make(tmp_path)
        assert "ready=0 with-blockers=0" in proc.stdout
        assert proc.returncode == 0
