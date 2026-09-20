#!/usr/bin/env python3
"""季度报告自动生成器 — FORWARD-PLAN v2 §A2 (P0)

一键生成季度报告 doc + 趋势数据，替代手工拼凑。

用法:
    python3 bin/reports/quarterly-report.py --quarter 2026-Q4 --output docs/reports/
    python3 bin/reports/quarterly-report.py --quarter 2026-Q3 --output /tmp/
    python3 bin/reports/quarterly-report.py --list-quarters

数据源:
    - docs/plans/3y-bet-ledger.yaml       → BET 完成率 + 趋势
    - .omo/state/health.yaml              → 7 维健康分
    - .omo/state/system.yaml              → 任务统计
    - docs/reports/weekly-value-snapshots.jsonl → AI 工具采纳统计
    - .omo/_knowledge/retros/             → 知识沉淀计数
    - docs/reports/                       → 历史报告引用
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML required. Install: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

# ─── 路径 ──────────────────────────────────────────────────────────────
WORKSPACE = Path(__file__).resolve().parent.parent.parent
BET_LEDGER = WORKSPACE / "docs" / "plans" / "3y-bet-ledger.yaml"
HEALTH_YAML = WORKSPACE / ".omo" / "state" / "health.yaml"
SYSTEM_YAML = WORKSPACE / ".omo" / "state" / "system.yaml"
WEEKLY_SNAPSHOTS = WORKSPACE / "docs" / "reports" / "weekly-value-snapshots.jsonl"
RETROS_DIR = WORKSPACE / ".omo" / "_knowledge" / "retros"
REPORTS_DIR = WORKSPACE / "docs" / "reports"


# ─── 数据加载 ──────────────────────────────────────────────────────────

def load_yaml(path: Path):
    """加载 YAML 文件，不存在返回空 dict。"""
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        print(f"  WARN: Failed to load {path}: {e}", file=sys.stderr)
        return {}


def load_jsonl(path: Path):
    """加载 JSONL 文件，不存在返回空 list。"""
    if not path.exists():
        return []
    results = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    results.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return results


def count_retros():
    """统计 retro 文件数量（排除 _archive 和 index 文件）。"""
    if not RETROS_DIR.exists():
        return 0
    count = 0
    for f in RETROS_DIR.rglob("*.md"):
        if f.name not in ("index.md", "_template.md"):
            count += 1
    return count


def count_quarter_reports():
    """统计历史季度报告数量。"""
    if not REPORTS_DIR.exists():
        return 0
    return len([f for f in REPORTS_DIR.iterdir() if "quarterly" in f.name.lower()])


# ─── 数据聚合 ──────────────────────────────────────────────────────────

def parse_quarter_label(quarter: str) -> tuple[int, int]:
    """解析 '2026-Q4' → (2026, 4)。"""
    m = re.match(r"(\d{4})-Q(\d)", quarter)
    if not m:
        raise ValueError(f"Invalid quarter format: {quarter}. Expected YYYY-QN.")
    return int(m.group(1)), int(m.group(2))


def bet_stats_by_window(bets: list[dict]) -> dict[str, dict]:
    """按 window 统计 BET 状态分布。"""
    stats = defaultdict(lambda: {"done": 0, "total": 0})
    for bet in bets:
        window = bet.get("window", "unknown")
        status = bet.get("status", "unknown")
        stats[window]["total"] += 1
        if status == "done":
            stats[window]["done"] += 1
    return dict(stats)


def window_range_for_quarter(year: int, quarter: int) -> list[str]:
    """给定 YYYY-QN 返回对应的 BET window 标签列表。
    
    财年映射: Y1=2025(项目启动年), Y2=2026, Y3=2027+
    实际映射需要根据项目历史确定，这里做近似映射。
    """
    # 项目历史: Y1Q1~Y1Q4 ≈ 2025Q1~Q4
    # Y2Q1~Y2Q4 ≈ 2026Q1~Q4
    # Y3H1~Y3H2 ≈ 2027H1~H2
    # 但 BET ledger 中的 window 标签是 Y1Q1, Y1Q2, ... 不是日历季度
    # 所以无法精确映射，返回所有 window
    return []


def get_quarter_health_scores(health_data: dict) -> dict:
    """提取 7 维健康分。"""
    return {
        "composite": health_data.get("health_score", "?"),
        "governance_anomaly": health_data.get("governance_anomaly_score", "?"),
        "freshness": health_data.get("freshness_score", "?"),
        "drift": health_data.get("drift_score", "?"),
        "staleness": health_data.get("staleness_score", "?"),
        "alignment": health_data.get("alignment_score", "?"),
        "service_online_ratio": health_data.get("service_online_ratio", "?"),
        "feedback_staleness_hours": health_data.get("feedback_staleness_hours", "?"),
    }


def ai_tool_adoption(snapshots: list[dict]) -> dict:
    """从 weekly snapshots 计算 AI 工具采纳统计。"""
    total = len(snapshots)
    measured = [s for s in snapshots if s.get("status") != "unmeasured"]
    accepted_total = sum(s.get("accepted_by_principal", 0) for s in measured)
    signals_total = sum(s.get("signals_count", 0) for s in measured)
    adoption_rate = (accepted_total / signals_total * 100) if signals_total > 0 else 0
    avg_weekly_adoption = (
        sum(s.get("weekly_adoption_rate", 0) for s in measured) / len(measured) * 100
        if measured
        else 0
    )
    return {
        "total_snapshots": total,
        "measured_snapshots": len(measured),
        "signals_count": signals_total,
        "accepted_count": accepted_total,
        "adoption_rate_pct": round(adoption_rate, 1),
        "avg_weekly_adoption_pct": round(avg_weekly_adoption, 1),
        "falsification_risks": sorted(
            set(r for s in measured for r in s.get("falsification_risks", []))
        ),
        "blockers": sorted(
            set(b for s in measured for b in s.get("blockers", []))
        ),
    }


# ─── 报告生成 ──────────────────────────────────────────────────────────

def health_level(score: float) -> str:
    """健康分等级标签。"""
    if score >= 90:
        return "卓越"
    if score >= 75:
        return "良好"
    if score >= 60:
        return "中等"
    if score >= 40:
        return "警戒"
    return "危险"


def generate_report(quarter: str, bet_data: dict, health_data: dict,
                    system_data: dict, snapshots: list[dict]) -> str:
    """生成季度报告 Markdown 内容。"""
    year, q = parse_quarter_label(quarter)
    bets = bet_data.get("bets", [])
    total_bets = len(bets)
    done_bets = sum(1 for b in bets if b.get("status") == "done")
    completion_pct = (done_bets / total_bets * 100) if total_bets > 0 else 0

    window_stats = bet_stats_by_window(bets)
    retro_count = count_retros()
    quarter_report_count = count_quarter_reports()
    adoption = ai_tool_adoption(snapshots)
    scores = get_quarter_health_scores(health_data)

    # 按 window 排列
    ordered_windows = sorted(window_stats.keys())

    # 生成报告
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    report = f"""---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}
title: 季度评估 ({quarter})
---

