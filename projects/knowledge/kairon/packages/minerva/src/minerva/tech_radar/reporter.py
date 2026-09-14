"""Tech Radar 报告生成器 — 输出 Markdown 技术雷达简报。"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from minerva.tech_radar.fetcher import TechItem


def generate_report(items: list[TechItem], run_date: str | None = None) -> str:
    """生成 Markdown 格式的技术雷达简报。"""
    run_date = run_date or datetime.now(UTC).strftime("%Y-%m-%d")
    candidates = [i for i in items if i.upgrade_candidate]
    by_source: dict[str, list[TechItem]] = {}
    for item in items:
        by_source.setdefault(item.source, []).append(item)

    lines: list[str] = [
        f"# 技术雷达简报 — {run_date}",
        "",
        "> 自动生成 · omostation P28-W1-TECH-RADAR · 数据源: ArXiv / GitHub Trending / HuggingFace",
        "",
        "---",
        "",
        "## 核心发现",
        "",
        f"- 本次抓取条目: **{len(items)}**",
        f"- 升级候选 (relevance ≥ 0.40): **{len(candidates)}**",
        f"- 数据源分布: {', '.join(f'{s}({len(v)})' for s, v in by_source.items())}",
        "",
        "---",
        "",
        "## 升级候选 Top 列表",
        "",
    ]

    if candidates:
        lines.append("| # | 标题 | 来源 | 相关度 | 链接 |")
        lines.append("|---|------|------|--------|------|")
        for idx, item in enumerate(candidates[:15], 1):
            score_bar = "🔴" if item.relevance_score >= 0.6 else "🟡"
            title_short = item.title[:60] + ("…" if len(item.title) > 60 else "")
            url_md = f"[link]({item.url})" if item.url else "-"
            lines.append(
                f"| {idx} | {title_short} | {item.source} | {score_bar} {item.relevance_score:.2f} | {url_md} |"
            )
    else:
        lines.append("_本次未发现高相关度升级候选。_")

    lines += [
        "",
        "---",
        "",
        "## 分源明细",
        "",
    ]

    for source, source_items in by_source.items():
        source_label = {"arxiv": "ArXiv 论文", "github": "GitHub Trending", "huggingface": "HuggingFace 模型"}.get(
            source, source
        )
        lines += [f"### {source_label} ({len(source_items)} 条)", ""]
        for item in source_items[:10]:
            score_str = f"[{item.relevance_score:.2f}]" if item.relevance_score > 0 else ""
            url_part = f" · [{item.url[:60]}]({item.url})" if item.url else ""
            lines.append(f"- **{item.title[:80]}** {score_str}{url_part}")
            if item.description:
                lines.append(f"  > {item.description[:150]}")
        lines.append("")

    lines += [
        "---",
        "",
        "## 建议行动",
        "",
    ]

    if candidates:
        for idx, item in enumerate(candidates[:3], 1):
            lines.append(
                f"{idx}. **{item.title[:60]}** — 相关度 {item.relevance_score:.2f}，建议评估是否可引入 omostation ({item.source})"
            )
    else:
        lines.append("_暂无高优先级行动项。_")

    lines += [
        "",
        "---",
        "",
        f"*生成时间: {datetime.now(UTC).isoformat()} · 任务: P28-W1-TECH-RADAR*",
    ]

    return "\n".join(lines)


def save_report(items: list[TechItem], output_path: str, run_date: str | None = None) -> Path:
    """生成并保存报告到文件。"""
    content = generate_report(items, run_date)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path
