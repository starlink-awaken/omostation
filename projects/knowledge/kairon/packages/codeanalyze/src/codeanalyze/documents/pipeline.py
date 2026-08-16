"""文档分析管线 — 串联 Docling / Marker / Unstructured，产出统一分析结果"""

from pathlib import Path

from codeanalyze.core.registry import Registry  # type: ignore[import-not-found]
from codeanalyze.documents import docling  # type: ignore[import-not-found]
from codeanalyze.documents.base import DocumentAnalysis  # type: ignore[import-not-found]


def analyze_path(path: str, registry: Registry) -> dict:
    """对单个文件或目录运行文档分析管线。"""
    target = Path(path).resolve()

    if target.is_file():
        return _analyze_file(target, registry)
    elif target.is_dir():
        return _analyze_directory(target, registry)
    else:
        return {"error": f"path not found: {path}"}


def _analyze_file(file_path: Path, registry: Registry) -> dict:
    ext = file_path.suffix.lower()
    result = DocumentAnalysis(path=file_path, format=ext)

    # PDF / Office 文档 → Docling 转换
    if ext in (".pdf", ".docx", ".pptx", ".xlsx", ".html", ".md") and registry.tools.get("docling", None):
        md = docling.convert_to_markdown(str(file_path))
        if md:
            result.word_count = len(md.split())
            result.sections.append({"type": "markdown", "content_length": len(md)})

    # Docling-Graph 知识图谱抽取（PDF 文档）
    if ext == ".pdf" and registry.tools.get("docling_graph", None):
        kg = docling.extract_knowledge_graph(str(file_path))
        if "nodes" in kg:
            result.entities = [{"count": kg["nodes"]}]
            result.relations = [{"count": kg["edges"]}]
            result.sections.append({"type": "knowledge_graph", "nodes": kg["nodes"], "edges": kg["edges"]})

    if not result.sections and not result.error:
        result.error = "no suitable analyzer found for this file type"

    return {
        "path": str(result.path),
        "format": result.format,
        "word_count": result.word_count,
        "sections": result.sections,
        "entities": result.entities,
        "relations": result.relations,
        "error": result.error,
    }


def _analyze_directory(dir_path: Path, registry: Registry) -> dict:
    """扫描目录，对每个文档文件运行分析。"""
    doc_extensions = {".pdf", ".docx", ".pptx", ".xlsx", ".html", ".md", ".txt", ".rst"}
    results = []
    total_words = 0
    total_docs = 0

    for fp in sorted(dir_path.rglob("*")):
        if fp.is_dir() and fp.name.startswith((".", "_")):
            continue
        if not fp.is_file() or fp.suffix.lower() not in doc_extensions:
            continue
        file_result = _analyze_file(fp, registry)
        if file_result.get("word_count", 0) > 0:
            total_words += file_result["word_count"]
            total_docs += 1
        results.append(file_result)

    return {
        "directory": str(dir_path),
        "total_docs": total_docs,
        "total_words": total_words,
        "files": results,
    }


def format_analysis_summary(result: dict) -> str:
    """格式化为可读摘要。"""
    if "directory" in result:
        lines = [
            f"📁 文档分析: {result['directory']}",
            f"   文档数: {result['total_docs']}",
            f"   总字数: {result['total_words']}",
            "",
        ]
        for f in result.get("files", []):
            if f.get("error"):
                lines.append(f"  ❌ {f['path']}: {f['error']}")
            elif f.get("word_count", 0) > 0:
                lines.append(f"  ✅ {Path(f['path']).name}: {f['word_count']}字")
            for sec in f.get("sections", []):
                if sec.get("type") == "knowledge_graph":
                    lines.append(f"     └─ 知识图谱: {sec['nodes']} 节点 / {sec['edges']} 边")
        return "\n".join(lines)
    else:
        return f"{result.get('path', '?')}: {result.get('word_count', 0)}字 ({len(result.get('sections', []))} 章节)"
