"""国转中心 / 文档项目扫描分析 — 目录结构、文件类型、实体抽取、交叉引用"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_CATEGORY_PREFIX = {
    "00": "中心介绍/总览",
    "10": "组织架构",
    "20": "高校对接",
    "30": "平台资料",
    "40": "政策法规",
    "41": "上位规划",
    "42": "两重项目",
    "50": "业务流转",
    "60": "实施方案与方法论",
    "70": "展厅资料",
    "90": "外部资源",
    "99": "文件中转",
}

_CODE_EXTENSIONS = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".go",
    ".rs",
    ".java",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".rb",
    ".cs",
    ".kt",
    ".swift",
    ".sh",
    ".bash",
    ".vue",
    ".svelte",
}
_SUPERSEDES_PATTERN = re.compile(r"(?:supersedes|版本|v)(\d+)", re.IGNORECASE)
_VERSION_PATTERN = re.compile(r"v?(\d+(?:\.\d+)*)", re.IGNORECASE)


def _version_sort_key(doc: Any) -> tuple:
    """Sort versions: int-like first, semver fallback."""
    v = doc.version or "0"
    parts = v.split(".")
    try:
        return (0, int(parts[0]), *(int(p) for p in parts[1:]))
    except ValueError:
        return (1, 0, 0)


@dataclass
class DocFile:
    path: Path
    category: str = "未分类"
    file_type: str = "unknown"
    is_versioned: bool = False
    version: str | None = None
    is_archive: bool = False
    byte_size: int = 0
    is_wiki: bool = False

    @property
    def relative_path(self) -> str:
        return str(self.path)


@dataclass
class DirectoryMap:
    root: str
    name: str
    total_files: int = 0
    wiki_files: int = 0
    raw_docs: int = 0
    spreadsheets: int = 0
    presentations: int = 0
    text_files: int = 0
    archive_files: int = 0
    code_files: int = 0
    version_chains: list[list[DocFile]] = field(default_factory=list)
    categories: dict[str, list[DocFile]] = field(default_factory=dict)
    all_files: list[DocFile] = field(default_factory=list)

    @property
    def summary(self) -> str:
        lines = [
            f"📁 {self.name}",
            f"   总文件: {self.total_files}",
            f"   Wiki文档: {self.wiki_files}",
            f"   原始文档 (PDF/DOCX/DOC): {self.raw_docs}",
            f"   表格 (XLSX/XLS): {self.spreadsheets}",
            f"   文本 (MD/TXT): {self.text_files}",
            f"   归档文件: {self.archive_files}",
        ]
        if self.version_chains:
            lines.append(f"   版本链: {len(self.version_chains)} 组")
        if self.categories:
            lines.append("\n   分类目录:")
            for cat, files in sorted(self.categories.items()):
                lines.append(f"     {cat}: {len(files)} 文件")
        return "\n".join(lines)


def scan_directory(root_path: str) -> DirectoryMap:
    """扫描文档项目目录，返回结构化目录映射。"""
    root = Path(root_path).resolve()
    dm = DirectoryMap(root=str(root), name=root.name)

    by_cat: dict[str, list[DocFile]] = {}
    version_map: dict[str, list[DocFile]] = {}

    for fp in sorted(root.rglob("*")):
        if not fp.is_file():
            continue
        if fp.name == ".DS_Store":
            continue
        if ".venv" in fp.parts or "node_modules" in fp.parts:
            continue

        dm.total_files += 1
        rel = fp.relative_to(root)
        parts = fp.parts

        # Determine category from parent directory name
        cat = "其他"
        for prefix, label in _CATEGORY_PREFIX.items():
            if any(prefix in str(p) for p in parts):
                cat = label
                break

        # Determine file type
        suffix = fp.suffix.lower()
        is_wiki = "_工作机制/wiki" in str(rel)
        is_archive = "_archive" in str(rel) or "已废弃" in str(rel)

        # Count by type
        if is_wiki:
            dm.wiki_files += 1
        elif suffix == ".md":
            dm.text_files += 1
        elif suffix in (".pdf", ".docx", ".doc"):
            dm.raw_docs += 1
        elif suffix in (".xlsx", ".xls"):
            dm.spreadsheets += 1
        elif suffix in (".pptx", ".ppt"):
            dm.presentations += 1
        elif suffix == ".txt":
            dm.text_files += 1

        # Code file detection (non-wiki, non-archive)
        if suffix in _CODE_EXTENSIONS:
            dm.code_files += 1

        # Version detection
        version = None
        is_versioned = False
        m = _VERSION_PATTERN.search(fp.stem)
        if m:
            version = m.group(1)
            is_versioned = True

        doc_file = DocFile(
            path=fp,
            category=cat,
            file_type=suffix,
            is_versioned=is_versioned,
            version=version,
            is_archive=is_archive,
            byte_size=fp.stat().st_size,
            is_wiki=is_wiki,
        )

        # Track version chains (same base name, different versions)
        if is_versioned and version:
            base_key = _VERSION_PATTERN.sub("", fp.stem).strip()
            if base_key not in version_map:
                version_map[base_key] = []
            version_map[base_key].append(doc_file)

        # Categorize
        if cat not in by_cat:
            by_cat[cat] = []
        by_cat[cat].append(doc_file)
        dm.all_files.append(doc_file)

    # Add version chains (groups with 2+ versions)
    for base, files in version_map.items():
        if len(files) >= 2:
            files.sort(key=_version_sort_key)
            dm.version_chains.append(files)

    dm.categories = by_cat
    if is_archive:  # type: ignore[reportPossiblyUnboundVariable]
        dm.archive_files = sum(1 for f in dm.all_files if f.is_archive)

    return dm


def analyze_wiki_structure(root_path: str) -> dict:
    """分析 _工作机制/wiki 的结构完整性。"""
    wiki_root = Path(root_path).resolve() / "_工作机制" / "wiki"
    if not wiki_root.is_dir():
        return {"available": False, "error": "no _工作机制/wiki directory"}

    required_files = ["MEMORY.md", "STATE.md", "ENTITIES.md", "TIMELINE.md", "INDEX.md"]
    meta_files = ["KnowledgeProtocol.md", "frontmatter规范.md", "信源监测矩阵.md", "状态机.md", "维护手册.md"]

    found_req = [f for f in required_files if (wiki_root / f).exists()]
    found_meta = [f for f in meta_files if (wiki_root / "_meta" / f).exists()]

    section_dirs = sorted(d.name for d in wiki_root.iterdir() if d.is_dir() and not d.name.startswith("_"))

    return {
        "available": True,
        "wiki_root": str(wiki_root),
        "required_files": {
            "total": len(required_files),
            "found": len(found_req),
            "missing": [f for f in required_files if f not in found_req],
        },
        "meta_files": {
            "total": len(meta_files),
            "found": len(found_meta),
            "missing": [f for f in meta_files if f not in found_meta],
        },
        "sections": section_dirs,
        "section_count": len(section_dirs),
    }
