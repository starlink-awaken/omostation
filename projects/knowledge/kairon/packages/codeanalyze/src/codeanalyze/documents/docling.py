"""Docling / Docling-Graph 分析适配器"""

from typing import cast

from codeanalyze.core.registry import ToolInfo  # type: ignore[import-not-found]


def check_docling(tool: ToolInfo | None = None) -> dict:
    """检测 Docling 可用性并返回版本信息。"""
    if tool and not tool.available:
        return {"available": False, "error": "docling not installed"}
    try:
        import docling  # type: ignore[import-not-found]

        return {"available": True, "version": getattr(docling, "__version__", "unknown")}
    except ImportError:
        return {"available": False, "error": "docling not installed"}


def check_docling_graph(tool: ToolInfo | None = None) -> dict:
    """检测 Docling-Graph 可用性。"""
    if tool and not tool.available:
        return {"available": False, "error": "docling-graph not installed"}
    try:
        import docling_graph  # type: ignore[import-not-found]

        return {"available": True, "version": "installed"}
    except ImportError:
        return {"available": False, "error": "docling-graph not installed"}


def convert_to_markdown(file_path: str) -> str | None:
    """使用 Docling 将文档转为 Markdown。"""
    try:
        from docling.document_converter import DocumentConverter  # type: ignore[import-not-found]

        converter = DocumentConverter()
        result = converter.convert(file_path)
        return cast("str", result.document.export_to_markdown())
    except Exception:
        return None


def extract_knowledge_graph(file_path: str, template_path: str | None = None) -> dict:
    """使用 Docling-Graph 从文档提取知识图谱。"""
    try:
        from docling_graph import PipelineContext, run_pipeline  # type: ignore[reportMissingImports]

        config = {
            "source": file_path,
            "backend": "llm",
            "inference": "remote",
            "processing_mode": "many-to-one",
            "extraction_contract": "staged",
            "structured_output": True,
            "use_chunking": True,
        }
        if template_path:
            config["template"] = template_path

        context = run_pipeline(config)
        graph = context.knowledge_graph
        return {
            "nodes": graph.number_of_nodes() if graph else 0,
            "edges": graph.number_of_edges() if graph else 0,
            "models": len(context.extracted_models) if hasattr(context, "extracted_models") else 0,
        }
    except ImportError:
        return {"error": "docling-graph not installed"}
    except Exception as e:
        return {"error": str(e)}
