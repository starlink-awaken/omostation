"""工具可用性注册中心 — 探测本地安装了哪些分析工具"""

import importlib
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from codeanalyze.core.workspace import CLAUDE_PLUGINS_DIR  # type: ignore[import-not-found]


@dataclass
class ToolInfo:
    name: str
    description: str
    available: bool = False
    version: str | None = None
    path: str | None = None
    error: str | None = None
    min_version: str | None = None
    max_version: str | None = None


@dataclass
class Registry:
    tools: dict[str, ToolInfo] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return any(t.available for t in self.tools.values())


@dataclass
class ToolSpec:
    """工具检测规范 — 替代手写 dict。"""

    name: str
    desc: str
    python_module: str | None = None
    python_fallback: str | None = None
    cli: str | None = None
    check_plugin_dir: bool = False
    module_then_cli: bool = False


def _check_python_module(mod: str, name: str, desc: str) -> ToolInfo:
    info = ToolInfo(name=name, description=desc)
    try:
        m = importlib.import_module(mod)
        info.available = True
        ver = getattr(m, "__version__", None)
        # 有些包的 __version__ 是个子模块而非字符串（如 unstructured）
        if ver is not None and not isinstance(ver, str):
            ver = getattr(ver, "__version__", None) or str(ver)
        info.version = ver
    except Exception as e:
        info.error = str(e)[:120]
    return info


def _check_cli(cmd: str, name: str, desc: str, version_flag: str = "--version") -> ToolInfo:
    info = ToolInfo(name=name, description=desc)
    cli_path = shutil.which(cmd)
    if not cli_path:
        info.error = f"`{cmd}` not found on PATH"
        return info
    info.path = cli_path
    info.available = True
    try:
        result = subprocess.run([cli_path, version_flag], capture_output=True, text=True, timeout=10)
        info.version = result.stdout.strip() or result.stderr.strip() or None
    except Exception:
        pass
    return info


_TOOL_SPECS: list[ToolSpec] = [
    ToolSpec(
        "graphify",
        "Semantic code knowledge graph (Tree-sitter AST + LLM)",
        python_module="graphify",
        python_fallback="graphifyy",
    ),
    ToolSpec("gitnexus", "Repo dependency graph & call-chain analysis (LadybugDB)", cli="gitnexus"),
    ToolSpec(
        "serena",
        "Symbol-level code retrieval & editing (LSP-based MCP)",
        cli="serena",
        python_module="serena_agent",
        check_plugin_dir=True,
    ),
    ToolSpec("docling", "IBM document → structured data (PDF/Word/HTML)", python_module="docling"),
    ToolSpec("docling_graph", "IBM Docling → Pydantic → Knowledge Graph (NetworkX)", python_module="docling_graph"),
    ToolSpec("marker", "PDF → Markdown/JSON/HTML (high accuracy)", cli="marker_single", python_module="marker"),
    ToolSpec("unstructured", "Document chunking & partition (PDF/HTML/DOCX)", python_module="unstructured"),
    ToolSpec(
        "mineru",
        "中文PDF→Markdown/JSON (OpenDataLab, 中文最优)",
        python_module="magic_pdf",
        cli="magic_pdf",
        module_then_cli=True,
    ),
    ToolSpec("ripgrep", "Ultra-fast code search (Rust, 10x grep)", cli="rg"),
    ToolSpec(
        "code_review_graph",
        "Tree-sitter persistent KG (token compression)",
        cli="code-review-graph",
        python_module="code_review_graph",
    ),
    ToolSpec("ast-grep", "AST-based structural code search (sg)", cli="ast-grep", python_fallback="sg"),
    ToolSpec("repomix", "Pack repository to LLM-friendly format (XML/MD)", cli="repomix", python_fallback="npx"),
    ToolSpec(
        "codegraphcontext",
        "CodeGraphContext semantic property graph (CGC)",
        cli="cgc",
        python_module="codegraphcontext",
    ),
]


