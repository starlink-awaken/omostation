"""Advanced analysis patterns (A6-A9 + extras)."""

from typing import Any

from ..analytics_constants import (
    _DISRUPTION_KW,
    _HISTORY_KW,
    _INERTIA_KW,
    _MARKET_KW,
    _RESOURCE_KW,
    _TECH_NEW_KW,
    _TECH_OLD_KW,
)
from .common import _extract_num, _iter_facts, detect_remediation_needed


def detect_market_structure(engine: Any, facts: Any, entities: Any, relations: Any) -> bool:
    """检测: ≥3实体 或 存在市场份额关键词"""
    n_entities = len(entities) if isinstance(entities, dict) else len(entities)
    if n_entities >= 3:
        return True
    for _, info in _iter_facts(facts):
        if any(kw in info.get("desc", "") for kw in _MARKET_KW):
            return True
    return False


def analyze_market_structure(engine: Any, facts: Any, entities: Any, relations: Any, enhancer: Any) -> Any:
    """HHI集中度 + 市场类型判定"""
    results: list[Any] = []
    n = len(entities) if isinstance(entities, dict) else len(entities)
    shares = []
    for fid, info in _iter_facts(facts):
        desc = info.get("desc", "")
        if any(kw in desc for kw in _MARKET_KW):
            shares.append(_extract_num(info.get("value", "")))
    if not shares:
        return results
    # HHI = sum(share_i^2)
    total = sum(shares) or 1
    hhi = sum((s / total * 100) ** 2 for s in shares)
    mtype = "垄断" if hhi > 2500 else ("寡头" if hhi > 1500 else ("集中" if hhi > 1000 else "分散"))
    cr3 = sum(sorted(shares, reverse=True)[:3]) / total * 100 if len(shares) >= 3 else 100
    results.append(
        {
            "type": "analytics",
            "conclusion": f"市场结构: HHI={hhi:.0f}({mtype}), CR3={cr3:.0f}%, {n}个参与者",
            "derives_from": [fid for fid in facts],
            "confidence": 0.80,
        }
    )
    return results


# ═══ A7: 博弈均衡检测 ═══


def detect_game_equilibrium(engine: Any, facts: Any, entities: Any, relations: Any) -> Any:
    """检测: 多方竞争/合作关系"""
    comp_count = sum(1 for r in (relations or []) if r.get("relation_type") == "competes_with")
    coop_count = sum(1 for r in (relations or []) if r.get("relation_type") == "cooperates_with")
    return comp_count >= 1 or coop_count >= 2


def analyze_game_equilibrium(engine: Any, facts: Any, entities: Any, relations: Any, enhancer: Any) -> Any:
    """识别博弈结构: 囚徒困境/协调博弈/零和博弈"""
    results = []
    comps = [r for r in (relations or []) if r.get("relation_type") == "competes_with"]
    coops = [r for r in (relations or []) if r.get("relation_type") == "cooperates_with"]
    # 竞争+合作共存 → 潜在囚徒困境
    if comps and coops:
        results.append(
            {
                "type": "analytics",
                "conclusion": f"囚徒困境风险: {len(comps)}对竞争+{len(coops)}对合作共存, 个体理性可能导致集体次优",
                "derives_from": [],
                "confidence": 0.65,
            }
        )
    # 纯竞争 → 零和或负和博弈
    if comps and not coops:
        results.append(
            {
                "type": "analytics",
                "conclusion": f"零和博弈: {len(comps)}对竞争关系, 无合作→可能陷入价格战/军备竞赛",
                "derives_from": [],
                "confidence": 0.70,
            }
        )
    return results


# ═══ A8: 策略选项生成 ═══


def detect_strategic_options(engine: Any, facts: Any, entities: Any, relations: Any) -> Any:
    """检测: 存在问题+约束+资源"""
    has_problem = detect_remediation_needed(engine, facts, entities, relations)
    has_constraint = any(
        "约束" in info.get("desc", "") or "限制" in info.get("desc", "") for _, info in _iter_facts(facts)
    )
    return has_problem or has_constraint