# 季度评估 ({quarter})

> **Generated**: {now} | **Source**: `bin/reports/quarterly-report.py` (FORWARD-PLAN v2 §A2)
> **评估周期**: {year}-Q{q}
> **FORWARD-PLAN §C3 季度评估**

## 1. 完成率 (Completion Rate)

| 维度 | 目标 | 实际 | 评估 |
|------|------|------|------|
| 总 BET 完成率 | ≥ 95% | **{completion_pct:.0f}% ({done_bets}/{total_bets})** | {'✅ 卓越' if completion_pct >= 95 else '🟡 需关注'} |
| 任务完成率 | ≥ 90% | {system_data.get('completed_tasks', '?')}/{system_data.get('total_tasks', '?')} | — |
| 场景卡生命周期 | 覆盖 5 域 | 见 cockpit scene-cards | — |

### 按 Window 分布

| Window | Done | Total | 完成率 |
|--------|------|-------|--------|
"""

    for w in ordered_windows:
        ws = window_stats[w]
        pct = (ws["done"] / ws["total"] * 100) if ws["total"] > 0 else 0
        report += f"| {w} | {ws['done']} | {ws['total']} | {pct:.0f}% |\n"

    report += f"""
## 2. 健康分 (Health Score)

| 维度 | 数值 | 等级 |
|------|------|------|
| **复合健康分** | **{scores['composite']}/100** | {health_level(float(scores['composite']) if isinstance(scores['composite'], (int, float)) else 0)} |
| GAC 异常扣分 | {scores['governance_anomaly']}/100 | {'✅ 正常' if int(scores['governance_anomaly']) == 0 else '⚠️ 有异常'} |
| 新鲜度 (Freshness) | {scores['freshness']}/100 | — |
| 漂移 (Drift) | {scores['drift']}/100 | — |
| 陈旧 (Staleness) | {scores['staleness']}/100 | — |
| 对齐 (Alignment) | {scores['alignment']}/100 | — |
| 服务在线率 | {scores['service_online_ratio']} | — |
| 反馈活跃度 | {scores['feedback_staleness_hours']}h staleness | {'✅ 活跃' if float(scores['feedback_staleness_hours']) < 24 else '⚠️ 停滞'} |

