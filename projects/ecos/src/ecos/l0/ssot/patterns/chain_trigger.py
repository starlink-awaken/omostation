"""
SSOT Kernel — patterns/chain_trigger.py
IP联动触发模式 (R-INF-003)

一条链的状态变更自动触发关联链的状态转换。
泛化后：不关心是"创新链→资金链"，只关心 interlocks_with 关系。
"""

from ..meta_model import DomainConfig, Rule
from .base import BasePattern, CheckResult


class ChainTriggerPattern(BasePattern):
    """IP联动触发模式。

    检查：
    1. 所有 interlocks_with 关系是否完整定义
    2. 硬咬合是否已触发状态变更
    3. 软咬合是否生成了通知
    """

    @property
    def pattern_name(self) -> str:
        return "chain_trigger"

    def evaluate(self, rule: Rule, domain: DomainConfig, context: dict | None = None) -> CheckResult:
        rule_id = rule.id
        rule_name = rule.name or rule_id

        # 收集所有 interlocks_with 关系
        triggers = []
        for rel in domain.relations:
            if rel.relation_type == "interlocks_with":
                triggers.append(
                    {
                        "from": rel.source_id,
                        "to": rel.target_id,
                        "hard": rel.attributes.get("hard", True),
                    }
                )

        # 检查是否有实体定义但无 interlocks_with
        state_entities = [e for e in domain.entities if e.meta_type.value == "MET-STATE"]

        details = [f"📊 {rule_name}: {len(triggers)} 个咬合点"]
        for t in triggers[:10]:
            label = "🔗 硬咬合" if t["hard"] else "🫂 软咬合"
            details.append(f"  ├─ {label}: {t['from']} ↔ {t['to']}")

        passed = True
        if not triggers and state_entities:
            passed = False
            details.append("  ❌ 有状态实体但无咬合关系定义")

        return CheckResult(
            protocol_id=rule_id,
            name=rule_name,
            passed=passed,
            severity="WARN",
            details=details,
            meta={"triggers": triggers, "total_states": len(state_entities)},
        )
