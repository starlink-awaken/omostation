#!/usr/bin/env python3
"""
控制面保鲜审计 — 自动化审查 L4 文档域 CLAUDE.md / STATE.md 审查日期

用法:
  python3 control-plane-freshness-audit.py              # 控制台摘要
  python3 control-plane-freshness-audit.py --report     # Markdown 报告
  python3 control-plane-freshness-audit.py --write-signal  # 逾期≥7天写入 @驾驶舱/_control/signals.md
"""

import os
import re
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

DOCUMENTS_BASE = Path(os.path.expanduser("~/Documents"))
SIGNALS_FILE = DOCUMENTS_BASE / "@驾驶舱/_control/signals.md"

# L4 文档域映射
DOMAINS = {
    "@驾驶舱": ("cockpit", "meta"),
    "@个人": ("personal", "personal"),
    "@学习进化": ("vault", "vault"),
    "@创意创作": ("creative", "creative"),
    "@OPC": ("opc", "opc"),
    "@公共": ("shared", "shared"),
    "@家庭生活": ("family", "family"),
    "@工作文档": ("work-docs", "work-docs"),
    "@工作文档/卫健委": ("work-weijian", "work-weijian"),
    "@工作文档/国转中心": ("work-guozhuan", "work-guozhuan"),
    "@工作文档/合同法规": ("contract", "contract"),
    "@工作文档/规自委": ("work-liyongke", "work-liyongke"),
}


def parse_date(s: str) -> datetime:
    """解析 ISO 或 YYYY-MM-DD 日期"""
    s = s.strip()
    if not s or s == "?":
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def read_claude_dates(domain_path: Path) -> dict:
    """读取 CLAUDE.md 的最后更新和下次审查日期"""
    result = {"updated": None, "review": None}
    claude_file = domain_path / "CLAUDE.md"
    if not claude_file.exists():
        return result
    text = claude_file.read_text(encoding="utf-8")
    m = re.search(r"最后更新[:：]\s*(\d{4}-\d{2}-\d{2})", text)
    if m:
        result["updated"] = parse_date(m.group(1))
    m = re.search(r"下次审查[:：]\s*(\d{4}-\d{2}-\d{2})", text)
    if m:
        result["review"] = parse_date(m.group(1))
    return result


def read_state_date(domain_path: Path) -> dict:
    """读取 STATE.md 的 last-reviewed 日期"""
    result = {"last_reviewed": None}
    state_file = domain_path / "_control/STATE.md"
    if not state_file.exists():
        return result
    text = state_file.read_text(encoding="utf-8")
    # 先尝试 YAML frontmatter
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            fm = parts[1]
            m = re.search(r"last-reviewed[:：]\s*(\S+)", fm)
            if m:
                result["last_reviewed"] = parse_date(m.group(1))
                return result
    # 退回到正文搜索
    m = re.search(r"last-reviewed[:：]\s*(\S+)", text)
    if m:
        result["last_reviewed"] = parse_date(m.group(1))
    return result


def days_overdue(dt: datetime, ref: datetime = None) -> int:
    """返回逾期天数，未逾期返回 0"""
    if dt is None:
        return -1
    if ref is None:
        ref = datetime.now(timezone.utc).replace(tzinfo=None)
    delta = ref - dt
    return max(0, delta.days)


def audit_domain(domain_name: str, domain_path: Path) -> dict:
    """审计单个域的控制面保鲜状态"""
    claude = read_claude_dates(domain_path)
    state = read_state_date(domain_path)

    result = {
        "domain": domain_name,
        "claude_updated": claude["updated"],
        "claude_review": claude["review"],
        "state_reviewed": state["last_reviewed"],
        "claude_overdue": days_overdue(claude["review"]),
        "state_overdue": days_overdue(state["last_reviewed"]),
    }
    return result


def status_for_overdue(days: int) -> str:
    if days < 0:
        return "⚪"
    if days == 0:
        return "🟢"
    if days < 7:
        return "🟡"
    return "🔴"


def print_summary(results: list):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print("=" * 100)
    print(f"控制面保鲜审计 | {now}")
    print("=" * 100)
    print()
    print(f"{'域':<22} {'CLAUDE 最后更新':<16} {'CLAUDE 下次审查':<18} {'STATE last-reviewed':<20} {'状态':<6}")
    print("─" * 100)

    total = len(results)
    greens = 0
    for r in results:
        cu = r["claude_updated"].strftime("%Y-%m-%d") if r["claude_updated"] else "—"
        cr = r["claude_review"].strftime("%Y-%m-%d") if r["claude_review"] else "—"
        sr = r["state_reviewed"].strftime("%Y-%m-%d") if r["state_reviewed"] else "—"
        status_c = status_for_overdue(r["claude_overdue"])
        status_s = status_for_overdue(r["state_overdue"])
        overall = "🟢" if status_c in ("🟢", "⚪") and status_s in ("🟢", "⚪") else "🔴" if "🔴" in (status_c, status_s) else "🟡"
        if overall == "🟢":
            greens += 1
        print(f"{r['domain']:<22} {cu:<16} {cr:<18} {sr:<20} {overall} ({status_c}{status_s})")

    print()
    print(f"🟢 保鲜通过: {greens}/{total} ({greens/total*100:.0f}%)")


