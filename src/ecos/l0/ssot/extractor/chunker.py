"""
ssot-kernel — extractor/chunker.py
====================================
文档结构感知的智能分块 + 轻量级中文专名提取。

核心能力：
1. AST 分块：基于 MarkdownParser 的树结构，按章节边界分块
2. 专名提取：模式匹配，从中文文本中提取人名、组织名、数字指标
3. LLM 分块调度：每块是完整的章节，不截断

不依赖 jieba 等外部词典。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .markdown_ast import DocNode, MarkdownParser

# ── 专名模式 ──────────────────────────────────────

# 人名后缀（中文语境）
_PERSON_TITLE_PATTERNS = [
    r"(?<![一-鿿])([一-鿿]{2,4})(?:书记|区长|主任|校长|院长|主席|部长|局长|司长|处长|科长|组长|经理|总裁|CEO|总监|教授|研究员|院士)",
    r"(?<![一-鿿])([一-鿿]{2,4})(?:同志|先生|女士|老师)",
]

# 组织名后缀（排除动词和介词前缀）
_ORG_PATTERNS = [
    r"(?:(?:中国|北京|国家|全国|高校)[一-鿿]{2,8}(?:中心|集团|公司|委员会|大学|学院))",
    r"(?<![一-鿿的与和及了])([一-鿿]{4,12}(?:中心|集团|公司|委员会|办公室|委员会|局|处|部|院|所|校|会|联盟|平台))(?![一-鿿的与和及了])",
    r"([一-鿿]{2,8}(?:大学|学院|研究所|实验室))",
]

# 数字指标
_METRIC_PATTERNS = [
    r"(\d+[一-鿿]*(?:项|个|家|所|亿|万|万元|亿元|人|名|处|次|%|％))",
]

# 中文姓名（2-4字中文字符）
_CHINESE_NAME = r"([一-鿿]{2,4})"


@dataclass
class Chunk:
    """一个文档分块"""

    index: int  # 块序号
    content: str  # 块文本内容
    char_count: int = 0  # 字符数
    token_estimate: int = 0  # 预估 token 数（中文约 1.8 字符/token）
    headings: list[str] = field(default_factory=list)  # 包含的标题路径
    entities: list[str] = field(default_factory=list)  # 提取的专名

    @property
    def summary(self) -> str:
        return f"块{self.index}: {self.char_count}字 ~{self.token_estimate}tokens [{'; '.join(self.headings[:3])}]"


@dataclass
class NamedEntity:
    """提取出的命名实体"""

    text: str  # 实体的文本
    type: str  # person / org / metric / title
    position: int = 0  # 在原文中的位置
    confidence: float = 0.5  # 置信度


class Chunker:
    """文档分块器：按 AST 章节边界 + token 限制分块"""

    def __init__(self, max_chars: int = 6000):
        self.max_chars = max_chars  # 每块最大字符数（中文约 1.8 字符/token）

    def chunk_by_sections(self, text: str) -> list[Chunk]:
        """按章节边界分块，每块不超过 max_chars"""
        doc = MarkdownParser().parse(text)
        chunks = []
        current_chunk_lines: list[str] = []
        current_chars = 0
        chunk_index = 0
        heading_path: list[str] = []

        def flush():
            nonlocal chunk_index, current_chunk_lines, current_chars
            if not current_chunk_lines:
                return
            content = "\n".join(current_chunk_lines)
            entities = extract_entities(content)
            chunks.append(
                Chunk(
                    index=chunk_index,
                    content=content,
                    char_count=current_chars,
                    token_estimate=int(current_chars / 1.8),
                    headings=list(heading_path),
                    entities=[e.text for e in entities if e.confidence > 0.5],
                )
            )
            chunk_index += 1
            current_chunk_lines = []
            current_chars = 0

        def walk_node(node: DocNode, lines_ref: list[str]):
            nonlocal current_chunk_lines, current_chars

            if node.type == "heading":
                heading_path.append(node.title[:30])

            # 获取这个节点的原文行
            node_text = (
                node.to_text()
                if node.type != "heading"
                else f"{'#' * node.level} {node.title}"
            )
            node_lines = node_text.split("\n")
            node_chars = len(node_text)

            # 如果当前块+这个节点超限，先刷新
            if current_chars + node_chars > self.max_chars and current_chars > 0:
                flush()

            current_chunk_lines.extend(node_lines)
            current_chars += node_chars

            # 递归子节点
            for child in node.children:
                walk_node(child, lines_ref)

            if node.type == "heading":
                heading_path.pop()

        # 初始标题行
        lines = text.split("\n")
        for top_node in doc:
            walk_node(top_node, lines)

        flush()  # 最后一块
        return chunks

    def chunk_for_llm(self, text: str, max_chars: int | None = None) -> list[Chunk]:
        """生成适合 LLM 处理的分块。每块是完整的章节子树。"""
        if max_chars:
            self.max_chars = max_chars
        return self.chunk_by_sections(text)


# ── 专名提取 ──────────────────────────────────────


def extract_entities(text: str) -> list[NamedEntity]:
    """从文本中提取命名实体（人名、组织名、数字指标）

    纯模式匹配，不依赖外部词典。
    """
    entities = []
    seen = set()

    def add(etype: str, name: str, pos: int, conf: float = 0.6):
        key = f"{etype}:{name}"
        if key not in seen and len(name) >= 2:
            seen.add(key)
            entities.append(
                NamedEntity(text=name, type=etype, position=pos, confidence=conf)
            )

    # 1. 提取带职位的人名
    for pattern in _PERSON_TITLE_PATTERNS:
        for m in re.finditer(pattern, text):
            try:
                name = m.group(1)
            except IndexError:
                continue
            # 排除非人名词汇
            if name not in ("中心", "集团", "委员会", "办公室", "中国", "北京", "国家"):
                add("person", name, m.start(), 0.7)

    # 2. 提取组织名
    for pattern in _ORG_PATTERNS:
        for m in re.finditer(pattern, text):
            try:
                name = m.group(1)
            except IndexError:
                continue
            if len(name) >= 4:
                add("org", name, m.start(), 0.65)

    # 3. 提取数字指标
    for pattern in _METRIC_PATTERNS:
        for m in re.finditer(pattern, text):
            try:
                metric = m.group(1)
            except IndexError:
                continue
            add("metric", metric, m.start(), 0.8)

    # 4. 去重排序
    entities.sort(key=lambda e: -e.confidence)
    return entities


def extract_orgs(text: str) -> list[str]:
    """快速提取组织名"""
    return [e.text for e in extract_entities(text) if e.type == "org"]


def extract_persons(text: str) -> list[str]:
    """快速提取人名"""
    return [e.text for e in extract_entities(text) if e.type == "person"]
