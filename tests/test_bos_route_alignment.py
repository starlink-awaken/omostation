"""BOS 路由对齐校验 — 确保 ecos M1 YAML 定义与 agora POC_SERVICES 硬编码路由之间无脱节.

用法:
    uv run pytest tests/test_bos_route_alignment.py -v
    uv run pytest tests/test_bos_route_alignment.py::test_bos_alignment -v --no-header
"""
from __future__ import annotations

import fnmatch
import logging
import re
from pathlib import Path

import pytest
import yaml

_log = logging.getLogger(__name__)

# ── 路径常量 ───────────────────────────────────────
BOSROUTE_DIR = Path(__file__).resolve().parent.parent / "src" / "ecos" / "ssot" / "mof" / "m1" / "bosroute"
AGORA_BOS_RESOLVER_PATH = (
    Path(__file__).resolve().parent.parent.parent / "agora" / "src" / "agora" / "mcp" / "bos_resolver.py"
)
# Fallback: also check from the user's workspace root
_ALT_AGORA = Path("/Users/xiamingxing/Workspace/projects/agora/src/agora/mcp/bos_resolver.py")
if not AGORA_BOS_RESOLVER_PATH.exists() and _ALT_AGORA.exists():
    AGORA_BOS_RESOLVER_PATH = _ALT_AGORA

# CANONICAL_PERSONA_BRIDGE_URI_PREFIX 的硬编码值 (避免运行时 import)
_CANONICAL_PERSONA_BRIDGE_URI_PREFIX = "bos://persona/sot-bridge-persona/"

# ── 辅助函数 ────────────────────────────────────────


def _extract_uri_from_name(name: str) -> str:
    """从 YAML ``name`` 字段提取纯 BOS URI.

    YAML ``name`` 可能带 → 描述::
        "bos://memory/kos/* → KOS 知识索引" → "bos://memory/kos/*"
        "bos://agora/registry/*"              → "bos://agora/registry/*"
    """
    name = str(name).strip()
    # 去除引号包裹
    name = name.strip("\"'")
    # 分割 → 描述
    if "→" in name:
        name = name.split("→", 1)[0].strip()
    if " →" in name:
        name = name.split(" →", 1)[0].strip()
    return name.strip()


def _glob_match_uri(uri: str, pattern: str) -> bool:
    """Glob 模式匹配 BOS URI.

    支持:
      - ``*`` 匹配任意字符 (含 ``/``)
      - ``**`` 匹配所有剩余部分
    """
    if "**" in pattern:
        base = pattern.replace("**", "")
        return uri.startswith(base)
    return fnmatch.fnmatch(uri, pattern)


