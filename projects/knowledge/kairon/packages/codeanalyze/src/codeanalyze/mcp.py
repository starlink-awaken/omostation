"""codeanalyze MCP Server — exposes all analysis tools via Model Context Protocol.

Register with Agora:
  agora proxy add codeanalyze --command "python3" --args "-m codeanalyze.mcp"
Or manually via Agora's MCP:
  proxy_add_service(name="codeanalyze", command="python3", args="-m codeanalyze.mcp")
"""

from pathlib import Path

from codeanalyze import __version__  # type: ignore[import-not-found]
from codeanalyze.core.results import KnowledgeGraph  # type: ignore[import-not-found]
from codeanalyze.integrations.forge import guardrail  # type: ignore[import-not-found]

try:
    from fastmcp import FastMCP

    mcp = FastMCP(
        f"codeanalyze v{__version__} — Unified Code & Document Analysis",
        mask_error_details=True,
    )
except ImportError:
    raise RuntimeError("fastmcp required: pip install fastmcp")

# Lazy-loaded CRG graph query
from codeanalyze.analyzers.crg_graph import (  # type: ignore[import-not-found]
    callees as _crg_callees,
)
from codeanalyze.analyzers.crg_graph import (
    callers as _crg_callers,
)
from codeanalyze.analyzers.crg_graph import (
    context as _crg_context,
)
from codeanalyze.analyzers.crg_graph import (
    search as _crg_search,
)


def _resolve(path: str) -> str:
    """Resolve and validate path."""
    return str(Path(path).resolve())


FORMAT_VERSION = "codeanalyze-v1"


def _error(msg: str) -> dict:
    """返回标准错误响应（内建 format_version）。"""
    return {"status": "error", "error": msg, "format_version": FORMAT_VERSION}


def _ok(data: dict) -> dict:
    """返回标准成功响应。data 中应包含 format_version 字段。"""
    return {"status": "ok", **data}


