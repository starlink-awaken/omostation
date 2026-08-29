#!/usr/bin/env python3
"""
check-ontology-consistency.py — 本体 YAML↔md 双格式一致性校验

SSOT 契约（见 _entities/ontology/README.md）：
  - classes.yaml  ↔ ONTOLOGY.md §一 类表（9 类 C1-C9）
  - relations.yaml ↔ ONTOLOGY.md §三 关系表（R1-R9）
  - gaps.yaml     ↔ 体系本体模型 §8 缺口表（16 项）
  - instances.yaml ↔ classes.yaml instance_count / ONTOLOGY.md §六 / 模型 §2.1 实例数
  - instances.yaml id 前缀必须匹配所属类、ref 指向的详表文件必须存在

用法：
  python3 _runtime/check-ontology-consistency.py [--strict]
  --strict 使实例数不匹配也 FAIL（默认 WARN，允许语义性计数差异）

退出码：0 = 全部 PASS；1 = 存在 FAIL
"""
import re
import sys
import yaml
from pathlib import Path

BASE = Path(__file__).parent.parent
STRICT = "--strict" in sys.argv

FAILS: list[str] = []
WARNS: list[str] = []


def fail(msg: str) -> None:
    FAILS.append(msg)


def warn(msg: str) -> None:
    WARNS.append(msg)


def load_yaml(rel: str) -> dict:
    p = BASE / rel
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f)


def read_md(rel: str) -> str:
    p = BASE / rel
    if not p.exists():
        return ""  # 域自适应：md 视图文件缺失时降级（仅 YAML 校验）
    return p.read_text(encoding="utf-8")


def get_section(text: str, header_pattern: str) -> list[str]:
    """返回匹配 header_pattern 的章节行（含表头），到下一个同级或更高级标题为止。"""
    lines = text.splitlines()
    start = None
    for idx, ln in enumerate(lines):
        if re.match(header_pattern, ln.strip()):
            start = idx
            break
    if start is None:
        return []
    out, cur_level = [], None
    for ln in lines[start:]:
        m = re.match(r"^(#{2,4})\s+", ln.strip())
        if m:
            level = len(m.group(1))
            if cur_level is None:
                cur_level = level
            elif level <= cur_level:
                break
        out.append(ln)
    return out


# ---------- 读取结构化源 ----------
classes = load_yaml("_entities/ontology/classes.yaml")["classes"]
relations = load_yaml("_entities/ontology/relations.yaml")["relations"]
gaps = load_yaml("_entities/ontology/gaps.yaml")["gaps"]
instances = load_yaml("_entities/ontology/instances.yaml")
inst_list = instances["instances"]

ontology_md = read_md("_entities/ONTOLOGY.md")
model_md = read_md("_entities/models/体系本体模型-数字化信息化智能化.md")
MD_OK = bool(ontology_md and model_md)
if not MD_OK:
    print("  [NOTE] 未检测到 ONTOLOGY.md / 体系本体模型.md（域精简模式），仅校验 YAML 内部一致性")

# ---------- 1. classes.yaml ↔ ONTOLOGY.md §一 ----------
if MD_OK:
    sec1 = get_section(ontology_md, r"^##\s+一、九类本体")
    md_classes = dict(re.findall(r"^\|\s*C(\d)\s*\|\s*([A-Za-z]+)\s*\|", "\n".join(sec1), re.M))
else:
    md_classes = {}
yaml_classes = {c["id"]: c["code"] for c in classes}
expect_c = {f"C{i}" for i in range(1, 10)}

if set(yaml_classes) != expect_c:
    fail(f"classes.yaml 类集合不完整：缺 {expect_c - set(yaml_classes)} / 多 {set(yaml_classes) - expect_c}")
if MD_OK:
    for cid, code in sorted(yaml_classes.items()):
        md_code = md_classes.get(cid.replace("C", ""))
        if md_code is None:
            fail(f"ONTOLOGY.md §一 缺失类行 {cid}")
        elif md_code != code:
            fail(f"类代码不一致：classes.yaml {cid}={code} vs ONTOLOGY.md={md_code}")
