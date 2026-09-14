"""Analytics reasoning rules."""

import re
from typing import Any

from .common import (
    closest_known,
    comparable,
    extract_prefix,
    guess_parent,
)


def change_detection(engine: Any, facts: Any) -> Any:
    """检测事实中的时间戳字段, 如果存在则分析变化趋势"""
    results = []
    dated = []
    for fid, info in facts.items():
        text = f"{info.get('desc', '')} {info.get('value', '')}"
        # 检测年份/季度
        years = re.findall(r"(20\d{2})", text)
        if years:
            dated.append((fid, info, years))
    if len(dated) >= 2:
        dated.sort(key=lambda x: x[2][0])
        results.append(
            {
                "type": "temporal_sequence",
                "conclusion": f"检测到{len(dated)}个带时间戳的事实, 时间跨度{dated[0][2][0]}-{dated[-1][2][0]}",
                "derived_from": [d[0] for d in dated],
                "confidence": 0.85,
                "method": "rule_engine",
            }
        )
    return results


# ═══ R16: 一致性分析 (Consistency Analysis) ═══


def consistency_analysis(engine: Any, inferences: Any, facts: Any) -> Any:
    """检测体系内部的一致性: 置信度/KQI/覆盖率是否自洽"""
    results = []
    n_inf = len(inferences)
    n_facts = len(facts)

    # 计算平均置信度
    confs = []
    for info in inferences.values():
        m = re.search(r"confidence:\s*(\w+)", info.get("text", ""))
        if m:
            conf_map = {"high": 0.92, "inference": 0.85, "medium": 0.70}
            confs.append(conf_map.get(m.group(1), 0.85))
    if confs:
        sum(confs) / len(confs)
        high_conf_count = sum(1 for c in confs if c >= 0.85)
        # 如果所有推论都标high但推导链深度只有1 → 不一致
        if high_conf_count == len(confs) and n_inf >= 3:
            results.append(
                {
                    "type": "consistency_warning",
                    "conclusion": f"所有{len(confs)}个推论置信度过高(均≥0.85)但推导链深度不足, 可能存在过度自信",
                    "derived_from": [],
                    "confidence": 0.70,
                    "method": "rule_engine",
                }
            )

    # 事实数:推偶数比例
    if n_facts > 0 and n_inf > 0:
        ratio = n_inf / n_facts
        if ratio > 3:
            results.append(
                {
                    "type": "consistency_warning",
                    "conclusion": f"推偶数/事实数={ratio:.1f}, 可能过度推导(建议<3)",
                    "derived_from": [],
                    "confidence": 0.60,
                    "method": "rule_engine",
                }
            )
    return results


# ═══ R17: 结构洞检测 (Structural Holes) ═══


def structural_holes(engine: Any, inferences: Any) -> Any:
    """检测网络中的结构洞: 移除某个节点后图会断裂成几个连通分量"""
    results: list[Any] = []
    if not inferences:
        return results
    # 构建引用图
    graph: dict[Any, Any] = {}
    for title, info in inferences.items():
        deps = [d for d in info.get("derives_from", []) if d in inferences or d.startswith(("D-F", "P-F"))]
        for dep in deps:
            graph.setdefault(title, set()).add(dep)
            graph.setdefault(dep, set()).add(title)

    # 计算每个节点的betweenness简化版
    for node in inferences:
        neighbors = len(graph.get(node, set()))
        if neighbors >= 3:
            results.append(
                {
                    "type": "structural_hole",
                    "conclusion": f"节点'{node[:30]}'连接{neighbors}个其他节点, 是潜在结构洞/瓶颈",
                    "derived_from": list(graph.get(node, set()))[:5],
                    "confidence": 0.65,
                    "method": "rule_engine",
                }
            )
    return results


# ═══ R19: 关系推理 (Relation Reasoning) ═══

# 逆关系映射
_INVERSE_RELATIONS = {
    "employs": "employed_by",
    "part_of": "contains",
    "contains": "part_of",
    "cooperates_with": "cooperates_with",
    "competes_with": "competes_with",
    "depends_on": "depended_on_by",
    "authored_by": "authors",
    "precedes": "follows",
    "belongs_to": "contains",
    "influences": "influenced_by",
}


