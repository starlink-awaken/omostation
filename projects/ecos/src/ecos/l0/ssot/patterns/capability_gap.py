"""
SSOT Kernel — patterns/capability_gap.py
能力缺失检测模式 (R-INF-005)

当业务设计需要某个能力，但领域实例中不存在对应的实现载体时，标记缺失。
泛化后：不关心具体能力是什么，只检查"推论的结论 → 实体实例"的覆盖。
"""

from ..meta_model import DomainConfig, Rule
from .base import BasePattern, CheckResult


class CapabilityGapPattern(BasePattern):
    """能力缺失检测模式。

    流程：
    1. 找出所有推论中的"需要能力X来实现策略Y"的断言
    2. 检查领域实体中是否存在对应的能力实现
    3. 产出能力覆盖报告
    """

    @property
    def pattern_name(self) -> str:
        return "capability_gap"

    def evaluate(self, rule: Rule, domain: DomainConfig, context: dict | None = None) -> CheckResult:
        rule_id = rule.id
        rule_name = rule.name or rule_id

        # 从推论中提取"需要能力X"的断言
        gaps = []
        covered = []

        for inf in domain.inferences:
            conclusion = inf.conclusion
            # 查找 "需要..." 的表述
            needs = self._extract_needs(conclusion)
            for need in needs:
                # 检查是否有对应的实体
                found = any(need in e.name or need in str(e.attributes) for e in domain.entities)
                if found:
                    covered.append({"inference": inf.id, "need": need})
                else:
                    gaps.append({"inference": inf.id, "need": need, "gap": f"缺少'{need}'对应的 Resource 或 Project"})

        if gaps:
            details = [f"⚠️ {rule_name}: 发现 {len(gaps)} 项能力缺失"]
            for g in gaps[:8]:
                details.append(f"  ├─ {g['inference']}: {g['need']}")
            return CheckResult(
                protocol_id=rule_id,
                name=rule_name,
                passed=False,
                severity="WARN",
                details=details,
                fixes=["为缺失的能力添加对应的 Resource 或 Project 实体", "或在推论中补充实现路径"],
                meta={"gaps": gaps, "covered": covered},
            )
        else:
            return CheckResult(
                protocol_id=rule_id,
                name=rule_name,
                passed=True,
                details=[f"✅ {rule_name}: 能力覆盖完整 ({len(covered)} 项已覆盖)"],
                meta={"gaps": [], "covered": covered},
            )

    def _extract_needs(self, text: str) -> list[str]:
        """从文本中提取"需要X"的表述"""
        import re

        needs = []
        # 匹配 "需要..." / "need..." 等模式
        patterns = [
            r"需要([^，。,.]{2,30})",
            r"缺乏([^，。,.]{2,30})",
            r"缺少([^，。,.]{2,30})",
            r"need[s]?\s+([A-Z][a-zA-Z\s]{2,40})",
        ]
        for pat in patterns:
            for m in re.finditer(pat, text):
                need = m.group(1).strip()
                if len(need) > 2:
                    needs.append(need)
        return needs