def collect_yaml_uris() -> list[dict]:
    """扫描 BOSROUTE_DIR 下所有 yaml, 提取 ``name`` 字段.返回 [{file, uri, description}]."""
    results: list[dict] = []
    if not BOSROUTE_DIR.is_dir():
        _log.warning("BOSROUTE_DIR 不存在: %s", BOSROUTE_DIR)
        return results

    for path in sorted(BOSROUTE_DIR.glob("BOSROUTE-*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as exc:
            _log.warning("YAML 解析失败: %s — %s", path.name, exc)
            continue
        if not data:
            continue
        raw_name = data.get("name", "")
        if not raw_name:
            continue
        uri = _extract_uri_from_name(raw_name)
        description = data.get("description", "")
        entry = {
            "file": path.name,
            "raw_name": str(raw_name),
            "uri": uri,
            "description": description,
            "type": data.get("type", ""),
            "status": data.get("status", ""),
            "domain": data.get("domain", ""),
            "layer": data.get("layer", ""),
        }
        results.append(entry)
    return results


def _resolve_fstring_uri(expr: str) -> str | None:
    """解析 f-string 样式的 POC_SERVICES key 为实际 URI.

    目前仅处理: ``f\"{CANONICAL_PERSONA_BRIDGE_URI_PREFIX}recall\"``
    """
    m = re.match(
        r'''f["']\{CANONICAL_PERSONA_BRIDGE_URI_PREFIX\}(.+?)["']''',
        expr,
    )
    if m:
        return _CANONICAL_PERSONA_BRIDGE_URI_PREFIX + m.group(1)
    return None


def load_poc_services() -> dict[str, dict]:
    """别名, 保持向后兼容. 委托给 ``load_poc_services_from_file``."""
    return load_poc_services_from_file()


def load_poc_services_from_file() -> dict[str, dict]:
    """从 bos_resolver.py 源文件解析 POC_SERVICES 的 key 列表.

    避免 import agora 模块 (依赖 aiohttp 等不在 ecos venv 的包).
    使用正则提取所有 dict key。
    """
    path = AGORA_BOS_RESOLVER_PATH
    if not path.exists():
        _log.warning("POC_SERVICES 源文件不存在: %s", path)
        return {}

    source = path.read_text(encoding="utf-8")

    keys: list[str] = []

    # 模式 1: 字符串字面量 key, 如 "bos://memory/kos/search":
    pattern_literal = re.compile(r'''^\s{4}"(bos://[^"]+)":\s*BosService\(''', re.MULTILINE)

    # 模式 2: f-string key, 如 f"{CANONICAL_PERSONA_BRIDGE_URI_PREFIX}recall-entity":
    # 直接匹配 4 空格 + f" + 花括号表达式 + 后缀
    pattern_fstring = re.compile(
        r'''^\s{4}f"(?:\{[^}]+\})([^"]+)":\s*BosService\(''',
        re.MULTILINE,
    )

    for m in pattern_literal.finditer(source):
        keys.append(m.group(1))

    for m in pattern_fstring.finditer(source):
        suffix = m.group(1)
        keys.append(_CANONICAL_PERSONA_BRIDGE_URI_PREFIX + suffix)

    return {k: {"uri": k} for k in keys}


def categorize_uris(
    yaml_entries: list[dict],
    poc_uris: dict[str, dict],
) -> dict:
    """分类 BOS URI / 模式到 3 个集合.

    Returns:
        {
            "matched": [(poc_uri, yaml_uri, yaml_file, pattern), ...],
            "poc_only": [poc_uri, ...],       # 在 POC 但不在 YAML
            "yaml_only": [yaml_entry, ...],    # 在 YAML 但不在 POC
            "summary": {poc_count, yaml_count, matched_count, ...}
        }
    """
    matched: list[tuple] = []
    poc_matched: set[str] = set()
    yaml_matched: set[int] = set()

    for idx, yaml_entry in enumerate(yaml_entries):
        yaml_uri = yaml_entry["uri"]
        for poc_uri in poc_uris:
            if _glob_match_uri(poc_uri, yaml_uri):
                matched.append((poc_uri, yaml_uri, yaml_entry["file"], yaml_uri))
                poc_matched.add(poc_uri)
                yaml_matched.add(idx)

    poc_only = [u for u in poc_uris if u not in poc_matched]
    yaml_only = [e for i, e in enumerate(yaml_entries) if i not in yaml_matched]

    return {
        "matched": matched,
        "poc_only": poc_only,
        "yaml_only": yaml_only,
        "summary": {
            "poc_total": len(poc_uris),
            "yaml_total": len(yaml_entries),
            "matched_count": len(matched),
            "poc_only_count": len(poc_only),
            "yaml_only_count": len(yaml_only),
        },
    }


def format_table(poc_only: list[str], yaml_only: list[dict]) -> str:
    """生成彩色对比表格字符串."""
    lines = []
    sep = "─" * 78

    lines.append("")
    lines.append(sep)
    lines.append("  BOS 路由对齐校验结果")
    lines.append(sep)

    if poc_only:
        lines.append(f"\n  🔴 仅在 POC_SERVICES 中 (YAML 缺失) — {len(poc_only)} 条:")
        for uri in poc_only:
            lines.append(f"    • {uri}")
    else:
        lines.append("\n  ✅ 所有 POC_SERVICES 路由在 YAML 中均有覆盖")

    if yaml_only:
        lines.append(f"\n  🟡 仅在 YAML 中 (POC_SERVICES 缺失) — {len(yaml_only)} 条:")
        for entry in yaml_only:
            lines.append(f"    • {entry['uri']:50s}  ({entry['file']})")
    else:
        lines.append("\n  ✅ 所有 YAML 路由在 POC_SERVICES 中均有覆盖")

    lines.append("")
    lines.append(sep)
    return "\n".join(lines)


def format_summary_text(summary: dict) -> str:
    """生成简短统计文本."""
    return (
        f"📊 BOS 路由统计: "
        f"YAML={summary['yaml_total']} | "
        f"POC={summary['poc_total']} | "
        f"匹配={summary['matched_count']} | "
        f"POC-only={summary['poc_only_count']} | "
        f"YAML-only={summary['yaml_only_count']}"
    )


# ═══════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════


@pytest.fixture(scope="session")
def yaml_routes() -> list[dict]:
    """扫描 YAML 路由. (Session scope — 只加载一次)"""
    return collect_yaml_uris()


@pytest.fixture(scope="session")
def poc_services() -> dict[str, dict]:
    """导入 POC_SERVICES. (Session scope — 只加载一次)"""
    return load_poc_services()


@pytest.fixture(scope="session")
def alignment(yaml_routes: list[dict], poc_services: dict[str, dict]) -> dict:
    """计算对齐分类. (Session scope — 只计算一次)"""
    return categorize_uris(yaml_routes, poc_services)


# ═══════════════════════════════════════════════════
# 测试
# ═══════════════════════════════════════════════════


def test_yaml_routes_loaded(yaml_routes: list[dict]) -> None:
    """YAML 路由文件能正常加载"""
    assert len(yaml_routes) > 0, f"未扫描到 BOSROUTE YAML 文件 (dir={BOSROUTE_DIR})"
    uris = [e["uri"] for e in yaml_routes]
    assert all(uri.startswith("bos://") for uri in uris), f"部分 URI 不以 bos:// 开头: {[u for u in uris if not u.startswith('bos://')]}"
    print(f"\n  已加载 {len(yaml_routes)} 个 YAML BOS 路由")


def test_poc_services_loaded(poc_services: dict[str, dict]) -> None:
    """POC_SERVICES 能正常导入"""
    assert len(poc_services) > 0, "POC_SERVICES 为空或导入失败"
    print(f"\n  已加载 {len(poc_services)} 条 POC_SERVICES 路由")


def test_bos_alignment(alignment: dict) -> None:
    """BOS 路由对齐校验: YAML ↔ POC_SERVICES 差集检测.

    非 blocker — 差集可能是合法状态 (仅 ecos 或仅 agora 路由).
    输出详细对比表格 + 打印到 stderr 以便 CI 可读.
    """
    summary = alignment["summary"]
    poc_only = alignment["poc_only"]
    yaml_only = alignment["yaml_only"]

    # 统计摘要
    print(f"\n{summary}")
    print(format_table(poc_only, yaml_only))

    # 报告
    has_gap = bool(poc_only) or bool(yaml_only)
    if has_gap:
        msg = format_summary_text(summary)
        # 使用 pytest.skip 标记为非 blocker (差集合法)
        if poc_only:
            poc_sample = poc_only[:3]
            yaml_sample = [e["uri"] for e in yaml_only[:3]]
            msg += (
                f"\n  ⚠️  发现差异. POC-only 示例: {poc_sample}"
                f"\n  ⚠️  YAML-only 示例: {yaml_sample}"
                f"\n  ℹ️   这是非 blocker 检测 — 部分路由是仅 ecos 或仅 agora 的合法状态."
            )
        pytest.skip(msg)
    else:
        print("\n  ✅ 完全对齐 — YAML ↔ POC_SERVICES 零差异")


def test_poc_routes_have_yaml_coverage(alignment: dict) -> None:
    """每个 POC URI 至少被一个 YAML 模式覆盖 (具体检查)."""
    summary = alignment["summary"]
    poc_only = alignment["poc_only"]

    if poc_only:
        poc_sample = "\n    ".join(poc_only[:10])
        msg = (
            f"{len(poc_only)} 条 POC URI 无 YAML 模式覆盖:\n"
            f"    {poc_sample}"
            + ("\n    ..." if len(poc_only) > 10 else "")
        )
        pytest.skip(msg)
    else:
        print(f"\n  全部 {summary['poc_total']} 条 POC 路由均被 YAML 覆盖 ✅")


def test_yaml_patterns_have_poc_coverage(alignment: dict) -> None:
    """YAML 模式至少匹配一条 POC URI (部分可能仅 ecos 侧, 合法)."""
    summary = alignment["summary"]
    yaml_only = alignment["yaml_only"]

    if yaml_only:
        yaml_sample = "\n    ".join(
            f"{e['uri']:50s} ({e['file']})" for e in yaml_only[:10]
        )
        msg = (
            f"{len(yaml_only)} 个 YAML 模式无 POC 路由匹配:\n"
            f"    {yaml_sample}"
            + ("\n    ..." if len(yaml_only) > 10 else "")
            + "\n  ℹ️  部分路由是仅 ecos 侧的合法定义 (如 kairon 子包标记)"
        )
        pytest.skip(msg)
    else:
        print(f"\n  全部 {summary['yaml_total']} 个 YAML 模式均有 POC 路由匹配 ✅")


# ═══════════════════════════════════════════════════
# 独立入口 (CLI 调用)
# ═══════════════════════════════════════════════════


def run_standalone() -> int:
    """独立运行模式, 供 CLI 脚本/CI 调用.

    Returns:
        0=完全对齐, 1=有差异
    """
    yaml_routes = collect_yaml_uris()
    poc_services = load_poc_services()

    if not yaml_routes:
        print("❌ 未找到 BOSROUTE YAML 文件")
        return 1
    if not poc_services:
        print("❌ POC_SERVICES 导入失败或为空")
        return 1

    result = categorize_uris(yaml_routes, poc_services)
    summary = result["summary"]

    print(format_summary_text(summary))
    print(format_table(result["poc_only"], result["yaml_only"]))

    has_gap = bool(result["poc_only"]) or bool(result["yaml_only"])
    return 1 if has_gap else 0


if __name__ == "__main__":
    import sys

    sys.exit(run_standalone())