def relation_reasoning(engine: Any, relations: Any) -> Any:
    """关系推理 — 传递性+逆关系+域约束检测"""
    results: list[Any] = []
    if not relations:
        return results

    # 构建关系图
    rel_graph: dict[Any, Any] = {}  # {subject: [(relation_type, object), ...]}
    for rel in relations:
        s, r, o = rel.get("subject", ""), rel.get("relation_type", ""), rel.get("object", "")
        if s and o:
            rel_graph.setdefault(s, []).append((r, o))

    # 1. 传递性推理: s→r→o, o→r→p → s→r→p (仅对传递关系)
    transitive_rels = {"part_of", "contains", "depends_on", "precedes", "belongs_to"}
    seen_pairs = set()  # 防循环: 记录已生成的(s, p)对
    for s, edges in rel_graph.items():
        for r, o in edges:
            if r in transitive_rels and o in rel_graph:
                for r2, p in rel_graph[o]:
                    if r2 == r and s != p and (s, p) not in seen_pairs:
                        seen_pairs.add((s, p))
                        results.append(
                            {
                                "type": "relation_transitive",
                                "conclusion": f"关系传递: {s}→{r}→{o}→{r2}→{p} ∴ {s} {r} {p}",
                                "derived_from": [s, o, p],
                                "confidence": 0.80,
                                "method": "rule_engine",
                            }
                        )

    # 2. 逆关系检测
    for rel in relations:
        r_type = rel.get("relation_type", "")
        inverse = _INVERSE_RELATIONS.get(r_type)
        if inverse:
            results.append(
                {
                    "type": "relation_inverse",
                    "conclusion": f"逆关系: {rel.get('subject')}→{r_type}→{rel.get('object')} ⇒ "
                    f"{rel.get('object')}→{inverse}→{rel.get('subject')}",
                    "derived_from": [rel.get("subject", ""), rel.get("object", "")],
                    "confidence": 0.90,
                    "method": "rule_engine",
                }
            )

    # 3. 域约束检测: employs的domain应为ORG, range应为ROL
    domain_rules = {
        "employs": ({"ORG"}, {"ROL"}),
        "authored_by": ({"DOC", "INF"}, {"ORG", "ROL"}),
    }
    for rel in relations:
        r_type = rel.get("relation_type", "")
        if r_type in domain_rules:
            exp_dom, exp_rng = domain_rules[r_type]
            subj_prefix = rel.get("subject", "").split("-")[0] if "-" in rel.get("subject", "") else ""
            obj_prefix = rel.get("object", "").split("-")[0] if "-" in rel.get("object", "") else ""
            if subj_prefix and subj_prefix not in exp_dom:
                results.append(
                    {
                        "type": "relation_domain",
                        "conclusion": (
                            f"域约束: {r_type}的domain应为{exp_dom}, "
                            f"但subject'{rel.get('subject')}'前缀为'{subj_prefix}'"
                        ),
                        "derived_from": [rel.get("subject", "")],
                        "confidence": 0.70,
                        "method": "rule_engine",
                    }
                )
            if obj_prefix and obj_prefix not in exp_rng:
                results.append(
                    {
                        "type": "relation_range",
                        "conclusion": (
                            f"域约束: {r_type}的range应为{exp_rng}, 但object'{rel.get('object')}'前缀为'{obj_prefix}'"
                        ),
                        "derived_from": [rel.get("object", "")],
                        "confidence": 0.70,
                        "method": "rule_engine",
                    }
                )

    return results


# ═══ R18: 约束传播 (Constraint Propagation) ═══


def constraint_propagation(engine: Any, inferences: Any, facts: Any) -> Any:
    """基于规约阈值传播约束: 断言追溯率<阈值→触发改善建议"""
    results = []
    # 统计断言数
    total_assertions = 0
    for info in inferences.values():
        text = info.get("text", "")
        assertions = re.findall(r"[^。\n]*?(?:应该|必须|需要)[^。]*?[。]", text)
        total_assertions += len([a for a in assertions if len(a) >= 15])

    if total_assertions > 0:
        # 检查是否有引用
        traced = 0
        for info in inferences.values():
            text = info.get("text", "")
            for a in re.findall(r"[^。\n]*?(?:应该|必须|需要)[^。]*?[。]", text):
                if re.search(r"D-F\d+|P-F\d+", a):
                    traced += 1
        rate = traced / total_assertions if total_assertions > 0 else 1
        if rate < 0.5:
            results.append(
                {
                    "type": "constraint_violation",
                    "conclusion": (
                        f"断言追溯率{rate:.0%}低于50%阈值(C-05), 建议为{total_assertions - traced}个断言标注事实引用"
                    ),
                    "derived_from": [],
                    "confidence": 0.90,
                    "method": "rule_engine",
                }
            )
    return results


# ═══ R7: 假言推理 (Modus Ponens/Tollens) ═══