def _run_eidos_export(kg: KnowledgeGraph, root: Path) -> dict:
    """运行 Eidos 格式转换 + Schema 校验。"""
    import json as _json

    from codeanalyze.integrations.eidos_adapter import (  # type: ignore[import-not-found]
        convert_kg,
        try_eidos_validate,
    )

    eidos_data = convert_kg(kg)
    eidos_target = root / "codeanalyze-eidos.json"
    eidos_target.write_text(
        _json.dumps(eidos_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    validation = try_eidos_validate(eidos_data)
    return {
        "output_path": str(eidos_target),
        "ontology_nodes": len(eidos_data["ontology_nodes"]),
        "relations": len(eidos_data["relations"]),
        "facts": len(eidos_data["facts"]),
        "cards": len(eidos_data["cards"]),
        "validation": validation,
    }


def _md_summary(kg: KnowledgeGraph) -> str:
    """生成 Markdown 摘要。"""
    lines = [
        "# 知识图谱导出报告",
        "## 概览",
        f"- 实体: {kg.entity_count} 个",
        f"- 关系: {kg.relation_count} 条",
        f"- 来源文件: {len(kg.source_files)} 个",
        "",
        "## 实体列表",
    ]
    for e in kg.entities.values():
        prov = f" [来源: {e.provenance.source_file.split('/')[-1] if e.provenance else '-'}]"
        lines.append(f"- [{e.type}] **{e.name}** (域: {e.domain}, 置信: {e.confidence}){prov}")
    lines.extend(["", "## 关系列表"])
    for i, r in enumerate(kg.relations):
        if i >= 60:
            lines.append(f"  ... 还有 {len(kg.relations) - 60} 条")
            break
        src = kg.entities.get(r.source_id)
        tgt = kg.entities.get(r.target_id)
        sn = src.name if src else r.source_id[:30]
        tn = tgt.name if tgt else r.target_id[:30]
        lines.append(f"- {sn} --[{r.type}]--> {tn}")
    lines.extend(["", "## 来源文件"])
    for sf_path, info in kg.source_files.items():
        name = sf_path.split("/")[-1]
        lines.append(f"- {name} (分析器: {info['analyzer']})")
    return "\n".join(lines)


# ── Tools ──


@guardrail(required_steps=["analyze", "export"], max_retries=2)
@mcp.tool()
def analyze_project(path: str = ".") -> dict:
    """Run full analysis pipeline on a project (code + documents).

    Detects project type, runs available analyzers, returns entity-relation graph.

    Args:
        path: Path to the project root directory
    """
    try:
        from codeanalyze.documents.official import analyze_policy_directory  # type: ignore[import-not-found]
        from codeanalyze.reports.export import policy_graph_to_kg  # type: ignore[import-not-found]

        root = _resolve(path)
        pg = analyze_policy_directory(root)
        kg = policy_graph_to_kg(pg)

        return _ok(
            {
                "project": Path(root).name,
                "format_version": FORMAT_VERSION,
                "entities": kg.entity_count,
                "relations": kg.relation_count,
                "source_files": len(kg.source_files),
                "summary": {
                    "entity_count": kg.entity_count,
                    "relation_count": kg.relation_count,
                },
            }
        )
    except Exception as e:
        return _error(str(e))


@guardrail(required_steps=["analyze", "validate"], max_retries=2)
@mcp.tool()
async def export_graph(path: str = ".", output_format: str = "json", code: bool = False, eidos: bool = False) -> dict:
    """Export project knowledge graph in structured format.

    Args:
        path: Project root path
        output_format: json | json-ld | cypher | md
        code: Include code analysis entities (requires graphify)
        eidos: Convert to Eidos-compatible format + schema validation
    """
    try:
        import json as _json

        from codeanalyze.documents.official import analyze_policy_directory
        from codeanalyze.reports.export import merge_code_kg, policy_graph_to_kg

        root = Path(path).resolve()
        pg = analyze_policy_directory(str(root))
        kg = policy_graph_to_kg(pg)

        if code:
            kg = merge_code_kg(kg, str(root))

        # 序列化
        suffix_map = {"json": ".json", "json-ld": ".jsonld", "cypher": ".cypher", "md": ".md"}
        serializers = {
            "json": lambda: kg.to_json(),
            "json-ld": lambda: _json.dumps(kg.to_json_ld(), ensure_ascii=False, indent=2),
            "cypher": lambda: kg.to_cypher(),
            "md": lambda: _md_summary(kg),
        }

        content = serializers[output_format]()
        suffix = suffix_map[output_format]
        target = root / f"codeanalyze-export{suffix}"
        target.write_text(content, encoding="utf-8")

        result = {
            "output_path": str(target),
            "format_version": FORMAT_VERSION,
            "format": output_format,
            "entity_count": kg.entity_count,
            "relation_count": kg.relation_count,
            "source_files": len(kg.source_files),
        }

        # Eidos 集成（可选）
        if eidos:
            eidos_result = _run_eidos_export(kg, root)
            result["eidos"] = eidos_result

        return _ok(result)
    except Exception as e:
        return _error(str(e))


@mcp.tool()
def audit_project(path: str = ".") -> dict:
    """Run knowledge audit — cross-validate raw documents against wiki knowledge base.

    Checks 5 dimensions: policy docs vs policy graph, architecture docs vs knowledge base,
    org files vs ENTITIES.md, platform data vs platform overview, wiki structural integrity.

    Args:
        path: Project root path (must contain _工作机制/wiki directory)
    """
    try:
        from codeanalyze.reports.audit import run_audit  # type: ignore[import-not-found]

        root = _resolve(path)
        report = run_audit(root)

        return _ok(
            {
                "project": Path(root).name,
                "format_version": FORMAT_VERSION,
                "groups": len(report.groups),
                "total_checks": report.total_checks,
                "passed": report.total_passed,
                "failed": report.total_failed,
                "score": f"{report.score:.0f}%",
                "details": report.to_markdown(),
            }
        )
    except Exception as e:
        return _error(str(e))


@mcp.tool()
def extract_policy_docs(path: str = ".") -> dict:
    """Extract policy document metadata (doc numbers, issuing orgs, dates, levels).

    Scans PDF/DOCX/DOC files and extracts structured metadata using
    regex patterns and pdftotext.

    Args:
        path: Path to policy document directory (e.g. 40-政策法规)
    """
    try:
        from codeanalyze.documents.official import analyze_policy_directory, format_policy_graph_report

        root = _resolve(path)
        graph = analyze_policy_directory(root)

        return _ok(
            {
                "total_docs": graph.total_count,
                "format_version": FORMAT_VERSION,
                "levels": {k: len(v) for k, v in graph.level_groups.items()},
                "domains": {k: len(v) for k, v in graph.domain_groups.items()},
                "report": format_policy_graph_report(graph),
            }
        )
    except Exception as e:
        return _error(str(e))


@mcp.tool()
def status() -> dict:
    """Show installed code analysis and document processing tools."""
    from codeanalyze.core.registry import build_registry  # type: ignore[import-not-found]

    reg = build_registry()
    tools = {}
    for name, tool in sorted(reg.tools.items()):
        tools[name] = {
            "available": tool.available,
            "version": tool.version or "-",
            "description": tool.description,
        }
    return _ok(
        {
            "version": __version__,
            "format_version": FORMAT_VERSION,
            "tools": tools,
            "available": sum(1 for t in reg.tools.values() if t.available),
            "total": len(reg.tools),
        }
    )


@mcp.tool()
def scan_directory(path: str = ".") -> dict:
    """Scan and analyze a document project directory structure.

    Detects file types, categories (by 00-99 prefix), version chains,
    and wiki structural integrity.

    Args:
        path: Project root path
    """
    try:
        from codeanalyze.documents.scanner import analyze_wiki_structure  # type: ignore[import-not-found]
        from codeanalyze.documents.scanner import scan_directory as _scan

        root = _resolve(path)
        dm = _scan(root)
        wiki_info = analyze_wiki_structure(root)

        return _ok(
            {
                "project": Path(root).name,
                "format_version": FORMAT_VERSION,
                "total_files": dm.total_files,
                "code_files": dm.code_files,
                "raw_docs": dm.raw_docs,
                "spreadsheets": dm.spreadsheets,
                "wiki_files": dm.wiki_files,
                "version_chains": len(dm.version_chains),
                "wiki_available": wiki_info.get("available", False),
            }
        )
    except Exception as e:
        return _error(str(e))


@mcp.tool()
def crg_status(path: str = ".") -> dict:
    """Get code-review-graph stats (Tree-sitter persistent KG).

    Returns file/node/edge counts from the local SQLite database.
    Zero LLM cost - pure Tree-sitter AST parsing.

    Args:
        path: Project root path
    """
    try:
        from codeanalyze.analyzers import codereviewgraph as crg  # type: ignore[import-not-found]

        stats = crg.status(path)
        if stats.error:
            # Not installed - return empty
            return _ok(
                {
                    "format_version": FORMAT_VERSION,
                    "available": False,
                    "error": stats.error,
                }
            )

        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "available": True,
                "total_files": stats.total_files,
                "total_nodes": stats.total_nodes,
                "total_edges": stats.total_edges,
            }
        )
    except Exception as e:
        return _error(str(e))


