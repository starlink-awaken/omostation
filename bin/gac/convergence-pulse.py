#!/usr/bin/env python3
"""ADR-0443 收敛脉搏采集器：产出/收敛事件口径 v1 的周级汇总。

只数有 SSOT 记录的治理事件（排除 self-data 原则）：
- 收敛侧：escape 指纹豁免（.omo/_delivery/swarm-escape/）、gate 健康事件
  （.omo/_knowledge/governance-history.jsonl）
- 产出侧：ADR/信号新增（git log）、debt items 变更（git log）
落 `.omo/state/convergence-pulse-{YYYY-WNN}.json`。本工具只计数与聚类，
趋势判断与阈值告警排 Q4（见 ADR-0443 演进路径）。
"""

from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "governance.convergence-pulse.v1"
ESCAPE_DIR = ROOT / ".omo/_delivery/swarm-escape"
HISTORY = ROOT / ".omo/_knowledge/governance-history.jsonl"
DECISIONS = ROOT / ".omo/_knowledge/decisions"
SIGNALS = ROOT / ".omo/_knowledge/signals"
DEBT_ITEMS = ROOT / ".omo/debt/items"
STATE_DIR = ROOT / ".omo/state"
TOP_N = 10


def _week_key(today: date) -> str:
    year, week, _ = today.isocalendar()
    return f"{year}-W{week:02d}"


def _window(since: date, until: date) -> tuple[datetime, datetime]:
    start = datetime(since.year, since.month, since.day, tzinfo=UTC)
    end = datetime(until.year, until.month, until.day, tzinfo=UTC) + timedelta(days=1)
    return start, end


