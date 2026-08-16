"""代码洞察分析 — 基于 CRG、GitNexus 数据生成架构洞见。

架构层级规则从 pyproject.toml 的 [tool.codeanalyze.layers] 段读取，
每个规则格式: {low = "低层路径", high = "高层路径", description = "说明"}
"""

import configparser
import os
import re
from pathlib import Path

from codeanalyze.core.workspace import EXCLUDE_DIRS  # type: ignore[import-not-found]

# 严重级别图标映射
_SEVERITY_ICONS = {"insight": "💡", "warning": "⚠️", "critical": "🔴"}

# 分析阈值
_LARGE_FILE_BYTES = 100_000
_MAX_LARGE_FILES = 5
_MAX_EMPTY_FILES = 8
_MAX_MODULES_ANALYZE = 3000
_MAX_VIOLATIONS = 10
_MAX_INSIGHT_DETAIL = 3


def _collect_python_files(root: Path, exclude: set[str] | None = None) -> list[Path]:
    """单次遍历收集所有 Python 文件，主动修剪排除目录。"""
    exclude = exclude or EXCLUDE_DIRS
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in exclude]
        for fname in filenames:
            if fname.endswith(".py"):
                files.append(Path(dirpath) / fname)
    return files


def analyze(project_path: str, gitnexus_result: dict) -> list[dict]:
    """运行所有洞察分析，返回洞察项列表。

    每项: {severity, category, title, detail}
    severity: insight | warning | critical
    """
    root = Path(project_path).resolve()
    py_files = _collect_python_files(root)
    layer_rules = _load_layer_rules(root)
    insights = []

    insights.extend(_file_size_insights(py_files, root))
    insights.extend(_docstring_coverage(py_files))
    insights.extend(_layer_check(py_files, root, layer_rules))
    insights.extend(_import_safety(py_files, root))
    insights.extend(_dep_health(gitnexus_result))

    return insights


def _load_layer_rules(root: Path) -> list[tuple[str, str, str]]:
    """从 pyproject.toml 读取 [tool.codeanalyze.layers] 配置。

    格式:
        [tool.codeanalyze.layers]
        rules = [
            {low = "低层路径", high = "高层路径", description = "说明"},
        ]
    返回: [(low, high, description), ...]
    """
    cfg_path = root / "pyproject.toml"
    if not cfg_path.exists():
        return []

    cfg = configparser.ConfigParser()
    try:
        cfg.read_string(cfg_path.read_text(encoding="utf-8"))
    except Exception:
        return []

    rules = []
    # ConfigParser 处理 ini 格式，不支持 dict list 嵌套
    # 所以也用 TOML 方式读取
    import tomllib

    try:
        data = tomllib.loads(cfg_path.read_text(encoding="utf-8"))
        layers = data.get("tool", {}).get("codeanalyze", {}).get("layers", {})
        for rule in layers.get("rules", []):
            low = rule.get("low", "")
            high = rule.get("high", "")
            desc = rule.get("description", "")
            if low and high:
                rules.append((low, high, desc))
    except (ImportError, tomllib.TOMLDecodeError, Exception):
        pass

    return rules


def _file_size_insights(py_files: list[Path], root: Path) -> list[dict]:
    """找出超大文件和空文件。"""
    large_files = []
    empty_files = []
    for f in py_files:
        try:
            size = f.stat().st_size
            if size == 0:
                empty_files.append(f)
            elif size > _LARGE_FILE_BYTES:
                large_files.append((f, size))
        except OSError:
            pass
        if len(large_files) >= _MAX_LARGE_FILES and empty_files:
            break

    results = []
    if large_files:
        paths = []
        for f, s in sorted(large_files, key=lambda x: -x[1])[:_MAX_LARGE_FILES]:
            paths.append(f"{relative_path(f, root)} ({s // 1024}KB)")
        results.append(
            {
                "severity": "warning",
                "category": "代码规模",
                "title": f"超大文件 ({len(large_files)} 个 >{_LARGE_FILE_BYTES // 1024}KB)",
                "detail": "\n".join(paths),
            }
        )

    if empty_files:
        paths_str = "\n".join(relative_path(f, root) for f in empty_files[:_MAX_EMPTY_FILES])
        results.append(
            {
                "severity": "insight",
                "category": "代码异常",
                "title": f"空文件 ({len(empty_files)} 个)",
                "detail": paths_str,
            }
        )
    return results


def _docstring_coverage(py_files: list[Path]) -> list[dict]:
    """估算模块/函数文档覆盖率。"""
    total = 0
    documented = 0
    for f in py_files:
        if f.name == "__init__.py":
            continue
        total += 1
        try:
            text = f.read_text("utf-8", errors="ignore")
            if text.strip().startswith(('"""', "'''", "# ---", "# domain:")):
                documented += 1
        except OSError:
            pass
        if total >= _MAX_MODULES_ANALYZE:
            break

    if total == 0:
        return []

    pct = documented / total * 100
    sev = "critical" if pct < 20 else "warning" if pct < 50 else "insight"
    return [
        {
            "severity": sev,
            "category": "文档覆盖",
            "title": f"文档覆盖率: {pct:.0f}% ({documented}/{total})",
            "detail": "文件无模块级文档" if pct < 20 else "文档覆盖偏低" if pct < 50 else "文档覆盖良好",
        }
    ]


