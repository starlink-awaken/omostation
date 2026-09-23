#!/usr/bin/env python3
"""驾驶舱三板块（logs / metrics / value）的真实数据采集层.

设计约束（2026-09-18 架构迭代）:

1. **无来源不显示** —— 每个数字必须可回溯到具体文件字段; 无来源的不采集。
2. **缺失即 MISSING** —— 声明但从未产出的源显式标 ``MISSING``, 不当作 0 混入统计。
3. **派生而非新增** —— 时序全部从既有日志实时聚合, 不新建时序库。
4. **确定性** —— 排序稳定、不含随机; 同输入同输出, 可 diff。

被 ``panorama-collect.build_payload()`` 调用, 输出三个键:

* ``panel_events``  —— 结构化事件流 + 分面 + 逐时/逐日真实序列 + 来源健康
* ``panel_history`` —— 从 refresh.jsonl / 心跳 / tick 派生的真实指标时序
* ``panel_value``   —— 真实价值证据 + 验收门槛进度（严格 NOT_PROVEN 语义）
"""

from __future__ import annotations

import json
import hashlib
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Iterator

ROOT = Path(__file__).resolve().parents[2]

# ── 事件源注册表 ───────────────────────────────────────────────────────
# 每个源: 路径 + 归一化时用的字段候选 + 展示标签。
# 路径不存在的源在输出里标 MISSING（不得静默当 0）。
EVENT_SOURCES: dict[str, dict[str, Any]] = {
    "resident-heartbeat": {
        "path": ".omo/state/resident-heartbeat.jsonl",
        "label": "常驻心跳",
        "ts": ("ts",),
        "type": ("source", "type", "event"),
        "status": ("health",),
    },
    "agent-tick": {
        "path": ".omo/state/agent-tick-daemon.jsonl",
        "label": "Agent 心跳",
        "ts": ("ts", "timestamp"),
        "type": ("type", "event"),
        "status": (),
    },
    "agent-workflows": {
        "path": ".omo/_delivery/agent-workflows/events.jsonl",
        "label": "Agent 工作流",
        "ts": ("ts", "occurred_at", "created_at"),
        "type": ("event", "event_type", "type"),
        "status": ("status",),
    },
    "workflow-mesh": {
        "path": ".omo/_knowledge/workflow-mesh/events.jsonl",
        "label": "工作流网状",
        "ts": ("ts", "occurred_at", "created_at"),
        "type": ("event", "event_type", "type"),
        "status": ("status",),
    },
    "a2a-messages": {
        "path": ".omo/state/a2a-messages.jsonl",
        "label": "Agent 间消息",
        "ts": ("ts", "timestamp"),
        "type": ("type", "event"),
        "status": (),
    },
    "agent-cell": {
        "path": ".omo/state/agent-cell/live-smoke-receipts.jsonl",
        "label": "Agent Cell 回执",
        "ts": ("ts", "created_at", "timestamp"),
        "type": ("type", "event", "kind"),
        "status": ("status", "result"),
    },
    # ── 以下两个源已在代码中声明但**从未产出过事件**（目录/文件不存在）──
    # 保留在注册表内以显式暴露"MISSING"，而不是从统计中悄悄消失。
    "signal-poller": {
        "path": ".omo/_delivery/signal-poller/poll-log.jsonl",
        "label": "信号轮询",
        "ts": ("ts", "polled_at"),
        "type": ("event", "type"),
        "status": ("status",),
    },
    "swarm-conflicts": {
        "path": ".omo/_delivery/swarm-conflicts/events.jsonl",
        "label": "蜂群冲突",
        "ts": ("ts", "occurred_at"),
        "type": ("event", "type"),
        "status": ("status",),
    },
}

_TS_FORMATS = ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%f%z",
               "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ")


def _parse_ts(value: Any) -> float | None:
    """把多种时间表示解析为 epoch 秒; 失败返回 None（而非假装成 0）。"""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        v = float(value)
        return v / 1000 if v > 1e11 else v  # 毫秒时间戳
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        for fmt in _TS_FORMATS:
            try:
                dt = datetime.strptime(str(value), fmt)
                break
            except ValueError:
                continue
        else:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.timestamp()


def _iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_jsonl(path: Path) -> Iterator[dict]:
    """健壮读取 JSONL: 跳过坏行, 不因单行损坏中断整个源。"""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict):
                    yield obj
    except OSError:
        return


