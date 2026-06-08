#!/usr/bin/env python3
"""Audit Unified — 统一审计层 | SSB + JSONL + CARDS 关联记录与查询

消除 bos-audit.jsonl / operations.jsonl / SSB SQLite 三源碎片。
所有审计写入走统一入口，自动生成 ssb_event_id + cards_id 交叉引用。

Usage:
    from audit_unified import log_event, query_events
    log_event(source="l0", event_type="domain_read", uri="bos://vault", passed=True)
    events = query_events(hours=24, source="all")
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import sys
import time as time_module
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

H = Path.home()

# ── 路径常量 ──
SSB_DB = H / ".ecos" / "LADS" / "ssb" / "ecos.db"
L0_AUDIT_LOG = H / ".ecos" / "audit" / "operations.jsonl"
BOS_AUDIT_LOG = H / ".ecos" / "bos-audit.jsonl"
DAEMON_STATE_DB = H / ".ecos" / "daemon-state.db"
HEALER_STATE_DB = H / ".ecos" / "healer-state.db"
UNIFIED_AUDIT_LOG = H / ".ecos" / "audit" / "unified.jsonl"

# ── 统一 Schema 字段 ──
REQUIRED_FIELDS = [
    "id",           # 唯一ID: unified-{date}-{seq}
    "source",       # l0 | bos | ssb | daemon | healer | cards
    "event_type",   # domain_read | bos_call | cycle_run | heal_attempt | ...
    "timestamp",    # ISO-8601
    "summary",      # 简短描述 (≤120 chars)
]
OPTIONAL_FIELDS = [
    "detail",
    "uri",
    "domain",
    "passed",
    "ssb_event_id",
    "cards_id",
    "daemon_cycle_id",
    "healer_check_type",
    "violations",
    "duration_ms",
    "anomaly",
    "metadata",
]

# ── 顺序 ID 生成器 ──

def _generate_id() -> str:
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"unified-{ts}-{uuid.uuid4().hex[:8]}"


def _format_event(event: dict) -> dict:
    e = dict(event)
    e.setdefault("id", _generate_id())
    e.setdefault("timestamp", datetime.now().isoformat())
    for f in REQUIRED_FIELDS:
        if f not in e:
            e[f] = "?"
    return e


# ═══════════════════════════════════════════════════
# SSB 集成
# ═══════════════════════════════════════════════════


def _ssb_publish(event: dict) -> str | None:
    """发布事件到 SSB 数据库，返回 ssb_event_id"""
    if not SSB_DB.exists():
        return None
    try:
        conn = sqlite3.connect(str(SSB_DB), timeout=5)
        c = conn.cursor()
        tables = c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='ssb_events'"
        ).fetchall()
        if not tables:
            conn.close()
            return None
        event_id = str(uuid.uuid4())
        row = c.execute("SELECT MAX(seq) FROM ssb_events").fetchone()
        next_seq = (row[0] or 0) + 1
        summary = event.get("summary", "")[:200]
        detail = event.get("detail", "")[:500]
        c.execute(
            "INSERT INTO ssb_events "
            "(id, seq, timestamp, session_id, source_agent, source_instance,"
            " target_scope, target_hint, event_type, event_subtype,"
            " summary, detail, confidence, risk_level, priority,"
            " action_req, deadline, payload_json, semantic_json, agent_signature, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                event_id,
                next_seq,
                event.get("timestamp", datetime.now().isoformat()),
                "audit-unified",
                "ecos-audit",
                "audit_unified.py",
                event.get("domain", "all"),
                event.get("uri", ""),
                "AUDIT",
                event.get("event_type", ""),
                summary,
                detail,
                1.0,
                "low",
                "P3",
                "",
                "",
                json.dumps(event.get("metadata", {}), ensure_ascii=False),
                json.dumps(
                    {"source": event.get("source", ""), "cards_id": event.get("cards_id")},
                    ensure_ascii=False,
                ),
                "",
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
        conn.close()
        return event_id
    except Exception:
        return None


# ═══════════════════════════════════════════════════
# JSONL 写入
# ═══════════════════════════════════════════════════


def _append_jsonl(path: Path, event: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a") as f:
            f.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass


# ═══════════════════════════════════════════════════
# 统一日志入口
# ═══════════════════════════════════════════════════


def log_event(
    source: str = "l0",
    event_type: str = "audit",
    summary: str = "",
    detail: str = "",
    uri: str = None,
    domain: str = None,
    passed: bool = True,
    violations: list = None,
    cards_id: str = None,
    daemon_cycle_id: int = None,
    healer_check_type: str = None,
    duration_ms: int = None,
    anomaly: bool = False,
    metadata: dict = None,
    **kwargs,
) -> dict:
    """统一审计日志入口 — 同时写入 SSB + 对应源 JSONL + unified.jsonl"""
    event = {
        "source": source,
        "event_type": event_type,
        "summary": (summary or "")[:200],
        "detail": (detail or "")[:1000],
    }
    if uri:
        event["uri"] = uri
    if domain:
        event["domain"] = domain
    if passed is not None:
        event["passed"] = passed
    if violations:
        event["violations"] = violations
    if cards_id:
        event["cards_id"] = cards_id
    if daemon_cycle_id is not None:
        event["daemon_cycle_id"] = daemon_cycle_id
    if healer_check_type:
        event["healer_check_type"] = healer_check_type
    if duration_ms is not None:
        event["duration_ms"] = duration_ms
    if anomaly:
        event["anomaly"] = anomaly
    if metadata:
        event["metadata"] = metadata

    event = _format_event(event)
    event["ssb_event_id"] = _ssb_publish(event)

    if source == "l0":
        _append_jsonl(L0_AUDIT_LOG, event)
    elif source == "bos":
        _append_jsonl(BOS_AUDIT_LOG, event)

    _append_jsonl(UNIFIED_AUDIT_LOG, event)
    return event


# ═══════════════════════════════════════════════════
# CARDS 桥接 (去重 mof-bos.py / mof_agora_hook.py 逻辑)
# ═══════════════════════════════════════════════════


def create_audit_debt(uri: str, anomaly_type: str, detail: str) -> str | None:
    """根据审计异常自动创建 CARDS 债务卡"""
    try:
        cards_db = H / "Workspace" / "projects" / "ecos" / "data" / "cards" / "cards.db"
        if not cards_db.exists():
            return None
        from datetime import date

        today = date.today().isoformat()
        safe_uri = re.sub(r'[^a-zA-Z0-9_-]', '_', uri.split("://")[-1] if "://" in uri else uri)[:30]
        cards_id = f"DEBT-AUDIT-{today}-{safe_uri}"

        conn = sqlite3.connect(str(cards_db))
        exists = conn.execute("SELECT id FROM cards WHERE id=?", (cards_id,)).fetchone()
        if exists:
            conn.close()
            return cards_id

        conn.execute(
            "INSERT INTO cards (id, type, status, title, domain, priority, summary, content, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (
                cards_id,
                "debt",
                "identified",
                f"审计异常: {anomaly_type} ({uri})",
                "infra",
                "P2",
                f"审计发现异常: {anomaly_type} — {detail[:120]}",
                f"## 审计异常\n\n**URI**: {uri}\n**类型**: {anomaly_type}\n**详情**: {detail}\n\n自动创建于 {datetime.now().isoformat()}",
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
        conn.close()
        return cards_id
    except Exception:
        return None


# ═══════════════════════════════════════════════════
# 跨源审计查询
# ═══════════════════════════════════════════════════


def _parse_dt(ts: str) -> datetime | None:
    """解析 ISO-8601 时间戳，统一为 naive datetime"""
    try:
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is not None:
            dt = dt.replace(tzinfo=None)
        return dt
    except (ValueError, TypeError):
        return None


def _query_jsonl(path: Path, hours: int = 24, source_filter: str = None) -> list[dict]:
    """从 JSONL 文件查询事件"""
    if not path.exists():
        return []
    cutoff = datetime.now() - timedelta(hours=hours)
    events = []
    try:
        with open(path) as f:
            for line in f:
                try:
                    e = json.loads(line)
                    ts = e.get("timestamp", "")
                    if ts:
                        et = _parse_dt(ts)
                        if et and et < cutoff:
                            continue
                    if source_filter and e.get("source") != source_filter:
                        continue
                    events.append(e)
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass
    return events


def _query_ssb(hours: int = 24, event_type: str = None) -> list[dict]:
    """从 SSB SQLite 查询审计事件"""
    if not SSB_DB.exists():
        return []
    cutoff = datetime.now() - timedelta(hours=hours)
    events = []
    try:
        conn = sqlite3.connect(str(SSB_DB), timeout=5)
        c = conn.cursor()
        tables = c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='ssb_events'"
        ).fetchall()
        if not tables:
            conn.close()
            return []

        q = "SELECT id, seq, timestamp, event_type, event_subtype, summary, detail, source_agent, target_scope FROM ssb_events WHERE timestamp >= ?"
        params = [cutoff.isoformat()]
        if event_type:
            q += " AND event_type = ?"
            params.append(event_type)
        q += " ORDER BY seq DESC LIMIT 200"

        rows = c.execute(q, params).fetchall()
        conn.close()
        for row in rows:
            events.append(
                {
                    "id": row[0],
                    "seq": row[1],
                    "timestamp": row[2],
                    "event_type": row[3],
                    "event_subtype": row[4],
                    "summary": row[5],
                    "detail": row[6],
                    "source": "ssb",
                    "source_agent": row[7],
                    "domain": row[8],
                }
            )
    except Exception:
        pass
    return events


def _query_daemon_db(hours: int = 24) -> list[dict]:
    """从 daemon-state.db 查询 cycle 记录"""
    if not DAEMON_STATE_DB.exists():
        return []
    cutoff = datetime.now() - timedelta(hours=hours)
    events = []
    try:
        conn = sqlite3.connect(str(DAEMON_STATE_DB), timeout=5)
        c = conn.cursor()
        tables = c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='cycles'"
        ).fetchall()
        if not tables:
            conn.close()
            return []
        rows = c.execute(
            "SELECT id, started_at, completed_at, exit_code, summary FROM cycles WHERE started_at >= ? ORDER BY id DESC LIMIT 50",
            (cutoff.isoformat(),),
        ).fetchall()
        conn.close()
        for row in rows:
            events.append(
                {
                    "id": f"daemon-cycle-{row[0]}",
                    "source": "daemon",
                    "event_type": "cycle_run",
                    "daemon_cycle_id": row[0],
                    "timestamp": row[1],
                    "summary": row[4] or f"Daemon cycle #{row[0]}",
                    "detail": f"exit_code={row[2]}, completed_at={row[3]}",
                    "passed": row[2] == 0,
                }
            )
    except Exception:
        pass
    return events


def _query_healer_db(hours: int = 24) -> list[dict]:
    """从 healer-state.db 查询修复记录"""
    if not HEALER_STATE_DB.exists():
        return []
    cutoff = datetime.now() - timedelta(hours=hours)
    events = []
    try:
        conn = sqlite3.connect(str(HEALER_STATE_DB), timeout=5)
        c = conn.cursor()
        tables = c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='heal_attempts'"
        ).fetchall()
        if not tables:
            conn.close()
            return []
        rows = c.execute(
            "SELECT id, check_type, issue, action, result, timestamp FROM heal_attempts WHERE timestamp >= ? ORDER BY id DESC LIMIT 50",
            (cutoff.isoformat(),),
        ).fetchall()
        conn.close()
        for row in rows:
            events.append(
                {
                    "id": f"healer-{row[0]}",
                    "source": "healer",
                    "event_type": "heal_attempt",
                    "healer_check_type": row[1],
                    "timestamp": row[5],
                    "summary": f"Healer [{row[1]}]: {(row[2] or '')[:60]}",
                    "detail": f"action={row[3]}, result={row[4]}",
                    "passed": "success" in (row[4] or "").lower(),
                }
            )
    except Exception:
        pass
    return events


def query_events(
    hours: int = 24,
    source: str = "all",
    event_type: str = None,
    domain: str = None,
    limit: int = 100,
) -> dict:
    """跨源联合审计查询 — SSB + L0 + BOS + daemon + healer + unified"""
    all_events = []
    source_counts = {}

    # When source=all, skip "unified" to avoid double-counting (unified.jsonl aggregates
    # events that also appear in l0/bos JSONLs). Use --source unified to query only the aggregate.
    sources_to_query = ["l0", "bos", "ssb", "daemon", "healer"] if source == "all" else [source]

    for s in sources_to_query:
        if s == "unified":
            evts = _query_jsonl(UNIFIED_AUDIT_LOG, hours)
        elif s == "l0":
            evts = _query_jsonl(L0_AUDIT_LOG, hours)
        elif s == "bos":
            evts = _query_jsonl(BOS_AUDIT_LOG, hours)
        elif s == "ssb":
            evts = _query_ssb(hours, event_type)
        elif s == "daemon":
            evts = _query_daemon_db(hours)
        elif s == "healer":
            evts = _query_healer_db(hours)
        else:
            evts = []

        if domain:
            evts = [e for e in evts if e.get("domain") == domain]
        if event_type and s != "ssb":
            evts = [e for e in evts if e.get("event_type") == event_type]

        all_events.extend(evts[:limit])
        source_counts[s] = len(evts)

    all_events.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
    all_events = all_events[:limit]

    passed = sum(1 for e in all_events if e.get("passed") in (True, None))
    failed = sum(1 for e in all_events if e.get("passed") is False)
    anomalies = sum(1 for e in all_events if e.get("anomaly"))

    return {
        "sources": source_counts,
        "total": len(all_events),
        "passed": passed,
        "failed": failed,
        "anomalies": anomalies,
        "events": all_events,
    }


def print_audit_report(result: dict) -> None:
    """打印审计查询报告"""
    print(f"\n  ═══ 统一审计查询 ═══\n")

    src_parts = [f"{k}={v}" for k, v in sorted(result["sources"].items()) if v > 0]
    print(f"  来源: {', '.join(src_parts)}")
    print(f"  事件: {result['total']} 条  |  ✅通过={result['passed']}  ❌失败={result['failed']}  ⚠️异常={result['anomalies']}")
    print()

    if not result["events"]:
        print("  📋 无审计事件\n")
        return

    print(f"  {'时间':<22} {'源':<8} {'类型':<18} {'通过':<6} {'摘要'}")
    print(f"  {'─'*22} {'─'*8} {'─'*18} {'─'*6} {'─'*50}")

    for e in result["events"]:
        ts = (e.get("timestamp") or "?")[:19]
        src = (e.get("source") or "?")[:7]
        etype = (e.get("event_type") or "?")[:17]
        pv = e.get("passed")
        if pv is True:
            p_icon = "✅"
        elif pv is False:
            p_icon = "❌"
        else:
            p_icon = "○"
        summary = (e.get("summary") or "")[:48]
        print(f"  {ts} {src:<8} {etype:<18} {p_icon:<6} {summary}")

    print(
        f"\n  提示: 使用 --source ssb 查看 SSB 事件, --source daemon 查看 daemon cycles, "
        f"--source healer 查看修复记录\n"
    )


# ═══════════════════════════════════════════════════
# CLI 入口
# ═══════════════════════════════════════════════════


def main():
    """audit-unified CLI"""
    hours = 24
    source = "all"
    domain = None
    event_type = None

    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a == "--hours" and i + 1 < len(args):
            hours = int(args[i + 1])
        elif a == "--source" and i + 1 < len(args):
            source = args[i + 1]
        elif a == "--domain" and i + 1 < len(args):
            domain = args[i + 1]
        elif a == "--event-type" and i + 1 < len(args):
            event_type = args[i + 1]

    result = query_events(hours=hours, source=source, domain=domain, event_type=event_type)
    print_audit_report(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
