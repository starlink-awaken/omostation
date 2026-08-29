#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""图谱查询工具 — 知识图谱单实体查询
用途：输入实体 id（或别名），输出该类/属性/出入关联边/关联事实，验证知识图谱可查询性。
数据源：
  _entities/ontology/instances.yaml   （实体注册表）
  _entities/ontology/associations.yaml（关联边）
  _entities/ontology/aliases.yaml     （别名/视图）
  _entities/facts.md                  （事实基座）
用法：
  python3 _runtime/graph-query.py <实体id>
  python3 _runtime/graph-query.py proj-data-collect
  python3 _runtime/graph-query.py policy-sanyi-144   # 别名自动解析
"""
import os, re, sys, yaml
from pathlib import Path

BASE = Path(__file__).parent.parent
CLS_NAME = {"C1": "政策法规", "C2": "组织机构", "C3": "项目工程", "C4": "应用系统",
            "C5": "数据资源", "C6": "基础设施", "C7": "人员角色", "C8": "监管考核", "C9": "智能化应用"}
REL_NAME = {"R1": "bases_on 依据", "R2": "governs 归属", "R3": "implements 建设", "R4": "deploys 承载",
            "R5": "data_flows 数据流", "R6": "assesses 考核", "R7": "enables 赋能",
            "R8": "cooperates 协同", "R9": "supplies 供应"}


def load_yaml(rel):
    with open(BASE / rel, encoding="utf-8") as f:
        return yaml.safe_load(f)


def main():
    if len(sys.argv) < 2:
        print("用法: python3 _runtime/graph-query.py <实体id>")
        return 1
    qid = sys.argv[1].strip()

    inst = {i["id"]: i for i in load_yaml("_entities/ontology/instances.yaml")["instances"]}
    aliases = load_yaml("_entities/ontology/aliases.yaml")
    alias_map = {a["alias"]: a["canonical"] for a in aliases.get("aliases", [])}
    view_map = {v["id"]: v for v in aliases.get("views", [])}
    edges = load_yaml("_entities/ontology/associations.yaml")["edges"]

    # 别名解析
    canonical = qid
    if qid in alias_map:
        canonical = alias_map[qid]
        print(f"⚠️ 别名 {qid} → 实例 {canonical}")
    if qid in view_map:
        v = view_map[qid]
        print(f"ℹ️ {qid} 为视图实体：{v['view']}（{v['class']}），不设实例")
        return 0
    if canonical not in inst:
        print(f"❌ 未找到实体 {qid}")
        return 1
    e = inst[canonical]

    print("=" * 64)
    print(f"实体: {e['name']}")
    print(f"  id     : {canonical}")
    print(f"  类     : {e['class']} {CLS_NAME.get(e['class'], '')}")
    print(f"  状态   : {e.get('status')}")
    print(f"  来源   : {e.get('ref')}")
    if e.get("note"):
        print(f"  备注   : {e['note']}")

    # 出入边
    out_edges = [x for x in edges if x["source"] == canonical]
    in_edges = [x for x in edges if x["target"] == canonical]
    print(f"\n  出边 ({len(out_edges)}):")
    for x in out_edges:
        tgt = inst.get(x["target"], {}).get("name", x["target"])
        print(f"    {x['relation']} {REL_NAME.get(x['relation'], '')} → {x['target']} [{tgt}]  {x.get('note','')}")
    print(f"  入边 ({len(in_edges)}):")
    for x in in_edges:
        src = inst.get(x["source"], {}).get("name", x["source"])
        print(f"    {x['relation']} {REL_NAME.get(x['relation'], '')} ← {x['source']} [{src}]  {x.get('note','')}")
    print(f"  度数   : {len(out_edges) + len(in_edges)}")

    # 关联事实
    fact_hits = []
    for ln in open(BASE / "_entities" / "facts.md", encoding="utf-8"):
        if not ln.startswith("| "):
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cells) >= 9 and cells[1] and cells[1] != "事实陈述" and cells[8] != "关联实体" \
                and "YYYY-MM-DD" not in cells[7] and "[可验证" not in cells[1]:
            ents = [x.strip().strip("[]") for x in re.split(r"[+,;、/ ]+", cells[8])]
            if canonical in ents or qid in ents:
                fact_hits.append((cells[0], cells[7][:10]))
    print(f"\n  关联事实 ({len(fact_hits)} 条):")
    for txt, exp in fact_hits[:12]:
        print(f"    · {txt[:58]}（过期 {exp}）")
    if len(fact_hits) > 12:
        print(f"    … 共 {len(fact_hits)} 条")
    return 0


if __name__ == "__main__":
    sys.exit(main())
