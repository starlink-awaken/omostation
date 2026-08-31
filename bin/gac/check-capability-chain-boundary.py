#!/usr/bin/env python3
"""check-capability-chain-boundary.py — MCP 工具链端到端覆盖验证.

验证 MOF M1 声明 ↔ 实现 ↔ 依赖链的完整性:
  1. 声明存在 (MCPTOOL-*.yaml) → 实现存在 (code)
  2. 依赖链: depends_on 中引用的工具本身必须有声明
  3. 提供链: provides 中引用的工具本身必须有声明
  4. 孤儿声明: 声明了但无实现的工具
  5. 孤儿实现: 有实现但无声明的工具 (MOF 漏注册)

rule_id: CR-X4-CAPABILITY-CHAIN-BOUNDARY

用法:
    python3 bin/gac/check-capability-chain-boundary.py        # 全量扫
    python3 bin/gac/check-capability-chain-boundary.py --json  # JSON 输出
    python3 bin/gac/check-capability-chain-boundary.py --ci    # CI 模式 (需要 MCP server)
"""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
MCPTOOL_DIR = REPO / "projects/ecos/src/ecos/ssot/mof/m1/mcptool"

# server -> 实现扫描配置
SERVERS: dict[str, dict] = {
    "cockpit": {
        "cmd": [
            "uv",
            "run",
            "--project",
            str(REPO / "projects/cockpit"),
            "cockpit",
            "mcp",
            "--list-tools",
        ],
        "prefix": "MCPTOOL-COCKPIT-",
    },
    "agora": {
        "cmd": None,  # AST scan
        "prefix": "MCPTOOL-AGORA-",
        "source_dirs": [
            str(REPO / "projects/agora/src/agora/server"),
        ],
    },
}


def _scan_ast_mcp_tools(source_dirs: list[str]) -> set[str]:
    """Scan Python source for @mcp.tool() decorated functions via AST.

    Also handles mcp.tool()(func_name) pattern via regex fallback.
    """
    import re

    tools: set[str] = set()
    for source_dir in source_dirs:
        dirpath = Path(source_dir)
        if not dirpath.exists():
            continue
        for py_file in sorted(dirpath.rglob("*.py")):
            if "agent_cell" in py_file.name:
                continue  # not registered in production mcp.py
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"))
            except (SyntaxError, OSError):
                continue
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                for deco in node.decorator_list:
                    deco_str = ast.dump(deco)
                    if "mcp" in deco_str and "tool" in deco_str:
                        tools.add(node.name)
            # Regex fallback for mcp.tool()(func_name) pattern
            content = py_file.read_text(encoding="utf-8")
            for m in re.finditer(r'mcp\.tool\(\)\((\w+)\)', content):
                tools.add(m.group(1))
    return tools


