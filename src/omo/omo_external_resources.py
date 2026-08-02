"""Governed observation store for the External Connection Fabric.

Agora owns discovery and projection. OMO owns the durable observation record so
human and machine consumers can distinguish a governed observation from a
one-off live discovery result. This module never invokes an external provider.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from omo.omo_external_evaluation import (
    ExternalResourceEvaluationError,
    record_external_resource_evaluation,
)
from omo.omo_external_observation_run import (
    ExternalObservationRunError,
    record_external_observation_run,
)
from omo.omo_external_pack import (
    ExternalResourcePackProposalError,
    record_external_resource_pack_proposal,
)
from omo.omo_io import AppendOnlyLog, fcntl_lock, write_text_atomic
from omo.omo_paths import find_omo_dir
from omo.workflow_eval import build_external_resource_selection_dataset

CATALOG_SCHEMA = "external-resource-catalog/v1"
OBSERVATION_SCHEMA = "external-resource-observation/v1"
OBSERVATION_LOG_NAME = "external-resource-observations.jsonl"
OBSERVATION_LATEST_NAME = "external-resource-observation-latest.json"

_FORBIDDEN_KEYS = frozenset(
    {
        "access_token",
        "refresh_token",
        "password",
        "private_key",
        "raw_private_content",
        "content",
        "raw_content",
        "raw_input",
        "raw_output",
        "sample_data",
        "input_data",
        "output_data",
    }
)


class ExternalResourceObservationError(ValueError):
    """Raised when an observation is not a safe catalog projection."""


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _reject_forbidden(value: Any, path: str = "catalog") -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if str(key).lower() in _FORBIDDEN_KEYS:
                raise ExternalResourceObservationError(
                    f"forbidden raw or secret field: {path}.{key}"
                )
            _reject_forbidden(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_forbidden(nested, f"{path}[{index}]")


def _validate_catalog(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(snapshot, Mapping):
        raise ExternalResourceObservationError("catalog snapshot must be an object")
    _reject_forbidden(snapshot)
    if snapshot.get("schema") != CATALOG_SCHEMA:
        raise ExternalResourceObservationError("unexpected catalog schema")
    if snapshot.get("mode") != "read_only_projection":
        raise ExternalResourceObservationError("catalog must be read_only_projection")
    if snapshot.get("activation") != "forbidden":
        raise ExternalResourceObservationError("catalog activation must be forbidden")
    if not str(snapshot.get("observed_at") or "").strip():
        raise ExternalResourceObservationError("catalog observed_at is required")
    if not isinstance(snapshot.get("resources"), list):
        raise ExternalResourceObservationError("catalog resources must be a list")
    if not isinstance(snapshot.get("errors"), list):
        raise ExternalResourceObservationError("catalog errors must be a list")
    if not isinstance(snapshot.get("summary"), Mapping):
        raise ExternalResourceObservationError("catalog summary must be an object")
    changes = snapshot.get("changes")
    if changes is not None and (
        not isinstance(changes, Mapping)
        or changes.get("schema") != "external-resource-catalog-diff/v1"
    ):
        raise ExternalResourceObservationError("catalog changes have an invalid schema")
    return json.loads(_canonical(snapshot))


def _paths(omo_dir: Path) -> tuple[Path, Path]:
    log_dir = omo_dir / "_log"
    return log_dir / OBSERVATION_LOG_NAME, log_dir / OBSERVATION_LATEST_NAME


def read_latest_external_resource_observation(
    omo_dir: Path,
) -> dict[str, Any] | None:
    """Read the latest governed observation, or ``None`` before first run."""
    log_path, latest_path = _paths(omo_dir)
    candidates: list[dict[str, Any]] = []
    if latest_path.is_file():
        try:
            value = json.loads(latest_path.read_text(encoding="utf-8"))
            if isinstance(value, dict):
                candidates.append(value)
        except (OSError, json.JSONDecodeError):
            pass
    if not candidates:
        candidates.extend(AppendOnlyLog(log_path).tail(1))
    if not candidates:
        return None
    latest = candidates[-1]
    if latest.get("schema") != OBSERVATION_SCHEMA:
        raise ExternalResourceObservationError("latest observation schema is invalid")
    _reject_forbidden(latest)
    return latest


def record_external_resource_observation(
    omo_dir: Path,
    snapshot: Mapping[str, Any],
    *,
    actor: str = "external-resource-observer",
    source_ref: str = "omo:external-resources:observe",
) -> dict[str, Any]:
    """Validate and persist one safe catalog observation through OMO's log."""
    catalog = _validate_catalog(snapshot)
    catalog_state = dict(catalog)
    catalog_state.pop("observed_at", None)
    catalog_state.pop("changes", None)
    catalog_digest = _digest(catalog_state)
    observed_at = str(catalog["observed_at"])
    observation_key = _digest(
        {"catalog_digest": catalog_digest, "observed_at": observed_at}
    )

    previous = read_latest_external_resource_observation(omo_dir)
    if previous and previous.get("observation_key") == observation_key:
        return {
            "status": "deduplicated",
            "observation": previous,
        }

    changes = catalog.get("changes")
    change_summary = (changes or {}).get("summary", {}) if isinstance(changes, Mapping) else {}
    change_count = int(change_summary.get("change_count", 0) or 0)
    error_change_count = int(change_summary.get("error_change_count", 0) or 0)
    review_required = bool(change_summary.get("review_required", False))
    review_required_count = int(
        change_summary.get("review_required_count", 0) or 0
    )
    operational_observation_count = int(
        change_summary.get("operational_observation_count", 0) or 0
    )
    risk_codes = sorted(
        {
            str(code).strip()
            for code in change_summary.get("risk_codes", [])
            if str(code).strip()
        }
    )
    change_state = "baseline" if previous is None else (
        "changed" if change_count or error_change_count else "unchanged"
    )
    observation = {
        "schema": OBSERVATION_SCHEMA,
        "observation_id": f"external-resource-observation:{observation_key[:24]}",
        "observation_key": observation_key,
        "observed_at": observed_at,
        "recorded_at": _utc_now(),
        "actor": str(actor or "external-resource-observer"),
        "source_ref": str(source_ref or "omo:external-resources:observe"),
        "catalog_digest": catalog_digest,
        "change_state": change_state,
        "change_summary": {
            "change_count": change_count,
            "error_change_count": error_change_count,
            "review_required": review_required,
            "review_required_count": review_required_count,
            "operational_observation_count": operational_observation_count,
            "risk_codes": risk_codes,
        },
        "catalog": catalog,
    }
    log_path, latest_path = _paths(omo_dir)
    AppendOnlyLog(log_path, lock=fcntl_lock(log_path.with_suffix(".lock"))).append(
        observation, sort_keys=True
    )
    write_text_atomic(
        latest_path,
        json.dumps(observation, ensure_ascii=False, indent=2, sort_keys=True),
    )
    return {"status": "recorded", "observation": observation}


