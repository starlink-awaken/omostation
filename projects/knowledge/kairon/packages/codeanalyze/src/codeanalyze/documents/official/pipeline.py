"""公文/政策文档分析管线 — 目录扫描 + 元数据提取 + 报告生成"""

from __future__ import annotations

import logging
from pathlib import Path

from codeanalyze.documents.official.models import PolicyDocument, PolicyGraph  # type: ignore[import-not-found]
from codeanalyze.documents.official.parsers import (  # type: ignore[import-not-found]
    _clean_title,
    _extract_doc_number,
    extract_file_content,
)

logger = logging.getLogger(__name__)

MAX_PREVIEW_CHARS = 5000

_LEVEL_PATTERNS = [
    ("国家级", ["国务院", "国家", "全国", "中央", "中办", "国办"]),
    ("部委级", ["部", "委", "总局", "总署", "银保监", "证监会", "发改委"]),
    ("北京市级", ["北京", "京", "市局", "市教委", "市科委", "市经信"]),
    ("房山区级", ["房山"]),
]


def _guess_level_from_path_or_name(filepath: str, title: str = "") -> str:
    """从路径或文件名中猜测政策层级"""
    combined = f"{filepath} {title}".lower()
    for level, keywords in _LEVEL_PATTERNS:
        for kw in keywords:
            if kw.lower() in combined:
                return level
    return "其他"


def _extract_domain_from_path(filepath: str) -> str:
    """从文件路径中提取业务领域"""
    path = Path(filepath)
    parent = path.parent.name if path.parent.name != "." else ""
    grandparent = path.parent.parent.name if path.parent.parent else ""

    domain_map = {
        "人才": "人才政策",
        "科技": "科技政策",
        "教育": "教育政策",
        "产业": "产业政策",
        "金融": "金融政策",
        "医疗": "医疗政策",
        "住房": "住房政策",
        "税务": "税务政策",
        "环保": "环保政策",
        "数据": "数据政策",
        "AI": "人工智能",
        "政策法规": "通用政策",
        "资金申报": "资金政策",
        "中试": "中试平台",
        "概念验证": "概念验证",
        "成果转化": "科技成果转化",
        "中小试": "中试平台",
        "通知": "通用政策",
        "办法": "通用政策",
        "方案": "通用政策",
        "细则": "通用政策",
        "意见": "通用政策",
    }
    for keyword, domain in domain_map.items():
        if keyword in parent or keyword in grandparent:
            return domain
    return "通用政策"


def analyze_policy_directory(root_path: str) -> PolicyGraph:
    """分析公文/政策文档目录，返回结构化结果"""
    root = Path(root_path).resolve()
    graph = PolicyGraph()

    if not root.is_dir():
        logger.warning("路径不是目录: %s", root_path)
        return graph

    # 遍历所有政策文档文件
    extensions = {".pdf", ".docx", ".doc", ".xlsx", ".md", ".txt"}
    files = [f for f in root.rglob("*") if f.suffix.lower() in extensions and not f.name.startswith(".")]

    for fp in sorted(files):
        filename = fp.name
        rel_path = str(fp.relative_to(root))

        doc = PolicyDocument(
            path=fp,
            filename=filename,
            byte_size=fp.stat().st_size,
            file_type=fp.suffix.lower(),
        )

        doc.title = _clean_title(filename)
        doc.level = _guess_level_from_path_or_name(rel_path, filename)
        doc.domain = _extract_domain_from_path(rel_path)

        # 提取文号
        doc_nums = _extract_doc_number(filename)
        if doc_nums:
            doc.doc_number = doc_nums[0]

        # 提取内容
        content_text = extract_file_content(fp)
        if content_text:
            doc.content_preview = content_text[:500]
            doc.abstract = content_text[:200]

            # 从内容中再找文号
            more_nums = _extract_doc_number(fp.name, content_text)
            existing = set(doc_nums)
            for n in more_nums:
                if n not in existing:
                    existing.add(n)
                    if not doc.doc_number:
                        doc.doc_number = n
                        break

        graph.documents.append(doc)

    # 建层级索引
    for level in ["国家级", "部委级", "北京市级", "房山区级", "其他"]:
        docs = [d for d in graph.documents if d.level == level]
        if docs:
            graph.level_groups[level] = docs

    # 建领域索引
    domain_set = sorted(set(d.domain for d in graph.documents))
    for domain in domain_set:
        docs = [d for d in graph.documents if d.domain == domain]
        if docs:
            graph.domain_groups[domain] = docs

    return graph


def format_policy_graph_report(graph: PolicyGraph) -> str:
    """生成政策分析报告 Markdown"""
    lines = [
        "# 公文/政策分析报告",
        "",
        "## 概览",
        f"- 政策文档总数: {graph.total_count}",
        "",
        "## 按层级分布",
    ]
    for level in ["国家级", "部委级", "北京市级", "房山区级", "其他"]:
        docs = graph.level_groups.get(level, [])
        lines.append(f"- **{level}**: {len(docs)} 个文档")
        for d in docs[:5]:
            dn = f" | {d.doc_number}" if d.doc_number else ""
            lines.append(f"  - {d.title}{dn}")
        if len(docs) > 5:
            lines.append(f"  - ... 还有 {len(docs) - 5} 个")

    lines.extend(["", "## 按业务领域分布"])
    for domain, docs in sorted(graph.domain_groups.items()):
        lines.append(f"- **{domain}**: {len(docs)} 个文档")

    lines.extend(["", "## 关系", f"- 共 {len(graph.relationships)} 条关系"])
    for rel in graph.relationships[:20]:
        lines.append(f"- {rel.get('source')} --[{rel.get('type', '关联')}]--> {rel.get('target')}")
    if len(graph.relationships) > 20:
        lines.append(f"- ... 还有 {len(graph.relationships) - 20} 条")

    return "\n".join(lines)