def _layer_check(py_files: list[Path], root: Path, layer_rules: list[tuple[str, str, str]]) -> list[dict]:
    """检查架构层级依赖是否违规。

    规则从 pyproject.toml [tool.codeanalyze.layers] 读取。
    未配置规则时跳过检查。
    """
    if not layer_rules:
        return [
            {
                "severity": "insight",
                "category": "架构",
                "title": "层级依赖检查已跳过",
                "detail": "pyproject.toml 未配置 [tool.codeanalyze.layers]，跳过架构层级检查",
            }
        ]
    violations = []
    for f in py_files:
        try:
            text = f.read_text("utf-8", errors="ignore")
        except OSError:
            continue
        rel = relative_path(f, root)
        if not rel:
            continue

        for low, high, desc in layer_rules:
            if high not in rel:
                continue
            low_dotted = low.replace("/", ".")
            if low_dotted in text:
                violations.append(f"{rel} 反向依赖: {desc} ({high} → {low})")
                break
        if len(violations) >= _MAX_VIOLATIONS:
            break

    if violations:
        return [
            {
                "severity": "critical",
                "category": "架构",
                "title": f"层级依赖违规 ({len(violations)} 处)",
                "detail": "\n".join(violations[:_MAX_VIOLATIONS]),
            }
        ]
    return []


def _import_safety(py_files: list[Path], root: Path) -> list[dict]:
    """检查不安全导入模式。"""
    unsafe = []
    for f in py_files:
        try:
            text = f.read_text("utf-8", errors="ignore")
        except OSError:
            continue
        if re.search(r"sys\.path\.(insert|append)", text):
            unsafe.append(f"sys.path 修改: {relative_path(f, root)}")
        bare = re.findall(r"^except\s*:", text, re.MULTILINE)
        if bare:
            unsafe.append(f"裸 except: {relative_path(f, root)} ({len(bare)} 处)")
        if len(unsafe) >= _MAX_VIOLATIONS:
            break

    if unsafe:
        return [
            {
                "severity": "warning",
                "category": "代码安全",
                "title": f"不安全模式 ({len(unsafe)} 处)",
                "detail": "\n".join(unsafe[:_MAX_VIOLATIONS]),
            }
        ]
    return []


def _dep_health(gitnexus_result: dict) -> list[dict]:
    """基于 GitNexus 数据判断依赖健康度。"""
    results: list[dict[str, str | int | float]] = []
    stdout = gitnexus_result.get("stdout", "")
    if not stdout:
        return results

    m_nodes = re.search(r"([\d,]+)\s*nodes?", stdout)
    m_edges = re.search(r"([\d,]+)\s*edges?", stdout)
    m_clusters = re.search(r"([\d,]+)\s*clusters?", stdout)

    nodes = int(m_nodes.group(1).replace(",", "")) if m_nodes else 0
    edges = int(m_edges.group(1).replace(",", "")) if m_edges else 0
    clusters = int(m_clusters.group(1).replace(",", "")) if m_clusters else 0

    if nodes > 0:
        density = edges / nodes if nodes else 0
        detail = f"边/节点比: {density:.2f}"
        sev = "insight"
        if density > 5:
            sev = "warning"
            detail += " — 依赖密度偏高，模块间耦合可能过紧"
        elif density < 1:
            detail += " — 依赖稀疏，模块相对独立"
        results.append(
            {
                "severity": sev,
                "category": "依赖健康",
                "title": f"依赖密度: {density:.2f} ({edges} 边/{nodes} 节点)",
                "detail": detail,
            }
        )

    if clusters > 100:
        results.append(
            {
                "severity": "insight",
                "category": "模块分析",
                "title": f"社区数: {clusters}",
                "detail": f"{clusters} 个功能模块/社区，平均 {nodes // clusters if clusters else 0} 节点/社区",
            }
        )

    return results


def relative_path(path: Path, parent: Path) -> str:
    try:
        return str(path.relative_to(parent))
    except ValueError:
        return path.name


def format_insights(insights: list[dict]) -> str:
    """格式化洞察为 Markdown。"""
    lines = []
    for ins in insights:
        icon = _SEVERITY_ICONS.get(ins["severity"], "💡")
        lines.append(f"  {icon} **[{ins['category']}]** {ins['title']}")
        if ins.get("detail"):
            for d in ins["detail"].split("\n")[:_MAX_INSIGHT_DETAIL]:
                lines.append(f"    {d}")
    return "\n".join(lines)
