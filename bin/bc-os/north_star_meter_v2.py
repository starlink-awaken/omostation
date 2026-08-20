#!/usr/bin/env python3
"""Read-only North Star projection over OMO's causal Event Ledger.

The meter is a projection, never a writer. Personal value is counted only
from the existing ``Outcome.Human.v1`` broker path and the causal evidence
validated by :class:`omo.personal_episode.PersonalEpisodeService`. Missing
identity, missing evidence, an unavailable observer, or a broken hash chain
is ``unprovable`` rather than guessed from PRs, BETs, tests, or a caller's
``consumer=human`` label.

Run with the OMO project environment::

    uv run --project projects/omo python bin/bc-os/north_star_meter_v2.py \
      --principal-id <principal-id> --json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LEDGER = ROOT / "runtime" / "omo" / "event-ledger.sqlite3"

# Kept only so callers can prove the legacy state writer is retired. No
# production path writes this file anymore.
CONSUMPTION_EVENTS = ROOT / ".omo" / "state" / "consumption-events.json"

SNAPSHOT_SCHEMA = "value-truth-snapshot/v1"
_CANONICAL_REPO_SOURCE = "repo://runtime/omo/event-ledger.sqlite3"
_LOCAL_SOURCE_RE = re.compile(r"^local-ledger:sha256:[0-9a-f]{64}$")
_TIP_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_WEEK_KEY_RE = re.compile(r"^[0-9]{4}-W(?:0[1-9]|[1-4][0-9]|5[0-3])$")
_VERDICTS = ("accept", "edit", "reject", "defer", "ignore")


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return f"sha256:{hashlib.sha256(_canonical(value).encode('utf-8')).hexdigest()}"


def _utc_now() -> str:
    # timezone.utc keeps this root CLI compatible with the deployed Python 3.9.
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")  # noqa: UP017


def _source_ref(path: Path) -> str:
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(ROOT.resolve())
    except ValueError:
        return f"local-ledger:{_digest(str(resolved))}"
    return f"repo://{relative.as_posix()}"


def _safe_source_ref(value: object) -> str:
    candidate = value if isinstance(value, str) else ""
    if candidate == _CANONICAL_REPO_SOURCE or _LOCAL_SOURCE_RE.fullmatch(candidate):
        return candidate
    return f"local-ledger:{_digest(candidate)}"


def _safe_observed_at(value: object) -> str:
    if not isinstance(value, str):
        return "unavailable"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return "unavailable"
    if parsed.tzinfo is None:
        return "unavailable"
    return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")  # noqa: UP017


def _nonnegative_int(value: object) -> int:
    return value if type(value) is int and value >= 0 else 0


def _optional_nonnegative_number(value: object) -> float | None:
    if type(value) not in (int, float):
        return None
    number = float(value)
    return number if math.isfinite(number) and number >= 0 else None


def _safe_verdict_distribution(value: object) -> dict[str, int]:
    if not isinstance(value, Mapping):
        return {}
    return {verdict: count for verdict in _VERDICTS if type(count := value.get(verdict)) is int and count >= 0}


def _safe_integrity(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    projected: dict[str, Any] = {}
    if type(value.get("ok")) is bool:
        projected["ok"] = value["ok"]
    if type(value.get("total")) is int and value["total"] >= 0:
        projected["total"] = value["total"]
    if type(value.get("first_bad_sequence")) is int and value["first_bad_sequence"] >= 0:
        projected["first_bad_sequence"] = value["first_bad_sequence"]
    return projected


def _safe_week(value: object) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    week_key = value.get("week_key")
    if not isinstance(week_key, str) or _WEEK_KEY_RE.fullmatch(week_key) is None:
        return None
    return {
        "week_key": week_key,
        "total_episodes": _nonnegative_int(value.get("total_episodes")),
        "qualifying_episodes": _nonnegative_int(value.get("qualifying_episodes")),
        "system_accept_episodes": _nonnegative_int(value.get("system_accept_episodes")),
        "complete_burden_episodes": _nonnegative_int(value.get("complete_burden_episodes")),
        "review_lt_saved_episodes": _nonnegative_int(value.get("review_lt_saved_episodes")),
        "summed_review_seconds": _optional_nonnegative_number(value.get("summed_review_seconds")),
        "summed_saved_seconds": _optional_nonnegative_number(value.get("summed_saved_seconds")),
        "verdict_distribution": _safe_verdict_distribution(value.get("verdict_distribution")),
        "system_evidence_count": _nonnegative_int(value.get("system_evidence_count")),
        "user_evidence_count": _nonnegative_int(value.get("user_evidence_count")),
        "unknown_evidence_count": _nonnegative_int(value.get("unknown_evidence_count")),
        "gate_met": value.get("gate_met") is True,
    }


def _safe_gate_gaps(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    projected: list[str] = []
    for item in value:
        if item == "no episodes observed":
            code = "no_episodes_observed"
        elif item == "no weekly samples":
            code = "no_weekly_samples"
        elif isinstance(item, str) and item.startswith("no qualifying weeks yet"):
            code = "no_qualifying_weeks"
        elif isinstance(item, str) and item.startswith("only "):
            code = "insufficient_qualifying_weeks"
        elif isinstance(item, str) and item.startswith("non-consecutive gap between "):
            code = "non_consecutive_qualifying_weeks"
        elif isinstance(item, str) and item.endswith(" week(s) below threshold (need >=3 qualifying episodes each)"):
            code = "below_weekly_threshold"
        else:
            continue
        if code not in projected:
            projected.append(code)
    return projected


def _unprovable(reason: str, *, observed_at: str | None = None) -> dict[str, Any]:
    return {
        "schema": SNAPSHOT_SCHEMA,
        "status": "unprovable",
        "reason": reason,
        "observed_at": observed_at or _utc_now(),
        "truth_axes": {
            "engineering_delivery": "not_measured",
            "operational_proof": "unprovable",
            "personal_value": "unprovable",
        },
    }


def record_consumption(
    scene_id: str,
    action: str,
    consumer: str = "human",
    metadata: dict | None = None,
    journey_id: str | None = None,
) -> dict[str, Any]:
    """Reject the retired direct writer while preserving its call shape."""
    del scene_id, action, consumer, metadata, journey_id
    return {"ok": False, "reason": "direct_recording_retired_use_omo_broker"}


def project_value_truth(
    *,
    principal_id: str,
    observation: Mapping[str, Any],
    source_facts: Mapping[str, Any],
    source_ref: str,
    observed_at: str,
) -> dict[str, Any]:
    """Create a privacy-safe, three-axis projection from verified facts."""
    integrity = source_facts.get("integrity")
    integrity_ok = isinstance(integrity, Mapping) and integrity.get("ok") is True
    principal_ref = _digest({"principal_id": principal_id if isinstance(principal_id, str) else ""})
    safe_source_ref = _safe_source_ref(source_ref)
    safe_observed_at = _safe_observed_at(observed_at)
    safe_integrity = _safe_integrity(integrity)
    raw_tip_hash = source_facts.get("tip_hash")
    safe_tip_hash = (
        raw_tip_hash if isinstance(raw_tip_hash, str) and _TIP_HASH_RE.fullmatch(raw_tip_hash) is not None else ""
    )

    weekly_samples = observation.get("weekly_samples")
    if not isinstance(weekly_samples, list):
        weekly_samples = []
    safe_weeks = [week for item in weekly_samples if (week := _safe_week(item)) is not None]
    safe_weeks.sort(key=lambda item: str(item.get("week_key") or ""))
    latest = safe_weeks[-1] if safe_weeks else {}

    readiness = str(observation.get("readiness") or "not_ready")
    if not integrity_ok:
        status = "unprovable"
        operational = "failed"
        personal_value = "unprovable"
    else:
        operational = "proven"
        personal_value = readiness if readiness in {"passed", "collecting", "not_ready"} else "unprovable"
        status = "proven" if personal_value == "passed" else personal_value

    metrics = {
        "current_week": latest.get("week_key"),
        "current_week_qualifying_outcomes": _nonnegative_int(latest.get("qualifying_episodes")),
        "four_week_value_gate": personal_value,
        "total_episodes": _nonnegative_int(observation.get("total_episodes")),
        "verdict_distribution": _safe_verdict_distribution(observation.get("verdict_distribution")),
        "system_evidence_count": _nonnegative_int(observation.get("system_evidence_count")),
        "user_evidence_count": _nonnegative_int(observation.get("user_evidence_count")),
        "unknown_evidence_count": _nonnegative_int(observation.get("unknown_evidence_count")),
        "signal_to_verdict_latency_seconds": _optional_nonnegative_number(
            observation.get("signal_to_verdict_latency_seconds")
        ),
        "weekly_samples": safe_weeks,
        "gate_gaps": _safe_gate_gaps(observation.get("gate_gaps")),
    }
    digest_payload = {
        "schema": SNAPSHOT_SCHEMA,
        "principal_ref": principal_ref,
        "source_ref": safe_source_ref,
        "event_count": _nonnegative_int(source_facts.get("event_count")),
        "tip_hash": safe_tip_hash,
        "integrity": safe_integrity,
        "metrics": metrics,
    }
    return {
        "schema": SNAPSHOT_SCHEMA,
        "status": status,
        "observed_at": safe_observed_at,
        "principal_ref": principal_ref,
        "source": {
            "kind": "omo_causal_event_ledger",
            "ref": safe_source_ref,
            "event_count": digest_payload["event_count"],
            "tip_hash": digest_payload["tip_hash"],
            "integrity": digest_payload["integrity"],
            "query_digest": _digest(digest_payload),
        },
        "truth_axes": {
            "engineering_delivery": "not_measured",
            "operational_proof": operational,
            "personal_value": personal_value,
        },
        "metrics": metrics,
    }


def _observe_personal_value(db_path: Path, principal_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Use OMO's existing broker and personal-value projector."""
    omo_src = ROOT / "projects" / "omo" / "src"
    ecos_src = ROOT / "projects" / "ecos" / "src"
    for path in (str(ecos_src), str(omo_src)):
        if path not in sys.path:
            sys.path.insert(0, path)

    from omo.event_ledger.broker import LedgerBroker
    from omo.personal_episode import PersonalEpisodeService

    source_paths = (db_path, Path(str(db_path) + "-wal"), Path(str(db_path) + "-shm"))
    first_read = {path.name: path.read_bytes() for path in source_paths if path.is_file()}
    if db_path.name not in first_read:
        raise RuntimeError("event_ledger_missing")

    with tempfile.TemporaryDirectory(prefix="north-star-ledger-") as temp_dir:
        snapshot_path = Path(temp_dir) / db_path.name
        snapshot_path.write_bytes(first_read[db_path.name])
        wal_name = db_path.name + "-wal"
        if wal_name in first_read:
            Path(str(snapshot_path) + "-wal").write_bytes(first_read[wal_name])

        second_read = {path.name: path.read_bytes() for path in source_paths if path.is_file()}
        if second_read != first_read:
            raise RuntimeError("ledger_changed_during_snapshot")

        with LedgerBroker.connect(snapshot_path) as broker:
            before = broker.read()
            integrity = broker.verify_chain()
            observation = PersonalEpisodeService(broker).observe_principal(principal_id).to_dict()
            after = broker.read()
    before_identity = [(row.get("sequence"), row.get("event_hash")) for row in before]
    after_identity = [(row.get("sequence"), row.get("event_hash")) for row in after]
    if before_identity != after_identity:
        raise RuntimeError("ledger_changed_during_observation")
    return observation, {
        "event_count": len(after),
        "tip_hash": str(after[-1].get("event_hash") or "") if after else "",
        "integrity": integrity,
    }


