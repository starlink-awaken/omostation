#!/usr/bin/env python3
"""能力注册表生成器 — 扫描全生态 MCP/BOS/CLI，输出 capability-registry.yaml.

这是「能力全景覆盖」方案的 SSOT 生成器。所有 help 文档、能力地图、
CLI 参考均从本生成器输出的 YAML 派生。

扫描源:
  - projects/*/src/**/mcp_server.py  → Python MCP 工具
  - projects/*/src/**/mcp.py         → Python MCP 工具
  - projects/**/mcp_server.ts        → TypeScript MCP 工具
  - projects/agora/etc/bos-services.yaml → BOS 服务
  - projects/cockpit/src/cockpit/cli.py  → CLI 命令

输出: docs/generated/capability-registry.yaml

准确性说明 (静态扫描的固有限制):
  本生成器用正则/AST 静态提取工具名, 对动态注册的工具 (如 mcp.tool(name=var))
  可能漏抓, 实测准确率 ~95% (如 KOS 静态 44 vs 运行时 46)。
  长期改进: 加 --verify 模式启动各 MCP server 调 list_tools() 做运行时内省,
  用运行时结果校正静态扫描。当前数字作为"能力规模近似"已足够驱动 help/文档/UI。

Usage:
    uv run --with pyyaml python bin/cockpit/gen-capability-registry.py
    uv run --with pyyaml python bin/cockpit/gen-capability-registry.py --json
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

try:
    import yaml
except ImportError:
    print("❌ 需要 pyyaml: uv run --with pyyaml python ...", file=sys.stderr)
    sys.exit(2)

WORKSPACE = Path(__file__).resolve().parents[2]
OUTPUT_YAML = WORKSPACE / "docs" / "generated" / "capability-registry.yaml"

# ── MCP server 探测 ──────────────────────────────────────────

# 已知的 MCP server 文件 (layer, transport, ports)
# 避免 glob 漫无目的扫描, 用显式清单更稳 (KISS)
_KNOWN_MCP_SERVERS: list[dict] = [
    {"id": "omo", "name": "OMO Agent OS Kernel", "layer": "L2", "file": "projects/omo/src/omo/mcp_server.py", "transport": "stdio"},
    {"id": "kos", "name": "KOS Knowledge Retrieval", "layer": "L2", "file": "projects/kairon/packages/kos/src/kos/mcp/fastmcp_app.py", "transport": "stdio"},
    {"id": "kos-stdio", "name": "KOS (stdio JSON-RPC, legacy)", "layer": "L2", "file": "projects/kairon/packages/kos/src/kos/mcp/fastmcp_app.py", "transport": "stdio", "note": "kos-stdio 与 kos 共享同一套 44 工具, 仅传输层不同"},
    {"id": "l4-kernel", "name": "L4 Self-Layer Kernel", "layer": "L4", "file": "projects/l4-kernel/src/l4_kernel/mcp_server.py", "transport": "stdio/http/sse", "ports": {"http": 7455, "sse": 7456}},
    {"id": "agora", "name": "Agora Service Convergence Hub", "layer": "I0", "file": "projects/agora/src/agora/server/mcp.py", "transport": "stdio/sse", "extra_glob": "projects/agora/src/agora/server/tools_*.py"},
    {"id": "ecos", "name": "eCOS SSOT Kernel", "layer": "L0", "file": "projects/ecos/src/ecos/mcp_server.py", "transport": "stdio"},
    {"id": "ecos-ssot", "name": "eCOS L0 SSOT", "layer": "L0", "file": "projects/ecos/src/ecos/l0/ssot/mcp_server.py", "transport": "stdio"},
    {"id": "ecos-integration", "name": "eCOS Integration", "layer": "L0", "file": "projects/ecos/src/ecos/services/integration/mcp_server.py", "transport": "stdio"},
    {"id": "metaos", "name": "MetaOS Orchestration", "layer": "L2", "file": "projects/metaos/src/metaos/mcp_server.py", "transport": "stdio"},
    {"id": "aetherforge", "name": "AetherForge Compute", "layer": "X", "file": "projects/aetherforge/src/aetherforge/mcp_server.py", "transport": "stdio"},
    {"id": "model-driven", "name": "Model-Driven Lifecycle", "layer": "M0", "file": "projects/model-driven/src/model_driven/mcp_server.py", "transport": "stdio"},
    {"id": "model-driven-fastmcp", "name": "Model-Driven FastMCP", "layer": "M0", "file": "projects/model-driven/src/model_driven/fastmcp_server.py", "transport": "stdio"},
    {"id": "c2g", "name": "C2G Strategy Compass", "layer": "X", "file": "projects/c2g/src/c2g/mcp_server.py", "transport": "stdio"},
    {"id": "family-hub", "name": "Family Hub", "layer": "X", "file": "projects/family-hub/mcp_server.py", "transport": "stdio"},
    {"id": "agent-runtime", "name": "Cockpit Agent Runtime", "layer": "L3", "file": "projects/cockpit/src/cockpit/agent_runtime_mcp_server.py", "transport": "stdio"},
    {"id": "cockpit-mcp", "name": "Cockpit Workspace MCP", "layer": "L3", "file": "projects/cockpit/src/cockpit/scripts/cockpit_mcp.py", "transport": "stdio", "note": "工具经 _tool() 别名注册, 含 workspace_context/cards_check 等"},
    {"id": "iris", "name": "Iris", "layer": "L2", "file": "projects/kairon/packages/iris/src/iris/mcp_server.py", "transport": "stdio"},
    {"id": "sophia", "name": "Sophia Research Paradigm", "layer": "L2", "file": "projects/kairon/packages/sophia/src/sophia/server/mcp_server.py", "transport": "stdio"},
    {"id": "kronos", "name": "Kronos", "layer": "L2", "file": "projects/kairon/packages/kronos/src/kronos/mcp_server.py", "transport": "stdio"},
    {"id": "minerva", "name": "Minerva", "layer": "L2", "file": "projects/kairon/packages/minerva/src/minerva/mcp_server/server.py", "transport": "stdio"},
    {"id": "codeanalyze", "name": "CodeAnalyze", "layer": "L2", "file": "projects/kairon/packages/codeanalyze/src/codeanalyze/mcp.py", "transport": "stdio"},
    {"id": "forge", "name": "Forge", "layer": "L2", "file": "projects/kairon/packages/forge/src/mcp_server.py", "transport": "stdio"},
    {"id": "ontoderive", "name": "OntoDerive", "layer": "L2", "file": "projects/kairon/packages/ontoderive/src/ontoderive/mcp_server.py", "transport": "stdio"},
    {"id": "toolforge", "name": "ToolForge", "layer": "L2", "file": "projects/kairon/packages/ontoderive/src/ontoderive/toolforge/mcp_server.py", "transport": "stdio"},
    {"id": "gbrain", "name": "gbrain Knowledge DB", "layer": "L2", "file": "projects/gbrain/src/core/operations/exports.ts", "transport": "stdio", "entry": "projects/gbrain/src/mcp-entry.ts", "note": "工具从 operations 数组动态生成"},
]

# Python @mcp.tool() / @mcp.tool(name="x") / register 函数调用模式
_RE_PY_TOOL_DECORATOR = re.compile(
    r'@(?:mcp|server|app|self|_mcp)\.tool\s*\(\s*(?:name\s*=\s*["\']([^"\']+)["\'])?\s*\)'
)
_RE_PY_TOOL_CALL = re.compile(
    r'\.(?:tool|register_tool)\s*\(\s*(?:name\s*=\s*)?["\']([a-zA-Z0-9_.\-]+)["\']'
)
# metaos 风格 @_h("name") / model-driven self._register_tool("name", ...)
_RE_RAW_HANDLER = re.compile(r'@_h\s*\(\s*["\']([a-zA-Z0-9_.\-]+)["\']')
_RE_REGISTER_TOOL = re.compile(
    r'(?:self\.)?_?register_?(?:default_)?tool\s*\(\s*["\']([a-zA-Z0-9_.\-]+)["\']'
)
# l4-kernel TOOLS dict / TOOLS = {...}
_RE_TOOLS_KEYS = re.compile(r'TOOLS\s*[:=]\s*\{')
# TS: server.tool("name", ...)
_RE_TS_TOOL = re.compile(r'\.tool\s*\(\s*["\']([a-zA-Z0-9_.\-]+)["\']')


def _extract_tools_from_python(file_path: Path) -> list[str]:
    """从 Python MCP server 文件提取工具名 (多策略: 正则)."""
    if not file_path.exists():
        return []
    content = file_path.read_text(encoding="utf-8", errors="replace")
    tools: list[str] = []
    seen: set[str] = set()

    # 策略 1: @xxx.tool() / @xxx.tool(name="n")
    for m in _RE_PY_TOOL_DECORATOR.finditer(content):
        name = m.group(1)
        if name and name not in seen:
            seen.add(name)
            tools.append(name)

    # 策略 2: .tool("name", ...) / .register_tool("name", ...)
    for m in _RE_PY_TOOL_CALL.finditer(content):
        name = m.group(1)
        if name not in seen:
            seen.add(name)
            tools.append(name)

    # 策略 3: metaos @_h("name")
    for m in _RE_RAW_HANDLER.finditer(content):
        name = m.group(1)
        if name not in seen:
            seen.add(name)
            tools.append(name)

    # 策略 3b: model-driven self._register_tool("name", ...)
    for m in _RE_REGISTER_TOOL.finditer(content):
        name = m.group(1)
        if name not in seen:
            seen.add(name)
            tools.append(name)

    # 策略 4: l4-kernel TOOLS dict 字面量键
    if _RE_TOOLS_KEYS.search(content):
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id == "TOOLS" for t in node.targets
                ) and isinstance(node.value, ast.Dict):
                    for key in node.value.keys:
                        if isinstance(key, ast.Constant) and isinstance(key.value, str):
                            if key.value not in seen:
                                seen.add(key.value)
                                tools.append(key.value)
        except SyntaxError:
            pass

    # 策略 5: @xxx.tool() 或 @_tool() 无名时, 从紧邻的 def/async def 提取函数名
    if not tools:
        for m in re.finditer(
            r'@(?:mcp|server|app)\.tool\s*\([^)]*\)|@_tool\s*\(\s*\)\s*\n\s*(?:async\s+)?def\s+([a-zA-Z_][a-zA-Z0-9_]*)',
            content,
        ):
            name = m.group(1)
            if name and name not in seen:
                seen.add(name)
                tools.append(name)
        # 单独处理 @_tool() 模式 (cockpit_mcp 别名)
        for m in re.finditer(
            r'@_tool\s*\(\s*\)\s*\n\s*(?:async\s+)?def\s+([a-zA-Z_][a-zA-Z0-9_]*)',
            content,
        ):
            name = m.group(1)
            if name not in seen:
                seen.add(name)
                tools.append(name)

    # 策略 5b: cockpit_mcp 风格 _tool("name", ...) 别名调用
    for m in re.finditer(r'(?:^|\s)_tool\s*\(\s*["\']([a-zA-Z0-9_.\-]+)["\']', content):
        name = m.group(1)
        if name not in seen:
            seen.add(name)
            tools.append(name)

    # 策略 6: ecos-ssot TOOLS = [{"name": "x"}, ...] 列表字典
    for m in re.finditer(r'"name"\s*:\s*"([a-zA-Z0-9_.\-]+)"', content):
        name = m.group(1)
        if name not in seen and not name.startswith("http"):
            seen.add(name)
            tools.append(name)

    # 策略 7: ecos-integration def handle_xxx(args) handler 函数
    for m in re.finditer(r'def\s+(handle_[a-zA-Z0-9_]+)\s*\(', content):
        name = m.group(1)
        if name not in seen:
            seen.add(name)
            tools.append(name)

    return sorted(tools)


def _extract_tools_from_typescript(file_path: Path) -> list[str]:
    """从 TS MCP server 文件提取工具名."""
    if not file_path.exists():
        return []
    content = file_path.read_text(encoding="utf-8", errors="replace")
    tools: list[str] = []
    seen: set[str] = set()
    # 策略 1: .tool("name", ...) 调用
    for m in _RE_TS_TOOL.finditer(content):
        name = m.group(1)
        if name not in seen:
            seen.add(name)
            tools.append(name)
    # 策略 2: gbrain operations 数组 — 提取导入的 operation 名 (get_page, put_page 等)
    # 匹配: import { op1, op2 } from "...";  和数组内的裸标识符
    if "operations" in content and "import" in content:
        # 从 import 语句提取
        for m in re.finditer(r'import\s*\{([^}]+)\}\s*from\s*"', content):
            for name in re.findall(r'[a-z_][a-zA-Z0-9_]*', m.group(1)):
                if name not in seen:
                    seen.add(name)
                    tools.append(name)
    return sorted(tools)


def scan_mcp_servers() -> tuple[list[dict], int]:
    """扫描所有已知 MCP 服务器, 返回 (server_list, total_tool_count)."""
    servers: list[dict] = []
    total = 0
    for spec in _KNOWN_MCP_SERVERS:
        file_rel = spec["file"]
        file_path = WORKSPACE / file_rel
        srv: dict = {
            "id": spec["id"],
            "name": spec["name"],
            "layer": spec["layer"],
            "file": file_rel,
            "transport": spec["transport"],
            "exists": file_path.exists(),
        }
        if "ports" in spec:
            srv["ports"] = spec["ports"]
        if file_path.suffix == ".py":
            srv["tools"] = _extract_tools_from_python(file_path)
        elif file_path.suffix in (".ts", ".js"):
            srv["tools"] = _extract_tools_from_typescript(file_path)
        else:
            srv["tools"] = []

        # 扫描 extra_glob (如 agora 的 tools_*.py 分散文件)
        extra_glob = spec.get("extra_glob")
        if extra_glob:
            extra_tools: list[str] = []
            for ef in sorted(WORKSPACE.glob(extra_glob)):
                if ef.suffix == ".py":
                    extra_tools.extend(_extract_tools_from_python(ef))
            # 合并去重
            merged: list[str] = list(srv["tools"])
            seen_set: set[str] = set(merged)
            for t in extra_tools:
                if t not in seen_set:
                    seen_set.add(t)
                    merged.append(t)
            srv["tools"] = sorted(merged)

        srv["tool_count"] = len(srv["tools"])
        total += srv["tool_count"]
        servers.append(srv)
    return servers, total


# ── BOS services 扫描 ─────────────────────────────────────────

def scan_bos_services() -> tuple[dict[str, list[dict]], int]:
    """从 bos-services.yaml 提取所有服务, 按 domain 分组."""
    bos_path = WORKSPACE / "projects" / "agora" / "etc" / "bos-services.yaml"
    if not bos_path.exists():
        return {}, 0
    data = yaml.safe_load(bos_path.read_text(encoding="utf-8"))
    services_raw = data.get("services") or data.get("bos_services") or []
    domains: dict[str, list[dict]] = {}
    total = 0
    for svc in services_raw:
        uri = svc.get("uri") or svc.get("id") or ""
        # bos://{domain}/{package}/{action}
        domain = ""
        if uri.startswith("bos://"):
            domain = uri[6:].split("/")[0]
        elif "domain" in svc:
            domain = str(svc.get("domain"))
        entry = {
            "uri": uri,
            "description": svc.get("description") or svc.get("desc") or "",
            "transport": svc.get("transport") or "",
            "status": svc.get("status") or "active",
        }
        domains.setdefault(domain, []).append(entry)
        total += 1
    return domains, total


# ── CLI commands 扫描 ──────────────────────────────────────────

_RE_ADD_PARSER = re.compile(r'sub\.add_parser\s*\(\s*["\']([a-zA-Z0-9_\-]+)["\']')


def scan_cli_commands() -> list[dict]:
    """从 cockpit cli.py 提取所有 add_parser 注册的子命令."""
    cli_path = WORKSPACE / "projects" / "cockpit" / "src" / "cockpit" / "cli.py"
    if not cli_path.exists():
        return []
    content = cli_path.read_text(encoding="utf-8")
    seen: set[str] = set()
    commands: list[dict] = []
    for m in _RE_ADD_PARSER.finditer(content):
        name = m.group(1)
        if name in seen:
            continue
        seen.add(name)
        # 尝试从同一行后面提取 help="..."
        rest = content[m.end():m.end() + 200]
        help_match = re.search(r'help\s*=\s*["\']([^"\']+)["\']', rest)
        commands.append({
            "name": name,
            "description": help_match.group(1) if help_match else "",
        })
    return sorted(commands, key=lambda c: c["name"])


# ── 主流程 ─────────────────────────────────────────────────────

def build_registry() -> dict:
    servers, total_tools = scan_mcp_servers()
    bos_domains, total_bos = scan_bos_services()
    cli_commands = scan_cli_commands()

    bos_summary = {d: len(v) for d, v in sorted(bos_domains.items())}

    registry = {
        "version": "1.0.0",
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generator": "bin/cockpit/gen-capability-registry.py",
        "totals": {
            "mcp_servers": len(servers),
            "mcp_tools": total_tools,
            "bos_services": total_bos,
            "bos_domains": len(bos_domains),
            "cli_commands": len(cli_commands),
        },
        "mcp_servers": servers,
        "bos_services": {
            "_domain_counts": bos_summary,
            "domains": {d: bos_domains[d] for d in sorted(bos_domains)},
        },
        "cli_commands": cli_commands,
    }
    return registry


def write_yaml(registry: dict) -> Path:
    OUTPUT_YAML.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "# docs/generated/capability-registry.yaml — 全生态能力注册表 SSOT\n"
        "# 自动生成，请勿手动编辑\n"
        f"# 生成器: bin/cockpit/gen-capability-registry.py\n"
        f"# 生成时间: {registry['generated_at']}\n\n"
    )
    body = yaml.dump(registry, allow_unicode=True, sort_keys=False, default_flow_style=False, width=120)
    new_content = header + body

    # 时间戳稳定: 若已存在文件且仅时间戳不同, 保留旧文件避免假漂移
    if OUTPUT_YAML.exists():
        old_content = OUTPUT_YAML.read_text(encoding="utf-8")
        # 将所有 ISO 时间戳 (2026-08-02T10:17:40Z) 替换为占位符后比较
        iso_pattern = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z"
        old_no_ts = re.sub(iso_pattern, "TIMESTAMP", old_content)
        new_no_ts = re.sub(iso_pattern, "TIMESTAMP", new_content)
        if old_no_ts == new_no_ts:
            return OUTPUT_YAML  # 内容无变化, 不写 (避免时间戳假漂移)

    OUTPUT_YAML.write_text(new_content, encoding="utf-8")
    return OUTPUT_YAML


def verify_runtime(registry: dict) -> int:
    """运行时内省校验 — 对可 in-process 访问的 MCP server 调 list_tools() 对比静态数.

    目前覆盖 cockpit 自身 MCP (可 import). 其他 server 需独立启动, 留待后续.
    返回: 0=全部匹配, 1=有偏差.
    """
    import asyncio

    runtime_checks: list[dict] = []

    # cockpit MCP — 可 in-process 内省
    try:
        sys.path.insert(0, str(WORKSPACE / "projects" / "cockpit" / "src"))
        from cockpit.scripts.cockpit_mcp import mcp  # type: ignore[import-not-found]

        async def _list() -> list[str]:
            tools = await mcp.list_tools()
            return [getattr(t, "name", str(t)) for t in (tools or [])]

        runtime_tools = set(asyncio.run(_list()))
        # 注册表中 cockpit-mcp 的工具 (cockpit_mcp.py 的入口)
        static_entry = next((s for s in registry["mcp_servers"] if s["id"] == "cockpit-mcp"), {})
        static_tools = set(static_entry.get("tools", []))
        match = runtime_tools == static_tools
        runtime_checks.append({
            "server": "cockpit-mcp (in-process)",
            "runtime": len(runtime_tools),
            "static": len(static_tools),
            "match": match,
            "missing": sorted(static_tools - runtime_tools)[:5],
            "extra": sorted(runtime_tools - static_tools)[:5],
        })
    except Exception as exc:
        runtime_checks.append({"server": "cockpit-mcp", "error": str(exc)[:80]})

    print("🔍 运行时内省校验 (in-process MCP servers):")
    print("=" * 60)
    all_match = True
    for chk in runtime_checks:
        if "error" in chk:
            print(f"  ⚠️  {chk['server']}: 内省失败 ({chk['error']})")
            continue
        flag = "✅" if chk["match"] else "⚠️ "
        print(f"  {flag} {chk['server']}: 运行时={chk['runtime']} 静态={chk['static']}")
        if not chk["match"]:
            all_match = False
            if chk["missing"]:
                print(f"     静态多 (运行时无): {chk['missing']}")
            if chk["extra"]:
                print(f"     运行时多 (静态漏): {chk['extra']}")
    print("=" * 60)
    print("✅ 全部匹配" if all_match else "⚠️  有偏差 — 见上方详情 (动态注册工具静态扫描会漏)")
    return 0 if all_match else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="能力注册表生成器")
    parser.add_argument("--json", action="store_true", help="输出 JSON 到 stdout (不写文件)")
    parser.add_argument("--quiet", action="store_true", help="静默模式")
    parser.add_argument("--verify", action="store_true", help="运行时内省校验 (对比静态 vs 实际 MCP 工具)")
    args = parser.parse_args()

    registry = build_registry()

    if args.verify:
        return verify_runtime(registry)

    if args.json:
        json.dump(registry, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0

    out = write_yaml(registry)
    t = registry["totals"]
    if not args.quiet:
        print(f"✅ 能力注册表已生成: {out.relative_to(WORKSPACE)}")
        print(f"   MCP 服务器: {t['mcp_servers']}  |  MCP 工具: {t['mcp_tools']}")
        print(f"   BOS 服务: {t['bos_services']}  |  BOS 域: {t['bos_domains']}")
        print(f"   CLI 命令: {t['cli_commands']}")
        print(f"   运行时校验: python {Path(__file__).name} --verify")
    return 0


if __name__ == "__main__":
    sys.exit(main())