def print_report(results: list) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = []
    lines.append("# 控制面保鲜审计报告")
    lines.append("")
    lines.append(f"> 生成时间: {now}")
    lines.append("")
    lines.append("| 域 | CLAUDE 最后更新 | CLAUDE 下次审查 | STATE last-reviewed | 状态 |")
    lines.append("|---|:---------------:|:---------------:|:-------------------:|:----:|")

    total = len(results)
    greens = 0
    for r in results:
        cu = r["claude_updated"].strftime("%Y-%m-%d") if r["claude_updated"] else "—"
        cr = r["claude_review"].strftime("%Y-%m-%d") if r["claude_review"] else "—"
        sr = r["state_reviewed"].strftime("%Y-%m-%d") if r["state_reviewed"] else "—"
        status_c = status_for_overdue(r["claude_overdue"])
        status_s = status_for_overdue(r["state_overdue"])
        overall = "🟢" if status_c in ("🟢", "⚪") and status_s in ("🟢", "⚪") else "🔴" if "🔴" in (status_c, status_s) else "🟡"
        if overall == "🟢":
            greens += 1
        lines.append(f"| {r['domain']} | {cu} | {cr} | {sr} | {overall} |")

    lines.append("")
    lines.append(f"**保鲜通过率**: {greens}/{total} ({greens/total*100:.0f}%)")
    lines.append("")
    lines.append("## 逾期详情")
    lines.append("")
    has_overdue = False
    for r in results:
        overdue_items = []
        if r["claude_overdue"] > 0:
            overdue_items.append(f"CLAUDE.md 下次审查逾期 {r['claude_overdue']} 天")
        if r["state_overdue"] > 0:
            overdue_items.append(f"STATE.md last-reviewed 逾期 {r['state_overdue']} 天")
        if overdue_items:
            has_overdue = True
            status = "🔴" if max(r["claude_overdue"], r["state_overdue"]) >= 7 else "🟡"
            lines.append(f"- {status} **{r['domain']}**: " + "; ".join(overdue_items))
    if not has_overdue:
        lines.append("- ✅ 无逾期域")

    lines.append("")
    lines.append("## 处置规则")
    lines.append("")
    lines.append("- 🟡 逾期 <7 天: 写入 `@驾驶舱/_control/signals.md` 提醒")
    lines.append("- 🔴 逾期 ≥7 天: 自动创建 CARDS 任务(`cards create --domain meta`)")
    lines.append("- 本报告由 `@公共/_runtime/control-plane-freshness-audit.py` 生成")

    return "\n".join(lines)


def write_signals(results: list):
    """把逾期≥7天的域写入 SIGNALS.md"""
    overdue = []
    for r in results:
        if r["claude_overdue"] >= 7 or r["state_overdue"] >= 7:
            items = []
            if r["claude_overdue"] >= 7:
                items.append(f"CLAUDE.md 逾期 {r['claude_overdue']} 天")
            if r["state_overdue"] >= 7:
                items.append(f"STATE.md 逾期 {r['state_overdue']} 天")
            overdue.append((r["domain"], "; ".join(items)))

    if not overdue:
        print("✅ 无逾期≥7天的域，无需写入信号")
        return

    if not SIGNALS_FILE.exists():
        print(f"❌ {SIGNALS_FILE} 不存在")
        return

    text = SIGNALS_FILE.read_text(encoding="utf-8")
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")

    for domain, detail in overdue:
        signal_block = f"""
- message: '控制面保鲜告警：{domain} {detail}，需审查刷新'
  source: system.freshness
  ts: '{ts}'
  type: 🔴
  scope:
    - {domain.replace('@', '').replace('/', '-').lower()}
    - governance
"""
        # 在 signals: 后插入
        insert_pos = text.find("signals:")
        if insert_pos != -1:
            insert_pos += len("signals:")
            text = text[:insert_pos] + signal_block + text[insert_pos:]

    SIGNALS_FILE.write_text(text, encoding="utf-8")
    print(f"✅ 已写入 {len(overdue)} 条保鲜告警信号到 {SIGNALS_FILE}")


def main():
    results = []
    for name, (domain_id, cards_domain) in DOMAINS.items():
        path = DOCUMENTS_BASE / name
        if not path.exists():
            continue
        r = audit_domain(name, path)
        r["id"] = domain_id
        r["cards_domain"] = cards_domain
        results.append(r)

    if "--report" in sys.argv:
        print(print_report(results))
    elif "--write-signal" in sys.argv:
        write_signals(results)
    else:
        print_summary(results)


if __name__ == "__main__":
    main()
