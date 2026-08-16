"""Tech Radar 主运行器 — 抓取 → 分析 → KOS 入库 → 生成简报。"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import UTC, datetime
from pathlib import Path

from minerva.tech_radar.analyzer import analyze_items
from minerva.tech_radar.fetcher import TechItem, fetch_all
from minerva.tech_radar.kos_writer import save_to_kos
from minerva.tech_radar.reporter import save_report

logger = logging.getLogger(__name__)


def _resolve_workspace_root() -> Path | None:
    """查找 omostation 工作区根（包含顶层 .omo/_delivery）。

    优先级：
      1. 环境变量 OMOSTATION_ROOT
      2. 沿 cwd 向上找最深的 .omo/_delivery
    """
    env = os.environ.get("OMOSTATION_ROOT")
    if env and (Path(env) / ".omo" / "_delivery").is_dir():
        return Path(env)

    cwd = Path.cwd()
    # Walk up from cwd; return the FIRST (deepest/closest) match
    for parent in [cwd, *cwd.parents]:
        if (parent / ".omo" / "_delivery").is_dir():
            return parent
    return None


def _default_output_path(date: str) -> Path:
    """默认输出到 omostation 根 .omo/_delivery/，找不到则用 cwd。"""
    root = _resolve_workspace_root()
    base = root / ".omo" / "_delivery" if root else Path.cwd() / ".omo" / "_delivery"
    return base / f"tech-radar-{date}-report.md"


async def run(
    output_path: str | None = None,
    sources: list[str] | None = None,
    relevance_threshold: float = 0.15,
    dry_run: bool = False,
) -> dict:
    """执行一次完整的技术雷达扫描。

    Args:
        output_path: 报告输出路径，None 时使用默认路径。
        sources: 数据源列表，None 时使用全部 ["arxiv", "github", "huggingface"]。
        relevance_threshold: 最低相关度阈值，低于此值的条目被过滤。
        dry_run: True 时只抓取分析，不写 KOS、不保存文件。

    Returns:
        运行摘要 dict。
    """
    run_date = datetime.now(UTC).strftime("%Y-%m-%d")
    logger.info("tech_radar_start date=%s sources=%s dry_run=%s", run_date, sources, dry_run)

    # 1. 抓取
    print(f"[tech-radar] 抓取数据源: {sources or 'all'}…")
    raw_items: list[TechItem] = await fetch_all(sources)
    print(f"[tech-radar] 原始条目: {len(raw_items)}")

    # 2. 分析 & 过滤
    scored_items = analyze_items(raw_items, threshold=relevance_threshold)
    candidates = [i for i in scored_items if i.upgrade_candidate]
    print(f"[tech-radar] 相关条目: {len(scored_items)}  升级候选: {len(candidates)}")

    kos_stats: dict = {"saved": 0, "failed": 0, "skipped": 0}
    report_path: str = ""

    if not dry_run:
        # 3. KOS 入库
        print("[tech-radar] 写入 KOS…")
        kos_stats = save_to_kos(scored_items)
        print(f"[tech-radar] KOS 写入: saved={kos_stats['saved']} failed={kos_stats['failed']}")

        # 4. 生成报告
        out = output_path or str(_default_output_path(run_date))
        report_file = save_report(scored_items, out, run_date)
        report_path = str(report_file)
        print(f"[tech-radar] 报告已保存: {report_path}")
    else:
        print("[tech-radar] dry-run 模式，跳过 KOS 写入和文件保存")
        # 仍打印 top 5 到控制台
        for item in scored_items[:5]:
            print(f"  [{item.relevance_score:.2f}] {item.source:12s} {item.title[:60]}")

    summary = {
        "run_date": run_date,
        "raw_count": len(raw_items),
        "relevant_count": len(scored_items),
        "candidate_count": len(candidates),
        "kos": kos_stats,
        "report_path": report_path,
        "top_candidates": [
            {"title": i.title[:80], "source": i.source, "score": i.relevance_score, "url": i.url}
            for i in candidates[:5]
        ],
    }
    logger.info("tech_radar_done summary=%s", summary)
    return summary


def main(
    output: str | None = None,
    sources: str | None = None,
    threshold: float = 0.15,
    dry_run: bool = False,
) -> None:
    """CLI 入口（被 minerva cli.py 调用）。"""
    src_list = [s.strip() for s in sources.split(",")] if sources else None
    result = asyncio.run(
        run(
            output_path=output,
            sources=src_list,
            relevance_threshold=threshold,
            dry_run=dry_run,
        )
    )
    print(f"\n[tech-radar] 完成 — 候选: {result['candidate_count']} 条，报告: {result['report_path'] or '(dry-run)'}")
