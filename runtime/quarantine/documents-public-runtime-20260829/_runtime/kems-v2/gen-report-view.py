#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""汇报一屏看生成器（模型驱动）— gen-report-view.py
从模型 SSOT 动态生成领导一屏看报告，四域通用（不再硬编码卫健委项目）：
- 项目态势：从 instances.yaml C3 活跃实例读取（name/note 中解析预算）
- 关键节点：key-milestones.yaml
- 风险：gaps.yaml open/in_progress
- 建议：节点 + 缺口派生
用法：
  python3 _runtime/gen-report-view.py                # 输出 _control/汇报一屏看-YYYYMMDD.md
  python3 _runtime/gen-report-view.py --stdout       # 直接打印
"""
import datetime, re, sys, yaml
from pathlib import Path

BASE = Path(__file__).parent.parent
TODAY = datetime.date.today()


def load_yaml(rel: str):
    with open(BASE / rel, encoding="utf-8") as f:
        return yaml.safe_load(f)


def days_left(date_str: str) -> int:
    try:
        d = datetime.date(2026, int(date_str[:2]), int(date_str[3:]))
        return (d - TODAY).days
    except Exception:
        return -1


def load_projects() -> list[dict]:
    """从 instances.yaml 读取 C3 活跃项目；note 中解析预算（如 300.06万）。"""
    try:
        inst = load_yaml("_entities/ontology/instances.yaml")["instances"]
    except Exception:
        return []
    projects = []
    for i in inst:
        if i.get("class") != "C3" or i.get("status") not in ("active", None):
            continue
        note = str(i.get("note", "") or "")
        m = re.search(r"(\d+(?:\.\d+)?)\s*万", note)
        projects.append({
            "name": i.get("name", i["id"]),
            "id": i.get("id", ""),
            "budget": m.group(1) if m else "待补",
            "note": note[:40],
        })
    return projects


def build_report() -> str:
    now = TODAY.strftime("%Y-%m-%d")
    L = [f"# 🎯 一屏看（{now}）", "",
         "> 生成：模型驱动（instances + key-milestones + gaps）· 跨域通用"]

    # 一、项目态势（读实例）
    projects = load_projects()
    L.append("\n## 一、项目态势（C3 活跃实例）\n")
    if projects:
        L.append("| 项目 | 预算(万) | 备注 |")
        L.append("|------|:---:|------|")
        total = 0.0
        for p in projects:
            b = p["budget"]
            if b != "待补":
                total += float(b)
            L.append(f"| {p['name']} | {b} | {p['note']} |")
        L.append(f"| **合计** | **{total:.2f}** | — |\n")
    else:
        L.append("（无 C3 活跃实例，待填充 instances.yaml）\n")

    # 二、关键节点
    L.append("## 二、关键节点（倒计时）\n")
    try:
        ms = load_yaml("_control/key-milestones.yaml")["milestones"]
    except Exception:
        ms = []
    if ms:
        L.append("| 节点 | 日期 | 剩余 | 紧急度 | 责任人 |")
        L.append("|------|:---:|:---:|:---:|:---:|")
        for m in ms:
            dl = days_left(m["date"])
            L.append(f"| {m['title']} | {m['date']} | {'已过' if dl<0 else f'{dl}天'} | {m['severity']} | {m.get('owner','')} |")
    else:
        L.append("（无里程碑，待填充 key-milestones.yaml）\n")

    # 三、风险
    L.append("\n## 三、风险与阻塞\n")
    try:
        gaps = load_yaml("_entities/ontology/gaps.yaml")["gaps"]
    except Exception:
        gaps = []
    open_gaps = [g for g in gaps if g["status"] == "open"]
    prog_gaps = [g for g in gaps if g["status"] == "in_progress"]
    if open_gaps or prog_gaps:
        L.append("| 风险 | 状态 | 责任 |")
        L.append("|------|:---:|:---:|")
        for g in open_gaps:
            L.append(f"| 🔴 {g['name']} | open | {g.get('owner','')} |")
        for g in prog_gaps:
            L.append(f"| 🟡 {g['name']} | 调查中 | {g.get('owner','')} |")
    else:
        L.append("（无未闭环缺口）\n")

    # 四、建议动作
    L.append("\n## 四、建议动作\n")
    acts = []
    for m in ms:
        if m["severity"] == "🔴" and days_left(m["date"]) >= 0:
            acts.append(f"- **{m['date']} {m['title']}**（剩 {days_left(m['date'])} 天）：{m.get('note','')}")
    for g in open_gaps:
        acts.append(f"- 推进 **{g['name']}**（{g.get('owner','')}）")
    L.append("\n".join(acts) if acts else "（无紧急动作）")
    return "\n".join(L)


def main() -> int:
    report = build_report()
    if "--stdout" in sys.argv:
        print(report)
        return 0
    out = BASE / "_control" / f"汇报一屏看-{TODAY.strftime('%Y%m%d')}.md"
    out.write_text(report, encoding="utf-8")
    print(f"[OK] 已生成: {out}")
    print(f"      项目 {len(load_projects())} 个 · 节点 {len(load_yaml('_control/key-milestones.yaml')['milestones'])} 个")
    return 0


if __name__ == "__main__":
    sys.exit(main())
