"""Tests for internal-scene-trial.py — internal pipeline admission evidence recorder."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "internal_scene_trial", ROOT / "bin/ssot/internal-scene-trial.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["internal_scene_trial"] = module
    spec.loader.exec_module(module)
    return module


mod = _load_module()


def _base_scene_card() -> dict:
    """Minimal valid internal pipeline scene card for testing."""
    return {
        # Omit schema — preflight allows None but rejects v2
        "scene_type": "internal_pipeline",
        "lifecycle": "proposal_only",
        "activation": "forbidden",
        "scene_id": "test-internal",
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
        "permission_ref": "permission://internal/test-scene",
        "permission_scope": ["ci-read", "evidence-write"],
        "rollback_plan": "test-rollback",
        "sample_refs": [
            "evidence://github/pr/755",
            "evidence://github/pr/765",
            "evidence://github/pr/766",
        ],
        "activation_evidence_refs": [
            "evidence://github/pr/755",
            "evidence://github/pr/766",
        ],
        "required_capabilities": [
            "ref://capability/gac-local-gate",
        ],
        "approval_state": "confirmed",
        "activation_blockers": [],
    }


# ---------------------------------------------------------------------------
# --list tests
# ---------------------------------------------------------------------------


class TestListCommand:
    """Test --list output structure."""

    def test_list_returns_json_array(self, tmp_path: Path):
        """--list must return a JSON array of scene card summaries."""
        scene_dir = tmp_path / "docs" / "scene-cards"
        scene_dir.mkdir(parents=True)
        card = _base_scene_card()
        (scene_dir / "test-card.yaml").write_text(
            f"scene_id: {card['scene_id']}\nscene_type: internal_pipeline\n",
            encoding="utf-8",
        )
        result = mod.list_internal_scenes(root=tmp_path)
        assert isinstance(result, list)

    def test_list_entry_has_required_fields(self, tmp_path: Path):
        """Each --list entry must have scene_id, scene_type, trial_status."""
        scene_dir = tmp_path / "docs" / "scene-cards"
        scene_dir.mkdir(parents=True)
        card = _base_scene_card()
        (scene_dir / "test-card.yaml").write_text(
            f"scene_id: {card['scene_id']}\nscene_type: internal_pipeline\n",
            encoding="utf-8",
        )
        result = mod.list_internal_scenes(root=tmp_path)
        assert len(result) >= 1
        entry = result[0]
        assert "scene_id" in entry
        assert "scene_type" in entry
        assert "trial_status" in entry

    def test_list_shows_not_recorded_when_no_jsonl(self, tmp_path: Path):
        """trial_status should be 'not_recorded' when JSONL file is absent."""
        scene_dir = tmp_path / "docs" / "scene-cards"
        scene_dir.mkdir(parents=True)
        (scene_dir / "test-card.yaml").write_text(
            "scene_id: test-scene\nscene_type: internal_pipeline\n",
            encoding="utf-8",
        )
        result = mod.list_internal_scenes(root=tmp_path)
        assert any(e["trial_status"] == "not_recorded" for e in result)

    def test_list_shows_recorded_when_jsonl_has_entry(self, tmp_path: Path):
        """trial_status should be 'recorded' when JSONL has matching entry."""
        scene_dir = tmp_path / "docs" / "scene-cards"
        scene_dir.mkdir(parents=True)
        (scene_dir / "test-card.yaml").write_text(
            "scene_id: test-scene\nscene_type: internal_pipeline\n",
            encoding="utf-8",
        )
        trial_dir = tmp_path / ".omo" / "_knowledge" / "workflow-mesh"
        trial_dir.mkdir(parents=True)
        trial_log = trial_dir / "internal-scene-trials.jsonl"
        trial_log.write_text(
            json.dumps({"scene_id": "test-scene", "verdict": "pass"}) + "\n",
            encoding="utf-8",
        )
        result = mod.list_internal_scenes(root=tmp_path)
        assert any(e["trial_status"] == "recorded" for e in result)


# ---------------------------------------------------------------------------
# --record tests (use ROOT for preflight, tmp_path for JSONL output)
# ---------------------------------------------------------------------------


class TestRecordCommand:
    """Test --record writes JSONL and format is accepted by lifecycle Check4."""

    def test_record_creates_jsonl_file(self, tmp_path: Path):
        """--record must create the JSONL file if it doesn't exist."""
        card = _base_scene_card()
        trial_log = tmp_path / "internal-scene-trials.jsonl"
        assert not trial_log.exists()

        mod.record_trial(
            root=ROOT, scene_card=card,
            evidence_ref="evidence://test/1",
            trial_log_path=trial_log,
        )
        assert trial_log.exists()

    def test_record_jsonl_has_required_fields(self, tmp_path: Path):
        """JSONL entry must have scene_id, recorded_at, evidence_ref, verdict, operator."""
        card = _base_scene_card()
        trial_log = tmp_path / "internal-scene-trials.jsonl"

        mod.record_trial(
            root=ROOT, scene_card=card,
            evidence_ref="evidence://test/1",
            trial_log_path=trial_log,
        )

        lines = [l for l in trial_log.read_text(encoding="utf-8").strip().split("\n") if l]
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["scene_id"] == "test-internal"
        assert "recorded_at" in entry
        assert entry["evidence_ref"] == "evidence://test/1"
        assert entry["verdict"] == "pass"
        assert "operator" in entry

    def test_record_appends_not_overwrites(self, tmp_path: Path):
        """--record must append to JSONL, not overwrite existing entries."""
        card = _base_scene_card()
        trial_log = tmp_path / "internal-scene-trials.jsonl"
        trial_log.write_text(
            json.dumps({"scene_id": "other-scene", "verdict": "pass"}) + "\n",
            encoding="utf-8",
        )

        mod.record_trial(
            root=ROOT, scene_card=card,
            evidence_ref="evidence://test/2",
            trial_log_path=trial_log,
        )

        lines = [l for l in trial_log.read_text(encoding="utf-8").strip().split("\n") if l]
        assert len(lines) == 2
        assert json.loads(lines[0])["scene_id"] == "other-scene"
        assert json.loads(lines[1])["scene_id"] == "test-internal"

    def test_record_jsonl_format_accepted_by_lifecycle(self, tmp_path: Path):
        """JSONL file existence satisfies scene-card-lifecycle Check4 (trial_recorded)."""
        card = _base_scene_card()
        trial_log = tmp_path / "internal-scene-trials.jsonl"

        mod.record_trial(
            root=ROOT, scene_card=card,
            evidence_ref="evidence://test/1",
            trial_log_path=trial_log,
        )

        # Check4 just checks file existence for internal_pipeline
        assert trial_log.exists()