def modus_ponens_check(engine: Any, inferences: Any, facts: Any) -> Any:
    """如果A成立且A→B, 则B成立。检测蕴含链的假设满足度"""
    results = []
    for title, info in inferences.items():
        premises = info.get("derives_from", [])
        satisfied = [p for p in premises if p in facts or p in inferences]
        if len(satisfied) < len(premises):
            missing = [p for p in premises if p not in satisfied]
            results.append(
                {
                    "type": "modus_ponens_fail",
                    "conclusion": f"推论'{title[:30]}'的前提{missing}不成立, 推论有效性存疑",
                    "derived_from": premises,
                    "confidence": 0.85,
                    "method": "rule_engine",
                }
            )
        elif len(satisfied) >= len(premises) >= 2:
            results.append(
                {
                    "type": "modus_ponens_valid",
                    "conclusion": f"推论'{title[:30]}'的{len(premises)}个前提全部成立, 推论有效",
                    "derived_from": premises,
                    "confidence": 0.90,
                    "method": "rule_engine",
                }
            )
    return results


# ═══ R8: 传递推理 (Transitive Closure) ═══


def transitive_closure(engine: Any, inferences: Any, facts: Any) -> Any:
    """A→B→C, 则A间接影响C。计算传递闭包"""
    results = []
    for title, info in inferences.items():
        indirect_deps = set()
        direct = set(info.get("derives_from", []))
        queue = list(direct)
        while queue:
            dep = queue.pop(0)
            if dep in inferences:
                for grandparent in inferences[dep].get("derives_from", []):
                    if grandparent not in direct and grandparent not in indirect_deps:
                        indirect_deps.add(grandparent)
                        queue.append(grandparent)
        if indirect_deps:
            results.append(
                {
                    "type": "transitive_dependency",
                    "conclusion": (f"推论'{title[:30]}'间接依赖{len(indirect_deps)}个前提: {list(indirect_deps)[:5]}"),
                    "derived_from": list(indirect_deps),
                    "confidence": 0.75,
                    "method": "rule_engine",
                }
            )
    return results


# ═══ R9: 包含推理 (Ontology Subsumption) ═══

ONTOLOGY_HIERARCHY = {
    "DOMAIN": ["ORG", "ROL", "PRJ", "RES"],
    "FACT": ["DAT", "POL"],
    "INFERENCE": ["CONTRADICTION", "BUSINESS", "ARCHITECTURE"],
    "STATE": ["T", "F", "H"],
    "DOCUMENT": ["COL", "DOC", "CH", "SEC", "STD"],
}

# ID前缀模式 → 元类型 (用于正确的ID归类)
_ID_PREFIX_MAP = {
    "ORG-": "DOMAIN",
    "ROL-": "DOMAIN",
    "PRJ-": "DOMAIN",
    "RES-": "DOMAIN",
    "D-F": "FACT",
    "P-F": "FACT",
    "INF-": "INFERENCE",
    "INF-V2-": "INFERENCE",
    "DOC-": "DOCUMENT",
    "CH-": "DOCUMENT",
    "SEC-": "DOCUMENT",
    "DCH-": "DOCUMENT",
    "STD-": "DOCUMENT",
    "CON-": "CONSTRAINT",
    "IP": "CONSTRAINT",
    "T": "STATE",
    "F": "STATE",
    "H": "STATE",
}

_PREFIX_TO_PARENT = {}
for _parent, _subs in ONTOLOGY_HIERARCHY.items():
    for _sub in _subs:
        _PREFIX_TO_PARENT[_sub] = _parent


def subsumption_check(engine: Any, inferences: Any, facts: Any) -> Any:
    """增强包含推理 — 分类建议+新类型检测+误分类检测"""
    results: list[Any] = []
    all_ids = list(inferences.keys()) + list(facts.keys())
    type_map = {}
    for id_str in all_ids:
        prefix = extract_prefix(engine, id_str)
        type_map[id_str] = prefix

    # 统计: 正确的标准 = 前缀在_ID_PREFIX_MAP中
    known_prefixes = set(_ID_PREFIX_MAP.keys())
    unknown_prefixes: dict[Any, Any] = {}
    correct = 0

    for id_str, prefix in type_map.items():
        if prefix in known_prefixes:
            correct += 1
        else:
            unknown_prefixes[prefix] = unknown_prefixes.get(prefix, 0) + 1

    n_total = len(type_map)
    if n_total == 0:
        return results

    # 输出1: 归类统计
    results.append(
        {
            "type": "subsumption",
            "conclusion": f"本体归类: {correct}/{n_total}个ID正确({correct * 100 // n_total}%)",
            "derived_from": [],
            "confidence": 0.85,
            "method": "rule_engine",
        }
    )

    # 输出2: 未知前缀 → 新类型建议
    for prefix, count in sorted(unknown_prefixes.items(), key=lambda x: -x[1]):
        if count >= 2:  # 至少出现2次才建议
            # 猜测最可能的父类型
            guess = guess_parent(engine, prefix, type_map)
            results.append(
                {
                    "type": "subsumption",
                    "conclusion": f"新类型建议: '{prefix}'出现{count}次, 建议归入{guess}类型",
                    "derived_from": [k for k, v in type_map.items() if v == prefix],
                    "confidence": 0.55,
                    "method": "rule_engine",
                }
            )
        elif count == 1:
            # 孤立未知前缀 → 可能是拼写错误
            example_id = next(k for k, v in type_map.items() if v == prefix)
            closest = closest_known(engine, prefix)
            results.append(
                {
                    "type": "subsumption",
                    "conclusion": f"孤立前缀: '{prefix}'(仅{example_id})可能是'{closest}'的拼写错误",
                    "derived_from": [example_id],
                    "confidence": 0.40,
                    "method": "rule_engine",
                }
            )

    return results


