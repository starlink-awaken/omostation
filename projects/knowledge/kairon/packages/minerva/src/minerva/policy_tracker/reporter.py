"""Policy Tracker 报告生成器 — 输出 Markdown 卫生政策简报。"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from minerva.policy_tracker.types import PolicyItem


def generate_report(
    items: list[PolicyItem],
    source_status: dict[str, str] | None = None,
    run_date: str | None = None,
) -> str:
    """生成 Markdown 格式的卫生政策简报。"""
    run_date = run_date or datetime.now(UTC).strftime("%Y-%m-%d")
    source_status = source_status or {}

    by_agency: dict[str, list[PolicyItem]] = {}
    for item in items:
        by_agency.setdefault(item.issuing_agency, []).append(item)

    lines: list[str] = [
        f"# 卫生政策简报 — {run_date}",
        "",
        "> 自动生成 · omostation P28-W1-POLICY-TRACKER · 数据源: 国家卫健委 / 国家医保局 / 国家药监局",
        "",
        "---",
        "",
        "## 核心发现",
        "",
        f"- 本次抓取条目: **{len(items)}**",
        f"- 数据源分布: {', '.join(f'{a}({len(v)})' for a, v in by_agency.items()) or '无'}",
    ]

    if source_status:
        lines.append("- 数据源可用性:")
        for src, st in source_status.items():
            icon = {"ok": "OK", "failed": "FAIL", "seed": "SEED"}.get(st, st)
            lines.append(f"  - {src}: {icon}")

    lines += [
        "",
        "---",
        "",
        "## 高相关度政策 Top 列表",
        "",
    ]

    if items:
        lines.append("| # | 标题 | 发布机构 | 相关度 | 文号 | 日期 | 链接 |")
        lines.append("|---|------|----------|--------|------|------|------|")
        for idx, item in enumerate(items[:15], 1):
            score_bar = "HIGH" if item.relevance_score >= 0.4 else "MED" if item.relevance_score >= 0.2 else "LOW"
            title_short = item.title[:50] + ("…" if len(item.title) > 50 else "")
            doc_no = item.doc_number or "-"
            url_md = f"[link]({item.url})" if item.url else "-"
            lines.append(
                f"| {idx} | {title_short} | {item.issuing_agency} | {score_bar} {item.relevance_score:.2f} | {doc_no} | {item.published_at} | {url_md} |"
            )
    else:
        lines.append("_本次未抓取到相关政策。_")

    lines += [
        "",
        "---",
        "",
        "## 分源明细",
        "",
    ]

    for agency, agency_items in by_agency.items():
        lines += [f"### {agency} ({len(agency_items)} 条)", ""]
        for item in agency_items[:10]:
            score_str = f"[{item.relevance_score:.2f}]" if item.relevance_score > 0 else ""
            doc_part = f" · {item.doc_number}" if item.doc_number else ""
            url_part = f" · [link]({item.url})" if item.url else ""
            lines.append(f"- **{item.title[:80]}**{doc_part} {score_str}{url_part}")
            if item.summary and item.summary != item.title:
                lines.append(f"  > {item.summary[:150]}")
        lines.append("")

    lines += [
        "---",
        "",
        "## 建议行动",
        "",
    ]

    high = [i for i in items if i.relevance_score >= 0.4]
    if high:
        for idx, item in enumerate(high[:3], 1):
            lines.append(
                f"{idx}. **{item.title[:60]}** — 相关度 {item.relevance_score:.2f}，"
                f"建议纳入 P28-W1-E2E-DEMO 的政策知识底座（{item.issuing_agency}）"
            )
    else:
        lines.append("_暂无高相关度政策。_")

    lines += [
        "",
        "---",
        "",
        f"*生成时间: {datetime.now(UTC).isoformat()} · 任务: P28-W1-POLICY-TRACKER*",
    ]

    return "\n".join(lines)


def save_report(
    items: list[PolicyItem],
    output_path: str,
    source_status: dict[str, str] | None = None,
    run_date: str | None = None,
) -> Path:
    """生成并保存报告到文件。"""
    content = generate_report(items, source_status, run_date)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path
