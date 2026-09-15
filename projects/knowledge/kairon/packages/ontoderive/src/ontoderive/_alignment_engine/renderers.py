from __future__ import annotations

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
# Renderers ≡ Module
# 内涵 ≝ {Renderers}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, Renderers)}
# 功能 ⊢ {Init_Renderers, Execute_Renderers, Validate_Renderers}
# =============================================================================

# ---
# domain: D-Logos
# layer: organ
# status: active
# version: 10.5.0
# owner: '@Architect'
# authority: organs/D-Logos/AGENTS.md
# ---
"""AlignmentEngine report rendering helpers."""


import json

from .models import EnhancedDiffReport  # type: ignore[reportMissingImports]


def generate_markdown_report(report: EnhancedDiffReport) -> str:
    """生成 Markdown 报告"""
    lines = [
        "# 文档-实现对齐报告 (增强版)",
        "",
        "## 总览",
        "",
        f"- **对齐率**: {report.alignment_rate:.1f}%",
        f"- **文档声明**: {report.total_declarations}",
        f"- **代码实体**: {report.total_entities}",
        f"- **已匹配**: {report.matched_count}",
        f"- **未匹配文档**: {report.unmatched_doc_count}",
        "",
        "## 差异分布 (兼容)",
        "",
        "| 类型 | 描述 | 数量 |",
        "|------|------|------|",
        f"| Type A | 文档过时，实现已变更 | {report.diff_type_a} |",
        f"| Type B | 实现缺失，文档有定义 | {report.diff_type_b} |",
        f"| Type C | 文档错误，需重新描述 | {report.diff_type_c} |",
        f"| Type D | 实现偏差，需重构代码 | {report.diff_type_d} |",
        "",
        "## 问题统计 (增强)",
        "",
        "### 按严重程度",
        "",
    ]

    for sev, count in report.by_severity.items():
        lines.append(f"- **{sev}**: {count}")

    lines.extend(
        [
            "",
            "### 按分类",
            "",
        ]
    )

    for cat, count in report.by_category.items():
        lines.append(f"- **{cat}**: {count}")

    lines.extend(
        [
            "",
            "## 问题详情 (前 20)",
            "",
        ]
    )

    for issue in report.issues[:20]:
        lines.extend(
            [
                f"### {issue.id}: {issue.declaration_name}",
                "",
                f"- **分类**: {issue.category.value}",
                f"- **严重程度**: {issue.severity.value}",
                f"- **描述**: {issue.description}",
                f"- **建议**: {issue.suggestion}",
            ]
        )
        if issue.doc_source:
            lines.append(f"- **文档位置**: {issue.doc_source}:{issue.doc_line or ''}")
        if issue.code_source:
            lines.append(f"- **代码位置**: {issue.code_source}:{issue.code_line or ''}")
        lines.append("")

    return "\n".join(lines)


def generate_json_report(report: EnhancedDiffReport) -> str:
    """生成 JSON 报告"""
    data = {
        "summary": {
            "total_declarations": report.total_declarations,
            "total_entities": report.total_entities,
            "matched": report.matched_count,
            "unmatched_doc": report.unmatched_doc_count,
            "alignment_rate": report.alignment_rate,
            "diff_type_a": report.diff_type_a,
            "diff_type_b": report.diff_type_b,
            "diff_type_c": report.diff_type_c,
            "diff_type_d": report.diff_type_d,
        },
        "issues": [
            {
                "id": issue.id,
                "category": issue.category.value,
                "severity": issue.severity.value,
                "declaration_name": issue.declaration_name,
                "description": issue.description,
                "suggestion": issue.suggestion,
                "doc_source": str(issue.doc_source) if issue.doc_source else None,
                "doc_line": issue.doc_line,
                "code_source": str(issue.code_source) if issue.code_source else None,
                "code_line": issue.code_line,
            }
            for issue in report.issues
        ],
        "by_severity": report.by_severity,
        "by_category": report.by_category,
        "recommendations": report.recommendations,
    }
    return json.dumps(data, indent=2, ensure_ascii=False)


def generate_html_report(report: EnhancedDiffReport) -> str:
    """生成 HTML 报告（简化版）"""
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>文档-实现对齐报告 (增强版)</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        .critical {{ color: #dc3545; }}
        .high {{ color: #ffc107; }}
        .medium {{ color: #fd7e14; }}
        .low {{ color: #28a745; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #4CAF50; color: white; }}
    </style>
</head>
<body>
    <h1>文档-实现对齐报告 (增强版)</h1>
    <h2>总览</h2>
    <p><strong>对齐率</strong>: {report.alignment_rate:.1f}%</p>
    <p><strong>文档声明</strong>: {report.total_declarations}</p>
    <p><strong>代码实体</strong>: {report.total_entities}</p>
    <p><strong>已匹配</strong>: {report.matched_count}</p>

    <h2>问题统计</h2>
    <p><strong>按严重程度</strong>: {", ".join(f"{k}: {v}" for k, v in report.by_severity.items())}</p>
    <p><strong>按分类</strong>: {", ".join(f"{k}: {v}" for k, v in report.by_category.items())}</p>
</body>
</html>"""


__all__ = [
    "generate_markdown_report",
    "generate_json_report",
    "generate_html_report",
]
