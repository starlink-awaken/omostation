#!/usr/bin/env python3
"""文档生成器 — 从 capability-registry.yaml 生成所有派生文档.

生成:
  - projects/cockpit/CAPABILITY-MAP.md  (能力地图)
  - docs/CLI-REFERENCE.md               (CLI 命令参考)
  - docs/INDEX-MCP.md                   (MCP 服务器索引)

前置: 先运行 gen-capability-registry.py 生成注册表

Usage:
    uv run --with pyyaml python bin/cockpit/gen-help-docs.py
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("❌ 需要 pyyaml", file=sys.stderr)
    sys.exit(2)

WORKSPACE = Path(__file__).resolve().parents[2]
REGISTRY_PATH = WORKSPACE / "docs" / "generated" / "capability-registry.yaml"


def load_registry() -> dict:
    if not REGISTRY_PATH.exists():
        print(f"❌ 注册表不存在: {REGISTRY_PATH}", file=sys.stderr)
        print("   先运行: python bin/cockpit/gen-capability-registry.py", file=sys.stderr)
        sys.exit(2)
    return yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))


# ── CAPABILITY-MAP.md ──────────────────────────────────────────

def gen_capability_map(reg: dict) -> str:
    t = reg["totals"]
    lines = [
        "# Cockpit 能力地图",
        "",
        f"> 自动生成于 {reg['generated_at']} | 版本 {reg['version']}",
        f"> 源: `docs/generated/capability-registry.yaml` | 请勿手动编辑",
        f"> 生成器: `bin/cockpit/gen-help-docs.py`",
        "",
        "## 概览",
        "",
        "| 通道 | 数量 |",
        "|------|------|",
        f"| CLI 命令 (含子命令) | {t['cli_commands']} |",
        f"| MCP 工具 | {t['mcp_tools']} |",
        f"| MCP 服务器 | {t['mcp_servers']} |",
        f"| BOS 服务 | {t['bos_services']} |",
        f"| BOS 域 | {t['bos_domains']} |",
        "",
        "## MCP 服务器清单",
        "",
        "| 服务器 | 层 | 工具数 | 传输 | 文件 |",
        "|--------|-----|--------|------|------|",
    ]
    for srv in sorted(reg["mcp_servers"], key=lambda x: x["tool_count"], reverse=True):
        exists = "" if srv["exists"] else " ⚠️未找到"
        lines.append(
            f"| `{srv['id']}` | {srv['layer']} | {srv['tool_count']} | {srv['transport']} | `{srv['file']}`{exists} |"
        )
    lines.append("")
    lines.append("## BOS 服务域分布")
    lines.append("")
    lines.append("| 域 | 服务数 |")
    lines.append("|-----|--------|")
    for domain, count in reg["bos_services"]["_domain_counts"].items():
        lines.append(f"| `{domain}` | {count} |")
    lines.append("")
    lines.append("## CLI 命令清单")
    lines.append("")
    lines.append("> 完整命令参考见 [`CLI-REFERENCE.md`](CLI-REFERENCE.md)")
    lines.append("")
    lines.append("| 命令 | 描述 |")
    lines.append("|------|------|")
    for cmd in reg["cli_commands"]:
        lines.append(f"| `cockpit {cmd['name']}` | {cmd['description']} |")
    lines.append("")
    lines.append("---")
    lines.append(f"*由 `bin/cockpit/gen-help-docs.py` 于 {reg['generated_at']} 生成*")
    return "\n".join(lines)


# ── CLI-REFERENCE.md ───────────────────────────────────────────

# 顶层命令归类 (用于 CLI-REFERENCE 分组)
_CMD_CATEGORIES: dict[str, list[str]] = {
    "研究": ["research", "import", "search", "vault", "daily", "discover", "dossier", "timeline"],
    "系统与状态": ["status", "health", "readiness", "product-health", "dashboard", "demo", "version", "brief", "context"],
    "治理": ["governance", "gac", "omo", "debt", "audit", "contracts", "ssb", "mof", "cards", "domains", "skill"],
    "项目入口": ["agora", "kairon", "gbrain", "model-driven", "runtime", "bus", "observe", "family-hub", "mesh", "compute"],
    "工作流与 Agent": ["workflow", "agent", "agent-workflow", "agent-runtime", "iterate", "compass", "wave2", "monitor", "events"],
    "BOS 与 MCP": ["bos", "mcp"],
    "知识与大脑": ["brain", "code", "data"],
    "生活场景": ["gongwen", "finance", "scenario", "profile"],
    "入门": ["quickstart", "init", "help"],
}


def _categorize(cmd_name: str) -> str:
    for cat, names in _CMD_CATEGORIES.items():
        if cmd_name in names:
            return cat
    return "其他"


def gen_cli_reference(reg: dict) -> str:
    lines = [
        "# Cockpit CLI 命令参考",
        "",
        f"> 自动生成于 {reg['generated_at']}",
        f"> 源: `docs/generated/capability-registry.yaml`",
        "",
        f"共 **{reg['totals']['cli_commands']}** 个命令 (含子命令)。按场景分组如下。",
        "",
    ]
    # 过滤掉子命令 (只保留顶层命令, 通过黑名单判断)
    # 子命令特征: xxx_sub.add_parser 注册的, 难以区分, 这里展示全部但按分类
    by_cat: dict[str, list[dict]] = {}
    for cmd in reg["cli_commands"]:
        cat = _categorize(cmd["name"])
        by_cat.setdefault(cat, []).append(cmd)

    for cat in ["入门", "研究", "系统与状态", "治理", "项目入口", "工作流与 Agent", "BOS 与 MCP", "知识与大脑", "生活场景", "其他"]:
        cmds = by_cat.get(cat, [])
        if not cmds:
            continue
        lines.append(f"## {cat}")
        lines.append("")
        lines.append("| 命令 | 描述 |")
        lines.append("|------|------|")
        for cmd in sorted(cmds, key=lambda c: c["name"]):
            desc = cmd["description"] or "—"
            lines.append(f"| `cockpit {cmd['name']}` | {desc} |")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("### MCP 工具映射")
    lines.append("")
    lines.append("每个项目入口命令对应的 MCP 服务器:")
    lines.append("")
    lines.append("| CLI 命令 | MCP 服务器 | 工具数 |")
    lines.append("|----------|-----------|--------|")
    cli_to_mcp = {
        "omo": "omo", "kairon": "kos/iris/sophia/kronos/minerva/codeanalyze/forge/ontoderive",
        "gbrain": "gbrain", "model-driven": "model-driven", "agora": "agora",
        "family-hub": "family-hub", "mesh": "aetherforge", "compute": "aetherforge",
    }
    srv_map = {s["id"]: s["tool_count"] for s in reg["mcp_servers"]}
    for cli_cmd, mcp_ids in cli_to_mcp.items():
        total = sum(srv_map.get(mid, 0) for mid in mcp_ids.split("/"))
        lines.append(f"| `cockpit {cli_cmd}` | `{mcp_ids}` | {total} |")
    lines.append("")
    lines.append(f"*由 `bin/cockpit/gen-help-docs.py` 于 {reg['generated_at']} 生成*")
    return "\n".join(lines)


# ── INDEX-MCP.md ───────────────────────────────────────────────

def gen_mcp_index(reg: dict) -> str:
    lines = [
        "# MCP 服务器索引",
        "",
        f"> 自动生成于 {reg['generated_at']}",
        f"> 源: `docs/generated/capability-registry.yaml`",
        "",
        f"全生态共 **{reg['totals']['mcp_servers']}** 个 MCP 服务器, **{reg['totals']['mcp_tools']}** 个工具。",
        "",
        "| 服务器 | 层 | 工具数 | 传输 | 端口 | 源文件 |",
        "|--------|-----|--------|------|------|--------|",
    ]
    for srv in sorted(reg["mcp_servers"], key=lambda x: (x["layer"], -x["tool_count"])):
        ports = srv.get("ports", {})
        port_str = ", ".join(f"{k}:{v}" for k, v in ports.items()) if ports else "—"
        lines.append(
            f"| `{srv['id']}` | {srv['layer']} | {srv['tool_count']} | {srv['transport']} | {port_str} | `{srv['file']}` |"
        )
    lines.append("")
    lines.append("## 工具清单")
    lines.append("")
    for srv in sorted(reg["mcp_servers"], key=lambda x: -x["tool_count"]):
        if not srv["tools"]:
            continue
        lines.append(f"### {srv['id']} ({srv['tool_count']} tools)")
        lines.append("")
        tool_list = ", ".join(f"`{t}`" for t in srv["tools"])
        lines.append(tool_list)
        lines.append("")
    lines.append(f"*由 `bin/cockpit/gen-help-docs.py` 于 {reg['generated_at']} 生成*")
    return "\n".join(lines)


def main() -> int:
    reg = load_registry()

    outputs = {
        WORKSPACE / "projects" / "cockpit" / "CAPABILITY-MAP.md": gen_capability_map(reg),
        WORKSPACE / "docs" / "CLI-REFERENCE.md": gen_cli_reference(reg),
        WORKSPACE / "docs" / "INDEX-MCP.md": gen_mcp_index(reg),
    }
    for path, content in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"✅ {path.relative_to(WORKSPACE)}")

    print(f"\n📊 生成完成: {reg['totals']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
