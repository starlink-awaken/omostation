"""DeepWiki-Open 适配器 — 代码项目自动文档生成

DeepWiki-Open 是自托管的 AI 文档生成器（Python/FastAPI + Next.js）。
此适配器支持两种模式:
1. API 模式: 连接已部署的 DeepWiki-Open 服务
2. 本地模式: 基于 Graphify/GitNexus 输出直接生成 Wiki Markdown
"""

import os
from pathlib import Path

from codeanalyze.core.registry import ToolInfo  # type: ignore[import-not-found]

DEEPWIKI_OPEN_URL = os.environ.get("DEEPWIKI_OPEN_URL", "")


def check_deepwiki_open(tool: ToolInfo | None = None) -> dict:
    """检测 DeepWiki-Open 可用性。"""
    result: dict[str, bool | str | None] = {"available": False, "mode": None}

    # 1. API 模式: 检查环境变量
    if DEEPWIKI_OPEN_URL:
        result["available"] = True
        result["mode"] = "api"
        result["url"] = DEEPWIKI_OPEN_URL
        return result

    # 2. 本地部署检测 (Docker-compose 项目)
    candidate_paths = [
        os.path.expanduser("~/Workspace/deepwiki-open"),
        os.path.expanduser("~/deepwiki-open"),
        "/opt/deepwiki-open",
    ]
    for path in candidate_paths:
        if Path(path).joinpath("docker-compose.yml").exists():
            result["available"] = True
            result["mode"] = "local"
            result["path"] = path
            return result

    return result


def generate_wiki_from_analysis(
    repo_path: str,
    graphify_result: dict | None = None,
    gitnexus_result: dict | None = None,
) -> str:
    """基于 Graphify/GitNexus 的分析结果生成 Wiki 风格文档。

    这是 DeepWiki-Open 不可用时的本地 fallback。
    生成内容:
    - 项目概览（类型、规模、语言）
    - 核心抽象（God Node）
    - 社区结构（模块发现）
    - 依赖图概览
    - 架构推断
    """
    root = Path(repo_path).resolve()
    lines = [
        f"# {root.name} — 项目 Wiki",
        "",
        "> 基于代码分析自动生成 | 生成时间: ...",
        "",
        "## 项目概览",
        f"- 路径: {root}",
    ]

    if graphify_result:
        entities = graphify_result.get("entities", [])
        relations = graphify_result.get("relations", [])
        lines.append(f"- 代码实体: {len(entities)} 个")
        lines.append(f"- 关系: {len(relations)} 条")

        # God Nodes (核心抽象)
        type_counts: dict[str, int] = {}
        for e in entities:
            t = e.get("type", "Unknown")
            type_counts[t] = type_counts.get(t, 0) + 1
        lines.append("")
        lines.append("## 核心抽象 (God Nodes)")
        if type_counts:
            lines.append("| 类型 | 数量 |")
            lines.append("|------|------|")
            for t, c in sorted(type_counts.items(), key=lambda x: -x[1])[:10]:
                lines.append(f"| {t} | {c} |")

        # 关系类型分布
        rel_types: dict[str, int] = {}
        for r in relations:
            rt = r.get("type", "UNKNOWN")
            rel_types[rt] = rel_types.get(rt, 0) + 1
        if rel_types:
            lines.append("")
            lines.append("## 关系分布")
            lines.append("| 关系类型 | 数量 |")
            lines.append("|----------|------|")
            for rt, c in sorted(rel_types.items(), key=lambda x: -x[1])[:10]:
                lines.append(f"| {rt} | {c} |")

        # 实体详情（高连接度实体）
        lines.append("")
        lines.append("## 关键实体详情")
        for e in entities[:20]:
            props = e.get("properties", {})
            path_str = props.get("path", "")
            lines.append(f"- **{e['name']}** ({e['type']}): {path_str}")

    if gitnexus_result:
        lines.append("")
        lines.append("## 依赖图状态")
        status = gitnexus_result.get("status", "unknown")
        lines.append(f"- 索引状态: {status}")

    # 读取已有的 GRAPH_REPORT.md（如果存在）
    report_path = root / "graphify-out" / "GRAPH_REPORT.md"
    if report_path.exists():
        lines.append("")
        lines.append("## 详细分析报告")
        lines.append(f"> 完整报告见: `{report_path.relative_to(root.parent)}`")
        content = report_path.read_text(encoding="utf-8")
        # 提取前 80 行
        report_lines = content.split("\n")[:80]
        lines.extend(report_lines)

    lines.append("")
    lines.append("---")
    lines.append("*该 Wiki 由 codeanalyze 基于静态分析生成。安装 DeepWiki-Open 可获取 AI 增强版文档。*")

    return "\n".join(content for content in lines)


def trigger_api_wiki_generation(repo_url: str, output_dir: str) -> dict:
    """调用 DeepWiki-Open API 生成 Wiki（需要服务已部署）。"""
    if not DEEPWIKI_OPEN_URL:
        return {"error": "DEEPWIKI_OPEN_URL not set", "status": "skipped"}

    try:
        import requests

        resp = requests.post(
            f"{DEEPWIKI_OPEN_URL.rstrip('/')}/export/wiki",
            json={
                "repo_url": repo_url,
                "pages": [],
                "format": "markdown",
            },
            timeout=300,
        )
        if resp.status_code == 200:
            output_path = Path(output_dir) / "deepwiki-generated-wiki.md"
            output_path.write_text(resp.text, encoding="utf-8")
            return {"status": "ok", "output": str(output_path)}
        else:
            return {"status": "error", "error": f"API returned {resp.status_code}: {resp.text[:200]}"}
    except ImportError:
        return {"error": "requests not installed", "status": "error"}
    except Exception as e:
        return {"error": str(e), "status": "error"}
