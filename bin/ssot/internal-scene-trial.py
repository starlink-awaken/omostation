#!/usr/bin/env python3
"""Build and optionally persist a proposal-only internal pipeline scene trial.

Mirrors external-scene-trial.py but uses internal-scene-preflight for
capability validation against make targets instead of external resource catalog.
Never activates a provider or creates a WorkflowRun. ``--record`` persists
only the safe trial contract through OMO.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA = "internal-scene-trial/v1"
OPAQUE_PREFIXES = ("evidence://", "vault://redacted/", "ref://", "sample://")


class SceneTrialInputError(ValueError):
    """Raised when a trial plan cannot be safely normalized."""


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SceneTrialInputError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SceneTrialInputError(f"cannot read JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise SceneTrialInputError(f"JSON must be an object: {path}")
    return payload


def _text(value: Any, field: str, *, max_length: int = 500) -> str:
    text = str(value or "").strip()
    if not text:
        raise SceneTrialInputError(f"missing required field: {field}")
    if len(text) > max_length:
        raise SceneTrialInputError(f"field is too long: {field}")
    return text


def _opaque(value: Any, field: str) -> str:
    text = _text(value, field)
    if not text.startswith(OPAQUE_PREFIXES):
        raise SceneTrialInputError(f"{field} must be an opaque reference")
    return text


def _refs(value: Any, field: str, *, minimum: int = 2, maximum: int = 20) -> list[str]:
    if not isinstance(value, list):
        raise SceneTrialInputError(f"{field} must be a list")
    refs = sorted({_opaque(item, f"{field}.item") for item in value})
    if not minimum <= len(refs) <= maximum:
        raise SceneTrialInputError(f"{field} must contain {minimum}-{maximum} references")
    return refs


def _digest(value: Any) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"


def _trial_plan(plan: Mapping[str, Any], scene_card: Mapping[str, Any]) -> dict[str, Any]:
    """Validate trial plan — same schema as external-scene-trial (track-agnostic)."""
    if not isinstance(plan, Mapping):
        raise SceneTrialInputError("trial plan must be an object")
    metric = plan.get("metric")
    sample_plan = plan.get("sample_plan")
    if not isinstance(metric, Mapping) or not isinstance(sample_plan, Mapping):
        raise SceneTrialInputError("trial plan requires metric and sample_plan")
    metric_result = {
        "metric_id": _text(metric.get("metric_id"), "metric.metric_id", max_length=160),
        "direction": _text(metric.get("direction"), "metric.direction", max_length=32),
        "unit": str(metric.get("unit") or "").strip() or None,
        "target": metric.get("target"),
        "baseline_ref": _opaque(metric.get("baseline_ref"), "metric.baseline_ref"),
        "measurement_ref": _opaque(metric.get("measurement_ref"), "metric.measurement_ref"),
    }
    if metric_result["direction"] not in {"increase", "decrease", "target", "binary"}:
        raise SceneTrialInputError("metric.direction is unsupported")
    if metric_result["target"] is not None and (
        isinstance(metric_result["target"], bool)
        or not isinstance(metric_result["target"], (int, float))
    ):
        raise SceneTrialInputError("metric.target must be numeric")
    minimum_samples = sample_plan.get("minimum_samples")
    window_seconds = sample_plan.get("window_seconds")
    if isinstance(minimum_samples, bool) or not isinstance(minimum_samples, int) or not 1 <= minimum_samples <= 10000:
        raise SceneTrialInputError("sample_plan.minimum_samples must be 1-10000")
    if isinstance(window_seconds, bool) or not isinstance(window_seconds, int) or not 1 <= window_seconds <= 31536000:
        raise SceneTrialInputError("sample_plan.window_seconds must be 1-31536000")
    permission_ref = plan.get("permission_ref") or scene_card.get("permission_ref")
    return {
        "consumer_ref": _opaque(plan.get("consumer_ref"), "consumer_ref"),
        "owner_ref": _opaque(plan.get("owner_ref"), "owner_ref"),
        "approver_ref": _opaque(plan.get("approver_ref"), "approver_ref"),
        "permission_ref": _opaque(permission_ref, "permission_ref"),
        "evidence_refs": _refs(plan.get("evidence_refs"), "evidence_refs"),
        "preflight_ref": _opaque(
            plan.get("preflight_ref") or f"ref://internal-scene-trial/preflight/{_digest(plan)[:24]}",
            "preflight_ref",
        ),
        "catalog_observation_id": _text(
            plan.get("catalog_observation_id"), "catalog_observation_id", max_length=240
        ),
        "metric": metric_result,
        "sample_plan": {"minimum_samples": minimum_samples, "window_seconds": window_seconds},
        "rollback_ref": _opaque(plan.get("rollback_ref"), "rollback_ref"),
    }


def build_scene_trial(
    root: Path,
    scene_card: Mapping[str, Any],
    trial_plan: Mapping[str, Any],
    *,
    now: datetime | None = None,
    actor: str = "scene-trial",
    source_ref: str = "root:internal-scene-trial",
) -> dict[str, Any]:
    # Load intake + internal preflight
    intake_module = _load_module(root / "bin/ssot/scene-card-intake.py", "scene_card_intake_for_internal_trial")
    preflight_module = _load_module(
        root / "bin/ssot/internal-scene-preflight.py", "internal_preflight_for_trial"
    )
    intake = intake_module.build_intake(dict(scene_card))
    preflight = preflight_module.build_preflight(dict(scene_card), root=root, now=now)
    if intake["status"] == "blocked" or preflight["status"] == "blocked":
        return {
            "schema": SCHEMA,
            "mode": "proposal_only_trial",
            "status": "blocked",
            "activation": "forbidden",
            "next_action": "complete_scene_card_and_verify_internal_capabilities",
            "missing_fields": sorted(set(intake["missing_fields"] + preflight["missing_fields"])),
            "preflight": preflight,
            "side_effects": {
                "raw_content_read": False,
                "provider_called": False,
                "omo_written": False,
                "workflow_created": False,
                "activation_attempted": False,
            },
        }
    safe_plan = _trial_plan(trial_plan, scene_card)
    scene = preflight["scene"]
    identity = {
        "scene": scene,
        "preflight": {
            "status": preflight["status"],
            "observed_at": preflight.get("observed_at"),
        },
        "plan": safe_plan,
    }
    trial_digest = _digest(identity)
    trial = {
        "schema": SCHEMA,
        "mode": "proposal_only_trial",
        "track": "internal_pipeline",
        "trial_id": f"internal-scene-trial:{scene['scene_id']}:{trial_digest[7:23]}",
        "scene_binding": {
            "scene_id": scene["scene_id"],
            "journey_id": scene["journey_id"],
            "outcome_metric": scene["outcome_metric"],
        },
        **safe_plan,
        "trial_stage": "observation_only",
        "status": "proposal_only",
        "activation": "forbidden",
        "provider_invocation": False,
        "workflow_run_id": None,
        "feedback_contract": {"schema": "outcome-feedback/v1"},
        "actor": _text(actor, "actor", max_length=240),
        "source_ref": _text(source_ref, "source_ref"),
        "observed_at": (now or datetime.now(UTC)).isoformat(),
        "trial_digest": trial_digest,
        "preflight": {
            "status": preflight["status"],
            "next_action": "collect_real_trial_evidence",
            "activation": "forbidden",
        },
        "side_effects": {
            "raw_content_read": False,
            "provider_called": False,
            "omo_written": False,
            "workflow_created": False,
            "activation_attempted": False,
        },
    }
    return {"schema": "internal-scene-trial-result/v1", "status": "proposal_only", "trial": trial, "preflight": preflight}


def _run_omo(root: Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    """Persist trial to internal-scene-trials.jsonl (append-only, fcntl locked).

    Uses same AppendOnlyLog + fcntl_lock pattern as OMO's external scene trial
    recorder, but writes to a separate log for internal pipeline scenes. This
    avoids requiring an OMO submodule change for the internal track.
    """
    import fcntl

    log_path = root / ".omo" / "_knowledge" / "workflow-mesh" / "internal-scene-trials.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    entry = {
        "ts": (datetime.now(UTC)).isoformat(),
        "schema": SCHEMA,
        "digest": f"sha256:{digest}",
        **payload,
    }
    line = json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n"
    with open(log_path, "a", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            f.write(line)
            f.flush()
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    return {"receipt": f"internal-scene-trial:{digest[:16]}", "status": "recorded"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--scene-card", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=False, help="(ignored for internal track, kept for CLI compat)")
    parser.add_argument("--trial-plan", type=Path, required=True)
    parser.add_argument("--record", action="store_true", help="persist through the OMO broker")
    parser.add_argument("--actor", default="scene-trial")
    parser.add_argument("--source-ref", default="root:internal-scene-trial")
    args = parser.parse_args(argv)
    try:
        result = build_scene_trial(
            args.root,
            _load_json(args.scene_card),
            _load_json(args.trial_plan),
            actor=args.actor,
            source_ref=args.source_ref,
        )
        if args.record and result["status"] != "blocked":
            broker_payload = {
                key: value
                for key, value in result["trial"].items()
                if key not in {"mode", "trial_digest", "preflight", "side_effects"}
            }
            receipt = _run_omo(args.root, broker_payload)
            result["receipt"] = receipt.get("receipt")
            result["record_status"] = receipt.get("status")
    except (OSError, SceneTrialInputError, ValueError) as exc:
        print(f"internal-scene-trial: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