def analyze_strategic_options(engine: Any, facts: Any, entities: Any, relations: Any, enhancer: Any) -> Any:
    """生成策略选项 — 基于目标/约束/资源组合"""
    results: list[Any] = []
    # 收集目标、约束、资源
    goals = [
        info.get("desc", "")
        for _, info in _iter_facts(facts)
        if any(kw in info.get("desc", "") for kw in ("目标", "计划", "预计"))
    ]
    constraints = [
        info.get("desc", "")
        for _, info in _iter_facts(facts)
        if any(kw in info.get("desc", "") for kw in ("限制", "约束", "上限", "不超过"))
    ]
    resources = [
        info.get("desc", "")
        for _, info in _iter_facts(facts)
        if any(kw in info.get("desc", "") for kw in ("预算", "团队", "储备", "现金"))
    ]
    if not goals and not constraints:
        return results
    # 策略空间 + 帕累托分析
    n_combos = 2 ** len(goals) if goals else 1
    feasible = max(1, n_combos - len(constraints))
    pareto_note = ""
    tree_depth = len(goals) + len(constraints)
    if len(goals) >= 2 and len(constraints) >= 1:
        pareto_note = f", 约束{len(constraints)}个→帕累托前沿需在{feasible}个可行解中寻找"
    depth_str = f", 博弈树深度≈{tree_depth}" if goals else ""
    results.append(
        {
            "type": "analytics",
            "conclusion": f"策略空间: {len(goals)}目标×{len(constraints)}约束×{len(resources)}资源"
            f"→ {n_combos}种组合{depth_str}{pareto_note}",
            "derives_from": [fid for fid in facts],
            "confidence": 0.60,
        }
    )
    return results


# ═══ A9: 信息生态健康度 (v3.5) ═══


def detect_info_ecology(engine: Any, facts: Any, entities: Any, relations: Any) -> bool:
    """检测: 虚假信息/可信度/信任度/共识度相关数据"""
    kw = ("虚假信息", "可信度", "信任度", "共识度", "信息", "公众信任")
    for _, info in _iter_facts(facts):
        if any(k in info.get("desc", "") for k in kw):
            return True
    return False


def analyze_info_ecology(engine: Any, facts: Any, entities: Any, relations: Any, enhancer: Any) -> Any:
    """信息生态健康度评分"""
    results: list[Any] = []
    disinfo = trust = consensus = 0.0
    for _, info in _iter_facts(facts):
        desc = info.get("desc", "")
        val = _extract_num(info.get("value", ""))
        if "虚假" in desc:
            disinfo = val
        elif "信任" in desc and val > 0:
            trust = val
        elif "共识" in desc and val > 0:
            consensus = val
    if not (disinfo or trust or consensus):
        return results
    # 信息生态健康度 = (1 - 虚假率) × 信任度 × 共识度归一化
    health = (100 - disinfo) / 100 * (trust / 100) * (consensus / 100) * 100
    status = "崩溃" if health < 5 else ("危机" if health < 15 else ("脆弱" if health < 30 else "健康"))
    results.append(
        {
            "type": "analytics",
            "conclusion": f"信息生态健康度: {health:.1f}/100({status}), "
            f"虚假{disinfo}%+信任{trust}%+共识{consensus}%→"
            f"{'事实共识已瓦解' if health < 15 else '尚可正常决策'}",
            "derives_from": [],
            "confidence": 0.75,
        }
    )
    return results


# ═══ A10: 因果链分析 (v3.6) ═══


def detect_causal_chain(engine: Any, facts: Any, entities: Any, relations: Any) -> Any:
    return len(relations or []) >= 1


