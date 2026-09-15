"""
UnifiedReasoner — 统一推理引擎 v3.4
=====================================
合并 RuleReasoner + FormalReasoner + AnalyticsEngine 输出为统一格式。
确定性/启发式/结构性/分析型四层分类 + certainty标注 + derivation_trail。
"""

from dataclasses import asdict, dataclass, field
from typing import Any

from .reasoner import RuleReasoner
from .reasoner_formal import FormalReasoner


@dataclass
class UnifiedConclusion:
    conclusion: str
    certainty: str  # certain/probable/uncertain/structural/analytical
    method: str
    derives_from: list[str] = field(default_factory=list)
    confidence: float = 0.80
    source: str = ""  # rule_engine / formal / analytics / llm
    derivation_trail: str = ""

    def to_dict(self) -> Any:
        d = asdict(self)
        d["type"] = self.method  # 向后兼容: type=method
        return d


class UnifiedReasoner:
    """统一推理入口 — 合并三引擎输出"""

    def __init__(self, loaded_rules: list | None = None) -> None:
        self.rule = RuleReasoner(loaded_rules=loaded_rules or [])
        self.formal = FormalReasoner()
        self._last_results: list = []

    def reason(
        self,
        facts: dict,
        inferences: dict,
        knowledge: Any = None,
        relations: list[dict] | None = None,
        enhancer: Any = None,
    ) -> list[UnifiedConclusion]:
        relations = relations or []
        results = []

        # 1. 确定性推理
        rr = self.rule.derive(facts, inferences, relations)
        for r in rr:
            if r["type"] in (
                "numeric_comparison",
                "modus_ponens_valid",
                "subsumption",
                "missing_reference",
                "chain_break",
                "threshold_alert",
            ):
                results.append(
                    UnifiedConclusion(
                        conclusion=r["conclusion"],
                        certainty="certain",
                        method=r["type"],
                        confidence=r.get("confidence", 0.90),
                        derives_from=r.get("derived_from", []),
                        source="rule_engine",
                        derivation_trail=r.get("derivation_trail", ""),
                    )
                )

        # 2. 启发式推理
        for r in rr:
            if r["type"] in (
                "shared_premise",
                "disjunctive_syllogism",
                "evidence_gap",
                "influence_analysis",
                "structural_hole",
                "transitive_dependency",
                "relation_transitive",
                "relation_inverse",
            ):
                results.append(
                    UnifiedConclusion(
                        conclusion=r["conclusion"],
                        certainty="probable",
                        method=r["type"],
                        confidence=r.get("confidence", 0.70),
                        derives_from=r.get("derived_from", []),
                        source="rule_engine",
                        derivation_trail=r.get("derivation_trail", ""),
                    )
                )

        # 3. 结构性分析
        for r in rr:
            if r["type"] in (
                "coverage",
                "redundancy_warning",
                "consistency_warning",
                "temporal_sequence",
                "incremental_recalc",
                "case_match",
                "relation_domain",
                "relation_range",
                "shallow_chain",
            ):
                results.append(
                    UnifiedConclusion(
                        conclusion=r["conclusion"],
                        certainty="structural",
                        method=r["type"],
                        confidence=r.get("confidence", 0.80),
                        derives_from=r.get("derived_from", []),
                        source="rule_engine",
                        derivation_trail=r.get("derivation_trail", ""),
                    )
                )

        # 4. 形式推理
        if knowledge:
            for c in self.formal.reason(knowledge):
                results.append(
                    UnifiedConclusion(
                        conclusion=c.conclusion,
                        certainty=c.certainty,
                        method=c.method,
                        confidence=c.confidence,
                        derives_from=c.derives_from,
                        source="formal",
                    )
                )

        # 5. 分析模式 (v3.4: AnalyticsEngine纳入统一输出)
        try:
            from ontoderive.theories.analytics import AnalyticsEngine

            ae = AnalyticsEngine(enhancer=enhancer)
            ae_results = ae.run(facts, {}, inferences, relations)
            for ar in ae_results:
                results.append(
                    UnifiedConclusion(
                        conclusion=ar["conclusion"],
                        certainty="analytical",
                        method=ar.get("pattern", "analytics"),
                        confidence=ar.get("confidence", 0.70),
                        derives_from=ar.get("derives_from", []),
                        source="analytics",
                        derivation_trail=f"A{ar.get('pattern', '?')}: {ar.get('category', '?')}",
                    )
                )
        except Exception as e:
            import sys

            print(f"[unified] analytics skip: {e}", file=sys.stderr)

        self._last_results = results
        return results

    def summary(self) -> dict:
        total = len(self._last_results)
        by_source: dict[str, int] = {}
        for r in self._last_results:
            by_source[r.source] = by_source.get(r.source, 0) + 1
        return {"total": total, "by_source": by_source}