def _load_cli_tools(cmd: list[str]) -> set[str]:
    """Load tools from CLI output (cockpit --list-tools)."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, cwd=str(REPO), timeout=60
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return set()
    tools: set[str] = set()
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith("│") and line.count("│") >= 3:
            name = line.split("│")[1].strip()
            if name and name.replace("_", "").replace("-", "").isalnum() and name.islower():
                tools.add(name)
    return tools


def load_all_declarations() -> dict[str, dict]:
    """Load all MCPTOOL YAML declarations. Returns {tool_name: {server, depends_on, provides, status}}."""
    declarations: dict[str, dict] = {}
    for yfile in sorted(MCPTOOL_DIR.glob("MCPTOOL-*.yaml")):
        data = yaml.safe_load(yfile.read_text(encoding="utf-8")) or {}
        props = data.get("properties") or {}
        tool_name = props.get("tool_name") or data.get("name")
        server = props.get("server", "unknown")
        relations = data.get("relations") or {}
        declarations[str(tool_name)] = {
            "server": server,
            "depends_on": relations.get("depends_on") or [],
            "provides": relations.get("provides") or [],
            "status": data.get("status", "unknown"),
            "file": yfile.name,
        }
    return declarations


def load_implemented_tools(server: str) -> set[str]:
    """Get implemented tools for a server."""
    cfg = SERVERS[server]
    cmd = cfg.get("cmd")
    if cmd is None and "source_dirs" in cfg:
        return _scan_ast_mcp_tools(cfg["source_dirs"])
    if cmd is None:
        return set()
    return _load_cli_tools(cmd)


def check_chain_boundaries() -> dict:
    """Full capability chain boundary check."""
    declarations = load_all_declarations()
    all_declared_names = set(declarations.keys())

    # Load implementations per server
    implementations: dict[str, set[str]] = {}
    for server in SERVERS:
        implementations[server] = load_implemented_tools(server)

    all_implemented: set[str] = set()
    for impl_set in implementations.values():
        all_implemented |= impl_set

    # Check 1: Declaration ↔ Implementation drift per server
    server_drift: dict[str, dict] = {}
    for server, cfg in SERVERS.items():
        server_decls = {
            name for name, d in declarations.items() if d["server"] == server
        }
        server_impls = implementations[server]
        decl_no_impl = sorted(server_decls - server_impls)
        impl_no_decl = sorted(server_impls - server_decls)
        server_drift[server] = {
            "declared": len(server_decls),
            "implemented": len(server_impls),
            "decl_no_impl": decl_no_impl,
            "impl_no_decl": impl_no_decl,
        }

    # Check 2: Dependency chain integrity (depends_on references must exist)
    broken_deps: list[dict] = []
    for tool_name, decl in declarations.items():
        for dep in decl["depends_on"]:
            if dep not in all_declared_names:
                broken_deps.append({
                    "tool": tool_name,
                    "missing_dep": dep,
                    "type": "depends_on",
                })

    # Check 3: Provides chain integrity (provides references must exist)
    broken_provides: list[dict] = []
    for tool_name, decl in declarations.items():
        for prov in decl["provides"]:
            if prov not in all_declared_names:
                broken_provides.append({
                    "tool": tool_name,
                    "missing_ref": prov,
                    "type": "provides",
                })

    # Check 4: Orphan declarations (declared but not implemented anywhere)
    orphan_decls = sorted(all_declared_names - all_implemented)

    # Check 5: Orphan implementations (implemented but not declared)
    orphan_impls = sorted(all_implemented - all_declared_names)

    return {
        "server_drift": server_drift,
        "broken_deps": broken_deps,
        "broken_provides": broken_provides,
        "orphan_declarations": orphan_decls,
        "orphan_implementations": orphan_impls,
        "total_declared": len(all_declared_names),
        "total_implemented": len(all_implemented),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="MCP 工具链端到端覆盖验证")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    result = check_chain_boundaries()

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("=== MCP 工具链端到端覆盖验证 ===\n")
        print(f"声明总数: {result['total_declared']} / 实现总数: {result['total_implemented']}")

        for server, drift in result["server_drift"].items():
            print(f"\n【{server.upper()}】声明 {drift['declared']} / 实现 {drift['implemented']}")
            if drift["decl_no_impl"]:
                print(f"  声明无实现 ({len(drift['decl_no_impl'])}): {drift['decl_no_impl']}")
            if drift["impl_no_decl"]:
                print(f"  实现无声明 ({len(drift['impl_no_decl'])}): {drift['impl_no_decl']}")
            if not drift["decl_no_impl"] and not drift["impl_no_decl"]:
                print("  一致")

        if result["broken_deps"]:
            print(f"\n断裂依赖链 ({len(result['broken_deps'])}):")
            for bd in result["broken_deps"]:
                print(f"  {bd['tool']} -> {bd['missing_dep']} (depends_on)")

        if result["broken_provides"]:
            print(f"\n断裂提供链 ({len(result['broken_provides'])}):")
            for bp in result["broken_provides"]:
                print(f"  {bp['tool']} -> {bp['missing_ref']} (provides)")

        if result["orphan_declarations"]:
            print(f"\n孤儿声明 ({len(result['orphan_declarations'])}): {result['orphan_declarations']}")
        if result["orphan_implementations"]:
            print(f"\n孤儿实现 ({len(result['orphan_implementations'])}): {result['orphan_implementations']}")

        total_issues = (
            len(result["broken_deps"])
            + len(result["broken_provides"])
            + len(result["orphan_declarations"])
            + len(result["orphan_implementations"])
        )
        for drift in result["server_drift"].values():
            total_issues += len(drift["decl_no_impl"]) + len(drift["impl_no_decl"])

        print(f"\nTotal: {total_issues} issues")

    has_issues = (
        result["broken_deps"]
        or result["broken_provides"]
        or result["orphan_declarations"]
        or result["orphan_implementations"]
        or any(
            d["decl_no_impl"] or d["impl_no_decl"]
            for d in result["server_drift"].values()
        )
    )
    return 1 if has_issues else 0


if __name__ == "__main__":
    sys.exit(main())
