#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KEMS 一键快照 — kems-snapshot.py
单命令输出全系统状态，消除冷启动「状态分散 6+ 脚本」的障碍。
新会话/汇报前/巡检时跑一条命令即得全景。
用法：
  python3 _runtime/kems-snapshot.py            # 快速快照（直接读 SSOT）
  python3 _runtime/kems-snapshot.py --full     # 全量（+ 治理/健康慢检）
  python3 _runtime/kems-snapshot.py --json     # JSON 输出
"""
import datetime, json, re, subprocess, sys, yaml
from pathlib import Path

BASE = Path(__file__).parent.parent
TODAY = datetime.date.today()
NOW = datetime.datetime.now()
FULL = "--full" in sys.argv
ASJSON = "--json" in sys.argv


def y(path):
    with open(BASE / path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def days(dstr):
    try:
        d = datetime.date(2026, int(dstr[:2]), int(dstr[3:]))
        return (d - TODAY).days
    except Exception:
        return 0


def snapshot() -> dict:
    s = {"生成": NOW.strftime("%Y-%m-%d %H:%M"), "full": FULL}

    # 1. 关键节点
    ms = y("_control/key-milestones.yaml")["milestones"]
    s["节点"] = []
    for m in ms:
        dl = days(m["date"])
        s["节点"].append({"date": m["date"], "title": m["title"],
                          "severity": m["severity"], "剩余": "已过" if dl < 0 else f"{dl}天",
                          "owner": m.get("owner", "")})

    # 2. 风险缺口
    gaps = y("_entities/ontology/gaps.yaml")["gaps"]
    s["缺口"] = {"resolved": 0, "in_progress": 0, "open": 0}
    s["风险"] = []
    for g in gaps:
        s["缺口"][g["status"]] = s["缺口"].get(g["status"], 0) + 1
        if g["status"] in ("open", "in_progress"):
            s["风险"].append({"id": g["id"], "status": g["status"], "name": g["name"],
                              "owner": g.get("owner", "")})

    # 3. 三层统计
    inst = y("_entities/ontology/instances.yaml")["instances"]
    edges = y("_entities/ontology/associations.yaml")["edges"]
    cons = y("_entities/ontology/constraints.yaml")
    n_cons = sum(len(cons.get(k, [])) for k in ["existence", "attribute", "relation", "lifecycle", "integrity"])
    # 事实/文件计数复用 refresh-indexes 权威断言（保证与守卫一致）
    rf = subprocess.run([sys.executable, str(BASE / "_runtime/refresh-indexes.py"), "--facts-count"],
                        capture_output=True, text=True)
    mf = re.search(r"(\d+) 条", rf.stdout)
    n_fact = int(mf.group(1)) if mf else 0
    s["统计"] = {"模型": len(list((BASE / "_entities/models").glob("*.md"))) - 1,
                 "实例": len(inst), "边": len(edges),
                 "约束": n_cons, "事实": n_fact,
                 "图谱": f"{len({i['id'] for i in inst})} 节点/{len(edges)} 边"}

    # 4. SSOT 守卫（核心）
    r = subprocess.run([sys.executable, str(BASE / "_runtime/check-ssot-sync.py"), "--json"],
                       capture_output=True, text=True, timeout=180)
    try:
        s["守卫"] = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        s["守卫"] = {"ok": False, "detail": r.stdout[-200:]}

    # 5. 治理（--full 才跑慢检）
    if FULL:
        r2 = subprocess.run([sys.executable, str(BASE / "_runtime/check-doc-governance.py")],
                            capture_output=True, text=True, timeout=300)
        m = re.search(r"违规: (🔴\d+ / 🟡\d+)", r2.stdout)
        s["治理"] = m.group(1) if m else "未知"
    else:
        s["治理"] = "（--full 查看）"

    # 6. 建议动作（P0 节点 + open 缺口）
    acts = []
    for m in ms:
        if m["severity"] == "🔴" and days(m["date"]) >= 0:
            acts.append(f"{m['date']} {m['title']}（剩{days(m['date'])}天）")
    for g in gaps:
        if g["status"] == "open" and g["id"] in ("A1", "A3"):
            acts.append(f"催办 {g['name']}（{g.get('owner','')}）")
    s["建议"] = acts[:6]
    return s


def render(s) -> str:
    L = []
    L.append(f"# KEMS 一键快照（{s['生成']}）")
    L.append("")
    L.append(f"## ⏱ 关键节点")
    for m in s["节点"]:
        L.append(f"  {m['date']} {m['title']} [{m['severity']}] {m['剩余']} — {m['owner']}")
    L.append("")
    L.append(f"## 🔴 风险（{len(s['风险'])} 项未闭环）")
    for g in s["风险"]:
        L.append(f"  {g['status']=='open' and '🔴' or '🟡'} {g['id']} {g['name']}（{g['owner']}）")
    L.append("")
    L.append(f"## 📊 三层统计")
    st = s["统计"]
    L.append(f"  模型 {st['模型']} · 实例 {st['实例']} · 边 {st['边']} · 约束 {st['约束']} · 事实 {st['事实']}")
    L.append(f"  图谱：{st['图谱']} · 缺口 {s['缺口']['resolved']}resolved/{s['缺口']['in_progress']}in/{s['缺口']['open']}open")
    L.append("")
    L.append(f"## ✅ SSOT 守卫：{'全绿' if s['守卫'].get('ok') else '有漂移 ' + str(s['守卫'])}")
    L.append(f"## 🚨 治理：{s['治理']}")
    L.append("")
    L.append(f"## 🎯 建议动作")
    for a in s["建议"]:
        L.append(f"  • {a}")
    return "\n".join(L)


def main():
    s = snapshot()
    if ASJSON:
        print(json.dumps(s, ensure_ascii=False, indent=1))
    else:
        print(render(s))
    return 0 if s["守卫"].get("ok", False) else 1


if __name__ == "__main__":
    sys.exit(main())
