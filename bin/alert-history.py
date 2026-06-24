#!/usr/bin/env python3
"""P68 R2: 告警历史趋势报告.

读 .omo/_log/alert-notifications.jsonl (P66 写入), 生成跨 N 天趋势:
- 按天统计告警数 + 级别分布
- P0/P1/P2 频次 + 触发时间
- 抑制命中率
- 与 P0/P1 频率异常高的日期

使用:
  python3 bin/alert-history.py
  python3 bin/alert-history.py --days 7
  python3 bin/alert-history.py --format json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _load_events(root: Path, days: int, kinds: set[str]) -> list[dict]:
    """从 OMO event log 读取指定 kind 的 payload, 过滤最近 N 天.

    Round 5 (P3): OMO event log 是事件持久化 SSOT, 替代直接读 .omo/_log/.
    """
    log_file = root / ".omo" / "_knowledge" / "omo-events.jsonl"
    if not log_file.exists():
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    records = []
    try:
        with open(log_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                    if d.get("kind") not in kinds:
                        continue
                    payload = d.get("payload", "{}")
                    if isinstance(payload, str):
                        payload = json.loads(payload)
                    ts = payload.get("timestamp", d.get("ts", ""))
                    if ts:
                        rec_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                        if rec_dt >= cutoff:
                            records.append(payload)
                except Exception:
                    pass
    except Exception:
        pass
    return records


def load_notifications(root: Path, days: int) -> list[dict]:
    """读 governance_alert_aggregated 事件 payload, 过滤最近 N 天."""
    return _load_events(root, days, {"governance_alert_aggregated"})


def load_suppressions(root: Path, days: int) -> list[dict]:
    """P69 增: 读 governance_alert_suppressed 事件 payload."""
    return _load_events(root, days, {"governance_alert_suppressed"})


def render_ascii_bar(value: int, max_value: int, width: int = 40) -> str:
    """P69: ASCII 柱状图."""
    if max_value <= 0:
        return ""
    bar_len = int(value / max_value * width)
    return "█" * bar_len + "░" * (width - bar_len)


def _within_hours(ts: str, hours: int) -> bool:
    """P74 增: 判断 ts 是否在最近 N 小时内."""
    if not ts:
        return False
    try:
        from datetime import datetime, timezone, timedelta
        rec_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        return rec_dt >= cutoff
    except Exception:
        return False


def analyze_history(records: list[dict], suppressions: list[dict]) -> dict:
    """分析告警历史 (P69 + suppressions, P71 + cross_level 维度)."""
    by_day: dict[str, Counter] = defaultdict(Counter)
    by_level: Counter = Counter()
    by_type: Counter = Counter()
    by_cross_level: dict[str, int] = {}  # P71: 按 (level, sup_state) 聚合
    peak_days = []

    for rec in records:
        ts = rec.get("timestamp", "")
        day = ts[:10] if ts else "unknown"
        level = rec.get("level", "P3")
        by_day[day][level] += 1
        by_level[level] += 1
        # P71: cross_level 维度 (按 level + suppression 状态)
        key = f"{level}_fired"
        by_cross_level[key] = by_cross_level.get(key, 0) + 1
        for bt, count in rec.get("by_type", {}).items():
            by_type[bt] += count

    # P71: suppression 维度加入
    for rec in suppressions:
        level = rec.get("level", "P3")
        key = f"{level}_suppressed"
        by_cross_level[key] = by_cross_level.get(key, 0) + 1

    for day, counts in by_day.items():
        critical = counts.get("P0", 0) + counts.get("P1", 0)
        if critical >= 3:
            peak_days.append(
                {"day": day, "critical_count": critical, "breakdown": dict(counts)}
            )

    total = sum(by_level.values())
    suppress_count = len(suppressions)
    suppression_rate = (
        suppress_count / (total + suppress_count) if (total + suppress_count) > 0 else 0
    )

    # P71: suppression efficiency (触发 vs 抑制比)
    fired_total = sum(v for k, v in by_cross_level.items() if k.endswith("_fired"))
    suppressed_total = sum(
        v for k, v in by_cross_level.items() if k.endswith("_suppressed")
    )
    efficiency = suppressed_total / fired_total if fired_total > 0 else 0.0

    # P74 增: by_level_sup_state (按级别拆分的触发 vs 抑制)
    by_level_sup_state: dict[str, dict[str, int]] = {}
    for level in by_level:
        by_level_sup_state[level] = {
            "fired": by_cross_level.get(f"{level}_fired", 0),
            "suppressed": by_cross_level.get(f"{level}_suppressed", 0),
        }

    # P74 增: by_time_window (1h / 6h / 24h 分桶)
    by_time_window: dict[str, int] = {
        "1h": sum(1 for r in records if _within_hours(r.get("timestamp", ""), 1)),
        "6h": sum(1 for r in records if _within_hours(r.get("timestamp", ""), 6)),
        "24h": sum(1 for r in records if _within_hours(r.get("timestamp", ""), 24)),
    }
    # P74 增: peak_hour (24h 内最频繁的 hour)
    hour_counter: dict[str, int] = {}
    for r in records:
        ts = r.get("timestamp", "")
        if ts:
            hour = ts[:13]  # YYYY-MM-DDTHH
            hour_counter[hour] = hour_counter.get(hour, 0) + 1
    peak_hour = max(hour_counter, key=lambda k: hour_counter[k]) if hour_counter else "N/A"

    return {
        "total_notifications": total,
        "by_level": dict(by_level),
        "by_type": dict(by_type),
        "by_day": {day: dict(counts) for day, counts in sorted(by_day.items())},
        "by_cross_level": by_cross_level,  # P71 新增
        "by_sup_state": {
            "fired": fired_total,
            "suppressed": suppressed_total,
        },
        "by_level_sup_state": by_level_sup_state,  # P74 增
        "by_time_window": by_time_window,  # P74 增
        "peak_hour": peak_hour,  # P74 增
        "peak_days": peak_days,
        "suppression_count": suppress_count,
        "suppression_rate": round(suppression_rate, 3),
        "suppression_efficiency": round(efficiency, 3),  # P71 新增
        "record_count": len(records),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="P68: 告警历史趋势报告")
    parser.add_argument("root", nargs="?", default=".", help="workspace root")
    parser.add_argument("--days", type=int, default=7, help="时间窗口 (天, 默认 7)")
    parser.add_argument("--format", choices=["json", "text"], default="text")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not (root / ".omo").exists():
        print(f"❌ .omo/ not found at {root}")
        return 1

    records = load_notifications(root, args.days)
    suppressions = load_suppressions(root, args.days)
    hist = analyze_history(records, suppressions)

    if args.format == "json":
        output = json.dumps(
            {
                "days": args.days,
                **hist,
            },
            indent=2,
            ensure_ascii=False,
        )
    else:
        # P70 增: rich 库颜色 (terminal-friendly)
        try:
            from rich.console import Console
            from rich.table import Table
            from rich.panel import Panel
            from rich.text import Text

            console = Console()
            level_color = {
                "P0": "bold red",
                "P1": "red",
                "P2": "yellow",
                "P3": "green",
            }

            # Header panel
            console.print(
                Panel(
                    f"[bold cyan]最近 {args.days} 天[/bold cyan]\n"
                    f"通知: {hist['record_count']}  |  总告警: {hist['total_notifications']}\n"
                    f"抑制: {hist['suppression_count']}  |  抑制率: {hist['suppression_rate'] * 100:.1f}%",
                    title="📊 P70 告警历史趋势",
                    border_style="cyan",
                )
            )

            # 级别表
            if hist["by_level"]:
                table = Table(title="按级别", show_header=True, header_style="bold")
                table.add_column("级别", style="cyan")
                table.add_column("次数", justify="right", style="green")
                for level, count in sorted(hist["by_level"].items()):
                    color = level_color.get(level, "white")
                    table.add_row(f"[{color}]{level}[/{color}]", str(count))
                console.print(table)

            # 按天柱状图 (rich Bar)
            if hist["by_day"]:
                recent_days = sorted(hist["by_day"].items())[-7:]
                max_total = (
                    max(sum(counts.values()) for _, counts in recent_days)
                    if recent_days
                    else 1
                )
                from rich.bar import Bar

                bar_table = Table(title="按天 (最近 7d)", show_header=True)
                bar_table.add_column("日期", style="cyan")
                bar_table.add_column("柱状图")
                bar_table.add_column("详情", justify="right")
                for day, counts in recent_days:
                    day_total = sum(counts.values())
                    # 富文本条
                    bar_len = max(1, int(day_total / max_total * 30))
                    bar_text = Text("█" * bar_len, style="cyan")
                    detail = " ".join(
                        f"[{level_color.get(k, 'white')}]{k}:{v}[/{level_color.get(k, 'white')}]"
                        for k, v in counts.items()
                    )
                    bar_table.add_row(day, bar_text, detail)
                console.print(bar_table)

            if hist["peak_days"]:
                console.print(
                    Panel(
                        "\n".join(
                            f"  {pd['day']}: critical={pd['critical_count']} {pd['breakdown']}"
                            for pd in hist["peak_days"]
                        ),
                        title="🚨 高峰日 (P0+P1 >= 3)",
                        border_style="red",
                    )
                )
            output = ""  # rich 自身渲染
        except ImportError:
            # fallback: 纯文本
            lines = [
                "=" * 60,
                f"📊 P70 告警历史趋势报告 (最近 {args.days} 天)",
                "=" * 60,
                f"📁 通知记录数: {hist['record_count']}",
                f"📈 总通知数: {hist['total_notifications']}",
                f"🔕 抑制记录: {hist['suppression_count']}",
                f"📊 抑制率: {hist['suppression_rate'] * 100:.1f}%",
                "",
                "--- 按级别 ---",
            ]
            for level, count in sorted(hist["by_level"].items()):
                lines.append(f"  {level:<8s} {count:>3d}")
            output = "\n".join(lines)

    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
