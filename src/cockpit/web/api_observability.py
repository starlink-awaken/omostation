"""Observability unified event-plane API.

聚合统一事件面 (bin/ssot/observability-events.py → .omo/_delivery/observability/events.jsonl)
为告警/日志一张面, 供 cockpit 可观测页替代分散的 /api/logs + /api/alerts 轮询。

事件面 schema (schema_version 1):
    {id, ts, domain, type, severity, source, trace_id, payload, schema_version}

Routes:
    GET /api/observability/events → 统一事件面 (过滤: severity/domain/type/trace_id/limit)
    GET /api/observability/stats  → 按 domain/severity 聚合统计
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from fastapi import APIRouter, Query

from cockpit.compat import WORKSPACE_ROOT

router = APIRouter()

ALERT_SEVERITIES = {"warning", "degraded", "critical", "recovered"}


def _events_file() -> Path:
    return WORKSPACE_ROOT / ".omo" / "_delivery" / "observability" / "events.jsonl"


def read_event_plane(limit: int = 2000) -> list[dict]:
    """读取统一事件面 (AppendOnlyLog jsonl), 失败时返回空列表."""
    path = _events_file()
    if not path.exists():
        return []
    events: list[dict] = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return events[-limit:]


@router.get("/api/observability/events")
async def get_observability_events(
    severity: str | None = Query(
        None,
        pattern="^(info|warning|degraded|critical|recovered)$",
        description="按严重度过滤",
    ),
    domain: str | None = Query(None, min_length=1, max_length=50, description="按 domain 过滤"),
    type: str | None = Query(None, min_length=1, max_length=100, description="按 type 过滤"),
    trace_id: str | None = Query(None, min_length=1, max_length=64, description="按 trace_id 过滤"),
    alert_only: bool = Query(False, description="只看告警级事件 (warning/degraded/critical/recovered)"),
    limit: int = Query(100, ge=1, le=2000, description="返回数量限制"),
):
    """统一事件面查询 — 告警与日志同源."""
    events = read_event_plane()
    if alert_only:
        events = [e for e in events if e.get("severity") in ALERT_SEVERITIES]
    if severity:
        events = [e for e in events if e.get("severity") == severity]
    if domain:
        events = [e for e in events if e.get("domain") == domain]
    if type:
        events = [e for e in events if e.get("type") == type]
    if trace_id:
        events = [e for e in events if e.get("trace_id") == trace_id]

    # 新→旧
    events = list(reversed(events))
    total = len(events)
    return {"items": events[:limit], "total": total}


@router.get("/api/observability/stats")
async def get_observability_stats() -> dict:
    """事件面聚合统计 — 按 domain / severity 汇总."""
    events = read_event_plane()
    return {
        "total": len(events),
        "by_severity": dict(Counter(e.get("severity", "unknown") for e in events)),
        "by_domain": dict(Counter(e.get("domain", "unknown") for e in events)),
        "alerts": sum(1 for e in events if e.get("severity") in ALERT_SEVERITIES),
    }
