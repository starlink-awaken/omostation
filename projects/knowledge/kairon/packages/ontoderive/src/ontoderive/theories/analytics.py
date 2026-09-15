"""
分析模式引擎 — Analytical Patterns Engine
============================================
将领域知识(博弈论/经济学/组织行为学/策略规划)编码为可复用的分析模板。
每个模式 = 检测规则(确定性) + 分析逻辑(公式/LLM增强) → 统一结论

与推理规则的区别:
  推理规则(R1-R19): 回答"推导对不对" — 逻辑一致性
  分析模式(A1-Ax):  回答"这意味着什么" — 领域洞察
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .analytics_patterns import (
    analyze_agency,
    analyze_capacity,
    analyze_causal_chain,
    analyze_game_equilibrium,
    analyze_incentive,
    analyze_info_ecology,
    analyze_market_structure,
    analyze_organizational_inertia,
    analyze_power_map,
    analyze_remediation,
    analyze_scenario_planning,
    analyze_strategic_options,
    analyze_supply_chain,
    analyze_tech_disruption,
    detect_agency_issue,
    detect_capacity_constraint,
    detect_causal_chain,
    detect_game_equilibrium,
    detect_incentive_issue,
    detect_info_ecology,
    detect_market_structure,
    detect_organizational_inertia,
    detect_power_map,
    detect_remediation_needed,
    detect_scenario_planning,
    detect_strategic_options,
    detect_supply_risk,
    detect_tech_disruption,
)


@dataclass
class AnalyticalPattern:
    """分析模式定义

    semantic_depth: 0-5连续推理深度
      0 = 纯正则/数值比较 (R1-R18级别)
      1 = 语义匹配 (TF-IDF)
      2 = 嵌入向量 (需外部模型)
      3 = 轻量分类器
      4 = 小语言模型 (本地)
      5 = 大语言模型 (云端LLM)
    """

    name: str
    description: str
    category: str  # game_theory | economics | supply_chain | organizational | strategic
    detect: Callable  # (facts, entities, relations) → bool
    analyze: Callable  # (facts, entities, relations, enhancer) → List[dict]
    semantic_depth: int = 0  # 0-5连续推理深度
    requires_llm: bool = False  # 向后兼容, 等同于 semantic_depth >= 4


class AnalyticsEngine:
    """Analytical Pattern Engine"""

    def __init__(self, enhancer: Any = None, matcher: Any = None) -> None:
        self.enhancer = enhancer
        self.matcher = matcher
        self.patterns = self._register_patterns()

    def _register_patterns(self) -> list[Any]:
        return [
            # === A1: capacity_elasticity ===
            AnalyticalPattern(
                name="capacity_elasticity",
                description="Detect capacity/inventory constraints",
                category="economics",
                detect=lambda f, e, r: detect_capacity_constraint(self, f, e, r),
                analyze=lambda f, e, r, enh: analyze_capacity(self, f, e, r, enh),
                semantic_depth=0,
            ),
            # === A2: supply_chain_amplification ===
            AnalyticalPattern(
                name="supply_chain_amplification",
                description="Calculate risk amplification",
                category="supply_chain",
                detect=lambda f, e, r: detect_supply_risk(self, f, e, r),
                analyze=lambda f, e, r, enh: analyze_supply_chain(self, f, e, r, enh),
                semantic_depth=1,
            ),
            # === A3: principal_agent ===
            AnalyticalPattern(
                name="principal_agent",
                description="Detect agency problems",
                category="game_theory",
                detect=lambda f, e, r: detect_agency_issue(self, f, e, r),
                analyze=lambda f, e, r, enh: analyze_agency(self, f, e, r, enh),
                semantic_depth=4,
            ),
            # === A4: incentive_misalignment ===
            AnalyticalPattern(
                name="incentive_misalignment",
                description="Compare goals vs incentives",
                category="organizational",
                detect=lambda f, e, r: detect_incentive_issue(self, f, e, r),
                analyze=lambda f, e, r, enh: analyze_incentive(self, f, e, r, enh),
                semantic_depth=1,
            ),
            # === A5: remediation_planning ===
            AnalyticalPattern(
                name="remediation_planning",
                description="Generate remediation plans",
                category="strategic",
                detect=lambda f, e, r: detect_remediation_needed(self, f, e, r),
                analyze=lambda f, e, r, enh: analyze_remediation(self, f, e, r, enh),
                semantic_depth=1,
            ),
            # === A6: market_structure ===
            AnalyticalPattern(
                name="market_structure",
                description="HHI concentration + market type",
                category="economics",
                detect=lambda f, e, r: detect_market_structure(self, f, e, r),
                analyze=lambda f, e, r, enh: analyze_market_structure(self, f, e, r, enh),
                semantic_depth=0,
            ),
            # === A7: game_equilibrium ===
            AnalyticalPattern(
                name="game_equilibrium",
                description="Equilibrium type detection",
                category="game_theory",
                detect=lambda f, e, r: detect_game_equilibrium(self, f, e, r),
                analyze=lambda f, e, r, enh: analyze_game_equilibrium(self, f, e, r, enh),
                semantic_depth=1,
            ),
            # === A8: strategic_options ===
            AnalyticalPattern(
                name="strategic_options",
                description="Goal+constraint+resource -> strategies",
                category="strategic",
                detect=lambda f, e, r: detect_strategic_options(self, f, e, r),
                analyze=lambda f, e, r, enh: analyze_strategic_options(self, f, e, r, enh),
                semantic_depth=2,
            ),
            # === A9: info_ecology ===
            AnalyticalPattern(
                name="info_ecology",
                description="Info ecology health score",
                category="strategic",
                detect=lambda f, e, r: detect_info_ecology(self, f, e, r),
                analyze=lambda f, e, r, enh: analyze_info_ecology(self, f, e, r, enh),
                semantic_depth=0,
            ),
            # === A10: causal_chain ===
            AnalyticalPattern(
                name="causal_chain",
                description="Causal path extraction",
                category="supply_chain",
                detect=lambda f, e, r: detect_causal_chain(self, f, e, r),
                analyze=lambda f, e, r, enh: analyze_causal_chain(self, f, e, r, enh),
                semantic_depth=0,
            ),
            # === A11: scenario_planning ===
            AnalyticalPattern(
                name="scenario_planning",
                description="2x2 scenario matrix",
                category="strategic",
                detect=lambda f, e, r: detect_scenario_planning(self, f, e, r),
                analyze=lambda f, e, r, enh: analyze_scenario_planning(self, f, e, r, enh),
                semantic_depth=1,
            ),
            # === A12: power_map ===
            AnalyticalPattern(
                name="power_map",
                description="Centrality from relation network",
                category="organizational",
                detect=lambda f, e, r: detect_power_map(self, f, e, r),
                analyze=lambda f, e, r, enh: analyze_power_map(self, f, e, r, enh),
                semantic_depth=0,
            ),
            # === A13: organizational_inertia ===
            AnalyticalPattern(
                name="organizational_inertia",
                description="Change resistance detection",
                category="organizational",
                detect=lambda f, e, r: detect_organizational_inertia(self, f, e, r),
                analyze=lambda f, e, r, enh: analyze_organizational_inertia(self, f, e, r, enh),
                semantic_depth=0,
            ),
            # === A14: tech_disruption ===
            AnalyticalPattern(
                name="tech_disruption",
                description="Tech substitution threat",
                category="strategic",
                detect=lambda f, e, r: detect_tech_disruption(self, f, e, r),
                analyze=lambda f, e, r, enh: analyze_tech_disruption(self, f, e, r, enh),
                semantic_depth=1,
            ),
        ]

    def run(
        self,
        facts: Any,
        entities: Any,
        inferences: Any,
        relations: Any = None,
        patterns: Any = None,
        max_depth: int = 5,
    ) -> Any:
        """运行所有(或指定)分析模式, 返回洞察列表

        max_depth: 最大推理深度 (0=仅纯规则, 3=含分类器, 5=含LLM)
        """
        if not isinstance(facts, dict):
            return []
        # 可用深度: 有enhancer→max 5, 有matcher→max 1, 否则→0
        available_depth = 0
        if self.enhancer and self.enhancer.available:
            available_depth = 5
        elif hasattr(self, "matcher") and self.matcher:
            available_depth = 1
        effective_depth = min(max_depth, available_depth)

        results = []
        targets = patterns or self.patterns
        for pat in targets:
            # 深度控制: 只运行深度在可用范围内的模式
            if pat.semantic_depth > effective_depth:
                continue
            try:
                if pat.detect(facts, entities, relations or []):
                    conclusions = pat.analyze(facts, entities, relations or [], self.enhancer)
                    for c in conclusions:
                        c["pattern"] = pat.name
                        c["category"] = pat.category
                        c["semantic_depth"] = pat.semantic_depth
                    results.extend(conclusions)
            except Exception:
                pass
        return results

    # ═══ A1: 供给弹性 ═══