def _payload_from_stdin() -> dict[str, Any]:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ExternalResourceObservationError("stdin is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ExternalResourceObservationError("stdin payload must be an object")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="omo external-resources", description="Governed external resource observations"
    )
    sub = parser.add_subparsers(dest="command")
    observe = sub.add_parser("observe", help="validate and persist a catalog observation")
    observe.add_argument("--stdin", action="store_true", help="read catalog JSON from stdin")
    observe.add_argument("--actor", default="external-resource-observer")
    observe.add_argument("--source-ref", default="omo:external-resources:observe")
    latest = sub.add_parser("latest", help="read the latest governed observation")
    latest.add_argument("--json", action="store_true", help="emit JSON")
    record_evaluation = sub.add_parser(
        "record-evaluation", help="persist one safe selection evaluation"
    )
    record_evaluation.add_argument("--stdin", action="store_true")
    record_evaluation.add_argument("--workflow-run-id")
    record_evaluation.add_argument("--actor", default="cockpit")
    record_evaluation.add_argument(
        "--source-ref", default="omo:external-resources:evaluate"
    )
    record_evaluation.add_argument("--observed-at")
    record_evaluation.add_argument("--evaluation-id")
    record_pack_proposal = sub.add_parser(
        "record-pack-proposal", help="persist one safe external pack review receipt"
    )
    record_pack_proposal.add_argument("--stdin", action="store_true")
    record_pack_proposal.add_argument("--proposal-id", required=True)
    record_pack_proposal.add_argument("--review-action", default="submit")
    record_pack_proposal.add_argument("--actor", default="cockpit")
    record_pack_proposal.add_argument(
        "--source-ref", default="omo:external-resources:pack-proposal"
    )
    record_pack_proposal.add_argument("--review-ref")
    record_pack_proposal.add_argument("--recorded-at")
    record_pack_proposal.add_argument("--json", action="store_true")
    record_observation_run = sub.add_parser(
        "record-observation-run", help="persist one read-only catalog observation run receipt"
    )
    record_observation_run.add_argument("--stdin", action="store_true")
    selection_eval = sub.add_parser(
        "selection-eval", help="build the event-derived selection evaluation dataset"
    )
    selection_eval.add_argument("--scene-id")
    selection_eval.add_argument("--output", type=Path)
    selection_eval.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    omo_dir = find_omo_dir()

    if args.command == "latest":
        try:
            print(json.dumps({"ok": True, "observation": read_latest_external_resource_observation(omo_dir)}, ensure_ascii=False, indent=2, sort_keys=True))
        except ExternalResourceObservationError as exc:
            print(f"external-resources latest: {exc}", file=sys.stderr)
            return 2
        return 0
    if args.command == "record-evaluation":
        if not args.stdin:
            print("external-resources record-evaluation requires --stdin", file=sys.stderr)
            return 2
        try:
            result = record_external_resource_evaluation(
                omo_dir,
                _payload_from_stdin(),
                workflow_run_id=args.workflow_run_id,
                actor=args.actor,
                source_ref=args.source_ref,
                observed_at=args.observed_at,
                evaluation_id=args.evaluation_id,
            )
        except (ExternalResourceEvaluationError, OSError, ValueError) as exc:
            print(f"external-resources record-evaluation: {exc}", file=sys.stderr)
            return 2
        print(json.dumps({"ok": True, **result}, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if args.command == "record-pack-proposal":
        if not args.stdin:
            print("external-resources record-pack-proposal requires --stdin", file=sys.stderr)
            return 2
        try:
            result = record_external_resource_pack_proposal(
                omo_dir,
                _payload_from_stdin(),
                proposal_id=args.proposal_id,
                review_action=args.review_action,
                actor=args.actor,
                source_ref=args.source_ref,
                review_ref=args.review_ref,
                recorded_at=args.recorded_at,
            )
        except (ExternalResourcePackProposalError, OSError, ValueError) as exc:
            print(f"external-resources record-pack-proposal: {exc}", file=sys.stderr)
            return 2
        print(json.dumps({"ok": True, **result}, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if args.command == "record-observation-run":
        if not args.stdin:
            print("external-resources record-observation-run requires --stdin", file=sys.stderr)
            return 2
        try:
            result = record_external_observation_run(omo_dir, _payload_from_stdin())
        except (ExternalObservationRunError, OSError, ValueError) as exc:
            print(f"external-resources record-observation-run: {exc}", file=sys.stderr)
            return 2
        print(json.dumps({"ok": True, **result}, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if args.command == "selection-eval":
        try:
            dataset = build_external_resource_selection_dataset(
                omo_dir, scene_id=args.scene_id, output_path=args.output
            )
        except (ExternalResourceEvaluationError, OSError, ValueError) as exc:
            print(f"external-resources selection-eval: {exc}", file=sys.stderr)
            return 2
        print(json.dumps(dataset, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if args.command != "observe":
        parser.print_help()
        return 1
    if not args.stdin:
        print("external-resources observe requires --stdin", file=sys.stderr)
        return 2
    try:
        result = record_external_resource_observation(
            omo_dir,
            _payload_from_stdin(),
            actor=args.actor,
            source_ref=args.source_ref,
        )
    except (ExternalResourceObservationError, OSError, ValueError) as exc:
        print(f"external-resources observe: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"ok": True, **result}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


__all__ = (
    "CATALOG_SCHEMA",
    "OBSERVATION_SCHEMA",
    "ExternalResourceObservationError",
    "main",
    "read_latest_external_resource_observation",
    "record_external_resource_observation",
)