### 健康分构成 (Composite Breakdown)

"""
    hb = health_data.get("health_composite_breakdown", {})
    weights = hb.get("weights", {})
    contributions = hb.get("contributions", {})
    report += "| 维度 | 权重 | 贡献分 |\n|------|------|--------|\n"
    for dim in ["governance", "freshness", "runtime", "drift", "staleness", "alignment"]:
        w = weights.get(dim, "?")
        c = contributions.get(dim, "?")
        report += f"| {dim} | {w} | {c} |\n"

    report += f"""
## 3. AI 工具采纳统计

| 指标 | 数值 |
|------|------|
| 周度快照总数 | {adoption['total_snapshots']} |
| 有测量快照数 | {adoption['measured_snapshots']} |
| 信号总数 | {adoption['signals_count']} |
| 采纳总数 | {adoption['accepted_count']} |
| **综合采纳率** | **{adoption['adoption_rate_pct']}%** |
| 周均采纳率 | {adoption['avg_weekly_adoption_pct']}% |

"""
    if adoption["falsification_risks"]:
        report += f"**Falsification Risks**: {', '.join(adoption['falsification_risks'])}\n"
    if adoption["blockers"]:
        report += f"**Blockers**: {', '.join(adoption['blockers'])}\n"

    report += f"""
## 4. 知识沉淀

| 指标 | 数值 |
|------|------|
| 累计 Retro | {retro_count} |
| 季度报告 | {quarter_report_count} |
| 知识沉淀目录 | `.omo/_knowledge/` |
| 模式目录 (Patterns) | `.omo/_knowledge/patterns/` |
| Retro 目录 | `.omo/_knowledge/retros/` |

## 5. 任务状态

| 指标 | 数值 |
|------|------|
| 当前阶段 | {system_data.get('current_phase', '?')} |
| 已完成任务 | {system_data.get('completed_tasks', '?')} |
| 计划中任务 | {system_data.get('planned_tasks', '?')} |
| 活跃任务 | {system_data.get('active_tasks', '?')} |
| 总任务数 | {system_data.get('total_tasks', '?')} |

## 6. 风险与缺口

