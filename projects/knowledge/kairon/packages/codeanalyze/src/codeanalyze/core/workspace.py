"""工作区检测 — 识别项目语言、规模、已有 graphify-out 等"""

from dataclasses import dataclass
from pathlib import Path

# 共享排除目录（用于文件遍历时过滤系统/生成目录）
EXCLUDE_DIRS = {
    ".venv",
    "node_modules",
    "__pycache__",
    ".git",
    ".worktrees",
    ".omc",
    ".benchmarks",
    ".hypothesis",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".graphify",
    ".gitnexus",
    ".serena",
    ".runtime",
    ".sessions",
    ".agent",
    "tmp",
    "logs",
    "graphify-out",
    "forge-mcp",
}

# Claude 插件目录
CLAUDE_PLUGINS_DIR = Path.home() / ".claude" / "plugins"


def relative_path(path: Path, parent: Path) -> str:
    """获取相对路径，失败时返回文件名。"""
    try:
        return str(path.relative_to(parent))
    except ValueError:
        return path.name


@dataclass
class WorkspaceInfo:
    path: Path
    name: str
    has_git: bool = False
    language_guesses: list[str] | None = None
    total_files: int = 0
    code_files: int = 0
    doc_files: int = 0
    has_graphify_out: bool = False
    has_gitnexus_index: bool = False
    is_python: bool = False
    is_typescript: bool = False
    is_rust: bool = False
    is_go: bool = False
    is_jvm: bool = False

    def __post_init__(self) -> None:
        if self.language_guesses is None:
            self.language_guesses = []

    @property
    def summary_lines(self) -> list[str]:
        lines = [f"项目: {self.name} ({self.path})"]
        lines.append(f"文件: {self.total_files} 总 / {self.code_files} 代码 / {self.doc_files} 文档")
        if self.language_guesses:
            lines.append(f"语言: {', '.join(self.language_guesses[:5])}")
        lines.append(f"Git: {'✅' if self.has_git else '❌'}")
        lines.append(f"Graphify 输出: {'✅' if self.has_graphify_out else '❌'}")
        lines.append(f"GitNexus 索引: {'✅' if self.has_gitnexus_index else '❌'}")
        return lines


_EXT_CODE = {
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
    ".scala",
    ".php",
    ".swift",
    ".lua",
    ".mjs",
    ".vue",
    ".svelte",
    ".astro",
    ".zig",
    ".ex",
    ".exs",
    ".jl",
    ".dart",
    ".v",
    ".sh",
    ".bash",
}
_EXT_DOC = {".md", ".mdx", ".html", ".pdf", ".docx", ".xlsx", ".pptx", ".txt", ".rst", ".yaml", ".yml", ".json", ".csv"}


def detect_workspace(path_str: str = ".") -> WorkspaceInfo:
    root = Path(path_str).resolve()
    info = WorkspaceInfo(path=root, name=root.name)

    if not root.is_dir():
        return info

    info.has_git = (root / ".git").is_dir()
    info.has_graphify_out = (root / "graphify-out" / "GRAPH_REPORT.md").exists()
    info.has_gitnexus_index = (root / ".gitnexus").exists()

    language_set: set[str] = set()
    for fp in root.rglob("*"):
        if fp.is_dir() and fp.name.startswith((".", "node_modules", "__pycache__", "venv", ".venv")):
            continue
        if not fp.is_file():
            continue
        if fp.suffix in _EXT_CODE:
            info.code_files += 1
            lang = _suffix_to_lang(fp.suffix)
            if lang:
                language_set.add(lang)
        elif fp.suffix in _EXT_DOC:
            info.doc_files += 1
        info.total_files += 1

    info.language_guesses = sorted(language_set)
    info.is_python = "Python" in language_set
    info.is_typescript = "TypeScript" in language_set or "JavaScript" in language_set
    info.is_rust = "Rust" in language_set
    info.is_go = "Go" in language_set
    info.is_jvm = bool(language_set & {"Java", "Kotlin", "Scala"})

    return info


def _suffix_to_lang(suffix: str) -> str | None:
    return {
        ".py": "Python",
        ".ts": "TypeScript",
        ".tsx": "TypeScript",
        ".js": "JavaScript",
        ".jsx": "JavaScript",
        ".go": "Go",
        ".rs": "Rust",
        ".java": "Java",
        ".kt": "Kotlin",
        ".scala": "Scala",
        ".c": "C",
        ".cpp": "C++",
        ".h": "C/C++",
        ".hpp": "C++",
        ".rb": "Ruby",
        ".cs": "C#",
        ".php": "PHP",
        ".swift": "Swift",
        ".dart": "Dart",
        ".zig": "Zig",
        ".vue": "Vue",
        ".svelte": "Svelte",
        ".astro": "Astro",
        ".jl": "Julia",
        ".ex": "Elixir",
        ".exs": "Elixir",
        ".sh": "Shell",
        ".bash": "Shell",
        ".mjs": "JavaScript",
    }.get(suffix)