def _first(evt: dict, keys: Iterable[str]) -> Any:
    for k in keys:
        if evt.get(k) not in (None, ""):
            return evt[k]
    return None


def _short(value: Any, limit: int = 160) -> str:
    if value is None:
        return ""
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    text = " ".join(text.split())
    return text[:limit]


def _summarize(source: str, evt: dict) -> str:
    """为事件生成人类可读摘要 —— 只用真实字段, 不做推测。"""
    for key in ("objective", "summary", "message", "action", "finding", "detail"):
        if evt.get(key):
            return _short(evt[key])
    if source == "a2a-messages":
        return f"{evt.get('from', '?')} → {evt.get('to', '?')}"
    if evt.get("run_id"):
        return _short(evt["run_id"])
    if evt.get("idempotency_key"):
        return _short(evt["idempotency_key"])
    return ""


def _normalize(source: str, evt: dict, spec: dict) -> dict | None:
    ts = _parse_ts(_first(evt, spec["ts"]))
    if ts is None:
        return None
    agent = evt.get("actor") or evt.get("agent_profile") or evt.get("agent") or evt.get("from") or ""
    status = _first(evt, spec["status"]) if spec["status"] else None
    if status is None and isinstance(evt.get("ok"), bool):
        status = "ok" if evt["ok"] else "failed"
    checks = evt.get("checks") if isinstance(evt.get("checks"), list) else None
    duration = None
    if checks:
        total = sum(c.get("duration_s", 0) or 0 for c in checks if isinstance(c, dict))
        duration = round(total, 2) if total else None
    if duration is None and isinstance(evt.get("duration_s"), (int, float)):
        duration = round(float(evt["duration_s"]), 2)
    failed_checks = sum(1 for c in (checks or []) if isinstance(c, dict) and c.get("ok") is False)
    return {
        "ts": _iso(ts),
        "_epoch": ts,
        "type": str(_first(evt, spec["type"]) or "unknown")[:40],
        "source": source,
        "agent": str(agent)[:40],
        "status": str(status)[:20] if status is not None else None,
        "run_id": str(evt.get("run_id") or "")[:80] or None,
        "workflow_id": str(evt.get("workflow_id") or "")[:60] or None,
        "duration_s": duration,
        "check_count": len(checks) if checks else None,
        "failed_check_count": failed_checks if checks else None,
        "changed_file_count": len(evt["changed_files"]) if isinstance(evt.get("changed_files"), list) else None,
        "summary": _summarize(source, evt),
    }


def _bucket_hourly(epoch: float) -> float:
    dt = datetime.fromtimestamp(epoch, tz=UTC)
    return dt.replace(minute=0, second=0, microsecond=0).timestamp()


def _bucket_daily(epoch: float) -> float:
    dt = datetime.fromtimestamp(epoch, tz=UTC)
    return dt.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()


def _series_from_counts(counts: dict[float, float], starts: list[float], bucket: str) -> list[list]:
    """按给定桶起点输出降采样后的 [[iso, value]]，缺桶补 0（时间轴连续）。"""
    return [[_iso(s), round(counts.get(s, 0), 2)] for s in starts]


def _hour_starts(now: float, hours: int) -> list[float]:
    end = _bucket_hourly(now)
    return [end - 3600 * (hours - 1 - i) for i in range(hours)]


def _day_starts(now: float, days: int) -> list[float]:
    end = _bucket_daily(now)
    return [end - 86400 * (days - 1 - i) for i in range(days)]


