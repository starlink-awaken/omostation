#!/usr/bin/env python3
"""
STATE-CARDS 一致性审计 — 治理审计 v1.0

检查 L4 文档域的 STATE.md 中声明的活跃事项/瓶颈/信号,
是否与 CARDS SQLite 中的实际任务一致。

用法:
  python3 state-substance-audit.py              # 控制台摘要
  python3 state-substance-audit.py --report     # Markdown 报告
  python3 state-substance-audit.py --domain @驾驶舱  # 单域审计
"""

import os
import re
import sys
from pathlib import Path
import sqlite3
from datetime import datetime, timezone

# ======== 配置 ========
DOCUMENTS_BASE = os.path.expanduser("~/Documents")
CARDS_DB = os.path.expanduser("~/Workspace/data/cards/cards.db")

# L4 文档域映射: 域显示名 -> 域路径(相对 Documents) -> CARDS domain
DOMAIN_PATHS = {
    "@驾驶舱": ("@驾驶舱", "meta"),
    "@个人": ("@个人", "personal"),
    "@学习进化": ("@学习进化", "vault"),
    "@创意创作": ("@创意创作", "creative"),
    "@OPC": ("@OPC", "opc"),
    "@公共": ("@公共", "shared"),
    "@家庭生活": ("@家庭生活", "family"),
    "@工作文档": ("@工作文档", "work-docs"),
    "卫健委": ("@工作文档/卫健委", "work-weijian"),
    "国转中心": ("@工作文档/国转中心", "work-guozhuan"),
    "合同法规": ("@工作文档/合同法规", "contract"),
}

# STATE.md 中需要扫描的段落关键词
# 注意: "近期完成" "历史完成" 中的 ✅ 事项通常已闭环,不应要求 CARDS 匹配
SECTION_KEYWORDS = [
    "活跃事项", "持续关注", "当前瓶颈",
    "跨域信号", "活跃任务", "当前规划", "下一步"
]

# CARDS 中视为"活跃"的状态
ACTIVE_STATUSES = {"active", "identified", "in_progress", "planned"}


def parse_frontmatter(text: str) -> dict:
    """简单 YAML frontmatter 解析"""
    meta = {}
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            fm = parts[1]
            for line in fm.splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip()
    return meta


def extract_state_items(state_text: str) -> list:
    """
    从 STATE.md 文本中提取事项条目。
    策略: 在 SECTION_KEYWORDS 后的 Markdown 表格中,提取第一列(事项名)。
    非表格段落也尝试按 '| 事项 |' 格式提取。
    """
    items = []
    lines = state_text.splitlines()
    in_section = False
    section_buffer = []

    for line in lines:
        stripped = line.strip()
        # 检测段落标题
        if stripped.startswith("## ") or stripped.startswith("### "):
            in_section = any(kw in stripped for kw in SECTION_KEYWORDS)
            section_buffer = []
            continue

        if in_section:
            section_buffer.append(line)
            # 表格行
            if line.startswith("|") and line.count("|") >= 3:
                cells = [c.strip() for c in line.split("|")[1:-1]]
                if cells and cells[0] and cells[0] not in ("事项", "项目", "瓶颈", "信号", "规划", "下一步", "—", ""):
                    # 跳过表头分隔行
                    if not all(c in "-:| " for c in cells[0]):
                        # 跳过纯日期单元格(跨域信号段落常见)
                        if not re.match(r"^\d{4}-\d{2}-\d{2}$", cells[0]):
                            items.append(cells[0])
            # 列表行(无序 -/* 或有序 1. 2.)
            elif re.match(r"^(?:[-*]|\d+\.)\s+", stripped):
                item = re.sub(r"^(?:[-*]|\d+\.)\s+", "", stripped).strip()
                if item and not item.startswith("2026-"):
                    items.append(item)

    # 去重并过滤空值
    seen = set()
    result = []
    for item in items:
        # 清理 Markdown 标记
        clean = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", item)
        clean = re.sub(r"[*`#]", "", clean).strip()
        # 跳过删除线事项(已修复/已关闭)
        if clean.startswith("~~") and clean.endswith("~~"):
            continue
        if clean and clean not in seen and len(clean) > 3:
            seen.add(clean)
            result.append(clean)
    return result


def load_cards() -> dict:
    """按 domain 聚合活跃卡片"""
    cards_by_domain = {}
    if not os.path.exists(CARDS_DB):
        return cards_by_domain

    conn = sqlite3.connect(CARDS_DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        "SELECT domain, status, title, summary FROM cards WHERE status IN (%s)"
        % ",".join("?" * len(ACTIVE_STATUSES)),
        tuple(ACTIVE_STATUSES),
    )
    for row in cur.fetchall():
        d = row["domain"]
        cards_by_domain.setdefault(d, []).append({
            "status": row["status"],
            "title": row["title"],
            "summary": row["summary"],
        })
    conn.close()
    return cards_by_domain