def analyze_causal_chain(engine: Any, facts: Any, entities: Any, relations: Any, enhancer: Any) -> Any:
    results: list[Any] = []
    deps: dict[Any, Any] = {}
    for r in relations or []:
        if r.get("relation_type") in ("depends_on", "causes", "influences"):
            deps.setdefault(r["subject"], []).append(r["object"])
    if len(deps) < 2:
        return results
    # BFS找所有因果路径 (v3.6 fix: 多分支)
    for start in deps:
        paths = [[start]]
        for path in paths:
            last = path[-1]
            if last in deps:
                for up in deps[last]:
                    if up not in path:
                        new_path = path + [up]
                        paths.append(new_path)
                        if len(new_path) >= 3:
                            results.append(
                                {
                                    "type": "analytics",
                                    "conclusion": f"因果链: {'→'.join(new_path)}, "
                                    f"深度{len(new_path) - 1}, "
                                    f"中介{new_path[1:-1]}, 根因={new_path[-1]}",
                                    "derives_from": new_path[:3],
                                    "confidence": 0.75,
                                }
                            )
    return results


# ═══ A11: 情景规划 (v3.6) ═══


def detect_scenario_planning(engine: Any, facts: Any, entities: Any, relations: Any) -> bool:
    kw = ("不确定性", "概率", "情景", "乐观", "悲观", "基线", "可能")
    for _, info in _iter_facts(facts):
        if any(k in info.get("desc", "") for k in kw):
            return True
    return False


def analyze_scenario_planning(engine: Any, facts: Any, entities: Any, relations: Any, enhancer: Any) -> Any:
    results: list[Any] = []
    uncertainties = []
    for _, info in _iter_facts(facts):
        desc = info.get("desc", "")
        val = info.get("value", "")
        if any(k in desc for k in ("不确定性", "概率", "风险")):
            uncertainties.append((desc, _extract_num(val)))
    if len(uncertainties) < 2:
        return results
    u1, u2 = uncertainties[:2]
    scenarios = [
        (f"{u1[0]}高+{u2[0]}高", "乐观"),
        (f"{u1[0]}高+{u2[0]}低", "基准偏上"),
        (f"{u1[0]}低+{u2[0]}高", "基准偏下"),
        (f"{u1[0]}低+{u2[0]}低", "悲观"),
    ]
    results.append(
        {
            "type": "analytics",
            "conclusion": f"情景矩阵(2×2): {len(scenarios)}情景, "
            f"关键轴={u1[0]}({u1[1]:.0f})×{u2[0]}({u2[1]:.0f}), "
            f"早鸟指标: {u1[0]}趋势逆转或{u2[0]}突破阈值",
            "derives_from": [],
            "confidence": 0.60,
        }
    )
    return results


# ═══ A12: 权力地图 (v3.6) ═══


def detect_power_map(engine: Any, facts: Any, entities: Any, relations: Any) -> Any:
    return len(relations or []) >= 4


def analyze_power_map(engine: Any, facts: Any, entities: Any, relations: Any, enhancer: Any) -> Any:
    results: list[Any] = []
    # Degree centrality (度中心性): 每个节点参与的关系数
    centrality: dict[Any, Any] = {}
    for r in relations or []:
        s, o = r.get("subject", ""), r.get("object", "")
        centrality[s] = centrality.get(s, 0) + 1
        centrality[o] = centrality.get(o, 0) + 1
    if not centrality:
        return results
    top = sorted(centrality.items(), key=lambda x: -x[1])[:3]
    results.append(
        {
            "type": "analytics",
            "conclusion": f"权力地图: 关键节点={', '.join(f'{k}(度={v})' for k, v in top)}, "
            f"最大影响力={top[0][0]}({top[0][1]}连接), "
            f"潜在单点={'是' if top[0][1] >= len(centrality) / 2 else '否'}",
            "derives_from": [k for k, _ in top],
            "confidence": 0.70,
        }
    )
    return results


# ═══ A13: 组织惯性分析 (v3.6) ═══