def _parse_ts(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def collect_escapes(start: datetime, end: datetime) -> dict[str, object]:
    """Escape 台账按指纹聚类；目录缺失（worktree/未启用）时 unavailable 而非崩溃。"""

    if not ESCAPE_DIR.is_dir():
        return {"available": False, "records": 0, "unique_fingerprints": 0, "top_fingerprints": []}
    counter: Counter[str] = Counter()
    preflight_clean = 0
    unattributed = 0
    records = 0
    for path in sorted(ESCAPE_DIR.glob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        ts = _parse_ts(str(record.get("ts") or ""))
        if ts is None or not (start <= ts < end):
            continue
        records += 1
        key = str(record.get("fingerprint_key") or path.stem)
        # ADR-0443 v2 (Q4/Q6): 三桶——preflight-clean 归因、老 unspecified 降级
        # unattributed（不回填）、其余正常指纹。
        if key.startswith("preflight-clean"):
            preflight_clean += 1
        elif key.startswith("unspecified"):
            unattributed += 1
        else:
            counter[key] += 1
    top = [{"fingerprint": fp, "count": n} for fp, n in counter.most_common(TOP_N)]
    return {
        "available": True,
        "records": records,
        "unique_fingerprints": len(counter),
        "preflight_clean": preflight_clean,
        "unattributed": unattributed,
        "top_fingerprints": top,
    }


def collect_history(start: datetime, end: datetime) -> dict[str, object]:
    """governance-history 事件计数与 grade 分布（0390 修复后的活数据流）。"""

    if not HISTORY.is_file():
        return {"available": False, "events": 0, "grade_counts": {}}
    grades: Counter[str] = Counter()
    events = 0
    for line in HISTORY.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts = _parse_ts(str(event.get("timestamp") or ""))
        if ts is None or not (start <= ts < end):
            continue
        events += 1
        grades[str(event.get("grade") or "unknown")] += 1
    return {"available": True, "events": events, "grade_counts": dict(grades)}


def _git_log_num(since: str, until: str, pathspec: str, diff_filter: str) -> int:
    result = subprocess.run(
        [
            "git",
            "-C",
            str(ROOT),
            "log",
            "--since",
            since,
            "--until",
            until,
            "--diff-filter",
            diff_filter,
            "--name-only",
            "--format=",
            "--",
            pathspec,
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        return -1
    return len({ln for ln in result.stdout.splitlines() if ln.strip()})


def collect_production(since: date, until: date) -> dict[str, object]:
    """产出侧：ADR/信号新增与 debt 开闭（git 事件，无 git 环境 unavailable）。"""

    since_s, until_s = since.isoformat(), (until + timedelta(days=1)).isoformat()
    adr_added = _git_log_num(since_s, until_s, ".omo/_knowledge/decisions", "A")
    signal_added = _git_log_num(since_s, until_s, ".omo/_knowledge/signals", "A")
    debt_opened = _git_log_num(since_s, until_s, ".omo/debt/items", "A")
    debt_closed = _git_log_num(since_s, until_s, ".omo/debt/items", "D")
    available = -1 not in (adr_added, signal_added, debt_opened, debt_closed)
    return {
        "available": available,
        "adr_added": max(adr_added, 0),
        "signal_added": max(signal_added, 0),
        "debt_opened": max(debt_opened, 0),
        "debt_closed": max(debt_closed, 0),
    }


def collect_health(until: date) -> dict[str, object]:
    """运行时健康面 (阶段0 告警闭环, 2026-09-02): 断产出告警进周报.

    Sources: tailscale 心跳 (bin/health/tailscale-heartbeat.sh 产物) /
    晨报断更 (当日 brief 缺失且已过 08:00) / embed node 探活 (Mac mini :18700).
    """
    alerts: list[str] = []
    state = {"tailscale": "unknown", "morning_brief": "unknown", "embed_node": "unknown"}

    hb_path = ROOT / ".omo" / "state" / "tailscale-heartbeat.json"
    if hb_path.is_file():
        try:
            hb = json.loads(hb_path.read_text(encoding="utf-8"))
            state["tailscale"] = "ok" if hb.get("ok") else ("zombie" if hb.get("zombie_interface") else "down")
            if not hb.get("ok"):
                alerts.append(f"tailscale 心跳失败 (zombie={hb.get('zombie_interface')}, checked_at={hb.get('checked_at')})")
        except (OSError, ValueError):
            state["tailscale"] = "unreadable"
            alerts.append("tailscale 心跳产物不可读")
    else:
        state["tailscale"] = "missing"
        alerts.append("tailscale 心跳产物缺失 (LaunchAgent 未跑?)")

    brief = ROOT / ".omo" / "state" / "policy-radar" / f"brief-{until.strftime('%Y%m%d')}.json"
    now_h = datetime.now(UTC).hour + datetime.now(UTC).minute / 60
    if now_h >= 8.0:  # 晨报预算 07:30, 08:00 后缺产物即断更
        state["morning_brief"] = "ok" if brief.is_file() else "stale"
        if not brief.is_file():
            alerts.append(f"晨报断更: {brief.name} 缺失 (已过 08:00 UTC)")
    else:
        state["morning_brief"] = "not_due_yet"

    try:
        import urllib.request

        req = urllib.request.Request("http://100.99.210.78:18700/health", headers={"User-Agent": "convergence-pulse/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            state["embed_node"] = "ok" if resp.status == 200 else f"http_{resp.status}"
    except Exception as exc:
        state["embed_node"] = "down"
        alerts.append(f"embed node 不可达 (Mac mini :18700): {type(exc).__name__}")

    return {"alerts": alerts, "sources": state, "alert_count": len(alerts)}


def collect_pulse(*, since: date, until: date, generated_at: datetime | None = None) -> dict[str, object]:
    start, end = _window(since, until)
    return {
        "schema": SCHEMA,
        "week": _week_key(until),
        "window": {"since": since.isoformat(), "until": until.isoformat()},
        "generated_at": (generated_at or datetime.now(UTC)).isoformat(),
        "production": collect_production(since, until),
        "convergence": {
            "escapes": collect_escapes(start, end),
            "history": collect_history(start, end),
        },
        "health": collect_health(until),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since", help="ISO date, 默认本周一")
    parser.add_argument("--until", help="ISO date, 默认今天")
    parser.add_argument("--stdout", action="store_true", help="只打印不落盘")
    args = parser.parse_args(argv)
    until = date.fromisoformat(args.until) if args.until else date.today()
    if args.since:
        since = date.fromisoformat(args.since)
    else:
        since = until - timedelta(days=until.weekday())  # 周一
    pulse = collect_pulse(since=since, until=until)
    text = json.dumps(pulse, ensure_ascii=False, sort_keys=True, indent=2)
    if args.stdout:
        print(text)
        return 0
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    out = STATE_DIR / f"convergence-pulse-{pulse['week']}.json"
    out.write_text(text + "\n", encoding="utf-8")
    print(f"convergence-pulse: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
