"""Analysis patterns"""

import re
from collections.abc import Iterator
from typing import Any

from ontoderive.foundation.semantic import SemanticMatcher

# Helpers
#############################################


def _is_dict(val: Any) -> Any:
    return isinstance(val, dict)


def _iter_facts(facts: Any) -> Iterator[Any]:
    """安全迭代facts — 过滤非dict值"""
    if not isinstance(facts, dict):
        return
    for fid, info in facts.items():
        if _is_dict(info):
            yield fid, info


def _extract_num(val: Any) -> Any:
    """从值中提取数字"""
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, bool):
        return 0.0  # bool→0.0 (bool在JSON中不应出现在value字段, 若出现视为0)
    m = re.search(r"(\d+\.?\d*)", str(val))
    return float(m.group(1)) if m else 0.0


def _find_entity_for_fact(fid: Any, desc: Any, entities: Any, matcher: Any = None) -> Any:
    """根据事实描述找到对应实体ID — 语义匹配优先"""
    if not isinstance(entities, dict):
        return fid
    # TF-IDF语义匹配
    if matcher:
        candidates = [info.get("name", "") for info in entities.values() if isinstance(info, dict)]
        if candidates:
            best, score = matcher.best_match(desc, candidates, threshold=0.15)
            if best and score > 0.15:
                for eid, info in entities.items():
                    if isinstance(info, dict) and info.get("name") == best:
                        return eid
    # 回退: 精确字符串匹配
    for eid, info in entities.items():
        if isinstance(info, dict) and info.get("name", "") in desc:
            return eid
    return fid


# Pattern functions
#############################################


def detect_capacity_constraint(engine: Any, facts: Any, entities: Any, relations: Any) -> bool:
    """检测: 利用率>90%供给紧张 或 利用率<60%产能过剩 或 库存偏离基准"""
    for fid, info in _iter_facts(facts):
        desc = info.get("desc", "") + info.get("description", "")
        val = info.get("value", "")
        if "利用率" in desc or "产能" in desc:
            num = _extract_num(val)
            if num > 90 or (num > 0 and num < 60):
                return True
        if "库存" in desc:
            stock = _extract_num(val)
            # 查找对应安全基准
            for fid2, info2 in _iter_facts(facts):
                if "安全" in info2.get("desc", "") and _extract_num(info2.get("value", "")) > stock:
                    return True
    return False


def analyze_capacity(engine: Any, facts: Any, entities: Any, relations: Any, enhancer: Any) -> Any:
    results = []
    for fid, info in _iter_facts(facts):
        desc = info.get("desc", "") + info.get("description", "")
        val = info.get("value", "")
        num = _extract_num(val)
        if num <= 0:
            continue
        # 利用率分析 (供给紧张)
        if "利用率" in desc and num > 90 and num <= 100:
            elasticity = max(0, (100 - num) / num)  # 剩余产能比例
            results.append(
                {
                    "type": "analytics",
                    "conclusion": f"供给弹性≈{elasticity:.2f}: '{desc}'={val}, "
                    f"仅余{100 - num:.0f}%产能, 需求波动将直接传导为短缺",
                    "derives_from": [fid],
                    "confidence": 0.85,
                }
            )
        # 产能过剩检测 (v3.4)
        elif "利用率" in desc and num > 0 and num < 60:
            excess_pct = 100 - num
            results.append(
                {
                    "type": "analytics",
                    "conclusion": f"产能过剩: '{desc}'={val}, 闲置{excess_pct:.0f}%产能, "
                    f"供过于求→价格下行→行业出清压力",
                    "derives_from": [fid],
                    "confidence": 0.80,
                }
            )
        # 库存vs安全基准
        if "库存" in desc:
            for fid2, info2 in _iter_facts(facts):
                if "安全" in info2.get("desc", ""):
                    safe = _extract_num(info2.get("value", ""))
                    if safe > num:
                        gap_pct = (safe - num) / safe * 100
                        results.append(
                            {
                                "type": "analytics",
                                "conclusion": f"库存缺口: '{desc}'={val}低于安全基准{safe}, "
                                f"缺口{gap_pct:.0f}%, 补库压力紧迫",
                                "derives_from": [fid, fid2],
                                "confidence": 0.90,
                            }
                        )
    return results


# ═══ A2: 供应链风险放大 ═══


def detect_supply_risk(engine: Any, facts: Any, entities: Any, relations: Any) -> Any:
    """检测: 存在depends_on链 + 交付/库存异常"""
    has_chain = any(r.get("relation_type") == "depends_on" for r in (relations or []))
    has_issue = any(
        "交付" in (f.get("desc", "") + f.get("description", "")) and _extract_num(f.get("value", "")) < 80
        for _, f in _iter_facts(facts)
    )
    return has_chain and has_issue