def measure_value_truth(
    *,
    db_path: Path | str = DEFAULT_LEDGER,
    principal_id: str,
    observed_at: str | None = None,
) -> dict[str, Any]:
    """Read and project one principal's value truth without writing state."""
    observed = observed_at or _utc_now()
    principal = str(principal_id or "").strip()
    if not principal:
        return _unprovable("principal_id_required", observed_at=observed)
    path = Path(db_path)
    if not path.is_file():
        return _unprovable("event_ledger_missing", observed_at=observed)
    try:
        observation, source_facts = _observe_personal_value(path, principal)
    except ModuleNotFoundError:
        return _unprovable("observer_unavailable", observed_at=observed)
    except Exception as exc:  # Fail closed; do not expose paths or raw payloads.
        reason = str(exc) if str(exc) == "ledger_changed_during_observation" else "ledger_observation_failed"
        return _unprovable(reason, observed_at=observed)
    return project_value_truth(
        principal_id=principal,
        observation=observation,
        source_facts=source_facts,
        source_ref=_source_ref(path),
        observed_at=observed,
    )


def measure_consumed_journeys(hours: int = 168) -> dict[str, Any]:
    """Compatibility projection; direct legacy state is no longer consumed."""
    del hours
    return {"total": 0, "by_scene": {}, "by_action": {}, "status": "unprovable"}