def audit_domain(domain_name, domain_path, cards_domain, cards_by_domain):
    """审计单个域"""
    state_file = os.path.join(DOCUMENTS_BASE, domain_path, "_control/STATE.md")
    result = {
        "domain": domain_name,
        "state_file": state_file,
        "state_exists": False,
        "state_items": [],
        "cards": [],
        "orphan_state_items": [],  # STATE 有但 CARDS 无
        "orphan_cards": [],        # CARDS 有但 STATE 未提及
        "score": 0.0,
    }

    if not os.path.exists(state_file):
        return result

    result["state_exists"] = True
    with open(state_file, "r", encoding="utf-8") as f:
        text = f.read()

    result["state_items"] = extract_state_items(text)
    result["cards"] = cards_by_domain.get(cards_domain, [])

    # 简单匹配: STATE 事项标题是否出现在某个 CARDS 标题/摘要中
    card_texts = []
    for c in result["cards"]:
        combined = f"{c['title']} {c['summary']}".lower()
        card_texts.append(combined)

    for item in result["state_items"]:
        item_lower = item.lower()
        # 提取关键词(去掉停用词)
        keywords = [w for w in re.findall(r"[\u4e00-\u9fa5a-zA-Z0-9]+", item_lower) if len(w) >= 2]
        matched = False
        for card_text in card_texts:
            if any(kw in card_text for kw in keywords[:3]):  # 前3个关键词命中即可
                matched = True
                break
        if not matched:
            result["orphan_state_items"].append(item)

    # CARDS 中未在 STATE 中提及的卡片
    for c in result["cards"]:
        card_text = f"{c['title']} {c['summary']}".lower()
        matched = False
        for item in result["state_items"]:
            item_lower = item.lower()
            keywords = [w for w in re.findall(r"[\u4e00-\u9fa5a-zA-Z0-9]+", item_lower) if len(w) >= 2]
            if any(kw in card_text for kw in keywords[:3]):
                matched = True
                break
        if not matched:
            result["orphan_cards"].append(c)

    # 计算一致性分数
    total = len(result["state_items"]) + len(result["cards"])
    aligned = total - len(result["orphan_state_items"]) - len(result["orphan_cards"])
    if total > 0:
        result["score"] = round(aligned / total * 100, 1)
    else:
        result["score"] = 100.0

    return result


def print_summary(results: list):
    print("=" * 80)
    print("STATE-CARDS 一致性审计")
    print(f"生成时间: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 80)
    print()

    total_score = 0
    count = 0
    for r in results:
        if not r["state_exists"]:
            print(f"❌ {r['domain']}: STATE.md 不存在")
            continue
        status = "✅" if r["score"] >= 80 else "🟡" if r["score"] >= 50 else "🔴"
        print(f"{status} {r['domain']:<12} 一致性 {r['score']:>5.1f}% | STATE 事项 {len(r['state_items']):>2} | CARDS 活跃 {len(r['cards']):>2}")
        total_score += r["score"]
        count += 1
        if r["orphan_state_items"]:
            for item in r["orphan_state_items"][:3]:
                print(f"      ⚠️  STATE 未在 CARDS 中匹配: {item[:60]}")
        if r["orphan_cards"]:
            for c in r["orphan_cards"][:3]:
                print(f"      ⚠️  CARDS 未在 STATE 中提及: {c['title'][:60]}")

    print()
    if count > 0:
        avg = total_score / count
        print(f"平均一致性: {avg:.1f}%")
        print(f"域覆盖数: {count}/{len(DOMAIN_PATHS)}")


def print_report(results: list):
    print("# STATE-CARDS 一致性审计报告")
    print()
    print(f"> 生成时间: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"> CARDS DB: `{CARDS_DB}`")
    print()

    total_score = 0
    count = 0
    for r in results:
        if not r["state_exists"]:
            print(f"## {r['domain']}")
            print("- ❌ STATE.md 不存在")
            print()
            continue

        status = "🟢" if r["score"] >= 80 else "🟡" if r["score"] >= 50 else "🔴"
        print(f"## {status} {r['domain']}")
        print(f"- 一致性得分: **{r['score']}%**")
        print(f"- STATE.md 提取事项: {len(r['state_items'])}")
        print(f"- CARDS 活跃卡片: {len(r['cards'])}")

        if r["orphan_state_items"]:
            print("- STATE 中有但 CARDS 未匹配:")
            for item in r["orphan_state_items"][:5]:
                print(f"  - {item}")
        if r["orphan_cards"]:
            print("- CARDS 中有但 STATE 未提及:")
            for c in r["orphan_cards"][:5]:
                print(f"  - [{c['status']}] {c['title']}")
        print()
        total_score += r["score"]
        count += 1

    if count > 0:
        print(f"## 汇总")
        print(f"- 平均一致性: **{total_score / count:.1f}%**")
        print(f"- 审计域数: {count}/{len(DOMAIN_PATHS)}")


def main():
    cards_by_domain = load_cards()
    target_domain = None
    if "--domain" in sys.argv:
        idx = sys.argv.index("--domain")
        target_domain = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else None

    results = []
    for name, (path, cards_domain) in DOMAIN_PATHS.items():
        if target_domain and name != target_domain:
            continue
        r = audit_domain(name, path, cards_domain, cards_by_domain)
        results.append(r)

    if "--report" in sys.argv:
        print_report(results)
    else:
        print_summary(results)


if __name__ == "__main__":
    main()