def analyze_supply_chain(engine: Any, facts: Any, entities: Any, relations: Any, enhancer: Any) -> Any:
    results = []
    # 语义匹配器: 基于事实描述
    descs = [info.get("desc", "") for _, info in _iter_facts(facts)]
    matcher = SemanticMatcher(descs if descs else ["default"])
    # 构建依赖图
    deps: dict[Any, Any] = {}
    for r in relations or []:
        if r.get("relation_type") == "depends_on":
            deps.setdefault(r["subject"], []).append((r["object"], 1.0))
    # 查找交付异常
    for fid, info in _iter_facts(facts):
        desc = info.get("desc", "") + info.get("description", "")
        if "交付" not in desc:
            continue
        delivery = _extract_num(info.get("value", ""))
        if delivery >= 80 or delivery <= 0:
            continue
        entity_name = _find_entity_for_fact(fid, desc, entities, matcher)
        upstreams = deps.get(entity_name, [])
        if not upstreams:
            for subj in deps:
                if matcher.is_semantically_related(subj, desc):
                    upstreams = deps.get(subj, [])
                    entity_name = subj
                    break
        for up_name, ratio in upstreams:
            for fid2, info2 in _iter_facts(facts):
                up_desc = info2.get("desc", "")
                if "库存" in up_desc:
                    stock = _extract_num(info2.get("value", ""))
                    amplification = (100 - delivery) / 100 * ratio
                    results.append(
                        {
                            "type": "analytics",
                            "conclusion": f"风险传导: {entity_name}交付{delivery}%→上游{up_name}"
                            f"库存{stock}天, 放大系数≈{amplification:.2f}",
                            "derives_from": [fid, fid2],
                            "confidence": 0.75,
                        }
                    )
    return results


# ═══ A3: 代理问题 ═══


def detect_agency_issue(engine: Any, facts: Any, entities: Any, relations: Any) -> bool:
    """检测: X employs Y, 且Y的工作输出实际服务于Z(≠X)"""
    employs_pairs = [(r["subject"], r["object"]) for r in (relations or []) if r.get("relation_type") == "employs"]
    if not employs_pairs:
        return False
    # 检查被雇佣方是否通过其他关系服务于第三方
    for employer, employee in employs_pairs:
        for r in relations or []:
            if (
                r.get("subject") == employee
                and r.get("relation_type") in ("cooperates_with", "depends_on", "influences")
                and r.get("object") != employer
            ):
                return True
    return False


def analyze_agency(engine: Any, facts: Any, entities: Any, relations: Any, enhancer: Any) -> Any:
    results = []
    employs_pairs = [(r["subject"], r["object"]) for r in (relations or []) if r.get("relation_type") == "employs"]
    for employer, employee in employs_pairs:
        for r in relations or []:
            if r.get("subject") == employee and r.get("object") != employer:
                base = (
                    f"潜在代理问题: {employer} employs {employee}, "
                    f"但{employee}的'{r['relation_type']}'关系指向{r['object']}"
                )
                if enhancer and enhancer.available:
                    try:
                        enhanced = enhancer._call(
                            f"分析以下代理问题的组织影响(一句话): {base}", "你是组织行为学专家。", 0.3
                        )
                        if enhanced:
                            base += f"。LLM分析: {enhanced.strip()[:200]}"
                    except Exception:
                        pass
                results.append(
                    {
                        "type": "analytics",
                        "conclusion": base,
                        "derives_from": [employer, employee, r.get("object", "")],
                        "confidence": 0.70,
                    }
                )
    return results


# ═══ A4: 激励不相容 ═══


def detect_incentive_issue(engine: Any, facts: Any, entities: Any, relations: Any) -> Any:
    """检测: 多实体共享资源(语义关联) + 有不同的事实描述"""
    # 找共享同一目标实体的多个主体
    targets: dict[Any, Any] = {}
    for r in relations or []:
        obj = r.get("object", "")
        targets.setdefault(obj, []).append(r.get("subject", ""))
    shared_resources = [(t, subs) for t, subs in targets.items() if len(subs) >= 2]
    return len(shared_resources) >= 1


