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
import os
import sqlite3
import sys
import threading
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
    principal_ref = _digest({"principal_id": principal_id})

    weekly_samples = observation.get("weekly_samples")
    if not isinstance(weekly_samples, list):
        weekly_samples = []
    safe_weeks = [dict(item) for item in weekly_samples if isinstance(item, Mapping)]
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
        "current_week_qualifying_outcomes": int(latest.get("qualifying_episodes") or 0),
        "four_week_value_gate": personal_value,
        "total_episodes": int(observation.get("total_episodes") or 0),
        "verdict_distribution": dict(observation.get("verdict_distribution") or {}),
        "system_evidence_count": int(observation.get("system_evidence_count") or 0),
        "user_evidence_count": int(observation.get("user_evidence_count") or 0),
        "unknown_evidence_count": int(observation.get("unknown_evidence_count") or 0),
        "signal_to_verdict_latency_seconds": observation.get("signal_to_verdict_latency_seconds"),
        "weekly_samples": safe_weeks,
        "gate_gaps": list(observation.get("gate_gaps") or []),
    }
    digest_payload = {
        "schema": SNAPSHOT_SCHEMA,
        "principal_ref": principal_ref,
        "source_ref": source_ref,
        "event_count": int(source_facts.get("event_count") or 0),
        "tip_hash": str(source_facts.get("tip_hash") or ""),
        "integrity": dict(integrity) if isinstance(integrity, Mapping) else {},
        "metrics": metrics,
    }
    return {
        "schema": SNAPSHOT_SCHEMA,
        "status": status,
        "observed_at": observed_at,
        "principal_ref": principal_ref,
        "source": {
            "kind": "omo_causal_event_ledger",
            "ref": source_ref,
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

    connection = sqlite3.connect(
        f"{db_path.resolve().as_uri()}?mode=ro",
        uri=True,
        check_same_thread=False,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    journal_mode = str(connection.execute("PRAGMA journal_mode").fetchone()[0]).lower()
    broker = LedgerBroker(
        db_path,
        conn=connection,
        journal_mode=journal_mode,
        lock=threading.RLock(),
    )
    with broker:
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
