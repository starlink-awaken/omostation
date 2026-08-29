#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""模型问答接口 — model-ask.py
用自然语言问 KEMS 模型：项目/资金/风险/节点/实体/考核，从模型 SSOT 作答。
让 28 个模型真实可用：日常「问一句」即得答案。
用法：
  python3 _runtime/model-ask.py "归集平台到哪一步了"
  python3 _runtime/model-ask.py "哪些项目在用医改资金"
  python3 _runtime/model-ask.py "8月有什么关键节点"
  python3 _runtime/model-ask.py "还有什么风险"
"""
import datetime, re, sys, yaml
from pathlib import Path

BASE = Path(__file__).parent.parent


def load():
    ontology = BASE / "_entities" / "ontology"
    inst = {i["id"]: i for i in yaml.safe_load(open(ontology / "instances.yaml", encoding="utf-8"))["instances"]}
    aliases = yaml.safe_load(open(ontology / "aliases.yaml", encoding="utf-8"))
    alias_map = {a["alias"]: a["canonical"] for a in aliases.get("aliases", [])}
    edges = yaml.safe_load(open(ontology / "associations.yaml", encoding="utf-8"))["edges"]
    gaps = yaml.safe_load(open(ontology / "gaps.yaml", encoding="utf-8"))["gaps"]
    ms = yaml.safe_load(open(BASE / "_control" / "key-milestones.yaml", encoding="utf-8"))["milestones"]
    return inst, alias_map, edges, gaps, ms


def ask(q: str) -> str:
    inst, alias_map, edges, gaps, ms = load()
    q0 = q.strip()
    out = []

    # 1. 关键节点
    if any(k in q0 for k in ["节点", "时间", "8月", "关键路径", "deadline", "截止", "还剩", "倒计时"]):
        today = datetime.date(2026, 8, 5)
        out.append("📅 8 月关键节点：")
        for m in ms:
            d = datetime.date(2026, int(m["date"][:2]), int(m["date"][3:]))
            dl = (d - today).days
            rem = "已过" if dl < 0 else f"剩 {dl} 天"
            out.append(f"  {m['date']} {m['title']} [{m['severity']}] {rem} — {m.get('note','')}")

    # 2. 风险/缺口/阻塞
    if any(k in q0 for k in ["风险", "缺口", "阻塞", "问题", "卡点", "待办", "催"]):
        out.append("⚠️ 未闭环缺口：")
        for g in gaps:
            if g["status"] == "open":
                out.append(f"  🔴 {g['name']}（{g.get('owner','')}，{g.get('blocked_by','推进中')}）")
        for g in gaps:
            if g["status"] == "in_progress":
                out.append(f"  🟡 {g['name']}（调查中）")

    # 2.5 谁负责/负责人（通用意图，跨域可用）
    if any(k in q0 for k in ["谁负责", "负责人", "谁管", "谁分管", "who"]):
        # 找查询词命中的组织
        hits = [i for iid, i in inst.items() if i.get("class") == "C2" and any(k in i.get("name", "") for k in
                [q0.replace("谁负责", "").replace("谁管", "").replace("负责人", "").strip()] if k)]
        if not hits:
            # 兜底：列出有 in-edge 的组织及其负责人
            persons = [i for i in inst.values() if i.get("class") == "C7"]
            for org in [i for i in inst.values() if i.get("class") == "C2"]:
                gov = [p.get("name", "") for p in persons
                       if any(e["relation"] == "R2" and e["target"] == org["id"] and e["source"] == p["id"] for e in edges)]
                if gov:
                    out.append(f"🏛 {org.get('name')}：{('、'.join(gov[:3]))}")
        else:
            for org in hits[:3]:
                gov = [p.get("name", "") for p in inst.values() if p.get("class") == "C7"
                       and any(e["relation"] == "R2" and e["target"] == org["id"] and e["source"] == p["id"] for e in edges)]
                out.append(f"🏛 {org.get('name')}：{'、'.join(gov[:4]) if gov else '（未登记）'}")

    # 3. 资金/预算（从实例读取，跨域通用）
    if any(k in q0 for k in ["资金", "预算", "钱", "多少钱", "投资", "万", "经费"]):
        projs = [i for i in inst.values() if i.get("class") == "C3" and i.get("status") == "active"]
        budgeted = [i for i in projs if i.get("note") and "万" in str(i.get("note"))]
        if budgeted:
            out.append("💰 项目资金（从模型实例读取）：")
            for i in budgeted[:5]:
                out.append(f"  · {i.get('name')}：{i.get('note')}")
        elif projs:
            out.append(f"💰 在管项目 {len(projs)} 个（预算信息待补录至实例 note 字段）")
            for i in projs[:5]:
                out.append(f"  · {i.get('name')}")
        else:
            out.append("💰 暂无预算信息（实例层未录入）")

    # 4. 实体查询（全动态：查询词去语气词 + 2字片断匹配实例名，零域硬编码）
    PARTICLES = "的了吗呢到哪步是等怎么样如何怎么"
    q_terms = [t for t in re.split(rf"[{PARTICLES}、,，/（）()\s：:+\-]+", q0) if len(t) >= 2]
    q_shingles = set()
    for t in q_terms:
        for i in range(len(t) - 1):
            q_shingles.add(t[i:i + 2])

    ents = {}
    for iid, e in inst.items():
        name = e.get("name", "")
        if not name:
            continue
        sc = 0
        if q0 in name:
            sc += 10
        for t in q_terms:
            if t in name:
                sc += 4 if len(t) >= 4 else 2
        for sh in q_shingles:
            if sh in name:
                sc += 1
        if sc > 0:
            ents[iid] = (sc, e)
    for alias, canon in alias_map.items():
        if alias in q0 and canon in inst:
            ents[canon] = (20, inst[canon])
    if ents:
        for iid, (sc, e) in sorted(ents.items(), key=lambda x: -x[1][0])[:5]:
            cls = e.get("class", "")
            out.append(f"🔍 {e.get('name')} [{cls}] 状态={e.get('status')}（相关度{sc}）")
            if e.get("note"):
                out.append(f"    {e.get('note')}")
            de = sum(1 for x in edges if x["source"] == iid) + sum(1 for x in edges if x["target"] == iid)
            out.append(f"    图谱度数 {de}，来源 {e.get('ref')}")

    # 5. 兜底：项目阶段（动态读 C3 活跃实例）
    if "项目" in q0 or "到哪" in q0 or "阶段" in q0 or "进度" in q0:
        active_projs = [i for i in inst.values() if i.get("class") == "C3" and i.get("status") in ("active", None)]
        if active_projs:
            out.append(f"📌 在管项目（{len(active_projs)} 个）：")
            for i in active_projs[:5]:
                out.append(f"  · {i.get('name')}（{i.get('note', '状态待补')[:25]}）")
        else:
            out.append("📌 暂无在管项目实例（待填充 instances.yaml）")

    if not out:
        return f"未命中已知意图。试试：「归集平台到哪步」「8月节点」「资金」「风险」「电子病历」。\n原始查询: {q0}"
    return "\n".join(out)


def main():
    if len(sys.argv) < 2:
        print("用法: python3 _runtime/model-ask.py \"问题\"")
        return 1
    print(ask(" ".join(sys.argv[1:])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