@mcp.tool()
def crg_build(path: str = ".", force: bool = False) -> dict:
    """Build or rebuild Tree-sitter knowledge graph.

    Parses all code files with Tree-sitter, extracts AST nodes and edges,
    stores result in local SQLite. Supports incremental updates.

    Args:
        path: Project root path
        force: Force full rebuild
    """
    try:
        from codeanalyze.analyzers import codereviewgraph as crg

        stats = crg.build(path, force=force)
        if stats.error:
            return _error(stats.error)

        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "total_files": stats.total_files,
                "total_nodes": stats.total_nodes,
                "total_edges": stats.total_edges,
            }
        )
    except Exception as e:
        return _error(str(e))


@mcp.tool()
def codegraph_search(pattern: str, kind: str | None = None, path: str = ".", limit: int = 20) -> dict:
    """搜索代码符号。从 CRG Tree-sitter 知识图谱中查询，零文件读取。

    类似 CodeGraph 的 codegraph_search 命令。
    比 grep 快，因为有预索引的 SQLite 数据库。

    Args:
        pattern: 符号名称模式（支持 LIKE 通配符）
        kind: 可选，符号类型过滤 (function, class, method, variable 等)
        path: 项目路径
        limit: 最大返回数
    """
    try:
        results = _crg_search(pattern, kind=kind, repo_path=path, limit=limit)
        if results and "error" in results[0]:
            return _error(results[0]["error"])
        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "pattern": pattern,
                "results": results,
                "count": len(results),
            }
        )
    except Exception as e:
        return _error(str(e))