# ── L1.1 事件流 ────────────────────────────────────────────────────────
def collect_event_stream(root: Path | None = None, now: float | None = None,
                         limit: int = 200) -> dict:
    """结构化事件流 + 分面 + 真实时序 + 来源健康。"""
    root = root or ROOT
    now = now if now is not None else datetime.now(tz=UTC).timestamp()
    cutoff_24h = now - 86400
    cutoff_30d = now - 86400 * 30

    events: list[dict] = []
    sources: list[dict] = []
    window_counts: Counter = Counter()
    total_counts: Counter = Counter()
    hourly: Counter = Counter()
    daily: Counter = Counter()

    for name, spec in sorted(EVENT_SOURCES.items()):
        path = root / spec["path"]
        if not path.is_file():
            sources.append({
                "name": name, "label": spec["label"], "path": spec["path"],
                "state": "MISSING", "window_count": None, "total_count": None,
                "last_ts": None, "note": "文件不存在 —— 该源从未产出事件（未接线）",
            })
            continue
        source_events: list[dict] = []
        total = 0
        last_epoch = None
        for raw in _read_jsonl(path):
            total += 1
            norm = _normalize(name, raw, spec)
            if norm is None:
                continue
            epoch = norm.pop("_epoch")
            last_epoch = epoch if last_epoch is None else max(last_epoch, epoch)
            if epoch < cutoff_30d:
                continue
            daily[_bucket_daily(epoch)] += 1
            if epoch >= cutoff_24h:
                window_counts[name] += 1
                hourly[_bucket_hourly(epoch)] += 1
            if epoch >= cutoff_24h:
                source_events.append(norm)
        total_counts[name] = total
        events.extend(source_events)
        sources.append({
            "name": name, "label": spec["label"], "path": spec["path"],
            "state": "OK" if source_events else ("STALE" if total else "EMPTY"),
            "window_count": window_counts[name], "total_count": total,
            "last_ts": _iso(last_epoch) if last_epoch else None, "note": None,
        })

    # 稳定排序: 时间倒序, 同刻按 (source, type) —— 保证可 diff
    events.sort(key=lambda e: (e["ts"], e["source"], e["type"]), reverse=True)

    by_type = {k: v for k, v in sorted(
        Counter(e["type"] for e in events).items(), key=lambda kv: (-kv[1], kv[0]))}
    by_source = {k: v for k, v in sorted(
        Counter(e["source"] for e in events).items(), key=lambda kv: (-kv[1], kv[0]))}
    by_agent = {k: v for k, v in sorted(
        Counter(e["agent"] for e in events if e["agent"]).items(),
        key=lambda kv: (-kv[1], kv[0]))}
    by_status = {k: v for k, v in sorted(
        Counter(e["status"] for e in events if e["status"]).items(),
        key=lambda kv: (-kv[1], kv[0]))}

    failed = sum(v for k, v in by_status.items() if str(k).lower() in {"failed", "error", "blocked", "degraded"})
    live_sources = [s for s in sources if s["state"] != "MISSING"]

    return {
        "schema": "panel-events/v1",
        "events": events[:limit],
        "events_all": events[:limit],   # 视图筛选所需的完整集合（events 为兼容短列表）
        "event_total": len(events),
        "facets": {"by_type": by_type, "by_source": by_source,
                   "by_agent": by_agent, "by_status": by_status},
        "series": {
            "hourly_24h": _series_from_counts(hourly, _hour_starts(now, 24), "hour"),
            "daily_7d": _series_from_counts(daily, _day_starts(now, 7), "day"),
            "daily_30d": _series_from_counts(daily, _day_starts(now, 30), "day"),
        },
        "sources": sorted(sources, key=lambda s: (s["state"] == "MISSING", s["name"])),
        "summary": {
            "events_24h": sum(window_counts.values()),
            "events_per_hour": round(sum(window_counts.values()) / 24, 2),
            "failed_24h": failed,
            "failure_rate": round(failed / len(events) * 100, 1) if events else None,
            "sources_live": len(live_sources),
            "sources_missing": len(sources) - len(live_sources),
            "agents_active": len(by_agent),
        },
    }


