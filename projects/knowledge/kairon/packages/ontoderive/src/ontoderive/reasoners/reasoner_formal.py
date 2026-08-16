"""
FormalReasoner — 形式推理引擎 (Phase 3, 零LLM)
================================================
输入: ABox + TBox + 推理规则
输出: 确定结论/推测建议/不确定性标注
"""

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FormalConclusion:
    conclusion: str
    certainty: str  # certain | probable | uncertain
    method: str  # subsumption | transitivity | constraint | classification
    derives_from: list[str] = field(default_factory=list)
    confidence: float = 0.90


class FormalReasoner:
    """确定性形式推理引擎 — 零LLM, 永远可用"""

    RULES = {
        "subsumption": "包含推理: X ⊑ Y, x ∈ X → x ∈ Y",
        "transitivity": "传递推理: R(x,y) ∧ R(y,z) → R(x,z)",
        "constraint": "约束传播: 阈值检查",
        "classification": "实例归类: properties → inferred type",
    }

    def __init__(self) -> None:
        self.conclusions: list[FormalConclusion] = []

    def reason(self, knowledge: Any) -> list[FormalConclusion]:
        """主推理入口"""
        self.conclusions = []
        facts = knowledge.abox.get("facts", {})
        entities = knowledge.abox.get("entities", {})
        tbox = knowledge.tbox

        # R1: 包含推理
        self.conclusions.extend(self._subsumption_reason(entities, tbox))

        # R2: 传递推理
        self.conclusions.extend(self._transitivity_reason(knowledge))

        # R3: 约束传播
        self.conclusions.extend(self._constraint_propagation(facts))

        # R4: 实例归类
        self.conclusions.extend(self._classification(facts, entities, tbox))

        return self.conclusions

    def _subsumption_reason(self, entities: Any, tbox: Any) -> Any:
        """包含推理: ORG-X ⊑ DOMAIN, ORG-X是DOMAIN的实例"""
        results = []
        domain_subtypes = tbox.get("DOMAIN", {}).get("subtypes", [])
        for eid, info in entities.items():
            prefix = eid.split("-")[0] if "-" in eid else eid[:3]
            if prefix in domain_subtypes:
                results.append(
                    FormalConclusion(
                        conclusion=f"{eid}({info.get('name', '')}) ∈ DOMAIN (子类型: {prefix})",
                        certainty="certain",
                        method="subsumption",
                        derives_from=[eid],
                        confidence=0.95,
                    )
                )
        if not results and entities:
            results.append(
                FormalConclusion(
                    conclusion="未检测到实体归属于已知本体层级",
                    certainty="uncertain",
                    method="subsumption",
                    derives_from=list(entities.keys())[:3],
                    confidence=0.40,
                )
            )
        return results

    def _transitivity_reason(self, knowledge: Any) -> Any:
        """传递推理: D-F1→INF-L1→INF-L2 则 D-F1间接影响INF-L2"""
        results = []
        inferences = knowledge.inferences
        for inf in inferences:
            direct = set(inf.derives_from)
            indirect = set()
            for src in direct:
                if src.startswith("INF") or src.startswith("D-F") or src.startswith("P-F"):
                    # 查找是否被其他推论引用
                    for other in inferences:
                        if other.id != inf.id and src in other.derives_from:
                            indirect.add(other.id)
            if indirect:
                results.append(
                    FormalConclusion(
                        conclusion=f"{inf.id}通过{list(direct)[:3]}间接影响{list(indirect)[:3]}",
                        certainty="probable",
                        method="transitivity",
                        derives_from=list(direct | indirect),
                        confidence=0.75,
                    )
                )
        return results

    def _constraint_propagation(self, facts: Any) -> Any:
        """约束传播: 内置阈值检查"""
        results = []
        thresholds = {"率": 60.0, "占比": 50.0, "覆盖": 60.0, "增长": 0}
        for fid, info in facts.items():
            desc = info.get("description", "")
            for keyword, threshold in thresholds.items():
                if keyword in desc:
                    nums = re.findall(r"(\d+\.?\d*)", str(info.get("value", "")))
                    if nums:
                        val = float(nums[0])
                        if threshold > 0 and val < threshold:
                            results.append(
                                FormalConclusion(
                                    conclusion=f"{desc}({val})低于基准{threshold}, 需关注",
                                    certainty="certain",
                                    method="constraint",
                                    derives_from=[fid],
                                    confidence=0.90,
                                )
                            )
        return results

    def _classification(self, facts: Any, entities: Any, tbox: Any) -> Any:
        """实例归类: 基于属性推断实例所属类别"""
        results = []
        fact_subtypes = tbox.get("FACT", {}).get("subtypes", [])
        for fid, info in facts.items():
            desc = info.get("description", "")
            if any(kw in desc for kw in ["率", "%", "占比"]):
                inferred = "DAT"  # 数据型
            elif any(kw in desc for kw in ["政策", "法规", "规定"]):
                inferred = "POL"  # 政策型
            else:
                inferred = "DAT"
            if inferred in fact_subtypes:
                results.append(
                    FormalConclusion(
                        conclusion=f"{fid}归类为FACT.{inferred}",
                        certainty="certain",
                        method="classification",
                        derives_from=[fid],
                        confidence=0.85,
                    )
                )
        return results

    def summary(self) -> dict:
        """推理总结"""
        certain = [c for c in self.conclusions if c.certainty == "certain"]
        probable = [c for c in self.conclusions if c.certainty == "probable"]
        uncertain = [c for c in self.conclusions if c.certainty == "uncertain"]
        return {
            "total": len(self.conclusions),
            "certain": len(certain),
            "probable": len(probable),
            "uncertain": len(uncertain),
            "methods": list(set(c.method for c in self.conclusions)),
        }