@mcp.tool()
def codegraph_callers(qualified_name: str, path: str = ".", limit: int = 20) -> dict:
    """查询谁调用了指定符号。类似 CodeGraph 的 codegraph_callers。

    从 CRG 知识图谱中追踪上游调用链。
    适用于理解依赖关系和变更影响范围。

    Args:
        qualified_name: 完全限定符号名 (e.g. "module.function_name")
        path: 项目路径
        limit: 最大返回数
    """
    try:
        results = _crg_callers(qualified_name, repo_path=path, limit=limit)
        if results and "error" in results[0]:
            return _error(results[0]["error"])
        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "symbol": qualified_name,
                "callers": results,
                "count": len(results),
            }
        )
    except Exception as e:
        return _error(str(e))


@mcp.tool()
def codegraph_callees(qualified_name: str, path: str = ".", limit: int = 20) -> dict:
    """查询指定符号调用了什么。类似 CodeGraph 的 codegraph_callees。

    从 CRG 知识图谱中追踪下游调用链。
    适用于影响分析、重构前评估。

    Args:
        qualified_name: 完全限定符号名
        path: 项目路径
        limit: 最大返回数
    """
    try:
        results = _crg_callees(qualified_name, repo_path=path, limit=limit)
        if results and "error" in results[0]:
            return _error(results[0]["error"])
        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "symbol": qualified_name,
                "callees": results,
                "count": len(results),
            }
        )
    except Exception as e:
        return _error(str(e))


@mcp.tool()
def codegraph_context(file_path: str, path: str = ".") -> dict:
    """获取文件的完整上下文：符号列表 + 调用关系。

    类似 CodeGraph 的 codegraph_context 命令。
    一次性返回 entry points、相关符号和代码片段。

    Args:
        file_path: 文件路径（支持模糊匹配）
        path: 项目路径
    """
    try:
        results = _crg_context(file_path, repo_path=path)
        if "error" in results:
            return _error(results["error"])
        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "file": file_path,
                "nodes": results.get("nodes", []),
                "callers": results.get("callers", []),
                "callees": results.get("callees", []),
            }
        )
    except Exception as e:
        return _error(str(e))


@mcp.tool()
def rg_search(
    pattern: str,
    path: str = ".",
    fixed_strings: bool = False,
    ignore_case: bool = False,
    max_count: int = 50,
    glob: str | None = None,
) -> dict:
    """Search codebase using ripgrep (fast, structured search).

    Returns structured matches with file paths, line numbers, and context.
    10x faster than grep, respects .gitignore.

    Args:
        pattern: Search pattern (regex or literal)
        path: Search root path
        fixed_strings: Treat pattern as literal string (not regex)
        ignore_case: Case-insensitive search
        max_count: Maximum matches to return
        glob: File glob filter (e.g. "*.py" for Python files)
    """
    try:
        from codeanalyze.analyzers import ripgrep as rg

        result = rg.search(
            pattern=pattern,
            path=path,
            regex=not fixed_strings,
            fixed_strings=fixed_strings,
            ignore_case=ignore_case,
            max_count=max_count,
            glob=glob,
            json_output=True,
        )

        if result.error:
            return _error(result.error)

        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "pattern": result.pattern,
                "total": result.total,
                "elapsed_ms": result.elapsed_ms,
                "matches": [
                    {
                        "path": m.path,
                        "line_number": m.line_number,
                        "text": m.text[:200],
                    }
                    for m in result.matches[:max_count]
                ],
            }
        )
    except Exception as e:
        return _error(str(e))


@mcp.tool()
def ast_search(
    pattern: str,
    path: str = ".",
    language: str | None = None,
    strict: bool = False,
    max_count: int = 50,
) -> dict:
    """Search codebase using ast-grep (structural AST pattern matching).

    Unlike text search, ast-grep finds code patterns based on syntax structure.
    Use patterns like '$FUNC($___)' or 'try { $A } catch ($E) { $B }'.

    Args:
        pattern: AST search pattern
        path: Search root path
        language: Language (py, js, ts, rs, etc.)
        strict: Strict pattern matching
        max_count: Maximum matches to return
    """
    try:
        from codeanalyze.analyzers import ast_grep

        result = ast_grep.search(
            pattern=pattern,
            path=path,
            language=language,
            strict=strict,
            max_count=max_count,
        )

        if result.error:
            return _error(result.error)

        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "pattern": result.pattern,
                "language": result.language,
                "total": result.total,
                "matches": [
                    {
                        "path": m.path,
                        "line": m.line_start,
                        "col": m.col_start,
                        "text": m.text[:200],
                    }
                    for m in result.matches[:max_count]
                ],
            }
        )
    except Exception as e:
        return _error(str(e))