# ── L1.2 指标时序 ──────────────────────────────────────────────────────
def collect_metrics_history(root: Path | None = None, now: float | None = None,
                            dashboard_dir: Path | None = None) -> dict:
    """从真实日志派生指标时序（24h 逐时 / 30d 逐日）。

    ``dashboard_dir`` 是驾驶舱部署目录（refresh.jsonl 所在）；显式可注入以便测试
    不误读生产数据。
    """
    root = root or ROOT
    now = now if now is not None else datetime.now(tz=UTC).timestamp()
    cutoff = now - 86400 * 30
    coverage: dict[str, Any] = {}

    refresh_ok: Counter = Counter()
    refresh_failed: Counter = Counter()
    nodes: dict[float, float] = {}
    edges: dict[float, float] = {}
    nodes_ts: dict[float, float] = {}
    edges_ts: dict[float, float] = {}

    base = dashboard_dir or (Path.home() / ".local/share/zhixing-dashboard")
    refresh_path = base / "refresh.jsonl"
    refresh_lines = 0
    if refresh_path.is_file():
        for rec in _read_jsonl(refresh_path):
            epoch = _parse_ts(rec.get("published_at") or rec.get("attempted_at"))
            if epoch is None:
                continue
            refresh_lines += 1
            if epoch < cutoff:
                continue
            day = _bucket_daily(epoch)
            if rec.get("failed_sources"):
                refresh_failed[day] += 1
            else:
                refresh_ok[day] += 1
            strategic = rec.get("strategic") or {}
            counts = strategic.get("counts") or {}
            if isinstance(counts.get("nodes"), (int, float)) and epoch >= nodes_ts.get(day, -1):
                nodes[day], nodes_ts[day] = counts["nodes"], epoch
            if isinstance(counts.get("edges"), (int, float)) and epoch >= edges_ts.get(day, -1):
                edges[day], edges_ts[day] = counts["edges"], epoch
        coverage["refresh_jsonl"] = {"path": str(refresh_path), "lines": refresh_lines}

    hb_ok: Counter = Counter()
    hb_degraded: Counter = Counter()
    hb_path = root / EVENT_SOURCES["resident-heartbeat"]["path"]
    hb_lines = 0
    if hb_path.is_file():
        for rec in _read_jsonl(hb_path):
            epoch = _parse_ts(rec.get("ts"))
            if epoch is None:
                continue
            hb_lines += 1
            if epoch < now - 86400:
                continue
            hour = _bucket_hourly(epoch)
            if str(rec.get("health", "")).lower() in {"ok", "healthy", "pass"}:
                hb_ok[hour] += 1
            elif rec.get("degraded_components"):
                hb_degraded[hour] += 1
        coverage["resident_heartbeat"] = {"path": str(hb_path), "lines": hb_lines}

    tick_ok: Counter = Counter()
    tick_failed: Counter = Counter()
    tick_path = root / EVENT_SOURCES["agent-tick"]["path"]
    tick_lines = 0
    if tick_path.is_file():
        for rec in _read_jsonl(tick_path):
            epoch = _parse_ts(rec.get("ts"))
            if epoch is None:
                continue
            tick_lines += 1
            if epoch < now - 86400:
                continue
            hour = _bucket_hourly(epoch)
            tick_ok[hour] += rec.get("ok_count", 0) or 0
            tick_failed[hour] += rec.get("failed_count", 0) or 0
        coverage["agent_tick"] = {"path": str(tick_path), "lines": tick_lines}

    hours = _hour_starts(now, 24)
    days = _day_starts(now, 30)
    days7 = _day_starts(now, 7)

    return {
        "schema": "panel-history/v1",
        "series": {
            "refresh_ok_daily": {"unit": "次", "points": _series_from_counts(refresh_ok, days, "day")},
            "refresh_failed_daily": {"unit": "次", "points": _series_from_counts(refresh_failed, days7, "day")},
            "graph_nodes_daily": {"unit": "个", "points": _series_from_counts(nodes, days, "day")},
            "graph_edges_daily": {"unit": "条", "points": _series_from_counts(edges, days, "day")},
            "heartbeat_ok_hourly": {"unit": "次", "points": _series_from_counts(hb_ok, hours, "hour")},
            "heartbeat_degraded_hourly": {"unit": "次", "points": _series_from_counts(hb_degraded, hours, "hour")},
            "tick_ok_hourly": {"unit": "次", "points": _series_from_counts(tick_ok, hours, "hour")},
            "tick_failed_hourly": {"unit": "次", "points": _series_from_counts(tick_failed, hours, "hour")},
        },
        "coverage": coverage,
    }


# ── L1.3 价值证据 ──────────────────────────────────────────────────────
GOLDEN_SLICE = (
    {"key": "samples", "label": "真实样本", "target": 30, "unit": "个", "comparator": "gte"},
    {"key": "acceptance", "label": "采纳率", "target": 70, "unit": "%", "comparator": "gte"},
    {"key": "revision_burden", "label": "修订负担下降", "target": 30, "unit": "%", "comparator": "gte"},
)
FINAL_VISION = (
    {"key": "weeks", "label": "连续自然周", "target": 12, "unit": "周", "comparator": "gte"},
    {"key": "weekly_accepted", "label": "每周 accepted", "target": 5, "unit": "个/周", "comparator": "gte"},
    {"key": "weekly_adjudications", "label": "每周有效裁决", "target": 10, "unit": "次/周", "comparator": "gte"},
    {"key": "acceptance", "label": "采纳率", "target": 40, "unit": "%", "comparator": "gte"},
    {"key": "revision_burden", "label": "修订负担下降", "target": 40, "unit": "%", "comparator": "gte"},
)

