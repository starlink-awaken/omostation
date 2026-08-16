from __future__ import annotations

#!/usr/bin/env python3
"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Authority Graph ≡ Module
# 内涵 ≝ {Authority, Graph}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, AuthorityGraph)}
# 功能 ⊢ {Authority_Graph, Init_Authority, Validate_Graph}
# =============================================================================

# ---
# Type: Module
# Status: ACTIVE
# Layer: L3
# ---
"""
Authority Graph - 文档权威引用图谱

功能:
- 构建文档间的引用关系图
- 检测孤立文档 (无引用、无被引用)
- 检测断裂链接 (引用不存在的文档)
- 检测循环依赖
- 可视化依赖关系
- 计算文档影响力分数

Usage:
    python3 -m organs.D_Logos.organs.authority_graph --scan docs/ --output graph.json
    python3 -m organs.D_Logos.organs.authority_graph --scan docs/ --visualize
    python3 -m organs.D_Logos.organs.authority_graph --check-orphans
    python3 -m organs.D_Logos.organs.authority_graph --check-broken-links
"""


import argparse
import json
import logging
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import networkx as nx
except ImportError:
    nx = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
_log = logging.getLogger(__name__)


@dataclass
class DocumentNode:
    """文档节点"""

    file_path: Path
    doc_type: str = "unknown"
    status: str = "unknown"
    authority: str = ""
    layer: str = ""

    # 引用关系
    references: set[str] = field(default_factory=set)  # 引用的文档
    referenced_by: set[str] = field(default_factory=set)  # 被谁引用

    # 元数据
    word_count: int = 0
    last_updated: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": str(self.file_path),
            "doc_type": self.doc_type,
            "status": self.status,
            "authority": self.authority,
            "layer": self.layer,
            "references_count": len(self.references),
            "referenced_by_count": len(self.referenced_by),
            "word_count": self.word_count,
            "last_updated": self.last_updated,
        }


@dataclass
class GraphAnalysis:
    """图谱分析结果"""

    total_nodes: int
    total_edges: int
    orphan_docs: list[str]  # 孤立文档
    broken_links: list[tuple[str, str]]  # (source, target) 断裂链接
    circular_dependencies: list[list[str]]  # 循环依赖
    root_documents: list[str]  # 根文档 (高影响力)
    leaf_documents: list[str]  # 叶文档 (只被引用，不引用别人)
    avg_references_per_doc: float
    max_depth: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_nodes": self.total_nodes,
            "total_edges": self.total_edges,
            "orphan_docs": self.orphan_docs,
            "broken_links": self.broken_links,
            "circular_dependencies": self.circular_dependencies,
            "root_documents": self.root_documents,
            "leaf_documents": self.leaf_documents,
            "avg_references_per_doc": round(self.avg_references_per_doc, 2),
            "max_depth": self.max_depth,
        }