@mcp.tool()
def pack_repo(
    path: str = ".",
    fmt: str = "xml",
    include: str | None = None,
    ignore: str | None = None,
    max_chars: int = 100000,
) -> dict:
    """Pack an entire repository into a single LLM-friendly file string.

    Uses repomix to convert multiple files into one context window.
    Only use this when you need broad context across many files.

    Args:
        path: Repository root path
        fmt: Output format (xml, markdown, plain)
        include: Comma-separated globs to include (e.g. 'src/**/*.py')
        ignore: Comma-separated globs to ignore
        max_chars: Truncate output if it exceeds this length
    """
    try:
        from codeanalyze.analyzers import repomix

        include_list = include.split(",") if include else None
        ignore_list = ignore.split(",") if ignore else None

        content = repomix.pack_to_string(
            path=path,
            fmt=fmt,
            include=include_list,
            ignore=ignore_list,
            max_chars=max_chars,
        )

        if content.startswith("<!-- repomix error:"):
            return _error(content)

        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "length": len(content),
                "content": content,
            }
        )
    except Exception as e:
        return _error(str(e))


@mcp.tool()
def cgc_query(query_str: str, path: str = ".") -> dict:
    """Query CodeGraphContext semantic property graph using Cypher/Kuzu.

    Args:
        query_str: Cypher query string
        path: Project root path
    """
    try:
        from codeanalyze.analyzers import cgc

        result = cgc.query(query_str, path=path)

        if not result.success:
            return _error(result.error or "CGC query failed")

        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "data": result.data,
            }
        )
    except Exception as e:
        return _error(str(e))


@mcp.tool()
def workflow_onboarding(path: str = ".", include: str | None = None) -> dict:
    """Run the Onboarding workflow to prepare AI context for a project.

    Uses repomix and ast-grep to bundle the repository and find entry points.

    Args:
        path: Project root path
        include: Comma-separated globs to include (e.g. 'src/**/*.py')
    """
    try:
        from codeanalyze.workflows import generate_onboarding_context

        include_list = include.split(",") if include else None
        result = generate_onboarding_context(path=path, include=include_list)
        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "workflow": "onboarding",
                "result": result,
            }
        )
    except Exception as e:
        return _error(str(e))


@mcp.tool()
def workflow_impact_analysis(symbol_name: str, language: str, path: str = ".") -> dict:
    """Run the Impact Analysis workflow for a symbol (function/class).

    Uses ast-grep to find structural usages and CodeGraphContext (if available)
    for deep dependency resolution.

    Args:
        symbol_name: Name of the function or class (e.g. 'process_data')
        language: Language of the project (e.g. 'py', 'js', 'ts')
        path: Project root path
    """
    try:
        from codeanalyze.workflows import analyze_impact

        result = analyze_impact(symbol_name=symbol_name, language=language, path=path)
        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "workflow": "impact_analysis",
                "result": result,
            }
        )
    except Exception as e:
        return _error(str(e))


@mcp.tool()
def codegraph_get_symbol_graph(symbol_name: str, path: str = ".") -> dict:
    """[Relational Engine] Get a tree of callers and callees for a specific symbol using codegraph.

    Args:
        symbol_name: The target symbol name (qualified name).
        path: Workspace root path.
    """
    try:
        callers = _crg_callers(symbol_name, repo_path=_resolve(path), limit=20)
        callees = _crg_callees(symbol_name, repo_path=_resolve(path), limit=20)

        # Check for errors
        if callers and "error" in callers[0]:
            return _error(callers[0]["error"])
        if callees and "error" in callees[0]:
            return _error(callees[0]["error"])

        return _ok({"format_version": FORMAT_VERSION, "symbol": symbol_name, "callers": callers, "callees": callees})
    except Exception as e:
        return _error(str(e))


@mcp.tool()
def codegraph_get_impact_radius(file_path: str, path: str = ".") -> dict:
    """[Relational Engine] Find all files that depend on the target file using codegraph SQLite index.

    Args:
        file_path: Target file path relative to workspace.
        path: Workspace root path.
    """
    try:
        ctx = _crg_context(file_path, repo_path=_resolve(path))
        if "error" in ctx:
            return _error(ctx["error"])

        # Extract unique source files from callers
        impacted_files = list(
            {caller.get("source_file") for caller in ctx.get("callers", []) if caller.get("source_file")}
        )

        return _ok({"format_version": FORMAT_VERSION, "target_file": file_path, "impacted_files": impacted_files})
    except Exception as e:
        return _error(str(e))


