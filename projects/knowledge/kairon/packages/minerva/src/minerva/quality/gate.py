from __future__ import annotations

"""
质量门控 - 验证和过滤低质量内容

Extracted from SharedBrain D_Harvest → minerva.
"""
from dataclasses import dataclass
from typing import Protocol

from minerva.extractors.base import StructuredKnowledge


@dataclass
class ValidatedKnowledge:
    """验证后的知识"""

    knowledge: StructuredKnowledge
    quality_score: float
    validation_reasons: list[str] | None = None
    passed: bool = False

    def __post_init__(self) -> None:
        if self.validation_reasons is None:
            self.validation_reasons = []
        # 根据分数自动设置 passed 状态
        if self.quality_score >= 0.6:
            object.__setattr__(self, "passed", True)


class IQualityRule(Protocol):
    """质量规则接口"""

    @property
    def name(self) -> str:  # type: ignore[return]
        """规则名称"""

    async def evaluate(self, knowledge: StructuredKnowledge) -> float:  # type: ignore[return]
        """评估质量分数 (0.0-1.0)"""


class QualityGate:
    """质量门控"""

    def __init__(self) -> None:
        self.rules: list[IQualityRule] = []
        self._register_default_rules()

    def _register_default_rules(self) -> None:
        """注册默认质量规则"""
        from minerva.quality.rules import (
            EncodingRule,
            LanguageRule,
            LengthRule,
            StructureRule,
        )

        self.rules.extend([LengthRule(), LanguageRule(), StructureRule(), EncodingRule()])

    async def validate(self, items: list[StructuredKnowledge]) -> list[ValidatedKnowledge]:
        """验证知识条目 - 返回所有项目的验证结果"""
        validated: list[ValidatedKnowledge] = []

        for item in items:
            # 执行所有规则
            total_score = 0.0
            reasons: list[str] = []

            for rule in self.rules:
                score = await rule.evaluate(item)
                total_score += score
                if score > 0:
                    reasons.append(f"{rule.name}: {score:.2f}")

            # 通过阈值：总分 >= 0.6
            passed = total_score >= 0.6
            validated.append(
                ValidatedKnowledge(
                    knowledge=item,
                    quality_score=total_score,
                    validation_reasons=reasons,
                    passed=passed,
                )
            )

        return validated
