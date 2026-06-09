"""
ssot-kernel — evolution/rule_miner.py
======================================
规则挖掘机：从引擎输出 + 领域数据中自动建议新规则。

不自动写入，只产出建议。由人确认后再注入 rules.yaml。

挖掘策略：
1. UNPAIRED_FACTS    — 两个数值事实存在显著比例差异但无对应规则
2. UNGUARDED_ENTITY  — 实体有状态变化但无一致性规则覆盖
3. CHAIN_GAP         — 状态机链间缺少硬/软咬合
4. THEORY_GAP        — 推论无理论支撑且可匹配已知理论
5. RECURRING_GAP     — 同一能力缺失连续多次出现
6. NEW_CONTRADICTION — 实体属性的矛盾组合未被覆盖
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..meta_model import DomainConfig
from ..patterns.base import DerivationReport
from ..patterns.contradiction import ContradictionPattern


@dataclass
class RuleSuggestion:
    """一条规则建议"""

    id: str = ""  # 建议 ID（自动生成）
    pattern: str = ""  # 建议的规则模式
    name: str = ""  # 建议名称
    rationale: str = ""  # 为什么建议这条规则
    confidence: float = 0.0  # 0~1
    tier: str = "medium"  # high / medium / low（由 mine_all 标注）
    conditions: list[str] = field(default_factory=list)  # 建议的前提条件
    logic: str = ""  # 建议的推导逻辑
    source: str = ""  # 触发源（UNPAIRED_FACTS / CHAIN_GAP 等）
    yaml_snippet: str = ""  # 可直接粘贴到 rules.yaml 的片段


@dataclass
class EvolutionReport:
    """一次进化分析的完整报告"""

    suggestions: list[RuleSuggestion] = field(default_factory=list)
    checkpoint: str = ""
    summary: str = ""


class RuleMiner:
    """从领域数据和引擎输出中挖掘新规则建议"""

    def __init__(self, domain: DomainConfig, report: DerivationReport | None = None):
        self.domain = domain
        self.report = report
        self._contradiction_checker = ContradictionPattern()

    # 置信度分档阈值
    CONFIDENCE_TIERS: dict[str, float] = {
        "high": 0.8,
        "medium": 0.5,
        "low": 0.0,
    }
    MIN_CONFIDENCE: float = 0.5  # 低于此值的建议将被过滤

    def mine_all(self) -> list[RuleSuggestion]:
        """执行全量挖掘，按置信度排序 + 分层过滤"""
        suggestions: list[RuleSuggestion] = []
        suggestions.extend(self._mine_unpaired_facts())
        suggestions.extend(self._mine_chain_gaps())
        suggestions.extend(self._mine_theory_gaps())
        suggestions.extend(self._mine_recurring_capability_gaps())

        # 分档标注 + 过滤低价值建议
        filtered = []
        for s in suggestions:
            s.tier = self._confidence_tier(s.confidence)
            if s.confidence >= self.MIN_CONFIDENCE:
                filtered.append(s)

        # 按置信度降序排列
        filtered.sort(key=lambda s: s.confidence, reverse=True)

        # 重新编号（全局唯一）
        for i, s in enumerate(filtered, 1):
            s.id = f"R-SUG-{i:03d}"

        return filtered

    @staticmethod
    def _confidence_tier(confidence: float) -> str:
        if confidence >= 0.8:
            return "high"
        elif confidence >= 0.5:
            return "medium"
        return "low"

    def _mine_unpaired_facts(self) -> list[RuleSuggestion]:
        """挖掘未配对的数值事实（可形成矛盾规则）

        优化：按大事实（分母）分组聚合，同一分母下的多个小事实合并为一条综合建议。
        """
        suggestions: list[RuleSuggestion] = []

        # 找所有数值型 data fact
        numeric_facts = []
        for f in self.domain.facts:
            try:
                val = float(f.value) if f.value else None
                if val is not None:
                    numeric_facts.append(f)
            except (ValueError, TypeError):
                continue

        # 第一轮：找出所有比例悬殊的配对，按 big_id 分组
        from collections import defaultdict

        groups: dict[str, list[dict]] = defaultdict(list)

        for i in range(len(numeric_facts)):
            for j in range(len(numeric_facts)):
                if i >= j:
                    continue
                a, b = numeric_facts[i], numeric_facts[j]
                if a.id == b.id:
                    continue
                try:
                    va, vb = float(a.value), float(b.value)
                except (ValueError, TypeError):
                    continue
                if va <= 0 or vb <= 0:
                    continue

                ratio = min(va, vb) / max(va, vb)
                if ratio < 0.1:
                    small, big = (a, b) if va < vb else (b, a)
                    if self._fact_pair_has_rule(small.id, big.id):
                        continue
                    groups[big.id].append(
                        {
                            "small": small,
                            "ratio": ratio,
                        }
                    )

        # 第二轮：每组最多取 top-3 个最悬殊的配对，合并为一条建议
        for big_id, members in groups.items():
            big_fact = next((f for f in numeric_facts if f.id == big_id), None)
            if not big_fact:
                continue

            members.sort(key=lambda x: x["ratio"])
            top3 = members[:3]

            if len(top3) == 1:
                # 单一配对 → 精确描述
                m = top3[0]
                name = f"{m['small'].title} vs {big_fact.title} 矛盾"
                rationale = f"{m['small'].id}({m['small'].value}) / {big_fact.id}({big_fact.value}) = {m['ratio'] * 100:.1f}%"
                logic = f"{m['small'].title}远低于{big_fact.title}，需要相应的解决方案"
                conditions = [
                    f'fact_ratio("{m["small"].id}", "{big_fact.id}") < {m["ratio"] * 2:.2f}'
                ]
            else:
                # 多配对 → 聚合描述
                small_names = "、".join(m["small"].title for m in top3)
                name = f"{big_fact.title} 资源错配（vs {small_names} 等）"
                rationale = f"{big_fact.title}({big_fact.value}) 与多个指标({', '.join(m['small'].id for m in top3)})比例悬殊"
                logic = f"{big_fact.title}与多个下游指标之间存在结构性断层，需要系统性解决方案"
                conditions = [
                    f'fact_ratio("{m["small"].id}", "{big_fact.id}") < {m["ratio"] * 2:.2f}'
                    for m in top3
                ]

            # 置信度取最高比例的那个（最悬殊 = 最高置信度）
            best_ratio = top3[0]["ratio"]
            confidence = round(min(1 - best_ratio, 0.99), 2)

            suggestions.append(
                RuleSuggestion(
                    id="",
                    pattern="contradiction",
                    name=name,
                    rationale=rationale,
                    confidence=confidence,
                    conditions=conditions,
                    logic=logic,
                    source="UNPAIRED_FACTS",
                    yaml_snippet=self._generate_yaml_snippet(
                        "contradiction", name, conditions
                    ),
                )
            )

        return suggestions

    def _mine_chain_gaps(self) -> list[RuleSuggestion]:
        """挖掘状态机链间缺失的咬合"""
        suggestions: list[RuleSuggestion] = []

        sms = self.domain.state_machines
        if len(sms) < 2:
            return suggestions

        # 收集所有已有的咬合
        existing_interlocks = set()
        for rel in self.domain.relations:
            if rel.relation_type == "interlocks_with":
                existing_interlocks.add((rel.source_id, rel.target_id))

        # 检查链间是否缺少咬合
        chain_ids = [sm.id for sm in sms]
        for i in range(len(chain_ids)):
            for j in range(i + 1, len(chain_ids)):
                # 找两条链中是否有节点应该互相关联
                sm_a = sms[i]
                sm_b = sms[j]
                has_interlock = False
                for s_a in sm_a.states:
                    for s_b in sm_b.states:
                        if (s_a.id, s_b.id) in existing_interlocks or (
                            s_b.id,
                            s_a.id,
                        ) in existing_interlocks:
                            has_interlock = True
                            break
                    if has_interlock:
                        break
                if not has_interlock and len(sm_a.states) > 2 and len(sm_b.states) > 2:
                    suggestion = RuleSuggestion(
                        id="",
                        pattern="chain_trigger",
                        name=f"{sm_a.name} ↔ {sm_b.name} 缺少咬合",
                        rationale=f"两条链({sm_a.name}, {sm_b.name})均有{len(sm_a.states)}和"
                        f"{len(sm_b.states)}个状态节点，但无任何 interlock 关系",
                        confidence=0.4,
                        source="CHAIN_GAP",
                        yaml_snippet=f"# {sm_a.name} ↔ {sm_b.name} 潜在咬合点\n"
                        f"# - source_id: {sm_a.states[-1].id if sm_a.states else '?'}\n"
                        f"#   relation_type: interlocks_with\n"
                        f"#   target_id: {sm_b.states[0].id if sm_b.states else '?'}\n"
                        f"#   attributes:\n"
                        f"#     hard: true\n"
                        f'#     description: ""',
                    )
                    suggestions.append(suggestion)

        return suggestions

    def _mine_theory_gaps(self) -> list[RuleSuggestion]:
        """挖掘缺少理论支撑的推论"""
        suggestions: list[RuleSuggestion] = []
        for inf in self.domain.inferences:
            if not inf.theory:
                suggestion = RuleSuggestion(
                    id=f"R-SUG-{len(suggestions) + 1:03d}",
                    pattern="theory_match",
                    name=f"{inf.id} 缺少理论支撑",
                    rationale=f"推论 '{inf.title}' 没有标注理论支撑，可尝试匹配组织管理/激励机制相关理论",
                    confidence=0.5,
                    source="THEORY_GAP",
                    yaml_snippet=f'# 为 {inf.id} 补充理论支撑\n# theory: "如委托代理理论 (Jensen & Meckling, 1976)"',
                )
                suggestions.append(suggestion)
        return suggestions

    def _mine_recurring_capability_gaps(self) -> list[RuleSuggestion]:
        """从引擎报告中的能力缺失提炼新规则"""
        suggestions: list[RuleSuggestion] = []
        if not self.report:
            return suggestions

        # 找能力缺失模式的规则
        for r in self.report.results:
            if "capability_gap" in r.protocol_id.lower() and not r.passed:
                for d in r.details:
                    m = re.search(r"缺少\'([^)]+)\'", d)
                    if m:
                        capability = m.group(1)
                        suggestion = RuleSuggestion(
                            id=f"R-SUG-{len(suggestions) + 1:03d}",
                            pattern="capability_gap",
                            name=f"能力 '{capability}' 持久缺失",
                            rationale=f"引擎持续检测到能力 '{capability}' 缺失，"
                            f"考虑是否需要新增 Resource 或 Project 实体",
                            confidence=0.6,
                            source="RECURRING_GAP",
                            yaml_snippet=f"# 为 '{capability}' 添加实现载体\n"
                            f"# - id: RES-{capability[:8]}\n"
                            f"#   type: Resource\n"
                            f'#   name: "{capability}"',
                        )
                        suggestions.append(suggestion)
        return suggestions

    def _fact_pair_has_rule(self, id_a: str, id_b: str) -> bool:
        """检查这两个事实是否已被某条规则覆盖"""
        for rule in self.domain.rules:
            for premise in rule.premises:
                cond = premise.get("condition", "")
                if id_a in cond and id_b in cond:
                    return True
                if id_b in cond and id_a in cond:
                    return True
        return False

    def _generate_yaml_snippet(
        self, pattern: str, name: str, conditions: list[str]
    ) -> str:
        """生成可直接粘贴到 rules.yaml 的片段"""
        lines = [f"# 建议规则（{self._source_label(self._current_source)}）"]
        lines.append("  - id: INF-SUG-001")
        lines.append(f"    pattern: {pattern}")
        lines.append(f'    name: "{name}"')
        lines.append("    premises:")
        for cond in conditions:
            lines.append(f"      - condition: '{cond}'")
        lines.append('    logic: "待补充推导逻辑"')
        return "\n".join(lines)

    def _source_label(self, source: str) -> str:
        labels = {
            "UNPAIRED_FACTS": "数据对比",
            "CHAIN_GAP": "链间缺失",
            "THEORY_GAP": "理论缺口",
            "RECURRING_GAP": "持续缺口",
        }
        return labels.get(source, source)

    @property
    def _current_source(self) -> str:
        return getattr(self, "_last_source", "UNPAIRED_FACTS")

    @_current_source.setter
    def _current_source(self, val):
        self._last_source = val
