#!/usr/bin/env python3
"""统一事件面 (Unified Event Surface) — 可观测 × 事件 × 治理联动枢纽.

设计: docs/observability-unified-architecture.md
物理落点: `.omo/_delivery/observability/events.jsonl` (AppendOnlyLog + fcntl 锁)
时序索引: metrics-store.jsonl 追加行

命令:
  emit      写一条事件 (统一 schema v1)
  search    查询事件 (按 domain/type/severity/trace_id/since)
  trace     按 trace_id 跨链查询 (运行时 → 事件 → 治理)
  adapters  run  增量同步各通道 → 事件面 (增量指针幂等)
  adapters  status  各通道 offset/启用状态
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
EVENTS_FILE = ROOT / ".omo" / "_delivery" / "observability" / "events.jsonl"
REGISTRY = ROOT / ".omo" / "_truth" / "registry" / "observability-events.yaml"
ADAPTER_STATE_DIR = ROOT / ".omo" / "state" / "observability-adapters"
METRICS_STORE = ROOT / ".omo" / "state" / "metrics-store.jsonl"

VALID_DOMAINS = {"runtime", "governance", "swarm", "perception", "scene", "knowledge", "debt"}
VALID_SEVERITIES = {"info", "warning", "degraded", "critical", "recovered"}


def _utcnow() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _new_id() -> str:
    return f"evt_{int(time.time())}_{os.urandom(3).hex()}"


# ── 物理写盘 (AppendOnlyLog 语义, 复用 §12 跨仓契约) ────────────────────
def append_event(event: dict[str, Any]) -> Path:
    """Append 一条事件到事件面 (fcntl 锁, 跨进程安全)."""
    EVENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    lock_path = EVENTS_FILE.with_suffix(".lock")
    line = json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n"
    with open(lock_path, "a", encoding="utf-8"):
        pass
    with open(lock_path, "r+", encoding="utf-8") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            with open(EVENTS_FILE, "a", encoding="utf-8") as f:
                f.write(line)
                f.flush()
                os.fsync(f.fileno())
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)
    return EVENTS_FILE


def read_events(limit: int = 100) -> list[dict[str, Any]]:
    if not EVENTS_FILE.exists():
        return []
    events: list[dict[str, Any]] = []
    with open(EVENTS_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                events.append({"raw": line})
    return events[-limit:]


def append_metrics_store(event: dict[str, Any]) -> None:
    """时序索引: 追加到 metrics-store.jsonl (与 gac-local-gate 同格式)."""
    try:
        METRICS_STORE.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "timestamp": event["ts"],
            "check": event["type"],
            "ok": event["severity"] not in {"critical", "degraded"},
            "duration_ms": 0,
            "reason": json.dumps({"domain": event["domain"], "source": event["source"]}, ensure_ascii=False),
        }
        with open(METRICS_STORE, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass


# ── 命令实现 ──────────────────────────────────────────────────────────
def cmd_emit(args: argparse.Namespace) -> int:
    if args.domain not in VALID_DOMAINS:
        print(f"❌ invalid domain: {args.domain} (valid: {sorted(VALID_DOMAINS)})", file=sys.stderr)
        return 1
    if args.severity not in VALID_SEVERITIES:
        print(f"❌ invalid severity: {args.severity} (valid: {sorted(VALID_SEVERITIES)})", file=sys.stderr)
        return 1
    payload: dict[str, Any] = {}
    if args.payload:
        try:
            payload = json.loads(args.payload)
        except json.JSONDecodeError as exc:
            print(f"❌ invalid --payload JSON: {exc}", file=sys.stderr)
            return 1
    event: dict[str, Any] = {
        "id": _new_id(),
        "ts": _utcnow(),
        "domain": args.domain,
        "type": args.type,
        "severity": args.severity,
        "source": args.source,
        "trace_id": args.trace_id,
        "payload": payload,
        "schema_version": 1,
    }
    append_event(event)
    if args.metrics:
        append_metrics_store(event)
    print(event["id"])
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    events = read_events(args.limit)
    if args.domain:
        events = [e for e in events if e.get("domain") == args.domain]
    if args.type:
        events = [e for e in events if e.get("type") == args.type]
    if args.severity:
        events = [e for e in events if e.get("severity") == args.severity]
    if args.trace_id:
        events = [e for e in events if e.get("trace_id") == args.trace_id]
    if args.since:
        events = [e for e in events if (e.get("ts") or "") >= args.since]
    print(f"Found {len(events)} event(s)")
    for e in events:
        print(f"  [{e.get('ts', '?')}] {e.get('domain', '?')}:{e.get('type', '?')} "
              f"sev={e.get('severity', '?')} src={e.get('source', '?')} id={e.get('id', '?')}")
        if args.verbose:
            print(f"      trace_id={e.get('trace_id')} payload={json.dumps(e.get('payload', {}), ensure_ascii=False)[:200]}")
    return 0


def cmd_trace(args: argparse.Namespace) -> int:
    """按 trace_id 跨链查询 — 运行时 → 事件 → 治理."""
    events = [e for e in read_events(2000) if e.get("trace_id") == args.trace_id]
    if not events:
        print(f"no events found for trace_id={args.trace_id}")
        return 1
    print(f"trace {args.trace_id}: {len(events)} event(s) across "
          f"{sorted({e.get('domain', '?') for e in events})}")
    for e in sorted(events, key=lambda x: x.get("ts", "")):
        print(f"  [{e.get('ts', '?')}] {e.get('domain')}:{e.get('type')} ({e.get('severity')}) <- {e.get('source')}")
        if args.verbose:
            print(f"      payload={json.dumps(e.get('payload', {}), ensure_ascii=False)[:300]}")
    return 0


# ── 通道适配器 (L1 归一化层) ───────────────────────────────────────────
def _load_registry() -> dict[str, Any]:
    try:
        import yaml
        # Frontmatter'd yaml: safe_load_all 取正文 (最后非 None 文档)
        docs = [d for d in yaml.safe_load_all(REGISTRY.read_text(encoding="utf-8")) if d]
        return docs[-1] if docs else {}
    except (OSError, ImportError, yaml.YAMLError):
        return {}


def _adapter_offset(channel: str) -> int:
    p = ADAPTER_STATE_DIR / f"{channel}.offset"
    try:
        return int(p.read_text().strip() or "0")
    except (OSError, ValueError):
        return 0


def _save_adapter_offset(channel: str, offset: int) -> None:
    ADAPTER_STATE_DIR.mkdir(parents=True, exist_ok=True)
    (ADAPTER_STATE_DIR / f"{channel}.offset").write_text(str(offset))


def _emit_from(channel: str, domain: str, event_type: str, severity: str,
               source: str, payload: dict[str, Any], trace_id: str | None = None) -> None:
    append_event({
        "id": _new_id(), "ts": _utcnow(), "domain": domain, "type": event_type,
        "severity": severity, "source": source, "trace_id": trace_id,
        "payload": payload, "schema_version": 1,
    })


def _adapt_swarm(channel_cfg: dict[str, Any]) -> int:
    """broadcast-bus.jsonl 增量 → 事件面."""
    path = ROOT / str(channel_cfg.get("source_path", ""))
    if not path.exists():
        return 0
    offset = _adapter_offset("swarm_broadcast")
    emitted = 0
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
    for i, line in enumerate(lines[offset:], start=offset):
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        _emit_from("swarm", "swarm", f"swarm:{rec.get('event_type', 'event')}",
                   "info", rec.get("sender_id", "swarm"),
                   {"channel": rec.get("channel"), "content": str(rec.get("content", ""))[:200],
                    "target_agent_id": rec.get("target_agent_id")},
                   rec.get("trace_id"))
        emitted += 1
    _save_adapter_offset("swarm_broadcast", len(lines))
    return emitted


def _adapt_gate(channel_cfg: dict[str, Any]) -> int:
    """metrics-store.jsonl 增量 → ok=false 行发 governance:gate_failed."""
    path = ROOT / str(channel_cfg.get("source_path", ""))
    if not path.exists():
        return 0
    offset = _adapter_offset("gate_result")
    emitted = 0
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
    for i, line in enumerate(lines[offset:], start=offset):
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("ok") is False:
            _emit_from("gate", "governance", "governance:gate_failed",
                       "critical", "gac-local-gate",
                       {"check": rec.get("check"), "duration_ms": rec.get("duration_ms"),
                        "reason": str(rec.get("reason", ""))[:300]})
            emitted += 1
    _save_adapter_offset("gate_result", len(lines))
    return emitted


def _adapt_debt(channel_cfg: dict[str, Any]) -> int:
    """debt/items/*.yaml 新增 → debt:opened 事件 (按文件名去重)."""
    items_dir = ROOT / str(channel_cfg.get("source_path", ""))
    if not items_dir.is_dir():
        return 0
    seen = _adapter_offset("debt_ledger")  # 复用 offset 存已见文件名数(近似)
    names = sorted(p.name for p in items_dir.glob("*.yaml"))
    if len(names) <= seen:
        return 0
    emitted = 0
    for name in names[seen:]:
        _emit_from("debt", "debt", "debt:opened", "warning", "debt-ledger",
                   {"debt_id": name.rsplit(".", 1)[0]})
        emitted += 1
    _save_adapter_offset("debt_ledger", len(names))
    return emitted


def _adapt_health(channel_cfg: dict[str, Any]) -> int:
    """health.yaml 变化 → governance:health_score 事件."""
    path = ROOT / str(channel_cfg.get("source_path", ""))
    if not path.exists():
        return 0
    try:
        import yaml
        health = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, ImportError):
        return 0
    score = health.get("health_score")
    if score is None:
        return 0
    _emit_from("health", "governance", "governance:health_score",
               "degraded" if (isinstance(score, (int, float)) and score < 70) else "info",
               "compass_radar",
               {"health_score": score, "source": health.get("source")})
    return 1


def cmd_adapters(args: argparse.Namespace) -> int:
    reg = _load_registry()
    adapters = (reg.get("adapters") or [])
    if args.channel:
        adapters = [a for a in adapters if a.get("id") == args.channel]
    if args.action == "status":
        print(f"{'adapter':<20} {'channel':<12} {'enabled':<8} {'offset':<8}")
        for a in adapters:
            off = _adapter_offset(a.get("id", "?"))
            print(f"{a.get('id', '?'):<20} {a.get('channel', '?'):<12} "
                  f"{str(a.get('enabled', True)):<8} {off}")
        return 0
    # run
    total = 0
    for a in adapters:
        if not a.get("enabled", True):
            continue
        fn = {
            "swarm_broadcast": _adapt_swarm,
            "gate_result": _adapt_gate,
            "debt_ledger": _adapt_debt,
            "health_score": _adapt_health,
        }.get(a.get("id", ""))
        if not fn:
            continue
        n = fn(a)
        if n:
            print(f"  {a.get('id')}: +{n} events")
        total += n
    print(f"adapters run: {total} events emitted")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    emit = sub.add_parser("emit")
    emit.add_argument("--domain", required=True)
    emit.add_argument("--type", required=True)
    emit.add_argument("--severity", default="info", choices=sorted(VALID_SEVERITIES))
    emit.add_argument("--source", default="cli")
    emit.add_argument("--trace-id")
    emit.add_argument("--payload")
    emit.add_argument("--metrics", action="store_true", help="同时追加 metrics-store 时序索引")
    emit.set_defaults(func=cmd_emit)

    search = sub.add_parser("search")
    search.add_argument("--domain")
    search.add_argument("--type")
    search.add_argument("--severity")
    search.add_argument("--trace-id")
    search.add_argument("--since")
    search.add_argument("--limit", type=int, default=100)
    search.add_argument("--verbose", "-v", action="store_true")
    search.set_defaults(func=cmd_search)

    trace = sub.add_parser("trace")
    trace.add_argument("trace_id")
    trace.add_argument("--verbose", "-v", action="store_true")
    trace.set_defaults(func=cmd_trace)

    adapters = sub.add_parser("adapters")
    adapters.add_argument("action", choices=["run", "status"])
    adapters.add_argument("--channel")
    adapters.set_defaults(func=cmd_adapters)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
