"""Markdown 渲染器 — 按严重度分桶，输出家庭可读待办。"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from minerva.health_summarizer.rules import HealthAlert, Severity

DEFAULT_OUTPUT: Path = Path(
    "~/Library/Mobile Documents/iCloud~md~obsidian/Documents/FamilyShared/01.健康/00-待办.md"
).expanduser()

SEVERITY_LABELS: dict[Severity, tuple[str, str]] = {
    "urgent": ("🔴", "紧急（7 天内）"),
    "soon": ("🟡", "即将（30 天内）"),
    "info": ("⚪", "一般（参考）"),
}


def _format_alert_line(a: HealthAlert) -> str:
    base = f"- **{a.member_name}** ({a.category}): {a.title} — {a.detail}"
    if a.action_by:
        base += f"  · 行动日期: {a.action_by.isoformat()}"
    return base


def render(alerts: list[HealthAlert], today: date | None = None) -> str:
    """渲染待办 Markdown。空列表 → 占位提示。"""
    today = today or date.today()
    lines: list[str] = [f"# 家庭健康待办 — {today.isoformat()}", ""]

    buckets: dict[Severity, list[HealthAlert]] = {"urgent": [], "soon": [], "info": []}
    for a in alerts:
        buckets[a.severity].append(a)

    any_alert = False
    for sev in ("urgent", "soon", "info"):
        icon, label = SEVERITY_LABELS[sev]
        items = buckets[sev]
        if not items:
            continue
        any_alert = True
        # 桶内按成员名分组
        by_member: dict[str, list[HealthAlert]] = {}
        for a in items:
            by_member.setdefault(a.member_name, []).append(a)
        lines.append(f"## {icon} {label}")
        for name in sorted(by_member.keys()):
            member_alerts = sorted(by_member[name], key=lambda x: (x.action_by or today, x.category))
            for a in member_alerts:
                lines.append(_format_alert_line(a))
        lines.append("")

    if not any_alert:
        lines.append("_当前无待办健康事项。_")
        lines.append("")
    else:
        lines.append("---")
        lines.append(
            f"_本摘要由 minerva.health_summarizer 自动生成 · {len(alerts)} 条提醒 · 数据源: FamilyShared/02.健康/档案_"
        )
    return "\n".join(lines)


def write_output(content: str, out: Path | None = None) -> Path:
    """写入 Markdown 到指定路径（默认 DEFAULT_OUTPUT）。"""
    target = out if out is not None else DEFAULT_OUTPUT
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target
