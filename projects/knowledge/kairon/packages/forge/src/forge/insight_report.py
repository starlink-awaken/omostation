#!/usr/bin/env python3
"""
insight_report — Forge 洞察引擎

将 scripts/insight-report.sh 移植为 Python。
分析能力缺口、生成周报、评估工具组合。

用法:
  python3 src/insight_report.py --gaps
  python3 src/insight_report.py --weekly
  python3 src/insight_report.py --portfolio
  python3 src/insight_report.py --gaps --weekly --portfolio --json --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from typing import cast

from forge.forge_config import FORGE_ROOT, REGISTRY  # type: ignore[import-not-found]

# ── 预设能力矩阵（与 shell 版一致）────────────────────────────────
PRESET_CAPABILITIES = [
    "代码生成:代码审查:代码补全:代码导航:代码重构:代码诊断",
    "文档编辑:笔记管理:PDF处理:格式转换:OCR:文字提取",
    "网页搜索:知识检索:文献搜索:论文搜索:深度研究",
    "模型推理:视觉分析:图像生成:多模型路由:长文本处理",
    "浏览器自动化:工作流编排:定时调度:自动抓取:批量处理",
    "思维链推理:方案设计:问题拆解:数据分析:报告生成",
]


def _load() -> dict:
    return cast("dict", json.loads(REGISTRY.read_text()))


def _save(reg: dict) -> None:
    """原子写入：tmp + rename，与 sync_registry.py 一致。"""
    tmp = REGISTRY.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(reg, indent=2, ensure_ascii=False) + "\n")
    tmp.rename(REGISTRY)


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _week_number() -> str:
    """返回 ISO 周号，如 '2026-W22'。"""
    now = datetime.now()
    iso = now.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def _week_start() -> str:
    """返回本周一的日期字符串 YYYY-MM-DD。"""
    now = datetime.now()
    monday = now - timedelta(days=now.weekday())
    return monday.strftime("%Y-%m-%d")


def _ninety_days_ago() -> str:
    return (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")


def _thirty_days_ago() -> str:
    return (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")


def _flatten_capabilities() -> list[str]:
    """将 PRESET_CAPABILITIES 展开为单个能力名字列表。"""
    result = []
    for group in PRESET_CAPABILITIES:
        for cap in group.split(":"):
            result.append(cap)
    return result


def _collect_existing_capabilities(reg: dict) -> list[str]:
    """收集注册表中所有工具的能力列表（小写）。"""
    caps: set[str] = set()
    for tool in reg.get("tools", []):
        for cap in tool.get("capabilities", []):
            caps.add(cap.lower())
    return sorted(caps)


def gaps_analysis(reg: dict) -> dict:
    """分析能力缺口（gap_analysis.gaps），返回缺口分析结果字典。

    将预设能力矩阵与注册表中已注册工具的能力进行对比，
    找出尚未覆盖的能力项。
    """
    all_preset = _flatten_capabilities()
    existing = _collect_existing_capabilities(reg)

    gaps: list[dict] = []
    for preset_cap in all_preset:
        found = False
        for ec in existing:
            if preset_cap.lower() in ec:
                found = True
                break
        if not found:
            gaps.append(
                {
                    "capability": preset_cap,
                    "request_count": 0,
                    "suggested_action": "考虑通过嗅探或搜索添加",
                }
            )

    result = {
        "generated": _now(),
        "gaps": gaps,
    }

    print("=== 能力缺口分析 ===")
    print(f"预设能力: {len(all_preset)} 个")
    print(f"已覆盖: {len(all_preset) - len(gaps)} 个")
    print(f"缺口: {len(gaps)} 个")
    print()
    if gaps:
        print("能力缺口列表:")
        for g in gaps:
            print(f"  🔴 {g['capability']}")
    else:
        print("✅ 无能力缺口")

    return result


def weekly_report(reg: dict) -> dict:
    """生成周报（weekly_reports），统计新增/活跃/变更。

    从注册表中提取工具数量、状态分布、本周事件、衍生资产等信息，
    输出终端可读文本报告。
    """
    week_num = _week_number()
    ws = _week_start()
    now = _now()

    tools = reg.get("tools", [])
    event_log = reg.get("event_log", [])

    total = len(tools)
    active = sum(1 for t in tools if t.get("status") == "active")
    candidate = sum(1 for t in tools if t.get("status") == "candidate")
    deprecated = sum(1 for t in tools if t.get("status") == "deprecated")
    stale = sum(1 for t in tools if t.get("status") == "stale")
    with_telemetry = sum(1 for t in tools if (t.get("telemetry") or {}).get("use_count", 0) > 0)

    # 本周事件统计
    new_tools = sum(
        1 for ev in event_log if ev.get("type", "").startswith("discovery:") and ev.get("timestamp", "") >= ws
    )
    version_updates = sum(
        1 for ev in event_log if ev.get("type", "").startswith("version:") and ev.get("timestamp", "") >= ws
    )
    sync_events = sum(
        1 for ev in event_log if ev.get("type", "").startswith("agora:") and ev.get("timestamp", "") >= ws
    )

    # 衍生资产
    skills_dir = FORGE_ROOT / "skills"
    pipelines_dir = FORGE_ROOT / "pipelines"
    skill_count = (
        len([d for d in skills_dir.iterdir() if d.is_dir() and d.name != ".gitkeep"]) if skills_dir.is_dir() else 0
    )
    pipe_count = len(list(pipelines_dir.glob("*.json"))) if pipelines_dir.is_dir() else 0
    graph_nodes = reg.get("graph", {}).get("node_count", 423)

    schema_version = reg.get("schema_version", "?")
    event_count = len(event_log)

    # 近 5 条事件
    recent_events = event_log[-5:]

    # 输出
    print("=== Forge 周报 — " + week_num + " ===")
    print("")
    print("┌──────────────────────────────────────────────────┐")
    print("│  📊 总览")
    print("│    总工具数: " + str(total))
    print("│    本周新增: " + str(new_tools) + " | 版本更新: " + str(version_updates) + " | 同步: " + str(sync_events))
    print("│")
    print(
        "│  🟢 激活: "
        + str(active)
        + " | 💡 候选: "
        + str(candidate)
        + " | ⚪ 沉默: "
        + str(stale)
        + " | 🗑️ 废弃: "
        + str(deprecated)
    )
    print("│")
    print(
        "│  📐 衍生: "
        + str(skill_count)
        + " skills | "
        + str(pipe_count)
        + " pipelines | "
        + str(graph_nodes)
        + " 图谱节点"
    )
    print("│  📈 使用追踪: " + str(with_telemetry) + " 个工具有使用记录")
    print("│  🔖 Schema: " + schema_version + " | 事件日志: " + str(event_count) + " 条")
    print("├──────────────────────────────────────────────────┤")
    print("│  本周事件摘要")
    for ev in recent_events:
        ts = (ev.get("timestamp") or "")[:10]
        summary = ev.get("summary", "")
        print("  [" + ts + "] " + summary)
    print("└──────────────────────────────────────────────────┘")

    result = {
        "week": week_num,
        "generated": now,
        "total_tools": total,
        "active_tools": active,
        "silent_tools": stale,
        "candidate_tools": candidate,
        "deprecated_tools": deprecated,
        "new_tools_this_week": new_tools,
        "version_updates": version_updates,
        "sync_events": sync_events,
        "skills": skill_count,
        "pipelines": pipe_count,
        "graph_nodes": graph_nodes,
        "usage_summary": str(with_telemetry) + " tools with usage data",
        "gaps_found": [],
        "top_events": [{"type": ev.get("type"), "summary": ev.get("summary")} for ev in event_log[-3:]],
        "recommendations": [],
    }

    # 收集现有缺口（从 gap_analysis 取前 5）
    existing_gaps = reg.get("gap_analysis", {}).get("gaps", [])[:5]
    result["gaps_found"] = [g.get("capability", "") for g in existing_gaps if g.get("capability")]

    return result


def portfolio_analysis(reg: dict) -> dict:
    """工具组合分析（portfolio）— 激活/沉默/潜在三分类。

    分类逻辑：
    - 激活资产: status=active 且近期 (30天) 有更新或有使用记录
    - 沉默资产: status=stale/evaluating, 或 active 但 90天无变更且使用量为 0
    - 潜在资产: status=candidate
    """
    tools = reg.get("tools", [])
    cut_30d = _thirty_days_ago()
    cut_90d = _ninety_days_ago()

    active_list: list[dict] = []
    silent_list: list[dict] = []
    candidate_list: list[dict] = []

    for t in tools:
        status = t.get("status", "")
        updated = t.get("updated", "")
        added = t.get("added", "")
        telemetry = t.get("telemetry", {}) or {}
        use_count = telemetry.get("use_count", 0)

        if status == "active" and (updated >= cut_30d or added >= cut_30d or use_count > 0):
            active_list.append(t)
        elif status in ("stale", "evaluating") or (status == "active" and updated < cut_90d and use_count == 0):
            silent_list.append(t)
        elif status == "candidate":
            candidate_list.append(t)

    # 生态潜在资产估算（不调用外部脚本，仅从注册表已有的 discovery 推断）
    eco_potential_candidates = sum(1 for t in tools if t.get("_discovery", {}).get("source") in ("eco", "ecosystem"))

    other_count = len(tools) - len(active_list) - len(silent_list) - len(candidate_list)

    # ── 输出 ──
    print("=== Forge 资产组合分析 ===")
    print("")
    print("┌──────────────────────────────────────────────────────────┐")
    print("│  总工具数: " + str(len(tools)))
    print("│")
    print("│  🟢 激活资产 (Active) — 有生命力的工具")
    print("│      注册状态=active + 近期更新/有使用记录")
    print("│      数量: " + str(len(active_list)))
    print("│")
    print("│  ⚪ 沉默资产 (Silent) — 已沉淀的工具")
    print("│      注册状态=stale/evaluating 或 90天无变更且0使用")
    print("│      数量: " + str(len(silent_list)))
    print("│")
    print("│  💡 潜在资产 (Potential) — 待发现/待确认")
    print("│      注册表 candidate: " + str(len(candidate_list)))
    print("│      生态未注册 (discovery来源=eco): " + str(eco_potential_candidates))
    print("│      合计: " + str(len(candidate_list) + eco_potential_candidates))
    print("│")
    print("│  📦 其它: " + str(other_count) + " (中间态)")
    print("└──────────────────────────────────────────────────────────┘")

    # 沉默资产明细
    if silent_list:
        print("")
        print("━━━ 沉默资产明细 ━━━")
        for t in silent_list:
            print(
                "    "
                + t.get("id", "?")
                + " ["
                + t.get("status", "?")
                + "] "
                + t.get("name", "?")
                + " — 添加于 "
                + str(t.get("added", "?"))
                + ", 更新 "
                + str(t.get("updated", "?"))
            )
        print("")
        print("建议: 检查这些工具是否还在用。不用的 → entropy-sunset 标记 deprecated")

    # 候选资产明细
    if candidate_list:
        print("")
        print("━━━ 候选资产明细 ━━━")
        for t in candidate_list:
            discovery_src = (t.get("_discovery") or {}).get("source", "?")
            print("    " + t.get("id", "?") + " [" + discovery_src + "] " + t.get("name", "?"))
        print("")
        print("建议: 运行 entropy-sunrise.sh --list 查看候选状态")

    # ── 扩展资产维度 ──
    print("")
    print("━━━ 扩展资产维度 ━━━")

    skills_dir = FORGE_ROOT / "skills"
    pipelines_dir = FORGE_ROOT / "pipelines"
    skill_count = (
        len([d for d in skills_dir.iterdir() if d.is_dir() and d.name != ".gitkeep"]) if skills_dir.is_dir() else 0
    )
    pipe_count = len(list(pipelines_dir.glob("*.json"))) if pipelines_dir.is_dir() else 0
    graph_nodes = reg.get("graph", {}).get("node_count", 423)
    graph_edges = reg.get("graph", {}).get("edge_count", 634)

    cat_count = len({c for t in tools for c in (t.get("category") or [])})

    print("")
    print("┌──────────────────────────────────────────────────────────┐")
    print("│  📐 衍生资产 (工具产生的价值)")
    print("│      Skills/技能: " + str(skill_count) + " 个")
    print("│      Pipelines/管线: " + str(pipe_count) + " 条")
    print("│      知识图谱: " + str(graph_nodes) + "节点 / " + str(graph_edges) + "边")
    print("│      能力维度: " + str(cat_count) + " 类")
    print("│")
    print("│  🌐 外界资产 (外部系统的引用)")
    print("│      KOS: 7域 8941 文档 (知识检索)")
    print("│      WPS Note: 课堂笔记/新闻简报/洞察")
    print("│      Obsidian: 双向链接知识库")
    print("│      Minerva: 1003 篇深度研究报告")
    print("│")
    print("│  ❓ 未知资产 (当前环境不可达)")
    print("│      另一台机器的工具")
    print("│      远程服务器的 CLI/SDK")
    print("│      npm/brew 有但本地未装的")
    print("└──────────────────────────────────────────────────────────┘")

    return {
        "total": len(tools),
        "active": len(active_list),
        "silent": len(silent_list),
        "candidate": len(candidate_list),
        "eco_potential": eco_potential_candidates,
        "other": other_count,
    }


def run(args: argparse.Namespace) -> int:
    """入口，支持 --gaps, --weekly, --portfolio, --json, --dry-run。

    返回退出码（0=成功）。
    """
    reg = _load()
    json_mode: bool = args.json
    dry_run: bool = args.dry_run

    results: dict[str, object] = {}

    if args.gaps:
        gap_result = gaps_analysis(reg)
        results["gap_analysis"] = gap_result
        if not dry_run:
            reg["gap_analysis"] = gap_result
            event_log = reg.setdefault("event_log", [])
            event_log.append(
                {
                    "type": "gap:analysis_done",
                    "tool_ids": [],
                    "summary": "Gap analysis: " + str(len(gap_result["gaps"])) + " gaps found",
                    "timestamp": _now(),
                }
            )
            _save(reg)
            print()
            print("✅ 缺口分析已写入 registry.gap_analysis")

    if args.weekly:
        weekly_result = weekly_report(reg)
        results["weekly_report"] = weekly_result
        if not dry_run:
            weekly_reports = reg.setdefault("weekly_reports", [])
            weekly_reports.append(weekly_result)
            if len(weekly_reports) > 8:
                reg["weekly_reports"] = weekly_reports[-8:]
            event_log = reg.setdefault("event_log", [])
            event_log.append(
                {
                    "type": "report:weekly_generated",
                    "tool_ids": [],
                    "summary": "Weekly report: "
                    + weekly_result["week"]
                    + ", "
                    + str(weekly_result["total_tools"])
                    + " tools",
                    "timestamp": _now(),
                }
            )
            _save(reg)
            print()
            print("✅ 周报已写入 registry.weekly_reports")

    if args.portfolio:
        portfolio_result = portfolio_analysis(reg)
        results["portfolio"] = portfolio_result
        if not dry_run:
            event_log = reg.setdefault("event_log", [])
            event_log.append(
                {
                    "type": "report:portfolio",
                    "tool_ids": [],
                    "summary": "Asset portfolio: "
                    + str(portfolio_result["active"])
                    + " active, "
                    + str(portfolio_result["silent"])
                    + " silent, "
                    + str(portfolio_result["candidate"] + portfolio_result["eco_potential"])
                    + " potential",
                    "timestamp": _now(),
                }
            )
            _save(reg)
            print()
            print("✅ 组合分析事件已写入 registry.event_log")

    if json_mode:
        print()
        print(json.dumps(results, indent=2, ensure_ascii=False))

    return 0


def main() -> int:
    """解析 CLI 参数并调用 run()。"""
    parser = argparse.ArgumentParser(
        description="Forge 洞察引擎 — 能力缺口分析、周报生成、资产组合分析",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  python3 src/insight_report.py --gaps\n"
            "  python3 src/insight_report.py --weekly\n"
            "  python3 src/insight_report.py --portfolio\n"
            "  python3 src/insight_report.py --gaps --weekly --portfolio --json --dry-run\n"
        ),
    )
    parser.add_argument("--gaps", action="store_true", help="能力缺口分析")
    parser.add_argument("--weekly", action="store_true", help="每周简报生成")
    parser.add_argument("--portfolio", action="store_true", help="资产组合分析")
    parser.add_argument("--json", action="store_true", help="JSON 格式输出")
    parser.add_argument("--dry-run", action="store_true", help="预览不写入")

    args = parser.parse_args()

    if not args.gaps and not args.weekly and not args.portfolio:
        parser.print_help()
        return 1

    return run(args)


if __name__ == "__main__":
    sys.exit(main())