print(f"  [PASS/CHECK] 类定义：classes.yaml {len(yaml_classes)} 类 ↔ ONTOLOGY.md §一 {len(md_classes)} 行")

# ---------- 2. relations.yaml ↔ ONTOLOGY.md §三 ----------
if MD_OK:
    sec3 = get_section(ontology_md, r"^##\s+三、关系类型")
    md_rels = dict(re.findall(r"^\|\s*(R\d)\s+([a-z_]+)\s+", "\n".join(sec3), re.M))
else:
    md_rels = {}
yaml_rels = {r["id"]: r["code"] for r in relations}
expect_r = {f"R{i}" for i in range(1, 10)}
if set(yaml_rels) != expect_r:
    fail(f"relations.yaml 关系集合不完整：缺 {expect_r - set(yaml_rels)} / 多 {set(yaml_rels) - expect_r}")
if MD_OK:
    for rid, code in sorted(yaml_rels.items()):
        md_code = md_rels.get(rid)
        if md_code is None:
            fail(f"ONTOLOGY.md §三 缺失关系行 {rid}")
        elif md_code != code:
            fail(f"关系代码不一致：relations.yaml {rid}={code} vs ONTOLOGY.md={md_code}")
print(f"  [PASS/CHECK] 关系定义：relations.yaml {len(yaml_rels)} 关系 ↔ ONTOLOGY.md §三 {len(md_rels)} 行")

# ---------- 3. gaps.yaml ↔ 模型 §8 ----------
if MD_OK:
    sec8 = get_section(model_md, r"^##\s+8\.\s+信息缺口清单")
    md_gap_ids = [m for m in re.findall(r"^\|\s*([A-D]\d)\s*\|", "\n".join(sec8), re.M)]
else:
    md_gap_ids = []
yaml_gap_ids = [g["id"] for g in gaps]
yaml_gap_set, md_gap_set = set(yaml_gap_ids), set(md_gap_ids)
if len(yaml_gap_ids) != len(yaml_gap_set):
    fail(f"gaps.yaml 存在重复缺口 id：{[x for x, n in __import__('collections').Counter(yaml_gap_ids).items() if n > 1]}")
if MD_OK and yaml_gap_set != md_gap_set:
    fail(f"缺口集合不一致：gaps.yaml 独有 {yaml_gap_set - md_gap_set} / 模型 §8 独有 {md_gap_set - yaml_gap_set}")
print(f"  [PASS/CHECK] 信息缺口：gaps.yaml {len(yaml_gap_ids)} 项 ↔ 模型 §8 {len(md_gap_ids)} 行")

# ---------- 4. instances.yaml 内部一致性 ----------
PREFIX = {
    "C1": ["pol-", "doc-", "event-"], "C2": ["org-", "vendor-"], "C3": ["proj-", "task-", "project-"],
    "C4": ["sys-", "platform-"], "C5": ["dat-"], "C6": ["inf-"],
    "C7": ["person-"], "C8": ["asmt-"], "C9": ["int-"],
}
STATUS_OK = {"active", "watch", "pending", "archived"}
ids = [i["id"] for i in inst_list]
dup_ids = [x for x, n in __import__("collections").Counter(ids).items() if n > 1]
if dup_ids:
    fail(f"instances.yaml 重复 id：{dup_ids}")

from collections import Counter  # noqa: E402
count_by_class = Counter(i["class"] for i in inst_list)

for i in inst_list:
    c = i.get("class")
    if c not in PREFIX:
        fail(f"实例 {i.get('id')} 类不合法：{c}")
        continue
    if not any(i["id"].startswith(p) for p in PREFIX[c]):
        fail(f"实例 {i['id']} 的 id 前缀与类 {c} 不符（期望 {PREFIX[c]}）")
    if i.get("status") not in STATUS_OK:
        fail(f"实例 {i['id']} 状态非法：{i.get('status')}")
    ref = i.get("ref", "")
    ref_path = ref.split("#", 1)[0]  # 去掉锚点片段（如 #doc-meeting-144）
    if ref_path.startswith("entities/"):
        if not (BASE / "_entities" / ref_path).exists():
            fail(f"实例 {i['id']} ref 指向文件不存在：_entities/{ref_path}")
    elif ref_path.startswith("模型-") or ref_path.startswith("合同台账"):
        fname = f"_entities/models/{ref_path}"
        if not (BASE / fname).exists():
            fail(f"实例 {i['id']} ref 指向文件不存在：{fname}")

