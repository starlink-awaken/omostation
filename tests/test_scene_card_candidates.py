from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).parents[1] / "bin/ssot/scene-card-candidates.py"
SPEC = importlib.util.spec_from_file_location("scene_card_candidates", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def _write_inputs(root: Path) -> None:
    (root / "docs").mkdir(parents=True)
    (root / ".omo/_truth/scenarios").mkdir(parents=True)
    (root / "docs/scene-card-candidate-seeds.yaml").write_text(
        """schema: scene-card-candidate-seeds/v1
candidates:
  - candidate_id: scene-candidate:meeting-supervision
    title: 会议到督办
    proposed_scene_id: meeting-supervision
    proposed_journey_id: meeting-to-delivery
    outcome_metric_hint: overdue_task_rate
    capability_refs: [kairon.ontoderive, omo.workflow_dispatch]
    discovery_refs: [docs/STRATEGY-3YEAR-PANORAMA.md#W3]
    safe_observations: [会议材料到任务回执]
""",
        encoding="utf-8",
    )
    (root / ".omo/_truth/scenarios/research.yaml").write_text(
        """---
status: active
---
id: research-pipeline
description: dry-run research binding
capabilities:
  - kairon.kronos
  - project.gbrain
bindings:
  - from: kairon.kronos
    to: project.gbrain
    mode: dry-run
failure_policy: fail-closed
""",
        encoding="utf-8",
    )


def test_collects_strategy_and_scenario_candidates_without_activation(tmp_path: Path) -> None:
    _write_inputs(tmp_path)

    payload = MODULE.collect_candidates(tmp_path)

    assert payload["schema"] == "scene-card-candidate/v1"
    assert payload["mode"] == "candidate_only"
    assert payload["activation"] == "forbidden"
    assert payload["summary"] == {
        "candidate_count": 2,
        "activation_eligible_count": 0,
        "requires_business_confirmation_count": 2,
    }
    candidates = {item["candidate_id"]: item for item in payload["candidates"]}
    meeting = candidates["scene-candidate:meeting-supervision"]
    research = candidates["scenario:research-pipeline"]
    assert meeting["discovery_source"] == "strategy_seed"
    assert research["discovery_source"] == "scenario_contract"
    assert meeting["activation_evidence_refs"] == []
    assert "owner" in meeting["missing_activation_fields"]
    assert "sample_refs" in research["missing_activation_fields"]
    assert "dry-run research binding" in research["safe_observations"]


def test_candidate_input_conflicts_fail_closed(tmp_path: Path) -> None:
    _write_inputs(tmp_path)
    seed = tmp_path / "docs/scene-card-candidate-seeds.yaml"
    seed.write_text(
        """schema: scene-card-candidate-seeds/v1
candidates:
  - candidate_id: scene-candidate:meeting-supervision
    title: conflicting title
    discovery_refs: [docs/other.md]
  - candidate_id: scene-candidate:meeting-supervision
    title: another conflicting title
    discovery_refs: [docs/third.md]
""",
        encoding="utf-8",
    )

    with pytest.raises(MODULE.CandidateInputError, match="conflicting candidate"):
        MODULE.collect_candidates(tmp_path)


def test_unsupported_seed_schema_fails_closed(tmp_path: Path) -> None:
    seed_file = tmp_path / "docs/scene-card-candidate-seeds.yaml"
    seed_file.parent.mkdir(parents=True)
    seed_file.write_text(
        "schema: scene-card-candidate-seeds/v0\ncandidates: []\n",
        encoding="utf-8",
    )

    with pytest.raises(MODULE.CandidateInputError, match="unsupported seed schema"):
        MODULE.collect_candidates(tmp_path)


def test_cli_output_is_machine_readable_and_does_not_write_state(
    tmp_path: Path, capsys
) -> None:
    _write_inputs(tmp_path)
    before = sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*"))

    assert MODULE.main(["--root", str(tmp_path)]) == 0
    output = json.loads(capsys.readouterr().out)

    after = sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*"))
    assert output["summary"]["candidate_count"] == 2
    assert after == before
