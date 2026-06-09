"""
SSOT Kernel — patterns/theory_match.py
理论匹配模式 (R-INF-002)

为推论匹配适用的理论支撑。
泛化后：从推论的类型标签查找预定义的理论映射表。
"""

from ..meta_model import DomainConfig, Rule
from .base import BasePattern, CheckResult

# 预定义的理论映射表（领域无关）
# 可在 domain.yaml 中覆盖
DEFAULT_THEORIES = {
    "组织管理困境": {
        "theories": ["双元性组织理论 (Tushman & O'Reilly, 1996)"],
        "scope": "探索性活动和利用性活动需要不同的组织结构、文化和激励",
    },
    "激励错配": {
        "theories": [
            "委托代理理论 (Jensen & Meckling, 1976)",
            "信息不对称理论 (Akerlof, 1970)",
        ],
        "scope": "当利益不一致且信息不对称时，代理人采取机会主义行为",
    },
    "风险决策": {
        "theories": ["财产规则 vs 责任规则 (Calabresi & Melamed, 1972)"],
        "scope": "事前审批(高交易成本) vs 事后赔偿(低交易成本)",
    },
    "平台经济": {
        "theories": ["固定成本分摊理论", "CAPEX/OPEX错配理论"],
        "scope": "固定投资的规模化收益依赖利用率",
    },
}


class TheoryMatchPattern(BasePattern):
    """理论匹配模式。"""

    @property
    def pattern_name(self) -> str:
        return "theory_match"

    def evaluate(
        self, rule: Rule, domain: DomainConfig, context: dict | None = None
    ) -> CheckResult:
        rule_id = rule.id
        rule_name = rule.name or rule_id

        # 检查推论的理论匹配状态
        matched: list[dict[str, str | bool]] = []
        unmatched = []

        for inf in domain.inferences:
            if inf.theory:
                matched.append({"inference": inf.id, "theory": inf.theory})
                continue

            # 尝试自动匹配
            conclusion_lower = inf.conclusion.lower()
            found_theory = None
            for keyword, theory_info in DEFAULT_THEORIES.items():
                if keyword.lower() in conclusion_lower:
                    found_theory = theory_info
                    break

            if found_theory:
                matched.append(
                    {
                        "inference": inf.id,
                        "theory": found_theory["theories"][0],
                        "auto_matched": True,
                    }
                )
            else:
                unmatched.append(
                    {"inference": inf.id, "conclusion": inf.conclusion[:60]}
                )

        details = [f"📊 {rule_name}: {len(matched)} 已匹配 / {len(unmatched)} 未匹配"]
        for m in matched[:5]:
            label = "🔗" if not m.get("auto_matched") else "🔄"
            theory = m["theory"]
            details.append(
                f"  ├─ {label} {m['inference']}: {theory[:50] if isinstance(theory, str) else theory}"
            )

        return CheckResult(
            protocol_id=rule_id,
            name=rule_name,
            passed=len(unmatched) == 0,
            severity="WARN",
            details=details,
            fixes=["为未匹配推论添加理论支撑"] if unmatched else [],
            meta={"matched": matched, "unmatched": unmatched},
        )