if instances.get("total_instances") != len(inst_list):
    fail(f"instances.yaml total_instances={instances['total_instances']} 与实际 {len(inst_list)} 不符")
print(f"  [PASS/CHECK] 实体注册表：{len(inst_list)} 条 id 唯一、前缀合法、ref 可解析")

# ---------- 5. 各类实例数三源对齐（classes.yaml / ONTOLOGY.md §六 / 模型 §2.1） ----------
yaml_count = {c["id"]: c["instance_count"] for c in classes}

sec6 = get_section(ontology_md, r"^##\s+六、覆盖校验")
md_ont_count = {
    f"C{m.group(1)}": int(m.group(2))
    for m in re.finditer(r"^\|\s*C(\d)\s+[A-Za-z]+\s*\|\s*(\d+)\s*\|", "\n".join(sec6), re.M)
}

sec21 = get_section(model_md, r"^###\s+2\.1\s+实体类总览")
md_model_count = {
    f"C{m.group(1)}": int(m.group(2))
    for m in re.finditer(r"^\|\s*C(\d)\s*\|\s*[^|]+?\s*\|\s*[^|]+?\s*\|\s*(\d+)\s*\|", "\n".join(sec21), re.M)
}

for cid in sorted(expect_c, key=lambda x: int(x[1:])):
    actual = count_by_class.get(cid, 0)
    sources = [("classes.yaml", yaml_count)] if not MD_OK else \
              [("classes.yaml", yaml_count), ("ONTOLOGY.md §六", md_ont_count), ("模型 §2.1", md_model_count)]
    for label, src in sources:
        declared = src.get(cid)
        if declared is None:
            warn(f"{cid} 在 {label} 未声明实例数")
            continue
        if declared != actual:
            msg = f"{cid} 实例数不一致：{label}={declared} vs instances.yaml={actual}"
            if STRICT:
                fail(msg)
            else:
                warn(msg)

print(f"  [PASS/CHECK] 实例数对齐：实例总数 {len(inst_list)}，9 类计数源已比对")

# ---------- 6. 关联注册表校验（associations.yaml ↔ instances/relations） ----------
try:
    assoc = load_yaml("_entities/ontology/associations.yaml")
    edges = assoc.get("edges", [])
    rel_by_id = {r["id"]: r for r in relations}
    inst_by_id = {i["id"]: i for i in inst_list}

    n_assoc_checked = 0
    for e in edges:
        rid, src, tgt = e.get("relation"), e.get("source"), e.get("target")
        if rid not in rel_by_id:
            fail(f"关联边 {e.get('id')} 关系 {rid} 不在 relations.yaml")
            continue
        for end, label in [(src, "source"), (tgt, "target")]:
            if end not in inst_by_id:
                fail(f"关联边 {e.get('id')} {label}={end} 不在 instances.yaml")
        if src in inst_by_id and tgt in inst_by_id:
            rmeta = rel_by_id[rid]
            scls, tcls = inst_by_id[src]["class"], inst_by_id[tgt]["class"]
            if scls not in rmeta.get("source_classes", []) or tcls not in rmeta.get("target_classes", []):
                warn(f"关联边 {e.get('id')} 类不匹配：{rid} 期望 {rmeta['source_classes']}→{rmeta['target_classes']}，实际 {scls}→{tcls}")
        n_assoc_checked += 1

    declared_edges = assoc.get("total_edges")
    if declared_edges != len(edges):
        warn(f"associations.yaml total_edges={declared_edges} 与实际 {len(edges)} 不符")
    print(f"  [PASS/CHECK] 关联注册表：{len(edges)} 条边（端点存在性/关系合法性/类匹配已检）")

    # 约束注册表校验（constraints.yaml schema）
    cons = load_yaml("_entities/ontology/constraints.yaml")
    for rl in cons.get("relation", []):
        rid = rl.get("relation", "").split()[0]
        if rid not in rel_by_id:
            fail(f"constraints.yaml 关系约束引用未定义关系：{rl.get('relation')}")
        for c in rl.get("source", []) + rl.get("target", []):
            if c not in expect_c:
                fail(f"constraints.yaml {rl.get('relation')} 引用未知类 {c}")
    print(f"  [PASS/CHECK] 约束注册表：{sum(len(cons.get(k, [])) for k in ['existence','attribute','relation','lifecycle','integrity'])} 条约束 schema 合法")
