#!/usr/bin/env python3
"""Discover safe Scene Card candidates without activating runtime capability.

The collector turns existing scenario contracts and explicitly curated
strategy seeds into reviewable candidates. It never reads or emits raw
business samples, never mutates OMO state, and never calls an activation API.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA = "scene-card-candidate/v1"
DEFAULT_SEED_FILE = Path("docs/scene-card-candidate-seeds.yaml")
DEFAULT_SCENARIO_DIR = Path(".omo/_truth/contracts")
CARD_FIELDS = (
    "scene_id",
    "journey_id",
    "goal",
    "trigger",
    "input_contract",
    "result_contract",
    "outcome_metric",
    "consumer",
    "approver",
    "owner",
    "failure_cost",
    "data_classification",
    "data_scope",
    "operator",
    "permission_ref",
    "rollback_plan",
    "sample_refs",
    "demand_evidence_or_opportunity_window",
)


class CandidateInputError(ValueError):
    """Raised when a governed discovery input cannot be safely normalized."""


def _text(value: Any, field: str) -> str:
    result = str(value or "").strip()
    if not result:
        raise CandidateInputError(f"missing required field: {field}")
    return result


def _refs(value: Any, field: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple, set)):
        raise CandidateInputError(f"{field} must be a list")
    return tuple(sorted({str(item).strip() for item in value if str(item).strip()}))


def _relative_ref(root: Path, path: Path, anchor: str = "") -> str:
    ref = path.relative_to(root).as_posix()
    return f"{ref}#{anchor}" if anchor else ref


def _resolve_input_path(root: Path, value: Path | None, default: Path) -> Path:
    """Resolve CLI input paths relative to the project root for repeatability."""
    path = value or default
    return (path if path.is_absolute() else root / path).resolve()


def _load_yaml_documents(path: Path) -> list[dict[str, Any]]:
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - exercised by CLI environment
        raise CandidateInputError("pyyaml is required for candidate discovery") from exc
    try:
        documents = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
    except (OSError, yaml.YAMLError) as exc:
        raise CandidateInputError(f"cannot read YAML: {path}") from exc
    return [document for document in documents if isinstance(document, dict)]


@dataclass(frozen=True)
class SceneCardCandidate:
    candidate_id: str
    title: str
    discovery_source: str
    discovery_refs: tuple[str, ...]
    proposed_scene_id: str
    proposed_journey_id: str
    outcome_metric_hint: str
    capability_refs: tuple[str, ...]
    safe_observations: tuple[str, ...]
    missing_fields: tuple[str, ...] = CARD_FIELDS

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "title": self.title,
            "status": "candidate",
            "discovery_source": self.discovery_source,
            "discovery_refs": list(self.discovery_refs),
            "proposed_scene_id": self.proposed_scene_id,
            "proposed_journey_id": self.proposed_journey_id,
            "outcome_metric_hint": self.outcome_metric_hint,
            "capability_refs": list(self.capability_refs),
            "safe_observations": list(self.safe_observations),
            "activation_evidence_refs": [],
            "sample_refs": [],
            "demand_evidence_refs": [],
            "opportunity_window": "",
            "missing_activation_fields": list(self.missing_fields),
        }


def _from_seed(root: Path, path: Path, seed: dict[str, Any]) -> SceneCardCandidate:
    candidate_id = _text(seed.get("candidate_id"), "candidate_id")
    title = _text(seed.get("title"), "title")
    refs = _refs(seed.get("discovery_refs"), "discovery_refs")
    if not refs:
        refs = (_relative_ref(root, path),)
    return SceneCardCandidate(
        candidate_id=candidate_id,
        title=title,
        discovery_source="strategy_seed",
        discovery_refs=refs,
        proposed_scene_id=str(seed.get("proposed_scene_id") or "").strip(),
        proposed_journey_id=str(seed.get("proposed_journey_id") or "").strip(),
        outcome_metric_hint=str(seed.get("outcome_metric_hint") or "").strip(),
        capability_refs=_refs(seed.get("capability_refs"), "capability_refs"),
        safe_observations=_refs(seed.get("safe_observations"), "safe_observations"),
    )


def _from_scenario(root: Path, path: Path, scenario: dict[str, Any]) -> SceneCardCandidate:
    scenario_id = _text(scenario.get("id"), "scenario.id")
    description = _text(scenario.get("description"), "scenario.description")
    capabilities = _refs(scenario.get("capabilities"), "scenario.capabilities")
    return SceneCardCandidate(
        candidate_id=f"scenario:{scenario_id}",
        title=scenario_id,
        discovery_source="scenario_contract",
        discovery_refs=(_relative_ref(root, path, scenario_id),),
        proposed_scene_id=f"scenario:{scenario_id}",
        proposed_journey_id="",
        outcome_metric_hint="",
        capability_refs=capabilities,
        safe_observations=(description,),
    )


def collect_candidates(
    root: Path,
    *,
    seed_file: Path | None = None,
    scenario_dir: Path | None = None,
) -> dict[str, Any]:
    """Build a deterministic, candidate-only projection from governed inputs."""
    root = root.resolve()
    seed_path = _resolve_input_path(root, seed_file, DEFAULT_SEED_FILE)
    scenario_path = _resolve_input_path(root, scenario_dir, DEFAULT_SCENARIO_DIR)
    candidates: list[SceneCardCandidate] = []

    if seed_path.exists():
        payload = _load_yaml_documents(seed_path)
        for document in payload:
            schema = document.get("schema")
            if schema and schema != "scene-card-candidate-seeds/v1":
                raise CandidateInputError(f"unsupported seed schema: {schema}")
            for seed in document.get("candidates", []) or []:
                if not isinstance(seed, dict):
                    raise CandidateInputError(f"candidate seed must be an object: {seed_path}")
                candidates.append(_from_seed(root, seed_path, seed))

    if scenario_path.exists():
        for path in sorted(scenario_path.glob("*.yaml")):
            for document in _load_yaml_documents(path):
                if "id" in document and "description" in document:
                    candidates.append(_from_scenario(root, path, document))

    by_id: dict[str, SceneCardCandidate] = {}
    for candidate in candidates:
        existing = by_id.get(candidate.candidate_id)
        if existing and existing != candidate:
            raise CandidateInputError(f"conflicting candidate definition: {candidate.candidate_id}")
        by_id[candidate.candidate_id] = candidate

    ordered = [by_id[key] for key in sorted(by_id)]
    return {
        "schema": SCHEMA,
        "mode": "candidate_only",
        "activation": "forbidden",
        "raw_content_policy": "never_read_or_export",
        "candidates": [candidate.to_dict() for candidate in ordered],
        "summary": {
            "candidate_count": len(ordered),
            "activation_eligible_count": 0,
            "requires_business_confirmation_count": len(ordered),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--seed-file", type=Path, default=None)
    parser.add_argument("--scenario-dir", type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        payload = collect_candidates(args.root, seed_file=args.seed_file, scenario_dir=args.scenario_dir)
    except CandidateInputError as exc:
        print(f"scene-card-candidates: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