def _check_tool(spec: ToolSpec) -> ToolInfo:
    """根据 spec 调度对应的检测策略。"""
    name = spec.name
    desc = spec.desc
    python_module = spec.python_module
    python_fallback = spec.python_fallback
    cli = spec.cli
    module_then_cli = spec.module_then_cli

    # 1. Module with fallback (graphify), or CLI with fallback (npx/sg)
    if python_module and python_fallback:
        info = _check_python_module(python_module, name, desc)
        if not info.available:
            info = _check_python_module(python_fallback, name, desc)
        return _check_plugin_dir(spec, info)

    if cli and python_fallback and not python_module:
        info = _check_cli(cli, name, desc)
        if not info.available:
            info = _check_cli(python_fallback, name, desc)
        return _check_plugin_dir(spec, info)

    # 2. Module only
    if python_module and not cli:
        return _check_plugin_dir(spec, _check_python_module(python_module, name, desc))

    # 3. CLI only
    if cli and not python_module:
        return _check_cli(cli, name, desc)

    # 4. Both CLI and module
    if cli and python_module:
        if module_then_cli:
            info = _check_python_module(python_module, name, desc)
            if not info.available:
                info = _check_cli(cli, name, desc)
        else:
            info = _check_cli(cli, name, desc)
            if not info.available:
                info = _check_python_module(python_module, name, desc)
        return _check_plugin_dir(spec, info)

    return ToolInfo(name=name, description=desc, error="No check method in spec")


def _check_plugin_dir(spec: ToolSpec, info: ToolInfo) -> ToolInfo:
    """检查 Claude Code plugin 目录（如 Serena）。"""
    if spec.check_plugin_dir and not info.available:
        plugin_dir = CLAUDE_PLUGINS_DIR / spec.name
        if plugin_dir.joinpath("package.json").exists():
            return ToolInfo(
                name=spec.name,
                description=spec.desc,
                available=True,
                version="plugin",
                path=str(plugin_dir),
            )
    return info


def _check_deepwiki_open() -> ToolInfo | None:
    """DeepWiki-Open 特殊检测：环境变量或本地路径。"""
    dw_url = os.environ.get("DEEPWIKI_OPEN_URL", "")
    if dw_url:
        return ToolInfo(
            name="deepwiki-open",
            description=f"Self-hosted AI Wiki generator (API: {dw_url})",
            available=True,
            version="api",
        )
    for p in [
        os.path.expanduser("~/Workspace/deepwiki-open"),
        os.path.expanduser("~/deepwiki-open"),
        "/opt/deepwiki-open",
    ]:
        if Path(p).joinpath("docker-compose.yml").exists():
            return ToolInfo(
                name="deepwiki-open",
                description=f"Self-hosted AI Wiki generator (local: {p})",
                available=True,
                version="local",
                path=p,
            )
    return None


def build_registry() -> Registry:
    """扫描并注册所有可用工具。"""
    reg = Registry()
    for spec in _TOOL_SPECS:
        reg.tools[spec.name] = _check_tool(spec)

    dw = _check_deepwiki_open()
    if dw is not None:
        reg.tools["deepwiki_open"] = dw

    return reg


def _check_version(info: ToolInfo, min_v: str | None = None, max_v: str | None = None) -> bool:
    """检查工具版本是否在兼容范围内。版本信息不可用时默认通过。"""
    if not info.available or not info.version or (min_v is None and max_v is None):
        return True
    try:
        ver = info.version.split(" ")[0].lstrip("v")
        parts = [int(p) for p in ver.split(".")]
        if min_v:
            min_parts = [int(p) for p in min_v.lstrip("v").split(".")]
            while len(parts) < len(min_parts):
                parts.append(0)
            for i, mp in enumerate(min_parts):
                if parts[i] < mp:
                    return False
                elif parts[i] > mp:
                    break
        if max_v:
            max_parts = [int(p) for p in max_v.lstrip("v").split(".")]
            while len(parts) < len(max_parts):
                parts.append(0)
            for i, mp in enumerate(max_parts):
                if parts[i] > mp:
                    return False
                elif parts[i] < mp:
                    break
    except Exception:
        pass
    return True


def verify_tool_versions(reg: Registry) -> list[str]:
    """验证所有已安装工具的版本兼容性，返回警告列表。"""
    warnings = []
    version_specs: dict[str, tuple[str | None, str | None]] = {
        "graphify": ("0.8.0", "0.9.0"),
        "gitnexus": ("1.0.0", None),
        "code_review_graph": ("0.1.0", None),
        "ripgrep": ("13.0.0", None),
    }
    for name, (min_v, max_v) in version_specs.items():
        tool = reg.tools.get(name)
        if tool and tool.available:
            if not _check_version(tool, min_v, max_v):
                msg = f"{name}: 版本 {tool.version} 超出兼容范围"
                if min_v:
                    msg += f" (需要 ≥ {min_v})"
                if max_v:
                    msg += f" (需要 ≤ {max_v})"
                warnings.append(msg)
    return warnings