REVISION_BASELINE_PATH = ".omo/_delivery/value/revision-baseline.json"


def _load_revision_baseline(root: Path) -> tuple[dict | None, str | None]:
    """Load a digest-bound pre-window baseline; invalid data is never used."""
    path = root / REVISION_BASELINE_PATH
    if not path.is_file():
        return None, None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"revision baseline unreadable: {type(exc).__name__}"
    if not isinstance(value, dict):
        return None, "revision baseline root is not an object"

    supplied_digest = value.get("digest")
    digest_body = {key: item for key, item in value.items() if key != "digest"}
    digest = "sha256:" + hashlib.sha256(
        json.dumps(digest_body, ensure_ascii=False, sort_keys=True,
                   separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if supplied_digest != digest:
        return None, "revision baseline digest mismatch"
    if value.get("schema") != "value-revision-baseline/v1":
        return None, "revision baseline schema mismatch"

    frozen_epoch = _parse_ts(value.get("frozen_at"))
    adjudicated, revised = value.get("adjudicated"), value.get("revised")
    rate = value.get("revision_burden_percent")
    if frozen_epoch is None or type(adjudicated) is not int or adjudicated <= 0 \
            or type(revised) is not int or revised < 0 or revised > adjudicated \
            or type(rate) is not float or rate != round(revised / adjudicated * 100, 1):
        return None, "revision baseline metrics invalid"
    return {
        "baseline_id": str(value.get("baseline_id") or "")[:128],
        "frozen_at": value.get("frozen_at"),
        "frozen_epoch": frozen_epoch,
        "adjudicated": adjudicated,
        "revised": revised,
        "revision_burden_percent": rate,
        "digest": digest,
    }, None


def _judge(current: float | None, spec: dict) -> bool | None:
    if current is None:
        return None
    target = spec["target"]
    return current >= target if spec["comparator"] == "gte" else current <= target


def collect_value_evidence(root: Path | None = None, now: float | None = None,
                           context: dict | None = None) -> dict:
    """真实价值证据 + 五阶段计数 + 验收门槛进度。

    ``context`` 传入 panorama 已采集的场景运行态，使五阶段计数与页面其它位置同源。
    """
    root = root or ROOT
    context = context or {}

    evidence: list[dict] = []
    for rel in (".omo/_delivery/ingress/value-evidence.jsonl",
                ".omo/_knowledge/workflow-mesh/scene-outcomes.jsonl"):
        for rec in _read_jsonl(root / rel):
            epoch = _parse_ts(rec.get("timestamp") or rec.get("ts") or rec.get("recorded_at"))
            evidence.append({
                "ts": _iso(epoch) if epoch else None,
                "_epoch": epoch,
                "scene_id": rec.get("scene_id") or rec.get("id"),
                "verdict": rec.get("verdict") or rec.get("adjudication"),
                "qualifying": bool(rec.get("qualifying")),
                "saved_seconds": rec.get("net_saved_seconds") or rec.get("estimated_time_saved_seconds") or 0,
                "run_id": rec.get("run_id"),
                "source": rel.split("/")[-1],
            })
    evidence.sort(key=lambda e: (e["ts"] or "", e["scene_id"] or ""), reverse=True)

    verdicts = Counter((e["verdict"] or "unknown") for e in evidence)
    baseline, baseline_error = _load_revision_baseline(root)
    post_adjudicated = post_revised = 0
    if baseline is not None:
        for item in evidence:
            if item["_epoch"] is not None and item["_epoch"] >= baseline["frozen_epoch"]:
                verdict = (item["verdict"] or "").lower()
                if verdict in {"accept", "edit", "reject", "accepted", "revised", "rejected"}:
                    post_adjudicated += 1
                    post_revised += verdict in {"edit", "revised"}
        post_rate = round(post_revised / post_adjudicated * 100, 1) if post_adjudicated else None
        baseline_revision_burden = (
            round((baseline["revision_burden_percent"] - post_rate)
                  / baseline["revision_burden_percent"] * 100, 1)
            if post_rate is not None else None
        )
    else:
        post_rate = baseline_revision_burden = None

    adjudicated = sum(verdicts[k] for k in ("accept", "edit", "reject", "accepted", "revised", "rejected"))
    accepted = verdicts["accept"] + verdicts["accepted"]
    samples_total = len(evidence)
    qualifying = sum(1 for e in evidence if e["qualifying"])
    acceptance = round(accepted / adjudicated * 100, 1) if adjudicated else None

    reflections = sum(1 for _ in _read_jsonl(root / ".omo/_knowledge/workflow-mesh/scene-reflections.jsonl"))
    shadow_trials = sum(1 for _ in _read_jsonl(root / ".omo/_knowledge/workflow-mesh/shadow-scene-trials.jsonl"))

    from collections import defaultdict as _dd
    daily_runs: dict[str, int] = _dd(int)
    exec_rows = context.get("execution_daily")
    if not exec_rows:
        # 无 context 时直接读真实导出文件（保证单独调用也拿到真实数）
        try:
            exec_rows = json.loads(
                (root / ".omo/_knowledge/scene-history/execution-daily.json").read_text(
                    encoding="utf-8")).get("rows") or []
        except (OSError, json.JSONDecodeError, AttributeError):
            exec_rows = []
    for row in exec_rows:
        if isinstance(row, dict) and row.get("day"):
            daily_runs[str(row["day"])] += int(row.get("runs") or 0)
    journey_runs = sum(daily_runs.values())

    scene_cards = context.get("scene_cards") or {}
    active_scenes = scene_cards.get("active_total")
    if active_scenes is None:
        active_scenes = len(scene_cards.get("scenes") or []) or None
    signal_poller = context.get("signal_poller") or {}

    def stage(key: str, name: str, count, source: str) -> dict:
        return {"key": key, "name": name, "count": count, "source": source,
                "state": "OK" if count else "NO_DATA"}

    stages = [
        stage("signal", "信号感知", signal_poller.get("poll_count") or signal_poller.get("total_signals") or 0,
              "signal_poller"),
        stage("intent", "意图分流", active_scenes or 0, "scene_cards.active_total"),
        stage("journey", "旅程执行", journey_runs, "scene-history/execution-daily.json"),
        stage("record", "价值记录", qualifying, "value-evidence.jsonl (qualifying)"),
        stage("feedback", "进化反馈", reflections or shadow_trials, "scene-reflections.jsonl"),
    ]

    # 比率型指标的「样本基础」门槛: 样本不足时不得判 met=True
    # （2 条记录 100% 采纳在统计上无意义, 绿色必须留给真实达标）
    sample_basis_ok = qualifying >= GOLDEN_SLICE[0]["target"]
    metrics = {
        "samples": qualifying,
        "acceptance": acceptance,
        "revision_burden": baseline_revision_burden,
        "weeks": None,
        "weekly_accepted": None,
        "weekly_adjudications": None,
    }
    rate_keys = {"acceptance", "revision_burden"}

    def _entry(spec: dict) -> dict:
        current = metrics.get(spec["key"])
        met = _judge(current, spec)
        gated = spec["key"] in rate_keys and not sample_basis_ok
        gate = None
        if spec["key"] == "revision_burden" and baseline is None:
            gate = "revision baseline unavailable" + (f": {baseline_error}" if baseline_error else "")
        elif spec["key"] == "revision_burden" and post_adjudicated == 0:
            gate = "revision baseline frozen; waiting for post-baseline adjudications"
        elif spec["key"] in rate_keys and not sample_basis_ok:
            gate = "样本 %d/%d 不足, 比率不可判定" % (qualifying, GOLDEN_SLICE[0]["target"])
        elif spec["key"] == "revision_burden" and baseline is None:
            gate = "revision baseline unavailable" + (f": {baseline_error}" if baseline_error else "")
        elif spec["key"] == "revision_burden" and post_adjudicated == 0:
            gate = "revision baseline frozen; waiting for post-baseline adjudications"
        return {**spec, "current": current,
                "met": None if gated else met,
                "gate": gate}

    thresholds = [_entry(spec) for spec in GOLDEN_SLICE]
    vision = [_entry(spec) for spec in FINAL_VISION]

    reasons: list[str] = []
    if samples_total == 0:
        reasons.append("尚无任何价值证据记录")
    else:
        if qualifying == 0:
            reasons.append(f"已有 {samples_total} 条记录，但 qualifying=false（未产生净节省，不计入价值门）")
        if samples_total < GOLDEN_SLICE[0]["target"]:
            reasons.append(f"样本 {samples_total}/{GOLDEN_SLICE[0]['target']} 不足")
        if acceptance is None:
            reasons.append("无 effective adjudication，采纳率不可计算")
        if baseline is None:
            reasons.append("修订负担降低缺真实基线（未在窗口开始前冻结，不可回填）")
        elif post_adjudicated == 0:
            reasons.append("修订基线已冻结；等待基线后的真实记录")

    # Independent full-window human attestation flips state only when
    # golden slice is met AND SSH-signed receipt verifies (agent cannot forge).
    # Keep lowercase to survive refresh.py clean_not_proven() filter.
    state = "not_proven"
    if (
        not reasons
        and qualifying >= GOLDEN_SLICE[0]["target"]
        and all(bool(t.get("met")) for t in thresholds)
    ):
        repo_root = root if root is not None else Path(__file__).resolve().parents[2]
        attestation_path = (
            Path(repo_root)
            / "docs"
            / "operations"
            / "human-attestations"
            / "VALUE-WINDOW-20260923-accept.yaml"
        )
        if attestation_path.is_file():
            try:
                import importlib.util

                bl_path = Path(repo_root) / "bin" / "plan" / "bet-ledger.py"
                spec = importlib.util.spec_from_file_location("_bet_ledger_attest", bl_path)
                if spec and spec.loader:
                    bl = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(bl)
                    errs = bl.validate_human_attestation(
                        receipt_path=attestation_path,
                        workspace=Path(repo_root),
                    )
                    if not errs:
                        state = "proven"
            except Exception:
                state = "not_proven"

    return {
        "schema": "panel-value/v1",
        # 注意: 必须用小写。部署侧 refresh.py 的 render() 里有个遗留的
        # clean_not_proven(), 它会 **删除任何值恰好等于字符串 'NOT_PROVEN' 的键**
        # （本意是清掉历史占位文本），导致大写状态在嵌入快照时整键消失、
        # 页面退化成 UNKNOWN。小写可安全穿过该规则, 由视图层负责大写展示。
        "state": state,
        "state_reason": reasons,
        "revision_baseline": None if baseline is None else {
            "schema": "value-revision-baseline-projection/v1",
            "baseline_id": baseline["baseline_id"],
            "frozen_at": baseline["frozen_at"],
            "digest": baseline["digest"],
            "baseline_revision_burden_percent": baseline["revision_burden_percent"],
            "post_window": {
                "adjudicated": post_adjudicated,
                "revised": post_revised,
                "revision_burden_percent": post_rate,
                "burden_reduction_percent": baseline_revision_burden,
            },
        },
        "samples": {
            "records": samples_total,
            "qualifying": qualifying,
            "accepted": accepted,
            "adjudicated": adjudicated,
            "by_verdict": dict(sorted(verdicts.items())),
            "net_saved_seconds": sum(e["saved_seconds"] or 0 for e in evidence),
        },
        "stages": stages,
        "thresholds": thresholds,
        "vision_thresholds": vision,
        "evidence": [{key: value for key, value in item.items() if not key.startswith("_")}
                     for item in evidence[:50]],
    }


def collect_all(root: Path | None = None, now: float | None = None,
                context: dict | None = None, dashboard_dir: Path | None = None) -> dict:
    """供 panorama-collect 一次调用挂载三个键。"""
    return {
        "panel_events": collect_event_stream(root=root, now=now),
        "panel_history": collect_metrics_history(root=root, now=now, dashboard_dir=dashboard_dir),
        "panel_value": collect_value_evidence(root=root, now=now, context=context),
    }


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="驾驶舱三板块数据采集")
    ap.add_argument("--key", default="all", choices=["all", "events", "history", "value"])
    args = ap.parse_args()
    payload = collect_all()
    out = payload if args.key == "all" else {f"panel_{args.key}": payload[f"panel_{args.key}"]}
    print(json.dumps(out, ensure_ascii=False, indent=1, default=str))
