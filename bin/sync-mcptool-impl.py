#!/usr/bin/env python3
"""sync-mcptool-impl — 同步 MOF M1 MCPTOOL 注册 ↔ cockpit 实现.

基于 check-mcptool-impl-drift 报告:
- impl_no_decl (实现无声明): 生成新 MCPTOOL yaml (从 cockpit MCP 实现)
- decl_no_impl (声明无实现): 删除过时 MCPTOOL yaml (改名/合并的旧名)

用法:
    python3 bin/sync-mcptool-impl.py --dry-run  # 预览变更
    python3 bin/sync-mcptool-impl.py             # 真同步 (写文件)
"""
from __future__ import annotations

import argparse
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
MCPTOOL_DIR = REPO / "projects/ecos/src/ecos/ssot/mof/m1/mcptool"
PREFIX = "MCPTOOL-COCKPIT-"


def load_declared() -> dict[str, Path]:
    """扫 MCPTOOL-COCKPIT-*.yaml 提取 {tool_name: yfile_path}."""
    declared: dict[str, Path] = {}
    for yfile in sorted(MCPTOOL_DIR.glob(f"{PREFIX}*.yaml")):
        data = yaml.safe_load(yfile.read_text(encoding="utf-8")) or {}
        props = data.get("properties") or {}
        name = props.get("tool_name") or data.get("name")
        if name:
            declared[str(name)] = yfile
    return declared


def load_implemented() -> set[str]:
    """跑 cockpit mcp --list-tools 解析 tool_name."""
    cmd = [
        "uv", "run", "--project", str(REPO / "projects/cockpit"),
        "cockpit", "mcp", "--list-tools",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO), timeout=60)
    tools: set[str] = set()
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith("│") and line.count("│") >= 3:
            name = line.split("│")[1].strip()
            if name and name.replace("_", "").replace("-", "").isalnum() and name.islower():
                tools.add(name)
    return tools


def gen_payload(tool_name: str) -> dict:
    """生成 MCPTOOL yaml 内容 (照 MCPTOOL-COCKPIT-cards_check 模板)."""
    now_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    now_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00Z")
    return {
        "id": f"MCPTOOL-COCKPIT-{tool_name}",
        "type": "MCPTool",
        "subtype": "CockpitTool",
        "name": tool_name,
        "description": f"cockpit MCP 工具: {tool_name}",
        "status": "active",
        "domain": "meta",
        "created": now_date,
        "version": "1.0.0",
        "layer": "L3",
        "properties": {"tool_name": tool_name, "server": "cockpit"},
        "model_driven_refs": {"source_file": "projects/ecos/src/ecos/ssot/mof/m1/"},
        "state_history": [
            {
                "state": "active",
                "timestamp": now_ts,
                "reason": "sync from cockpit mcp --list-tools (MOF 注册 ↔ 实现 drift 治本, PR#125 探针 follow-up)",
            }
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="同步 MOF MCPTOOL 注册 ↔ cockpit 实现")
    parser.add_argument("--dry-run", action="store_true", help="预览不写")
    args = parser.parse_args()

    declared = load_declared()
    implemented = load_implemented()
    decl_names = set(declared.keys())
    to_add = sorted(implemented - decl_names)  # 实现无声明 → 生成
    to_remove = sorted(decl_names - implemented)  # 声明无实现 → 删除

    print(f"=== MCPTOOL sync ({'dry-run' if args.dry_run else 'LIVE'}) ===")
    print(f"声明 {len(decl_names)} / 实现 {len(implemented)}")
    print(f"\n➕ 生成 {len(to_add)} 新 yaml: {to_add}")
    print(f"➖ 删除 {len(to_remove)} 过时 yaml: {to_remove}")

    if args.dry_run:
        print("\n[dry-run] 不写文件")
        return 0

    for name in to_add:
        yfile = MCPTOOL_DIR / f"{PREFIX}{name}.yaml"
        payload = gen_payload(name)
        yfile.write_text(
            yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        print(f"  ✅ 生成 {yfile.name}")

    for name in to_remove:
        yfile = declared[name]
        yfile.unlink()
        print(f"  🗑 删除 {yfile.name}")

    print(f"\n同步完成: +{len(to_add)} -{len(to_remove)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
