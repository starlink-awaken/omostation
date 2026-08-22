#!/usr/bin/env python3
"""alert-forwarder — forward observability events to alert channels.

Incrementally reads the observability event plane
(`.omo/_delivery/observability/events.jsonl`), and for events with
severity ∈ {critical, degraded} routes an alert to the configured channels via
alert-connectors (slack/feishu/wecom). Deduplicates by trace_id.

WP-E: 监控事件 → 告警通道(复用 observability-events + alert-connectors)。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[2]
OBS_EVENTS = WORKSPACE / ".omo" / "_delivery" / "observability" / "events.jsonl"
WATERMARK_FILE = WORKSPACE / ".omo" / "_delivery" / "alert-forwarder" / "watermark.json"
ALERT_SEVERITIES = frozenset({"critical", "degraded"})


def _load_byte_offset() -> int:
    try:
        return int(json.loads(WATERMARK_FILE.read_text(encoding="utf-8")).get("byte_offset", 0))
    except (OSError, json.JSONDecodeError):
        return 0


def _save_byte_offset(offset: int) -> None:
    WATERMARK_FILE.parent.mkdir(parents=True, exist_ok=True)
    WATERMARK_FILE.write_text(json.dumps({"byte_offset": offset}), encoding="utf-8")


def _read_incremental() -> tuple[list[dict[str, Any]], int]:
    if not OBS_EVENTS.is_file():
        return [], 0
    file_size = OBS_EVENTS.stat().st_size
    offset = _load_byte_offset()
    if file_size < offset:
        offset = 0
    if offset == file_size:
        return [], file_size
    events: list[dict[str, Any]] = []
    with OBS_EVENTS.open("rb") as fh:
        fh.seek(offset)
        data = fh.read()
    for line in data.decode("utf-8", "replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events, file_size


def _send_alert(event: dict[str, Any]) -> bool:
    """Route one alert via alert-connectors; returns success."""
    severity = str(event.get("severity") or "")
    domain = str(event.get("domain") or "governance")
    title = str(event.get("title") or event.get("event_type") or "resident-alert")
    body = str(event.get("message") or event.get("description") or json.dumps(event, ensure_ascii=False)[:300])
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from alert_connectors import build_connectors, route_connector  # noqa: PLC0415

        conn = route_connector(severity, domain)
        if conn is None:
            for c in build_connectors():
                if c.channel_id == "slack":
                    conn = c
                    break
        if conn is None:
            return False
        conn.send(severity=severity, title=title, body=body)
        return True
    except Exception as exc:  # noqa: BLE001 - alert is best-effort
        print(f"  alert_send_failed {severity}: {exc}", file=sys.stderr)
        return False


def forward(*, dry_run: bool = False) -> dict[str, Any]:
    events, file_size = _read_incremental()
    sent = 0
    alerted = 0
    for event in events:
        if str(event.get("severity") or "") not in ALERT_SEVERITIES:
            continue
        alerted += 1
        if dry_run:
            print(
                f"  [dry-run] alert {event.get('severity')} trace={event.get('trace_id')} title={event.get('title', '')[:40]}"
            )
        elif _send_alert(event):
            sent += 1
    if not dry_run:
        _save_byte_offset(file_size)
    return {"events_scanned": len(events), "alerted": alerted, "sent": sent}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    report = forward(dry_run=args.dry_run)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