def influence_analysis(engine: Any, inferences: Any, facts: Any) -> Any:
    """计算每个事实/推论的'影响力' = 被多少推论直接/间接引用"""
    results = []
    influence: dict[Any, Any] = {}
    for title, info in inferences.items():
        for dep in info.get("derives_from", []):
            influence[dep] = influence.get(dep, 0) + 1
    if influence:
        top = sorted(influence.items(), key=lambda x: -x[1])[:3]
        top_str = "; ".join(f"{k}(被{count}个推论引用)" for k, count in top)
        results.append(
            {
                "type": "influence_analysis",
                "conclusion": f"最具影响力的前提: {top_str}",
                "derived_from": [k for k, _ in top],
                "confidence": 0.80,
                "method": "rule_engine",
            }
        )
    return results


# ═══ R11: 冗余检测 (Redundancy Check) ═══


def redundancy_check(engine: Any, inferences: Any) -> Any:
    """检测推论间的冗余 — 共享3+前提且文本相似"""
    results = []
    inf_list = list(inferences.items())
    for i in range(len(inf_list)):
        for j in range(i + 1, len(inf_list)):
            a_id, a_info = inf_list[i]
            b_id, b_info = inf_list[j]
            shared = set(a_info.get("derives_from", [])) & set(b_info.get("derives_from", []))
            if len(shared) >= 3:
                results.append(
                    {
                        "type": "redundancy_warning",
                        "conclusion": f"'{a_id[:25]}'和'{b_id[:25]}'共享{len(shared)}个前提, 可能冗余",
                        "derived_from": list(shared),
                        "confidence": 0.65,
                        "method": "rule_engine",
                    }
                )
    return results


# ═══ R12: 覆盖度分析 (Coverage Analysis) ═══


def coverage_analysis(engine: Any, inferences: Any, facts: Any) -> Any:
    """分析事实被推论引用的覆盖率"""
    results: list[Any] = []
    if not facts:
        return results
    cited = set()
    for info in inferences.values():
        cited.update(info.get("derives_from", []))
    fact_ids = set(facts.keys())
    cited_facts = fact_ids & cited
    uncited = fact_ids - cited
    rate = len(cited_facts) / len(fact_ids) * 100 if fact_ids else 100
    results.append(
        {
            "type": "coverage",
            "conclusion": f"事实覆盖率{rate:.0f}%({len(cited_facts)}/{len(fact_ids)}), 未引用: {list(uncited)[:5]}",
            "derived_from": list(uncited),
            "confidence": 0.95,
            "method": "rule_engine",
        }
    )
    return results


def numeric_derive(engine: Any, facts: Any) -> Any:
    """R1: 数值比较推导 — 三段论最直接的体现"""
    results = []
    numeric = {}
    for fid, info in facts.items():
        m = re.search(r"(\d+\.?\d*)", str(info.get("value", "")))
        if m:
            numeric[fid] = {"label": info.get("desc", fid)[:30], "value": float(m.group(1))}

    # 两两比较 (仅比较单位相似的事实)
    ids = list(numeric.keys())
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = numeric[ids[i]], numeric[ids[j]]
            # 跳过跨维度比较 (人数vs金额vs百分比)
            if not comparable(engine, a["label"], b["label"], a["value"], b["value"]):
                continue
            if b["value"] > 0 and a["value"] > b["value"] * 1.5:  # 显著差异
                results.append(
                    {
                        "type": "numeric_comparison",
                        "conclusion": (
                            f"{a['label']}({a['value']})是{b['label']}({b['value']})的{a['value'] / b['value']:.1f}倍"
                        ),
                        "derived_from": [ids[i], ids[j]],
                        "confidence": 0.95,
                        "method": "rule_engine",
                    }
                )
    return results
