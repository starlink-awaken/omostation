"""
SSOT Kernel — patterns/consistency.py
一致性校验模式 (R-INF-004)

当某个实体的状态变更时，自动标记依赖该实体的推论为 needs_review。
泛化后不关心具体实体是什么，只关心 derives_from 关系链。
"""

from ..meta_model import DomainConfig, Fact, Rule
from .base import BasePattern, CheckResult


class ConsistencyPattern(BasePattern):
    """一致性校验模式。

    遍历所有推论，检查它们的 derives_from 依赖是否仍然有效：
    - 依赖的实体状态是否为 active
    - 依赖的实体是否仍然存在
    """

    @property
    def pattern_name(self) -> str:
        return "consistency"

    def evaluate(self, rule: Rule, domain: DomainConfig, context: dict | None = None) -> CheckResult:
        rule_id = rule.id
        rule_name = rule.name or rule_id

        impacted = []
        for inf in domain.inferences:
            for dep_id in inf.derives_from:
                dep_entity = domain.find_entity(dep_id)
                dep_fact = domain.find_fact(dep_id)
                dep_source = dep_entity or dep_fact

                if dep_source is None:
                    impacted.append(
                        {
                            "inference": inf.id,
                            "missing_dep": dep_id,
                            "issue": "依赖实体不存在",
                        }
                    )
                elif (
                    not isinstance(dep_source, Fact)
                    and hasattr(dep_source, "status")
                    and dep_source.status == "deprecated"
                ):
                    impacted.append(
                        {
                            "inference": inf.id,
                            "missing_dep": dep_id,
                            "issue": f"依赖实体已废弃 (status={dep_source.status})",
                        }
                    )

        if impacted:
            details = [f"⚠️ {rule_name}: {len(impacted)} 条依赖关系受影响"]
            for item in impacted[:10]:
                details.append(f"  ├─ {item['inference']} → {item['missing_dep']}: {item['issue']}")
            return CheckResult(
                protocol_id=rule_id,
                name=rule_name,
                passed=False,
                severity="ERROR",
                details=details,
                fixes=["重新评估受影响推论的正确性", "如事实已变化则更新推论", "如事实未变化则确认一致性"],
                meta={"impacted": impacted},
            )
        else:
            return CheckResult(
                protocol_id=rule_id,
                name=rule_name,
                passed=True,
                details=[f"✅ {rule_name}: 所有推论依赖关系一致"],
                meta={"impacted": []},
            )