| 项 | 风险 | 缓解 |
|------|------|------|
| bin-quota 维护压力 | add1=delete1 守恒，新功能需先归档 | 归档策略已固化 |
| SSL/网络稳定性 | submodule checkout 失败 | SSH fallback + `--no-verify` |
| AI 工具采纳率低 | 当前 {adoption['adoption_rate_pct']}% | A1 反馈循环验证 (2026Q4) |
| gh API 不稳定 | GraphQL EOF 频繁 | REST API fallback |
| health-predict 启发式 | 无历史回归基线 | B2 baseline 累积 (2027Q1) |

## 7. 关联

- `docs/OMOSTATION-FORWARD-PLAN-v2.md` (路线图)
- `docs/OMOSTATION-FORWARD-PLAN.md` (v1, 已完成)
- `docs/SOPs/ledger-closeout-sop.md` (5 步 SOP)
- `docs/reports/2026-Q3-quarterly-evaluation.md` (上季度报告)
- `docs/STRATEGY-3YEAR-PLAN-2026H2-2029.md` (3 年计划)
- `.omo/_knowledge/retros/` ({retro_count} retros)

## 版本

- **Generator**: `bin/reports/quarterly-report.py` (FORWARD-PLAN v2 §A2)
- **Generated**: {now}
"""

    return report


# ─── CLI ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="季度报告自动生成器 — FORWARD-PLAN v2 §A2",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python3 bin/reports/quarterly-report.py --quarter 2026-Q4
    python3 bin/reports/quarterly-report.py --quarter 2026-Q3 --output /tmp/
    python3 bin/reports/quarterly-report.py --list-quarters
        """,
    )
    parser.add_argument("--quarter", type=str, default=None,
                        help="季度标签，如 2026-Q4")
    parser.add_argument("--output", type=str, default=str(REPORTS_DIR),
                        help="输出目录 (默认 docs/reports/)")
    parser.add_argument("--list-quarters", action="store_true",
                        help="列出所有可用的 BET window 标签")
    parser.add_argument("--dry-run", action="store_true",
                        help="仅打印报告内容，不写入文件")
    parser.add_argument("--json", action="store_true",
                        help="同时输出 JSON 格式摘要")

    args = parser.parse_args()

    # 加载数据
    bet_data = load_yaml(BET_LEDGER)
    health_data = load_yaml(HEALTH_YAML)
    system_data = load_yaml(SYSTEM_YAML)
    snapshots = load_jsonl(WEEKLY_SNAPSHOTS)

    if args.list_quarters:
        bets = bet_data.get("bets", [])
        windows = sorted(set(b.get("window", "unknown") for b in bets))
        print("Available BET windows:")
        for w in windows:
            print(f"  {w}")
        return

    if not args.quarter:
        # 默认当前季度
        now = datetime.now(timezone.utc)
        q = (now.month - 1) // 3 + 1
        args.quarter = f"{now.year}-Q{q}"
        print(f"INFO: No --quarter specified, defaulting to {args.quarter}")

    # 生成报告
    report = generate_report(args.quarter, bet_data, health_data, system_data, snapshots)

    if args.dry_run:
        print(report)
        return

    # 写入文件
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{args.quarter}-quarterly-evaluation.md"
    output_path = output_dir / filename
    output_path.write_text(report, encoding="utf-8")
    print(f"Report written: {output_path}")
    print(f"  BETs: {len(bet_data.get('bets', []))}")
    print(f"  Health score: {health_data.get('health_score', '?')}")
    print(f"  Retros: {count_retros()}")
    print(f"  Weekly snapshots: {len(snapshots)}")

    # JSON 摘要
    if args.json:
        summary = {
            "quarter": args.quarter,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_bets": len(bet_data.get("bets", [])),
            "done_bets": sum(1 for b in bet_data.get("bets", []) if b.get("status") == "done"),
            "health_score": health_data.get("health_score", None),
            "retro_count": count_retros(),
            "output_path": str(output_path),
        }
        print(f"\nJSON summary:\n{json.dumps(summary, indent=2)}")


if __name__ == "__main__":
    main()
