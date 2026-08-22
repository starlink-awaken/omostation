#!/usr/bin/env python3
"""event-ingest-adapter — publish workflow-mesh JSONL events to the unified bus.

Reads `.omo/_knowledge/workflow-mesh/events.jsonl` (append-only workflow-mesh
event log), publishes each new event to bus_foundation with a canonical
`mesh:workflow:*` topic, and records a publish watermark so re-runs never
re-publish already-published events.

Publish path is best-effort: if bus_foundation is unavailable the script
reports the failure but does not advance the watermark (retry on next run).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# ── topic mapping ────────────────────────────────────────────────────
_EVENT_TYPE_TOPIC: dict[str, str] = {
    "WorkflowRequested": "mesh:workflow:requested",
    "WorkflowAdmitted": "mesh:workflow:started",
    "WorkflowStarted": "mesh:workflow:started",
    "StepDispatched": "mesh:workflow:started",
    "StepStarted": "mesh:workflow:started",
    "WorkflowSucceeded": "mesh:workflow:closed",
    "WorkflowClosed": "mesh:workflow:closed",
    "WorkflowFailed": "mesh:workflow:failed",
    "StepFailed": "mesh:step:failed",
    "StepTimeout": "mesh:step:failed",
}
_FALLBACK_TOPIC = "mesh:event:raw"

WORKSPACE = Path(__file__).resolve().parents[2]
EVENTS_JSONL = WORKSPACE / ".omo" / "_knowledge" / "workflow-mesh" / "events.jsonl"
WATERMARK_FILE = WORKSPACE / ".omo" / "_delivery" / "event-ingest" / "watermark.json"


def _inject_bus_foundation_path() -> None:
    """Make bus_foundation importable from the submodule without install."""
    candidate = WORKSPACE / "projects" / "bus-foundation" / "src"
    if candidate.is_dir() and str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))


def _load_watermark() -> str:
    """Return the last published event_id (empty string when none)."""
    try:
        data = json.loads(WATERMARK_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    return str(data.get("workflow_mesh_last_event_id") or "")


def _save_watermark(event_id: str) -> None:
    WATERMARK_FILE.parent.mkdir(parents=True, exist_ok=True)
    WATERMARK_FILE.write_text(
        json.dumps({"workflow_mesh_last_event_id": event_id}, indent=2),
        encoding="utf-8",
    )


def _read_events(events_jsonl: Path) -> list[dict[str, Any]]:
    if not events_jsonl.is_file():
        return []
    events: list[dict[str, Any]] = []
    for line in events_jsonl.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def publish_events(*, dry_run: bool = False, events_jsonl: Path = EVENTS_JSONL, ledger: Path | None = None) -> dict[str, Any]:
    """Publish new events to the bus; optionally also ingest into the ledger."""
    last_id = _load_watermark()
    events = _read_events(events_jsonl)

    # Optionally ingest new events into the event ledger (jsonl_shadow is
    # idempotent by content hash), so the resident daemon can consume them.
    ledger_report = None
    if ledger is not None and not dry_run:
        ledger_report = _ingest_into_ledger(events_jsonl, ledger)

    # New events are those after the watermark (by file order).
    new_events: list[dict[str, Any]] = []
    seen_last = not last_id
    for ev in events:
        ev_id = str(ev.get("event_id") or "")
        if ev_id == last_id:
            seen_last = True
            continue
        if seen_last:
            new_events.append(ev)

    if not new_events:
        return {"published": 0, "skipped_duplicates": 0, "new_events": 0}

    if dry_run:
        return {
            "published": 0,
            "dry_run": True,
            "new_events": len(new_events),
            "samples": [
                {
                    "event_type": ev.get("event_type"),
                    "topic": _EVENT_TYPE_TOPIC.get(ev.get("event_type", ""), _FALLBACK_TOPIC),
                    "workflow_run_id": ev.get("workflow_run_id"),
                }
                for ev in new_events[:5]
            ],
        }

    try:
        _inject_bus_foundation_path()
        from bus_foundation.facade import event as bus_event  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - environment dependent
        return {"published": 0, "error": f"bus_foundation unavailable: {exc}", "new_events": len(new_events)}

    published = 0
    failed = 0
    for ev in new_events:
        event_type = str(ev.get("event_type") or "")
        topic = _EVENT_TYPE_TOPIC.get(event_type, _FALLBACK_TOPIC)
        ev_id = str(ev.get("event_id") or "")
        payload = {
            "event_type": event_type,
            "workflow_run_id": ev.get("workflow_run_id"),
            "trace_id": ev.get("trace_id"),
            "occurred_at": ev.get("occurred_at"),
            "producer": ev.get("producer"),
            "event_id": ev_id,
        }
        try:
            bus_event.publish(
                topic=topic,
                payload=payload,
                source_uri="bos://capability/workflow-mesh/jsonl",
                trace_id=str(ev.get("trace_id") or ev_id),
            )
            published += 1
            # advance watermark as we go so a partial failure resumes correctly
            _save_watermark(ev_id)
        except Exception as exc:  # noqa: BLE001 - bus publish is best-effort
            failed += 1
            print(f"  publish failed {topic} ({event_type}): {exc}", file=sys.stderr)
            break  # stop at first failure; watermark stays at last good event

    return {
        "published": published,
        "failed": failed,
        "new_events": len(new_events),
        "watermark": _load_watermark(),
        "ledger": ledger_report,
    }


def _ingest_into_ledger(events_jsonl: Path, ledger: Path) -> dict[str, Any]:
    """Idempotently import the JSONL into the event ledger (shadow events)."""
    try:
        _inject_omo_path()
        from omo.event_ledger.broker import LedgerBroker  # noqa: PLC0415
        from omo.event_ledger.jsonl_shadow import import_jsonl  # noqa: PLC0415

        broker = LedgerBroker.connect(str(ledger))
        try:
            report = import_jsonl(broker, events_jsonl)
        finally:
            broker.close()
        return {
            "imported": report.get("imported", 0),
            "duplicates": report.get("duplicates", 0),
            "quarantined": report.get("quarantined", 0),
        }
    except Exception as exc:  # noqa: BLE001 - ledger ingest is optional
        return {"error": f"ledger ingest failed: {type(exc).__name__}: {exc}"}


def _inject_omo_path() -> None:
    candidate = WORKSPACE / "projects" / "omo" / "src"
    if candidate.is_dir() and str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="show new events without publishing")
    parser.add_argument("--events-jsonl", type=Path, default=EVENTS_JSONL, help="override events.jsonl path")
    parser.add_argument("--ledger", type=Path, default=None, help="also ingest into this event ledger")
    args = parser.parse_args()

    report = publish_events(dry_run=args.dry_run, events_jsonl=args.events_jsonl, ledger=args.ledger)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report.get("failed", 0) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