# ---------------------------------------------------------------------------
# Preflight failure → no write tests
# ---------------------------------------------------------------------------


class TestPreflightFailureNoWrite:
    """Test that preflight failure prevents JSONL write."""

    def test_preflight_fail_does_not_create_jsonl(self, tmp_path: Path):
        """When preflight fails, --record must NOT create the JSONL file."""
        card = _base_scene_card()
        # Remove required field to make preflight fail
        del card["permission_ref"]

        trial_log = tmp_path / "internal-scene-trials.jsonl"

        with pytest.raises(mod.PreflightFailedError):
            mod.record_trial(
                root=ROOT, scene_card=card,
                evidence_ref="evidence://test/1",
                trial_log_path=trial_log,
            )

        assert not trial_log.exists()

    def test_preflight_fail_returns_missing_fields(self, tmp_path: Path):
        """Preflight failure error must list the missing fields."""
        card = _base_scene_card()
        del card["required_capabilities"]

        with pytest.raises(mod.PreflightFailedError) as exc_info:
            mod.record_trial(
                root=ROOT, scene_card=card,
                evidence_ref="evidence://test/1",
                trial_log_path=tmp_path / "internal-scene-trials.jsonl",
            )

        assert "required_capabilities" in str(exc_info.value)


# ---------------------------------------------------------------------------
# --scene (preflight) tests
# ---------------------------------------------------------------------------


class TestSceneCommand:
    """Test --scene preflight execution."""

    def test_scene_returns_preflight_result(self):
        """--scene must return the preflight result dict."""
        card = _base_scene_card()
        result = mod.run_preflight(root=ROOT, scene_card=card)
        assert "schema" in result
        assert "status" in result
        assert "missing_fields" in result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_yaml_card(path: Path, card: dict) -> None:
    """Write a scene card as YAML."""
    try:
        import yaml

        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(card, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    except ImportError:
        # Fallback: write as JSON-like YAML
        lines = []
        for k, v in card.items():
            if isinstance(v, list):
                lines.append(f"{k}:")
                for item in v:
                    lines.append(f"  - {item}")
            else:
                lines.append(f"{k}: {v}")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