def detect_organizational_inertia(engine: Any, facts: Any, entities: Any, relations: Any) -> bool:
    """检测: 规模大/历史悠久/投入多 + 转型慢/变化难/惯性/路径依赖"""
    if len(entities or {}) >= 3 or len(relations or []) >= 4:
        return True
    for _, info in _iter_facts(facts):
        if any(k in info.get("desc", "") for k in _INERTIA_KW):
            return True
    return False


def analyze_organizational_inertia(engine: Any, facts: Any, entities: Any, relations: Any, enhancer: Any) -> Any:
    results: list[Any] = []
    if not entities:
        return results

    entity_count = len(entities or {})
    relation_count = len(relations or [])
    complexity = relation_count / max(entity_count, 1)

    history_signals = 0
    resource_lock = 0
    for _, info in _iter_facts(facts):
        desc = info.get("desc", "")
        if any(k in desc for k in _HISTORY_KW):
            history_signals += 1
        if any(k in desc for k in _RESOURCE_KW):
            resource_lock += 1

    inertia_index = complexity * (1 + history_signals) * (1 + resource_lock)
    level = "高" if inertia_index >= 6 else ("中" if inertia_index >= 3 else "低")

    top_entities = sorted(
        [eid for eid in (entities or {})],
        key=lambda e: sum(1 for r in (relations or []) if r.get("subject") == e or r.get("object") == e),
        reverse=True,
    )[:3]

    results.append(
        {
            "type": "analytics",
            "conclusion": f"组织惯性: 指数={inertia_index:.1f}({level}), "
            f"{entity_count}实体/{relation_count}关系, "
            f"复杂度={complexity:.1f}, "
            f"历史信号={history_signals}, 资源锁定={resource_lock}",
            "derives_from": top_entities,
            "confidence": 0.65,
        }
    )
    return results


# ═══ A14: 技术颠覆风险 (v3.6) ═══


def detect_tech_disruption(engine: Any, facts: Any, entities: Any, relations: Any) -> Any:
    """检测: 新技术信号 + 传统技术描述"""
    has_new = False
    has_old = False
    for _, info in _iter_facts(facts):
        desc = info.get("desc", "")
        if any(k in desc for k in _DISRUPTION_KW):
            return True
        if any(k in desc for k in _TECH_NEW_KW):
            has_new = True
        if any(k in desc for k in _TECH_OLD_KW):
            has_old = True
    return has_new or has_old


def analyze_tech_disruption(engine: Any, facts: Any, entities: Any, relations: Any, enhancer: Any) -> Any:
    results = []

    new_signals = 0
    old_lock = 0
    new_entities = []
    old_entities = []
    for fid, info in _iter_facts(facts):
        desc = info.get("desc", "")
        new_signals += sum(1 for k in _TECH_NEW_KW if k in desc)
        old_lock += sum(1 for k in _TECH_OLD_KW if k in desc)
        if any(k in desc for k in _TECH_NEW_KW):
            new_entities.append(fid)
        if any(k in desc for k in _TECH_OLD_KW):
            old_entities.append(fid)

    disruption_pressure = new_signals / max(old_lock, 1)
    threat_level = "高" if disruption_pressure >= 2 else ("中" if disruption_pressure >= 1 else "低")

    conclusion = (
        f"技术颠覆风险: 压力={disruption_pressure:.1f}({threat_level}), 新技术信号={new_signals}, 现有锁定={old_lock}, "
    )
    if threat_level == "高":
        conclusion += "警告: 新技术威胁显著, 建议制定转型路线图"
    elif threat_level == "中":
        conclusion += "关注: 新技术正在积累, 建议跟踪监测"
    else:
        conclusion += "正常: 现有技术仍占主导"

    results.append(
        {
            "type": "analytics",
            "conclusion": conclusion,
            "derives_from": new_entities[:3] + old_entities[:3],
            "confidence": 0.70,
        }
    )
    return results
