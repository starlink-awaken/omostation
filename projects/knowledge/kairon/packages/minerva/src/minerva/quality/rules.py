from __future__ import annotations

"""
质量验证规则

Extracted from SharedBrain D_Harvest → minerva.
"""
from minerva.extractors.base import StructuredKnowledge


class LengthRule:
    """长度规则"""

    def __init__(self, min_len: int = 50, max_len: int = 100000) -> None:
        self.min_len = min_len
        self.max_len = max_len

    @property
    def name(self) -> str:
        return "length"

    async def evaluate(self, knowledge: StructuredKnowledge) -> float:
        length = len(knowledge.body)
        if self.min_len <= length <= self.max_len:
            return 0.3
        return 0.0


class LanguageRule:
    """语言质量规则"""

    @property
    def name(self) -> str:
        return "language"

    async def evaluate(self, knowledge: StructuredKnowledge) -> float:
        # 简单检查：是否包含有意义的文本
        if self._is_meaningful_content(knowledge.body):
            return 0.3
        return 0.0

    def _is_meaningful_content(self, text: str) -> bool:
        """检查是否是有意义的内容"""
        # 检查是否包含字母或数字
        return any(c.isalnum() for c in text)


class StructureRule:
    """结构完整性规则"""

    @property
    def name(self) -> str:
        return "structure"

    async def evaluate(self, knowledge: StructuredKnowledge) -> float:
        score = 0.0

        # 检查标题
        if knowledge.title and len(knowledge.title) > 5:
            score += 0.2

        # 检查元数据
        if knowledge.metadata:
            score += 0.1

        return score


class EncodingRule:
    """编码规则"""

    @property
    def name(self) -> str:
        return "encoding"

    async def evaluate(self, knowledge: StructuredKnowledge) -> float:
        # 简单检查：是否为有效的UTF-8
        try:
            knowledge.body.encode("utf-8").decode("utf-8")
            return 0.2
        except UnicodeError:
            return 0.0
