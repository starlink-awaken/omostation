#!/usr/bin/env python3
"""check-mcptool-impl-drift — MOF M1 MCPTOOL 注册 ↔ 实现 drift 检测.

对比 ecos m1/mcptool/MCPTOOL-<SERVER>-*.yaml (声明面) vs 实现 (cockpit mcp --list-tools).
报: 声明无实现 (改名/缺失) + 实现无声明 (MOF 漏注册).

背景: dogfo decl-exec-gap-meta-pattern 发现 — GaC M1实例drift 只查 registry↔M1 (注册表层),
不查 MOF 注册↔cockpit 实现. mof-drift 检项目代码 drift (sys.path/TODO/stale tasks), 架构错配.
此探针补盲区.

用法:
    python3 bin/check-mcptool-impl-drift.py        # 全量扫
    python3 bin/check-mcptool-impl-drift.py --json  # JSON 输出
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
MCPTOOL_DIR = REPO / "projects/ecos/src/ecos/ssot/mof/m1/mcptool"

# server -> (实现命令, MCPTOOL 文件前缀)
SERVERS: dict[str, dict] = {
    "COCKPIT": {
        "cmd": [
            "uv", "run", "--project", str(REPO / "projects/cockpit"),
            "cockpit", "mcp", "--list-tools",
        ],
        "prefix": "MCPTOOL-COCKPIT-",
    },
}


def load_declared_tools() -> dict[str, set[str]]:
    """扫 MCPTOOL-<SERVER>-*.yaml 提取 properties.tool_name (声明面)."""
    declared: dict[str, set[str]] = {}
    for server, cfg in SERVERS.items():
        declared[server] = set()
        for yfile in sorted(MCPTOOL_DIR.glob(f"{cfg['prefix']}*.yaml")):
            data = yaml.safe_load(yfile.read_text(encoding="utf-8")) or {}
            props = data.get("properties") or {}
            tool_name = props.get("tool_name") or data.get("name")
            if tool_name:
                declared[server].add(str(tool_name))
    return declared


def load_implemented_tools(server: str) -> set[str]:
    """跑 cockpit mcp --list-tools 解析工具名 (执行面)."""
    cmd = SERVERS[server]["cmd"]
    result = subprocess.run(
        cmd, capture_output=True, text=True, cwd=str(REPO), timeout=60
    )
    tools: set[str] = set()
    for line in result.stdout.splitlines():
        line = line.strip()
        # cockpit 输出格式: │ <tool_name> │ <desc> │
        if line.startswith("│") and line.count("│") >= 3:
            name = line.split("│")[1].strip()
            # 过滤表头/分隔符/中文 (工具名是 snake_case)
            if name and name.replace("_", "").replace("-", "").isalnum() and name.islower():
                tools.add(name)
    return tools


def detect_drift() -> dict[str, dict]:
    """返回 {server: {declared, implemented, decl_no_impl, impl_no_decl}}."""
    declared = load_declared_tools()
    out: dict[str, dict] = {}
    for server in SERVERS:
        implemented = load_implemented_tools(server)
        decl = declared[server]
        out[server] = {
            "declared_count": len(decl),
            "implemented_count": len(implemented),
            "decl_no_impl": sorted(decl - implemented),  # 声明无实现 (改名/缺失)
            "impl_no_decl": sorted(implemented - decl),  # 实现无声明 (MOF 漏注册)
        }
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="MCPTOOL 注册 ↔ 实现 drift")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    drift = detect_drift()

    if args.json:
        print(json.dumps(drift, ensure_ascii=False, indent=2))
    else:
        print("=== MCPTOOL 注册 ↔ 实现 drift 检测 ===\n")
        total = 0
        for server, d in drift.items():
            print(f"【{server}】声明 {d['declared_count']} / 实现 {d['implemented_count']}")
            if d["decl_no_impl"]:
                print(f"  🔴 声明无实现 ({len(d['decl_no_impl'])}): {d['decl_no_impl']}")
            if d["impl_no_decl"]:
                print(f"  🟡 实现无声明 ({len(d['impl_no_decl'])}): {d['impl_no_decl']}")
            if not d["decl_no_impl"] and not d["impl_no_decl"]:
                print("  ✅ 一致")
            total += len(d["decl_no_impl"]) + len(d["impl_no_decl"])
            print()
        print(f"Total: {total} drifts")
    return 1 if any(d["decl_no_impl"] or d["impl_no_decl"] for d in drift.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