class AuthorityGraph:
    """文档权威引用图谱"""

    def __init__(self) -> None:
        self.nodes: dict[str, DocumentNode] = {}
        self.graph = nx.DiGraph() if nx else None
        self.all_files: set[str] = set()

    def build(self, scan_dir: Path, pattern: str = "**/*.md") -> AuthorityGraph:
        """构建图谱"""
        start_time = time.time()
        _log.info(f"Building authority graph from {scan_dir}")

        # 1. 收集所有文档
        all_files = list(scan_dir.glob(pattern))
        self.all_files = {str(f.relative_to(scan_dir.parent.parent)) for f in all_files}
        _log.info(f"Found {len(all_files)} documents")

        # 2. 解析每个文档的元数据和引用
        for file_path in all_files:
            node = self._parse_document(file_path, scan_dir)
            rel_path = str(file_path.relative_to(scan_dir.parent.parent))
            self.nodes[rel_path] = node

            if self.graph:
                self.graph.add_node(rel_path, **node.to_dict())

        # 3. 构建引用关系
        self._build_relationships()

        duration = time.time() - start_time
        _log.info(f"Built graph with {len(self.nodes)} nodes in {duration:.2f}s")

        return self

    def _parse_document(self, file_path: Path, base_dir: Path) -> DocumentNode:
        """解析单个文档"""
        content = file_path.read_text(encoding="utf-8")
        lines = content.split("\n")

        node = DocumentNode(file_path=file_path, word_count=len(content.split()))

        # 解析 frontmatter
        in_frontmatter = False
        frontmatter_lines = []
        for line in lines:
            if line.strip() == "---":
                if not in_frontmatter:
                    in_frontmatter = True
                else:
                    break
            elif in_frontmatter:
                frontmatter_lines.append(line)

        # 提取字段
        fm_text = "\n".join(frontmatter_lines)

        for field_pattern in [
            (r"Type:\s*(.+)", "doc_type"),
            (r"Status:\s*(.+)", "status"),
            (r"Authority:\s*(.+)", "authority"),
            (r"Layer:\s*(.+)", "layer"),
            (r"Updated:\s*(.+)", "last_updated"),
        ]:
            match = re.search(field_pattern[0], fm_text)
            if match:
                value = match.group(1).strip().strip("\"'")
                setattr(node, field_pattern[1], value)

        # 提取引用（Markdown 链接和显式引用）
        # 模式 1: [text](path.md)
        link_pattern = r"\[([^\]]+)\]\(([^)]+\.md)\)"
        for match in re.finditer(link_pattern, content):
            ref_path = match.group(2)
            # 规范化路径
            if not ref_path.startswith("/"):
                ref_path = str(file_path.parent / ref_path)
            node.references.add(ref_path)

        # 模式 2: Authority 字段引用
        if node.authority and not node.authority.startswith("http"):
            node.references.add(node.authority)

        return node

    def _build_relationships(self) -> None:
        """构建引用关系"""
        # 建立反向引用索引
        for rel_path, node in self.nodes.items():
            for ref in node.references:
                if ref in self.nodes:
                    self.nodes[ref].referenced_by.add(rel_path)

                    if self.graph:
                        self.graph.add_edge(rel_path, ref)

    def analyze(self) -> GraphAnalysis:
        """分析图谱"""
        _log.info("Analyzing authority graph")

        if not self.graph or nx is None:
            return self._simple_analysis()

        # 孤立文档：没有引用也没有被引用
        orphan_docs = []
        for node_id, _node_data in self.graph.nodes(data=True):
            in_degree = self.graph.in_degree(node_id)
            out_degree = self.graph.out_degree(node_id)
            if in_degree == 0 and out_degree == 0:
                orphan_docs.append(node_id)

        # 断裂链接：引用不存在的节点
        broken_links = []
        for source, data in self.graph.nodes(data=True):
            refs = data.get("references", set())
            for ref in refs:
                if ref not in self.graph.nodes:
                    broken_links.append((source, ref))

        # 循环依赖
        circular_deps = [list(cycle) for cycle in nx.simple_cycles(self.graph)]

        # 根文档：入度高，出度也高（影响力大）
        root_docs: list[str] = [
            n
            for n, d in sorted(
                [(n, d) for n, d in self.graph.nodes(data=True)],
                key=lambda x: x[1].get("referenced_by_count", 0),
                reverse=True,
            )
        ][:10]

        # 叶文档：只被引用，不引用别人
        leaf_docs = []
        for node_id in self.graph.nodes:
            in_deg = self.graph.in_degree(node_id)
            out_deg = self.graph.out_degree(node_id)
            if in_deg > 0 and out_deg == 0:
                leaf_docs.append(node_id)

        # 平均引用数
        total_refs = sum(len(self.nodes[n].references) for n in self.nodes)
        avg_refs = total_refs / len(self.nodes) if self.nodes else 0

        # 最大深度
        try:
            max_depth = nx.dag_longest_path_length(self.graph)
        except nx.NetworkXUnbounded:
            max_depth = -1  # 有环

        return GraphAnalysis(
            total_nodes=len(self.nodes),
            total_edges=self.graph.number_of_edges(),
            orphan_docs=orphan_docs,
            broken_links=broken_links,
            circular_dependencies=circular_deps,
            root_documents=root_docs,
            leaf_documents=leaf_docs,
            avg_references_per_doc=avg_refs,
            max_depth=max_depth,
        )

    def _simple_analysis(self) -> GraphAnalysis:
        """简化分析（无 networkx）"""
        orphan_docs = []
        broken_links = []

        for rel_path, node in self.nodes.items():
            if not node.references and not node.referenced_by:
                orphan_docs.append(rel_path)

            for ref in node.references:
                if ref not in self.nodes:
                    broken_links.append((rel_path, ref))

        total_refs = sum(len(n.references) for n in self.nodes.values())
        avg_refs = total_refs / len(self.nodes) if self.nodes else 0

        return GraphAnalysis(
            total_nodes=len(self.nodes),
            total_edges=sum(len(n.references) for n in self.nodes.values()),
            orphan_docs=orphan_docs,
            broken_links=broken_links,
            circular_dependencies=[],
            root_documents=list(self.nodes.keys())[:10],
            leaf_documents=[],
            avg_references_per_doc=avg_refs,
            max_depth=-1,
        )

    def get_influence_score(self, doc_path: str) -> float:
        """计算文档影响力分数"""
        if doc_path not in self.nodes:
            return 0.0

        node = self.nodes[doc_path]

        # 简单算法：被引用次数 * 2 + 引用次数
        score = len(node.referenced_by) * 2 + len(node.references)

        # 归一化到 0-100
        max_possible = len(self.nodes) * 3
        return min(100.0, (score / max_possible) * 100) if max_possible > 0 else 0

    def export_json(self, output_path: Path) -> None:
        """导出 JSON"""
        data = {
            "timestamp": datetime.now().isoformat(),
            "total_documents": len(self.nodes),
            "documents": {k: v.to_dict() for k, v in self.nodes.items()},
            "analysis": self.analyze().to_dict(),
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        _log.info(f"Exported graph to {output_path}")

    def visualize_ascii(self) -> str:
        """ASCII 可视化"""
        lines = []
        lines.append("=" * 80)
        lines.append("AUTHORITY GRAPH VISUALIZATION")
        lines.append("=" * 80)

        analysis = self.analyze()
        lines.append(f"Total Documents: {analysis.total_nodes}")
        lines.append(f"Total References: {analysis.total_edges}")
        lines.append(f"Orphan Docs: {len(analysis.orphan_docs)}")
        lines.append(f"Broken Links: {len(analysis.broken_links)}")
        lines.append("")

        # Top 10 根文档
        lines.append("Top 10 Root Documents (Most Referenced):")
        for i, doc in enumerate(analysis.root_documents[:10], 1):
            node = self.nodes.get(doc)
            ref_count = len(node.referenced_by) if node else 0
            lines.append(f"  {i:2d}. [{ref_count:3d} refs] {doc}")

        lines.append("")

        # 孤立文档
        if analysis.orphan_docs:
            lines.append(f"Orphan Documents ({len(analysis.orphan_docs)}):")
            for doc in analysis.orphan_docs[:10]:
                lines.append(f"  - {doc}")
            if len(analysis.orphan_docs) > 10:
                lines.append(f"  ... and {len(analysis.orphan_docs) - 10} more")

        lines.append("=" * 80)

        return "\n".join(lines)


def main() -> None:
    """CLI 入口"""
    parser = argparse.ArgumentParser(description="Authority Graph - Document Reference Network")
    parser.add_argument("--scan", type=str, required=True, help="Directory to scan")
    parser.add_argument("--output", type=str, help="Output JSON file")
    parser.add_argument("--visualize", action="store_true", help="Show ASCII visualization")
    parser.add_argument("--check-orphans", action="store_true", help="Check for orphan documents")
    parser.add_argument("--check-broken-links", action="store_true", help="Check for broken links")
    parser.add_argument("--pattern", type=str, default="**/*.md", help="File pattern")

    args = parser.parse_args()

    scan_dir = Path(args.scan)
    if not scan_dir.exists():
        _log.error(f"Directory not found: {scan_dir}")
        sys.exit(1)

    # 构建图谱
    graph = AuthorityGraph()
    graph.build(scan_dir, pattern=args.pattern)

    # 分析
    analysis = graph.analyze()

    # 输出
    if args.visualize:
        print(graph.visualize_ascii())

    if args.check_orphans:
        print(f"\nOrphan Documents: {len(analysis.orphan_docs)}")
        for doc in analysis.orphan_docs[:20]:
            print(f"  - {doc}")

    if args.check_broken_links:
        print(f"\nBroken Links: {len(analysis.broken_links)}")
        for source, target in analysis.broken_links[:20]:
            print(f"  - {source} → {target}")

    if args.output:
        graph.export_json(Path(args.output))
        print(f"\nGraph exported to: {args.output}")

    # 打印摘要
    print("\n" + "=" * 80)
    print("GRAPH SUMMARY")
    print("=" * 80)
    print(f"Total Documents: {analysis.total_nodes}")
    print(f"Total References: {analysis.total_edges}")
    print(f"Average References per Doc: {analysis.avg_references_per_doc:.2f}")
    print(f"Orphan Documents: {len(analysis.orphan_docs)}")
    print(f"Broken Links: {len(analysis.broken_links)}")
    print(f"Circular Dependencies: {len(analysis.circular_dependencies)}")
    print("=" * 80)


if __name__ == "__main__":
    main()
