"""
ssot-kernel — extractor/interactive.py
=======================================
交互式提取器：通过对话引导用户完成结构化提取。

设计用于 Claude 与用户的交互场景——Claude 读取原始内容，
用预定义的结构化槽位向用户提问，逐步引导形成完整的 YAML 配置。

不是自动化脚本，是"对话脚手架"。
"""

from __future__ import annotations

from typing import Any

from .base import ExtractionCandidate, ExtractionResult, Extractor, TextSource

# 预定义的提取模板：每一种"要提取什么"对应一组问题
EXTRACTION_TEMPLATES = {
    "entity": {
        "title": "实体",
        "id_prefix": "ORG-/ROL-/PRJ-",
        "questions": [
            ("id", "实体 ID（如 ORG-国转中心）"),
            ("type", "类型（Organization/Role/Project/Resource）"),
            ("name", "名称"),
            ("status", "状态（active/draft/deprecated）"),
            ("attributes.nature", "本质描述"),
            ("attributes.mechanism", "运行机制（如有）"),
            ("source", "信息来源"),
        ],
    },
    "fact_policy": {
        "title": "政策事实",
        "id_prefix": "POL-",
        "questions": [
            ("id", "编号（如 POL-P-F15）"),
            ("title", "标题"),
            ("level", "层级（1-4）"),
            ("authority", "发布主体"),
            ("date", "发布日期"),
            ("summary", "核心表述摘要"),
            ("source", "来源出处"),
        ],
    },
    "fact_data": {
        "title": "数据事实",
        "id_prefix": "DAT-",
        "questions": [
            ("id", "编号（如 DAT-D-F19）"),
            ("title", "指标名称"),
            ("value", "数值"),
            ("unit", "单位"),
            ("source", "来源"),
            ("date", "采集时间"),
            ("warnings", "口径说明/⚠️ 注意"),
        ],
    },
    "inference": {
        "title": "推论",
        "id_prefix": "INF-",
        "questions": [
            ("id", "推论 ID（如 INF-L7）"),
            ("title", "推论标题"),
            ("derives_from", "依赖事实编号列表"),
            ("logic", "推导逻辑"),
            ("conclusion", "结论"),
            ("theory", "理论支撑（如有）"),
        ],
    },
    "rule": {
        "title": "规则",
        "id_prefix": "R-INF-",
        "questions": [
            ("id", "规则 ID"),
            ("pattern", "规则模式（contradiction / consistency / theory_match 等）"),
            ("name", "规则名称"),
            ("premises", "前提条件（条件表达式列表）"),
            ("logic", "推导逻辑描述"),
        ],
    },
    "relation": {
        "title": "关系",
        "id_prefix": "（无）",
        "questions": [
            ("source_id", "源实体 ID"),
            (
                "relation_type",
                "关系类型（part_of / derives_from / interlocks_with 等）",
            ),
            ("target_id", "目标实体 ID"),
        ],
    },
}


class InteractivePromptBuilder:
    """交互式提取的提示词构建器。

    用法：
        1. Claude 调用 build_prompt(source) 得到一组问题
        2. 逐一或批量问用户
        3. 用户回答后调用 build_candidates(answers) 得到结构化候选
    """

    def __init__(self, template_name: str = "entity"):
        self.template: dict[str, Any] = EXTRACTION_TEMPLATES.get(
            template_name, EXTRACTION_TEMPLATES["entity"]
        )
        self.answers: dict[str, str] = {}

    def build_prompt(self, source: TextSource) -> str:
        """构建向用户提问的前言"""
        tpl = self.template
        lines = [
            f"## 提取：{tpl['title']}",
            "",
            f"从以下内容提取{tpl['title']}信息：",
            "",
            "```",
            source.raw_text[:500],
            "```"
            if len(source.raw_text) <= 500
            else f"（{len(source.raw_text)}字，过长已截断）",
            "",
            f"ID 前缀约定：{tpl['id_prefix']}",
            "",
            "请逐项填写：",
        ]
        for i, (field, question) in enumerate(tpl["questions"], 1):
            val = self.answers.get(field, "_")
            lines.append(f"  {i}. {question}")
            if val != "_":
                lines.append(f"     → 当前: {val}")
        lines.append("")
        return "\n".join(lines)

    def set_answer(self, field: str, value: str):
        self.answers[field] = value

    def build_candidate(self) -> ExtractionCandidate:
        """将当前答案组装为 ExtractionCandidate"""
        content: dict[str, Any] = {}
        for field, _ in self.template["questions"]:
            val = self.answers.get(field, "")
            # 处理嵌套字段（如 attributes.nature → {attributes: {nature: val}}）
            parts = field.split(".")
            target = content
            for p in parts[:-1]:
                if p not in target:
                    target[p] = {}
                target = target[p]
            target[parts[-1]] = val

        candidate = ExtractionCandidate(
            category=self._guess_category(),
            id=content.get("id", ""),
            content=content,
            confidence=0.8
            if all(self.answers.get(f) for f, _ in self.template["questions"][:3])
            else 0.5,
        )
        return candidate

    def _guess_category(self) -> str:
        t2c = {
            "实体": "entity",
            "政策事实": "fact",
            "数据事实": "fact",
            "推论": "inference",
            "规则": "rule",
            "关系": "relation",
        }
        return t2c.get(self.template["title"], "entity")


class InteractiveExtractor(Extractor):
    """交互式提取器。

    不自动做任何提取。它的作用是提供结构化的对话模板，
    让 Claude 在聊天中引导用户完成知识提取。
    """

    @property
    def extractor_name(self) -> str:
        return "interactive"

    def extract(self, source: TextSource) -> ExtractionResult:
        return ExtractionResult(
            summary="交互式提取器不会自动提取。请使用 InteractivePromptBuilder 引导用户。"
        )

    def build_session(
        self, template_name: str, source: TextSource
    ) -> InteractivePromptBuilder:
        """创建一个交互式提取会话"""
        return InteractivePromptBuilder(template_name)