@mcp.tool()
def architecture_generate_diagram(module_path: str, path: str = ".") -> dict:
    """[Visualization Engine] Generate a Mermaid.js architecture diagram using Mindpilot / SciTools.

    Args:
        module_path: Target module or directory relative to workspace.
        path: Workspace root path.
    """
    try:
        from codeanalyze.analyzers.understand import UnderstandAdapter

        adapter = UnderstandAdapter(workspace_root=_resolve(path))
        diagram = adapter.generate_architecture_diagram(module_path)
        return _ok({"format_version": FORMAT_VERSION, "mermaid": diagram})
    except Exception as e:
        return _error(str(e))


@mcp.tool()
def architecture_get_code_metrics(file_path: str, path: str = ".") -> dict:
    """[Visualization Engine] Get complexity and coupling metrics using SciTools Understand.

    Args:
        file_path: Target file path relative to workspace.
        path: Workspace root path.
    """
    try:
        from codeanalyze.analyzers.understand import UnderstandAdapter

        adapter = UnderstandAdapter(workspace_root=_resolve(path))
        result = adapter.get_code_metrics(file_path)
        return _ok({"format_version": FORMAT_VERSION, "result": result})
    except Exception as e:
        return _error(str(e))


@mcp.tool()
def codegraph_init(path: str = ".") -> dict:
    """[Relational Engine] Initialize CodeGraph in the workspace and build initial index."""
    try:
        from codeanalyze.integrations.codegraph import init_codegraph

        result = init_codegraph(_resolve(path))
        return _ok({"format_version": FORMAT_VERSION, "result": result})
    except Exception as e:
        return _error(str(e))


@mcp.tool()
def codegraph_sync(path: str = ".") -> dict:
    """[Relational Engine] Sync CodeGraph index with recent file changes."""
    try:
        from codeanalyze.integrations.codegraph import sync_codegraph

        result = sync_codegraph(_resolve(path))
        return _ok({"format_version": FORMAT_VERSION, "result": result})
    except Exception as e:
        return _error(str(e))


@mcp.tool()
def codegraph_get_affected_tests(files: list[str], path: str = ".") -> dict:
    """[Relational Engine] Find test files affected by changed source files using CodeGraph."""
    try:
        from codeanalyze.integrations.codegraph import get_affected_tests

        result = get_affected_tests(files, _resolve(path))
        return _ok({"format_version": FORMAT_VERSION, "result": result})
    except Exception as e:
        return _error(str(e))


@mcp.resource("bos://analysis/graph/{project}")
def read_analysis_graph(project: str) -> str:
    """Dynamically generate a Mermaid diagram for a project."""
    try:
        import urllib.parse

        project = urllib.parse.unquote(project)
        # Assuming project refers to a module path, e.g. "projects/omo"
        # Default workspace is the environment variable or common path
        import os

        from codeanalyze.analyzers.understand import UnderstandAdapter

        workspace_root = os.environ.get("WORKSPACE_ROOT", str(Path.home() / "Workspace"))
        adapter = UnderstandAdapter(workspace_root=_resolve(workspace_root))
        diagram = adapter.generate_architecture_diagram(project)
        return diagram
    except Exception as e:
        return f"Error generating graph: {str(e)}"


@mcp.resource("bos://analysis/metrics/{file}")
def read_analysis_metrics(file: str) -> str:
    """Calculate and return code metrics (e.g. Radon/Understand)."""
    try:
        import json
        import urllib.parse

        file = urllib.parse.unquote(file)
        import os

        workspace_root = os.environ.get("WORKSPACE_ROOT", str(Path.home() / "Workspace"))
        from codeanalyze.analyzers.understand import UnderstandAdapter

        adapter = UnderstandAdapter(workspace_root=_resolve(workspace_root))
        result = adapter.get_code_metrics(file)
        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Error getting metrics: {str(e)}"


def main() -> None:
    """Run the MCP server in stdio mode (for Agora integration)."""
    mcp.run()


@mcp.resource("health://status")
def health_check() -> str:
    """健康检查端点 — 返回服务状态。"""
    return "ok"


def http_main() -> None:
    """Run the MCP server in HTTP mode."""
    import asyncio

    asyncio.run(mcp.run_http_async(host="127.0.0.1", port=8765))


if __name__ == "__main__":
    main()