def analyze_incentive(engine: Any, facts: Any, entities: Any, relations: Any, enhancer: Any) -> Any:
    results = []
    # 匹配器: 用事实描述语料
    fact_desc = [f.get("desc", "") for f in facts.values() if isinstance(f, dict)]
    matcher = SemanticMatcher(fact_desc if fact_desc else ["default"])

    targets: dict[Any, Any] = {}
    for r in relations or []:
        obj = r.get("object", "")
        targets.setdefault(obj, []).append(r.get("subject", ""))

    shared = [(t, subs) for t, subs in targets.items() if len(subs) >= 2]
    for target, subjects in shared:
        # 检测: 共享同一资源的实体是否有语义差异大的事实
        subj_facts: dict[Any, Any] = {}
        for fid, info in _iter_facts(facts):
            desc = info.get("desc", "")
            for subj in subjects:
                if matcher.is_semantically_related(desc, subj, threshold=0.15):
                    subj_facts.setdefault(subj, []).append(desc)
        if len(subj_facts) >= 2:
            pairs = list(subj_facts.items())
            for i in range(len(pairs)):
                for j in range(i + 1, len(pairs)):
                    s1, f1 = pairs[i]
                    s2, f2 = pairs[j]
                    if matcher.is_semantically_related(" ".join(f1), " ".join(f2), threshold=0.30):
                        continue  # 相似→目标一致
                    # 不相似→潜在激励冲突
                    results.append(
                        {
                            "type": "analytics",
                            "conclusion": f"潜在激励冲突: {s1}({', '.join(f1[:2])})与"
                            f"{s2}({', '.join(f2[:2])})共享{target}但关注点不同",
                            "derives_from": subjects + [target],
                            "confidence": 0.60,
                        }
                    )
    return results


# ═══ A5: 补救规划 ═══


def detect_remediation_needed(engine: Any, facts: Any, entities: Any, relations: Any) -> bool:
    """检测: 存在'问题'/'审计'/'整改'相关事实或推论"""
    for _, info in _iter_facts(facts):
        desc = info.get("desc", "") + info.get("description", "")
        if any(kw in desc for kw in ("审计", "整改", "问题", "风险", "违规", "差距")):
            return True
    return False


def analyze_remediation(engine: Any, facts: Any, entities: Any, relations: Any, enhancer: Any) -> Any:
    results: list[Any] = []
    problems = []
    team_size, months = 4, 6  # 默认值
    for fid, info in _iter_facts(facts):
        desc = info.get("desc", "") + info.get("description", "")
        val = info.get("value", "")
        if "团队" in desc or "合规" in desc:
            team_size = max(1, int(_extract_num(val)))
        if "距" in desc and "月" in desc:
            months = max(1, int(_extract_num(val)))
        if any(kw in desc for kw in ("审计问题", "高风险", "整改率", "认证", "差距")):
            problems.append(f"{desc}={val}")
    if not problems:
        return results

    # 可行性比率 (v3.4): 问题任务数÷(人数×月数)
    task_count = 0
    for fid, info in _iter_facts(facts):
        desc = info.get("desc", "")
        val = info.get("value", "")
        if "问题" in desc and _extract_num(val) > 0:
            task_count = max(task_count, int(_extract_num(val)))
    remaining_tasks = max(task_count, 1)
    feasibility = remaining_tasks / max(team_size * months, 1)
    status = "不可行⚠️" if feasibility > 1.5 else ("紧张" if feasibility > 1.0 else "可行")
    results.append(
        {
            "type": "analytics",
            "conclusion": (
                f"整改可行性: {remaining_tasks}问题/{team_size}人/{months}月="
                f"人均{feasibility:.1f}个/月→{status}"
                f"{' 需增加人力或延长时间窗口' if feasibility > 1.0 else ''}"
            ),
            "derives_from": [
                fid
                for fid, _ in _iter_facts(facts)
                if any(kw in facts.get(fid, {}).get("desc", "") for kw in ("审计", "整改"))
            ][:5],
            "confidence": 0.85,
        }
    )

    # 严重度分类
    high_risk = sum(1 for p in problems if "高风险" in p or "差距" in p)
    if high_risk > 0:
        results.append(
            {
                "type": "analytics",
                "conclusion": f"短期(0-3月)优先: 解决{high_risk}个高风险项, 防止监管执法触发",
                "derives_from": [fid for fid in facts],
                "confidence": 0.80,
            }
        )

    if enhancer and enhancer.available:
        try:
            context = "; ".join(problems[:8])
            plan = enhancer._call(
                f"基于以下问题生成分阶段补救方案(短/中/长期各1-2句话): {context}", "你是战略规划专家。", 0.4
            )
            if plan:
                results.append(
                    {
                        "type": "analytics",
                        "conclusion": f"分阶段方案: {plan.strip()[:300]}",
                        "derives_from": [
                            fid
                            for fid in facts
                            if any(kw in facts[fid].get("desc", "") for kw in ("审计", "整改", "问题"))
                        ],
                        "confidence": 0.65,
                    }
                )
        except Exception:
            pass
    return results


# ═══ A6: 市场结构分析 ═══
