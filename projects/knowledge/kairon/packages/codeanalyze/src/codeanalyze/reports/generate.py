"""报告生成与合并 — 跨工具分析结果汇总，含 CRG、GitNexus、Graphify 数据。"""

import os
import re
from pathlib import Path

from codeanalyze.core.workspace import EXCLUDE_DIRS  # type: ignore[import-not-found]
from codeanalyze.reports.insights import format_insights  # type: ignore[import-not-found]


def generate_summary(
    repo_path: str,
    graphify_result: dict,
    gitnexus_result: dict,
    serena_result: dict,
    doc_result: dict | None = None,
    crg_result: dict | None = None,
    insights: list[dict] | None = None,
) -> str:
    """生成跨工具综合分析报告。

    Args:
        repo_path: 项目根路径
        graphify_result: Graphify 分析结果（entities/relations/error）
        gitnexus_result: GitNexus 结果（status/stdout/error）
        serena_result: Serena 工具列表（tools）
        doc_result: 文档分析结果（total_docs/total_words/files）
        crg_result: CRG 结果（total_files/total_nodes/total_edges）
        insights: 洞察分析结果列表
    """
    root = Path(repo_path).resolve()
    lines = [
        f"# 代码分析报告 — {root.name}",
        f"> 生成时间: ... | 路径: {root}",
        "",
    ]

    # ── 项目概览 ──
    lines.append("## 📦 项目概览")
    py_files = _collect_py_files(root)
    lines.append(f"- Python 文件: {len(py_files):,}")
    total_lines = 0
    for p in py_files[:5000]:
        try:
            total_lines += p.read_text("utf-8", errors="ignore").count("\n") + 1
        except (OSError, PermissionError):
            pass
    lines.append(f"- 源码行数: ~{total_lines:,}")
    all_files = _count_all_files(root)
    lines.append(f"- 目录总文件: {all_files:,}")
    lines.append("")

    # ── Graphify 语义图谱 ──
    lines.append("## 🌐 Graphify 语义图谱")
    if graphify_result.get("error") and graphify_result["error"] != "graphify import failed":
        lines.append(f"  ❌ {graphify_result['error']}")
    elif graphify_result.get("error"):
        lines.append("  ⏭️ 未安装")
    else:
        entities = graphify_result.get("entities", [])
        relations = graphify_result.get("relations", [])
        if not entities and not relations:
            entities = graphify_result.get("nodes", [])
            relations = graphify_result.get("edges", [])
        lines.append(f"  ✅ **{len(entities):,}** 实体 / **{len(relations):,}** 关系")
        type_counts: dict[str, int] = {}
        for e in entities:
            t = e.get("type") or e.get("kind") or "Unknown"
            type_counts[t] = type_counts.get(t, 0) + 1
        for t, c in sorted(type_counts.items(), key=lambda x: -x[1])[:8]:
            lines.append(f"    - {t}: {c:,}")
        # Check for graphify report/html
        report_path = root / "graphify-out" / "GRAPH_REPORT.md"
        html_path = root / "graphify-out" / "graph.html"
        if report_path.exists():
            lines.append("    📄 报告: graphify-out/GRAPH_REPORT.md")
        if html_path.exists():
            lines.append("    🌐 可视化: graphify-out/graph.html")
    lines.append("")

    # ── CRG Tree-sitter 知识图谱 ──
    lines.append("## 🧬 CRG (Code Review Graph)")
    if crg_result and crg_result.get("available"):
        lines.append(
            f"  ✅ **{crg_result['total_files']:,}** 文件 / **{crg_result['total_nodes']:,}** 节点 / **{crg_result['total_edges']:,}** 边"
        )
        lines.append("  🔍 零 LLM 成本，纯 Tree-sitter AST 解析")
        lines.append("  💡 在对话中使用 `codegraph_search` / `codegraph_callers` 查询")
    else:
        err = crg_result.get("error") if crg_result else "未检测"
        lines.append(f"  ⏭️ {err}")
    lines.append("")

    # ── GitNexus 依赖图 ──
    lines.append("## 🔗 GitNexus 依赖图")
    if gitnexus_result.get("status") == "unavailable":
        lines.append("  ⏭️ 未安装")
        lines.append("  💡 npm install -g gitnexus")
    elif gitnexus_result.get("status") == "ok":
        lines.append("  ✅ 索引完成")
        stdout = gitnexus_result.get("stdout", "")
        # Parse key metrics from gitnexus output
        node_match = re.search(r"([\d,]+)\s*nodes?", stdout)
        edge_match = re.search(r"([\d,]+)\s*edges?", stdout)
        cluster_match = re.search(r"([\d,]+)\s*clusters?", stdout)
        flow_match = re.search(r"([\d,]+)\s*flows?", stdout)
        if node_match:
            lines.append(f"    - 节点: {node_match.group(1)}")
        if edge_match:
            lines.append(f"    - 边: {edge_match.group(1)}")
        if cluster_match:
            lines.append(f"    - 社区: {cluster_match.group(1)}")
        if flow_match:
            lines.append(f"    - 执行流: {flow_match.group(1)}")
        lines.append("  💡 在对话中使用 `gitnexus_impact` / `gitnexus_query` 查询")
    else:
        err = gitnexus_result.get("error", "unknown error")
        lines.append(f"  ❌ {err}")
    lines.append("")

    # ── Serena 符号级分析 ──
    lines.append("## 🔍 Serena 符号级分析")
    serena_tools = serena_result.get("tools", [])
    if serena_result.get("available"):
        indexed = serena_result.get("indexed", 0)
        if indexed:
            lines.append(f"  ✅ 已索引 **{indexed:,}** 个符号")
        elif serena_result.get("index_exists"):
            lines.append("  ✅ 索引就绪")
        else:
            lines.append("  ✅ 可用")
        lines.append(f"  🔧 {len(serena_tools)} 个 MCP 工具: {', '.join(serena_tools[:6])}")
        if len(serena_tools) > 6:
            lines.append(f"    ... 还有 {len(serena_tools) - 6} 个")
        lines.append("  💡 在对话中直接调用 MCP 工具进行符号级查询")
    else:
        lines.append("  ⏭️ 未安装")
        lines.append("  💡 pip install serena-agent")
    lines.append("")

    # ── 文档分析 ──
    if doc_result and doc_result.get("total_docs", 0) > 0:
        lines.append("## 📝 文档分析")
        lines.append(f"  ✅ {doc_result['total_docs']} 文档 / {doc_result['total_words']:,} 字")
        for f in doc_result.get("files", [])[:8]:
            name = Path(f.get("path", "")).name
            wc = f.get("word_count", 0)
            label = "✅" if wc > 0 else "❌"
            lines.append(f"  {label} {name}: {wc:,}字")
        remaining = len(doc_result.get("files", [])) - 8
        if remaining > 0:
            lines.append(f"  ... 还有 {remaining} 个文件")
        lines.append("")

    # ── 建议 ──
    lines.append("## 💡 建议")
    suggestions = []
    if graphify_result.get("error") == "graphify import failed":
        suggestions.append("安装 Graphify: pip install graphifyy")
    if gitnexus_result.get("status") == "unavailable":
        suggestions.append("安装 GitNexus: npm install -g gitnexus")
    if not serena_tools:
        suggestions.append("安装 Serena MCP 获取符号级编辑能力")
    if crg_result and not crg_result.get("available"):
        suggestions.append("安装 code-review-graph: npm install -g code-review-graph")
    if suggestions:
        for s in suggestions:
            lines.append(f"  - {s}")
    else:
        lines.append("  ✅ 所有推荐工具已就绪")

    # ── 洞察分析 ──
    if insights:
        lines.append("")
        lines.append("## 🔬 洞察分析")
        lines.append(format_insights(insights))

    lines.append("")
    lines.append("---")
    lines.append("> 由 codeanalyze v0.3.0 生成")
    return "\n".join(lines)


def write_report(repo_path: str, content: str, output: str | None = None) -> str:
    """将报告写入文件。"""
    target = output or str(Path(repo_path).resolve() / "codeanalyze-report.md")
    Path(target).write_text(content, encoding="utf-8")
    return target


def _collect_py_files(root: Path) -> list[Path]:
    """单次 os.walk 收集 .py 文件，修剪排除目录。"""
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for fn in filenames:
            if fn.endswith(".py"):
                files.append(Path(dirpath) / fn)
    return files


def _count_all_files(root: Path) -> int:
    """统计所有文件数（修剪排除目录）。"""
    total = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        total += len(filenames)
    return total