except FileNotFoundError:
    warn("ontology/constraints.yaml 或 associations.yaml 缺失，跳过约束/关联校验")

# ---------- 7. 事实-实例关联完整性（IN-3，事实层↔实例层断链扫描 + 别名解析） ----------
try:
    # 加载别名/视图表（aliases.yaml）
    alias_map, view_ids = {}, set()
    try:
        al = load_yaml("_entities/ontology/aliases.yaml")
        alias_map = {a["alias"]: a["canonical"] for a in al.get("aliases", [])}
        view_ids = {v["id"] for v in al.get("views", [])}
    except FileNotFoundError:
        pass

    fact_ents = set()
    for ln in open(BASE / "_entities" / "facts.md", encoding="utf-8"):
        if not ln.startswith("| "):
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cells) >= 9 and cells[1] and cells[1] != "事实陈述" and cells[8] != "关联实体" and "YYYY-MM-DD" not in cells[7] and "[可验证" not in cells[1]:
            for e in re.split(r"[+,;、/ ]+", cells[8]):
                e = e.strip().strip("[]")
                if e and e != "-":
                    fact_ents.add(e)

    # 解析层级：实例注册 / 别名→实例 / 视图实体 / entities 详表
    entity_files = set()
    for ef in (BASE / "_entities" / "entities").glob("*.md"):
        txt = ef.read_text(encoding="utf-8")
        entity_files.update(re.findall(r"(?:^|\|)([\w-]+)\s*\|", txt))

    resolved = 0
    alias_used = 0
    view_used = 0
    table_used = 0
    truly_missing = []
    for e in sorted(fact_ents):
        if e in inst_by_id:
            resolved += 1
        elif e in alias_map:
            alias_used += 1  # 经别名归一到实例
        elif e in view_ids:
            view_used += 1   # 视图实体（知识域/预算/事件等，合法引用）
        elif e in entity_files:
            table_used += 1
        else:
            truly_missing.append(e)

    if truly_missing:
        warn(f"facts 引用 {len(truly_missing)} 个未解析实体 id（不在实例/别名/视图/详表）：{truly_missing[:12]}")
    linked_total = resolved + alias_used + view_used + table_used
    rate = linked_total * 100 // len(fact_ents) if fact_ents else 0
    print(f"  [PASS/CHECK] 事实-实例关联：facts 引用 {len(fact_ents)} 个实体，解析 {linked_total}（{rate}%）："
          f"实例 {resolved} / 别名 {alias_used} / 视图 {view_used} / 详表 {table_used}，未解析 {len(truly_missing)}")
except Exception as ex:
    warn(f"事实-实例关联扫描异常：{ex}")

# ---------- 汇总 ----------
print()
if FAILS:
    print("❌ 一致性校验失败（FAIL）：")
    for m in FAILS:
        print(f"   - {m}")
    if WARNS:
        print("⚠️  告警（WARN，需人工确认）：")
        for m in WARNS:
            print(f"   - {m}")
    sys.exit(1)
elif WARNS:
    print("⚠️  一致性校验通过，但有告警（WARN，需人工确认）：")
    for m in WARNS:
        print(f"   - {m}")
    print("\n✅ 结构化数据（YAML）与视图（md）无硬性冲突。")
    sys.exit(0)
else:
    print("✅ 一致性校验全部通过：YAML 与 md 双格式完全一致。")
    sys.exit(0)