def measure_completion_rate() -> float:
    """Compatibility projection; use ``measure_value_truth`` for the gate."""
    return 0.0


def weekly_report(
    *, db_path: Path | str = DEFAULT_LEDGER, principal_id: str = "", observed_at: str | None = None
) -> dict[str, Any]:
    return measure_value_truth(db_path=db_path, principal_id=principal_id, observed_at=observed_at)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--record", action="store_true", help="retired; always fails closed")
    parser.add_argument("--scene")
    parser.add_argument("--action")
    parser.add_argument("--consumer", default="human")
    parser.add_argument("--journey-id")
    parser.add_argument("--principal-id", default=os.environ.get("OMO_PRINCIPAL_ID", ""))
    parser.add_argument("--db-path", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--observed-at")
    args = parser.parse_args()

    if args.record:
        result = record_consumption(args.scene or "", args.action or "", args.consumer, journey_id=args.journey_id)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 2

    if (
        sys.version_info < (3, 11)
        and args.principal_id
        and args.db_path.is_file()
        and os.environ.get("NORTH_STAR_OMO_RUNTIME") != "1"
    ):
        command = [
            "uv",
            "run",
            "--project",
            str(ROOT / "projects" / "omo"),
            "--frozen",
            "python",
            str(Path(__file__).resolve()),
            *sys.argv[1:],
        ]
        env = {**os.environ, "NORTH_STAR_OMO_RUNTIME": "1", "PYTHONDONTWRITEBYTECODE": "1"}
        try:
            completed = subprocess.run(command, check=False, capture_output=True, text=True, env=env)
        except (OSError, subprocess.SubprocessError):
            completed = None
        if completed is None:
            report = _unprovable("observer_runtime_unavailable", observed_at=args.observed_at)
            print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
            return 2
        sys.stdout.write(completed.stdout)
        sys.stderr.write(completed.stderr)
        return completed.returncode

    report = weekly_report(db_path=args.db_path, principal_id=args.principal_id, observed_at=args.observed_at)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    else:
        axes = report["truth_axes"]
        print("=== Personal Value Truth ===")
        print(f"status: {report['status']}")
        print(f"operational_proof: {axes['operational_proof']}")
        print(f"personal_value: {axes['personal_value']}")
        if report.get("reason"):
            print(f"reason: {report['reason']}")
    return 2 if report["status"] == "unprovable" else 0


if __name__ == "__main__":
    raise SystemExit(main())
