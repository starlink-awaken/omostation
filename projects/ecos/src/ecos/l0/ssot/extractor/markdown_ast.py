"""
ssot-kernel — extractor/markdown_ast.py
=========================================
轻量级 Markdown AST 解析器。

在模板提取之前做一层文档结构解析，让提取器知道：
- 哪里有标题、什么层级
- 哪里有表格、几行几列
- 哪里有列表、多深嵌套

不依赖任何外部库，纯标准库实现。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class DocNode:
    """文档结构中的一个节点"""

    type: str  # heading / paragraph / list / list_item
    # table / code_block / blockquote / hr
    level: int = 0  # heading level / list nesting depth
    title: str = ""  # heading / list_item 的文本
    content: str = ""  # 原始文本
    children: list[DocNode] = field(default_factory=list)
    # 表格专用
    headers: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)

    def find_all(self, node_type: str, level: int = -1) -> list[DocNode]:
        """递归查找指定类型的所有节点"""
        results = []
        if self.type == node_type and (level < 0 or self.level == level):
            results.append(self)
        for c in self.children:
            results.extend(c.find_all(node_type, level))
        return results

    def to_text(self) -> str:
        """递归输出所有文本内容"""
        if self.type == "table":
            lines = []
            if self.headers:
                lines.append("| " + " | ".join(self.headers) + " |")
                lines.append("|" + "|".join("---" for _ in self.headers) + "|")
            for row in self.rows:
                lines.append("| " + " | ".join(str(c) for c in row) + " |")
            return "\n".join(lines)
        if self.type == "code_block":
            return self.content
        texts = [self.title or self.content]
        for c in self.children:
            t = c.to_text()
            if t:
                texts.append(t)
        return "\n".join(texts)

    def __repr__(self) -> str:
        return f"<{self.type} lv={self.level} title='{self.title[:20]}' kids={len(self.children)}>"


class MarkdownParser:
    """轻量级 Markdown 解析器——输出 DocNode 树"""

    def parse(self, text: str) -> list[DocNode]:
        """解析 Markdown 文本为 DocNode 列表"""
        lines = text.split("\n")
        return self._parse_lines(lines, 0, stop_level=0)[0]

    def _parse_lines(self, lines: list[str], start: int, stop_level: int = 0) -> tuple:
        """从指定行开始解析，遇到 <= stop_level 的标题时停止

        Args:
            lines: 所有行
            start: 起始行号
            stop_level: 遇到这个级别或更高的标题就停止（0表示不限制）

        Returns:
            (nodes, next_line)
        """
        nodes = []
        i = start

        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            # 空行
            if not stripped:
                i += 1
                continue

            # 代码块
            if stripped.startswith("```"):
                node, i = self._parse_code_block(lines, i)
                if node:
                    nodes.append(node)
                continue

            # 水平线
            if re.match(r"^---+$", stripped) or re.match(r"^\*\*\*+$", stripped):
                nodes.append(DocNode(type="hr", content=stripped))
                i += 1
                continue

            # 引用块
            if stripped.startswith(">"):
                node, i = self._parse_blockquote(lines, i)
                if node:
                    nodes.append(node)
                continue

            # 表格
            if "|" in stripped and i + 1 < len(lines) and "|" in lines[i + 1]:
                # 检查是否是表格（第二行是分隔线）
                next_stripped = lines[i + 1].strip()
                if re.match(r"^\|[\s:-]+\|", next_stripped):
                    node, i = self._parse_table(lines, i)
                    if node:
                        nodes.append(node)
                    continue

            # 标题
            heading_m = re.match(r"^(#{1,6})\s+(.+)$", stripped)
            if heading_m:
                level = len(heading_m.group(1))
                # 如果这个标题的级别 <= stop_level，停止收集子节点
                if stop_level > 0 and level <= stop_level:
                    break
                title = heading_m.group(2).strip()
                # 子内容的 stop_level = 当前标题级别（同级别标题会终止子内容）
                children, i = self._parse_lines(lines, i + 1, stop_level=level)
                # 如果子节点中第一个是段落而且是纯文本，作为摘要
                node = DocNode(type="heading", level=level, title=title, children=children)
                nodes.append(node)
                continue

            # 列表项
            list_m = re.match(r"^(\s*)[-*+]\s+(.+)$", line)
            if not list_m:
                list_m = re.match(r"^(\s*)\d+[.)]\s+(.+)$", line)
            if list_m:
                indent = len(list_m.group(1))
                text_content = list_m.group(2).strip()
                children, i = self._parse_list_item(lines, i + 1, indent)
                node = DocNode(type="list_item", level=indent // 2, title=text_content, children=children)
                nodes.append(node)
                continue

            # 普通段落
            node, i = self._parse_paragraph(lines, i)
            if node:
                nodes.append(node)
                continue

            i += 1

        return nodes, i

    def _parse_code_block(self, lines: list[str], start: int) -> tuple:
        """解析代码块"""
        content_lines = []
        i = start + 1
        while i < len(lines):
            if lines[i].strip().startswith("```"):
                i += 1
                break
            content_lines.append(lines[i])
            i += 1
        return DocNode(type="code_block", content="\n".join(content_lines)), i

    def _parse_blockquote(self, lines: list[str], start: int) -> tuple:
        """解析引用块"""
        content_lines = []
        i = start
        while i < len(lines) and lines[i].strip().startswith(">"):
            content_lines.append(lines[i].strip()[1:].strip())
            i += 1
        text = "\n".join(content_lines)
        # 引用块内部可能还有结构，暂简化处理
        children, _ = self._parse_lines(content_lines, 0)
        return DocNode(type="blockquote", content=text, children=children), i

    def _parse_table(self, lines: list[str], start: int) -> tuple:
        """解析表格"""
        # 表头行
        header_row = self._split_table_row(lines[start])
        if not header_row:
            return None, start + 1

        # 分隔线（跳过）
        # 数据行
        rows = []
        i = start + 2
        while i < len(lines):
            stripped = lines[i].strip()
            if not stripped.startswith("|") and "|" not in stripped:
                break
            row = self._split_table_row(lines[i])
            if row:
                rows.append(row)
            i += 1

        return DocNode(type="table", headers=header_row, rows=rows), i

    def _parse_list_item(self, lines: list[str], start: int, parent_indent: int) -> tuple:
        """解析列表项的子内容"""
        children = []
        i = start
        while i < len(lines):
            stripped = lines[i].strip()
            if not stripped:
                i += 1
                continue

            # 遇到任何标题 → 停止
            if re.match(r"^#{1,6}\s", stripped):
                break

            # 检查：缩进的列表项 → 作为子列表
            leading = len(lines[i]) - len(lines[i].lstrip())
            if stripped.startswith("- ") or stripped.startswith("* ") or re.match(r"^\d+[.)]\s", stripped):
                # 只有明确缩进的才算子项
                if leading > parent_indent:
                    indent = leading // 2
                    text = re.sub(r"^[\s]*[-*+]\s*|^\s*\d+[.)]\s*", "", lines[i]).strip()
                    children.append(DocNode(type="list_item", level=indent, title=text))
                    i += 1
                    continue
                # 同缩进的新列表项 → 不是子项，停止收集
                elif leading <= parent_indent:
                    break
            else:
                i += 1
        return children, i

    def _parse_paragraph(self, lines: list[str], start: int) -> tuple:
        """解析段落（连续的非空行直到遇到空行）"""
        content_lines = []
        i = start
        while i < len(lines):
            stripped = lines[i].strip()
            if not stripped:
                break
            if stripped.startswith("#") or stripped.startswith("```"):
                break
            if stripped.startswith("|") and "|" in stripped:
                break
            content_lines.append(stripped)
            i += 1
        if content_lines:
            return DocNode(type="paragraph", content="\n".join(content_lines)), i
        return None, i + 1

    def _split_table_row(self, line: str) -> list[str]:
        """拆分表格行"""
        parts = line.split("|")
        # 去掉首尾空（第一个|前和最后一个|后）
        if parts and not parts[0].strip():
            parts = parts[1:]
        if parts and not parts[-1].strip():
            parts = parts[:-1]
        return [p.strip() for p in parts]


def to_mermaid(doc: list[DocNode], indent: int = 0) -> str:
    """将 DocNode 树输出为 Mermaid 格式（调试用）"""
    lines = ["graph TD"]
    _build_mermaid(doc, lines, "root", indent)
    return "\n".join(lines)


def _build_mermaid(nodes: list[DocNode], lines: list[str], parent_id: str, indent: int):
    """递归构建 Mermaid 节点"""
    for i, node in enumerate(nodes):
        node_id = f"{parent_id}_{i}"
        label = f"{node.type}:{node.level}"
        if node.title:
            label += f" {node.title[:20]}"
        lines.append(f'    {node_id}["{label}"]')
        lines.append(f"    {parent_id} --> {node_id}")
        _build_mermaid(node.children, lines, node_id, indent + 1)
