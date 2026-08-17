"""高阶工作流 — 组合基础工具实现特定场景的自动化分析

包含场景：
1. 上下文构建 (Onboarding/Context Loading)
2. 影响面分析 (Impact Analysis)
3. 架构快照提取 (Architecture Snapshot)
"""

from pathlib import Path

from codeanalyze.analyzers import ast_grep, cgc, repomix  # type: ignore[import-not-found]


def generate_onboarding_context(
    path: str = ".",
    include: list[str] | None = None,
    ignore: list[str] | None = None,
    output_dir: str | None = None,
) -> dict:
    """生成 AI Agent 友好的 Onboarding 上下文。

    1. 使用 repomix 打包代码核心内容。
    2. 使用 ast-grep 提取核心入口点（如 main() 或 FastAPI app）。
    """
    root = Path(path).resolve()
    out_dir = Path(output_dir).resolve() if output_dir else root

    # 1. 提取入口点 (假设是 Python 项目，寻找类似 __main__ 或 main 的函数)
    entry_points = []
    ag_res = ast_grep.search("def main():\n  $___", path=str(root), language="py")
    if not ag_res.error:
        entry_points.extend([m.path for m in ag_res.matches])

    # 2. 打包代码库
    pack_res = repomix.pack(
        path=str(root),
        output=str(out_dir / "onboarding-context.xml"),
        fmt="xml",
        include=include,
        ignore=ignore or ["tests/**", "docs/**", ".*"],
    )

    return {
        "scenario": "onboarding",
        "project": root.name,
        "entry_points_found": entry_points,
        "context_file": pack_res.output_path,
        "file_count": pack_res.file_count,
        "token_estimate": pack_res.token_count,
        "error": pack_res.error,
    }


def analyze_impact(symbol_name: str, language: str, path: str = ".") -> dict:
    """分析特定函数/类的变更影响面。

    1. 使用 ast-grep 查找该符号的所有调用和引用。
    2. 使用 CGC (若可用) 提取深层调用链。
    """
    root = Path(path).resolve()

    # 1. 结构化搜索调用处
    # 匹配模式：对函数调用的通用匹配 (如 $FUNC($___))
    pattern = f"{symbol_name}($___)"
    ag_res = ast_grep.search(pattern, path=str(root), language=language)

    # 整理按文件分布的调用
    files_affected = set()
    usage_contexts = []

    for m in ag_res.matches:
        files_affected.add(m.path)
        usage_contexts.append(
            {
                "file": m.path,
                "line": m.line_start,
                "text": m.text.strip(),
            }
        )

    result = {
        "symbol": symbol_name,
        "total_usages_found": ag_res.total,
        "files_affected": list(files_affected),
        "usages": usage_contexts,
    }

    # 2. 如果 CGC 可用，执行图查询找间接影响
    if cgc.is_available():
        # 尝试查询调用此符号的节点（伪代码/需依据具体图谱 schema 调整）
        cgc_res = cgc.query(
            f"MATCH (caller)-[:CALLS]->(callee) WHERE callee.name = '{symbol_name}' RETURN caller.name, caller.file",
            path=str(root),
        )
        if cgc_res.success:
            result["graph_callers"] = cgc_res.data

    return result


def build_architecture_snapshot(path: str = ".") -> dict:
    """构建项目架构快照。

    1. 初始化 CGC 语义图。
    2. 查询顶层模块和类之间的依赖关系。
    """
    root = Path(path).resolve()

    if not cgc.is_available():
        return {"error": "CodeGraphContext is required for architecture snapshot."}

    init_res = cgc.init_graph(str(root))
    if not init_res.success:
        return {"error": f"Failed to build graph: {init_res.error}"}

    # 查询类继承关系
    inherit_res = cgc.query("MATCH (child)-[:INHERITS]->(parent) RETURN child.name, parent.name", path=str(root))

    return {
        "status": "success",
        "graph_initialized": True,
        "inheritance_relations": inherit_res.data if inherit_res.success else [],
    }
