#!/usr/bin/env python3
"""文档生成器 — 从 capability-registry.yaml 生成所有派生文档.

生成:
  - projects/cockpit/CAPABILITY-MAP.md  (能力地图)
  - docs/CLI-REFERENCE.md               (CLI 命令参考)
  - docs/INDEX-MCP.md                   (MCP 服务器索引)

前置: 先运行 gen-capability-registry.py 生成注册表

Usage:
    uv run --with pyyaml python bin/ssot/gen-help-docs.py
"""

from __future__ import annotations

import re
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
        print("   先运行: python bin/ssot/gen-capability-registry.py", file=sys.stderr)
        sys.exit(2)
    return yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))


# ── CAPABILITY-MAP.md ──────────────────────────────────────────


def gen_capability_map(reg: dict) -> str:
    t = reg["totals"]
    lines = [
        "# Cockpit 能力地图",
        "",
        f"> 自动生成于 {reg['generated_at']} | 版本 {reg['version']}",
        "> 源: `docs/generated/capability-registry.yaml` | 请勿手动编辑",
        "> 生成器: `bin/ssot/gen-help-docs.py`",
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
    lines.append(f"*由 `bin/ssot/gen-help-docs.py` 于 {reg['generated_at']} 生成*")
    return "\n".join(lines)


# ── CLI-REFERENCE.md ───────────────────────────────────────────

# 顶层命令归类 (用于 CLI-REFERENCE 分组 — 8D 场景化精细拆分)
_CMD_CATEGORIES: dict[str, list[str]] = {
    "治理与门禁": [
        "governance",
        "gac",
        "omo",
        "policy",
        "watchdog",
        "debt",
        "audit",
        "audit-ledger",
        "contracts",
        "ssb",
        "mof",
        "cards",
        "domains",
        "skill",
        "validate",
        "mutate",
        "scan",
        "facts-audit",
        "facts-validation",
        "domain-status",
        "sanyi-status",
        "kems",
        "identity",
        "impact",
    ],
    "工作流与协同": [
        "workflow",
        "agent",
        "agent-workflow",
        "agent-runtime",
        "agent-onboard",
        "onboarding",
        "iterate",
        "compass",
        "wave2",
        "monitor",
        "events",
        "events-watch",
        "event",
        "swarm",
        "resident",
        "bdsk",
        "c2g",
        "bcos",
        "journey",
        "panorama",
    ],
    "算力与推理": [
        "compute",
        "fabric",
        "fabric-mesh",
        "vram",
        "warm",
        "speculative-eval",
        "snapshot",
        "triage",
        "backends",
        "proxy-env",
        "mesh",
    ],
    "沙箱与卡带": [
        "cartridge",
        "runtime",
        "pack",
        "run",
        "serve",
        "up",
        "down",
        "invoke",
        "pipeline",
        "challenge",
    ],
    "内存总线与通信": [
        "daemon",
        "bus",
        "channels",
        "publish",
        "subscribe",
        "submit",
        "ack",
        "nack",
        "control",
        "controller-shadow",
        "pending",
        "agora",
    ],
    "BOS 与 MCP 网关": [
        "bos",
        "mcp",
        "bos-capability",
        "bos-inbox",
        "capability",
        "client",
        "resolve",
        "route",
        "reload",
        "register",
        "api",
        "url",
        "nodes",
        "types",
    ],
    "知识与图谱": [
        "brain",
        "code",
        "data",
        "graph",
        "index",
        "kairon",
        "gbrain",
        "knowledge",
        "export",
        "export-research",
        "consolidate",
        "archive",
        "gc",
    ],
    "记忆与认知": [
        "memory",
        "memory-distill",
        "remember",
        "recall",
        "forget",
        "intent",
        "ask",
        "read",
        "write",
        "get",
    ],
    "研究与探索": [
        "research",
        "search",
        "discover",
        "dossier",
        "timeline",
        "daily",
        "vault",
        "topics",
        "import",
    ],
    "系统状态与观测": [
        "status",
        "health",
        "readiness",
        "product-health",
        "dashboard",
        "observe",
        "inspect",
        "metrics",
        "stats",
        "score",
        "summary",
        "model-freshness",
        "history",
        "version",
        "brief",
        "context",
        "logs",
        "watch",
        "tui",
        "telemetry",
        "system",
    ],
    "生活与业务场景": [
        "gongwen",
        "finance",
        "scenario",
        "profile",
        "family-hub",
        "inbox",
        "list",
        "scene",
    ],
    "新手与入门": [
        "quickstart",
        "quickstart-check",
        "init",
        "help",
        "demo",
        "analyze",
        "project",
        "model-driven",
        "completion",
        "docs",
        "user",
    ],
}


def _categorize(cmd_name: str) -> str:
    for cat, names in _CMD_CATEGORIES.items():
        if cmd_name in names:
            return cat
    return "其他"


def _extract_frontmatter(path: Path) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8")
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            return f"---{parts[1]}---\n\n"
    return ""


def gen_cli_reference(reg: dict, frontmatter: str = "") -> str:
    """Tier-1 全量 CLI 参考 (BET-Y1Q4-T8-16): 每个命令独立成节, 单源生成。

    数据源优先级: cockpit.commands.registry.COMMAND_CATALOG (SSOT 元数据,
    含 summary/category/aliases/example) > capability-registry.yaml 的
    cli_commands (207 项, 扫描自 cli.py)。两者并集全量展开。
    """
    # 导入 cockpit SSOT registry
    catalog: dict = {}
    legacy: dict = {}
    domains: dict = {}
    cockpit_src = WORKSPACE / "projects" / "cockpit" / "src"
    if cockpit_src.is_dir():
        if str(cockpit_src) not in sys.path:
            sys.path.insert(0, str(cockpit_src))
        try:
            from cockpit.commands.registry import COMMAND_CATALOG, LEGACY_COMMAND_MAPPING, ORTHOGONAL_DOMAINS

            catalog = dict(COMMAND_CATALOG)
            legacy = dict(LEGACY_COMMAND_MAPPING)
            domains = dict(ORTHOGONAL_DOMAINS)
        except Exception:
            catalog, legacy, domains = {}, {}, {}

    # 命令 -> 描述 (registry 扫描结果)
    scanned: dict[str, str] = {c["name"]: (c.get("description") or "") for c in reg["cli_commands"]}
    gen_at = reg["generated_at"]

    lines: list[str] = []
    if frontmatter:
        lines.append(frontmatter.rstrip())
        lines.append("")
    lines.extend([
        "# Cockpit CLI 命令参考",
        "",
        f"> 自动生成于 {gen_at} | 源: cockpit.commands.registry (SSOT) + capability-registry.yaml",
        "> 生成器: `bin/ssot/gen-help-docs.py` | 请勿手动编辑",
        "",
        f"共 **{len(set(scanned) | set(catalog) | set(legacy))}** 个命令条目。八大正交域: "
        + "、".join(f"**{d}**" for d in domains) + "。",
        "",
        "## 目录",
        "",
    ])

    # 按 category 分组构建目录
    by_cat: dict[str, list[str]] = {}
    for name, meta in catalog.items():
        by_cat.setdefault(getattr(meta, "category", "其他") or "其他", []).append(name)
    for cat in sorted(by_cat):
        anchor = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", cat.lower()).strip("-")
        lines.append(f"- [{cat}](#{anchor}) ({len(by_cat[cat])} 个命令)")
    lines.extend([
        "- [遗留命令映射](#遗留命令映射) " + f"({len(legacy)} 个)",
        "- [全局 Flags](#全局-flags)",
        "- [MCP 工具映射](#mcp-工具映射)",
        "",
        "---",
        "",
    ])

    # 每命令详情节
    for cat in sorted(by_cat):
        lines.append(f"## {cat}")
        lines.append("")
        for name in sorted(by_cat[cat]):
            meta = catalog[name]
            summary = (getattr(meta, "summary", "") or scanned.get(name, "—")).strip()
            aliases = getattr(meta, "aliases", ()) or ()
            example = (getattr(meta, "example", "") or "").strip()
            maturity = getattr(meta, "maturity", "")
            risk = getattr(meta, "risk", "")
            delegated = getattr(meta, "delegated_target", "") or ""
            domain = domains.get(name) or (legacy.get(name) or ("", ""))[0]
            lines.append(f"### `cockpit {name}`")
            lines.append("")
            lines.append(summary or "—")
            lines.append("")
            lines.append("**用法**:")
            lines.append("")
            lines.append("```bash")
            lines.append(f"cockpit {name} [flags]")
            lines.append(f"cockpit {name} --json          # 机器可读输出")
            lines.append(f"cockpit {name} --dry-run       # 预检 (无副作用)")
            lines.append(f"cockpit {name} --help          # 完整参数面")
            lines.append("```")
            lines.append("")
            meta_rows = []
            if domain:
                meta_rows.append(f"所属域: `{domain}`")
            if maturity:
                meta_rows.append(f"成熟度: {maturity}")
            if risk:
                meta_rows.append(f"风险: {risk}")
            if aliases:
                meta_rows.append(f"别名: {', '.join(f'`{a}`' for a in aliases)}")
            if delegated:
                meta_rows.append(f"委派目标: `{delegated}`")
            if meta_rows:
                lines.append("  · " + "  |  ".join(meta_rows))
                lines.append("")
            if example:
                lines.append("```bash")
                lines.append(example if example.startswith("cockpit") else f"cockpit {example}")
                lines.append("```")
                lines.append("")
        lines.append("")

    # 遗留命令映射
    lines.extend(["## 遗留命令映射", "", "| 命令 | 域 | 目标 |", "|------|-----|------|"])
    for name in sorted(legacy):
        dom, target = legacy[name]
        lines.append(f"| `cockpit {name}` | {dom} | {target} |")
    lines.append("")

    # 仅出现在扫描结果、不在 CATALOG 的命令补全节
    extra = sorted(set(scanned) - set(catalog) - set(legacy))
    if extra:
        lines.extend(["## 扫描发现的其他命令", "", "| 命令 | 描述 |", "|------|------|"])
        for name in extra:
            lines.append(f"| `cockpit {name}` | {scanned.get(name) or '—'} |")
        lines.append("")

    # 全局 Flags
    lines.extend([
        "## 全局 Flags",
        "",
        "所有命令共享的全局参数面:",
        "",
        "| Flag | 说明 |",
        "|------|------|",
        "| `--help` / `-h` | 命令帮助 |",
        "| `--version` / `-V` | 版本号 |",
        "| `--json` | 机器可读 JSON 输出 |",
        "| `--dry-run` | 预检模式 (不执行副作用) |",
        "| `--quiet` / `-q` | 静默模式 |",
        "| `--verbose` / `-v` | 详细输出 |",
        "| `--output` / `-o` | 输出文件路径 |",
        "| `--trace-id` | 链路追踪 ID (跨命令 trace 贯穿) |",
        "",
        "## Shell 自动补全",
        "",
        "```bash",
        "source <(cockpit completion bash)   # Bash",
        "source <(cockpit completion zsh)    # Zsh",
        "cockpit completion fish | source    # Fish",
        "```",
        "",
        "输错命令时会给出 Levenshtein 最近邻建议 (`Did you mean ...`)。",
        "",
    ])

    # MCP 映射 (保留既有表)
    lines.extend([
        "## MCP 工具映射",
        "",
        "| CLI 命令 | MCP 服务器 | 工具数 |",
        "|----------|-----------|--------|",
    ])
    cli_to_mcp = {
        "omo": "omo",
        "kairon": "kos/iris/sophia/kronos/minerva/codeanalyze/forge/ontoderive",
        "gbrain": "gbrain",
        "model-driven": "model-driven",
        "agora": "agora",
        "family-hub": "family-hub",
        "mesh": "aetherforge",
        "compute": "aetherforge",
    }
    srv_map = {s["id"]: s["tool_count"] for s in reg["mcp_servers"]}
    for cli_cmd, mcp_ids in cli_to_mcp.items():
        total = sum(srv_map.get(mid, 0) for mid in mcp_ids.split("/"))
        lines.append(f"| `cockpit {cli_cmd}` | `{mcp_ids}` | {total} |")
    lines.extend([
        "",
        f"*由 `bin/ssot/gen-help-docs.py` 于 {gen_at} 生成 (T8-16 全量模式)*",
    ])
    return "\n".join(lines)

# ── INDEX-MCP.md ───────────────────────────────────────────────


def gen_mcp_index(reg: dict) -> str:
    lines = [
        "# MCP 服务器索引",
        "",
        f"> 自动生成于 {reg['generated_at']}",
        "> 源: `docs/generated/capability-registry.yaml`",
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
    lines.append(f"*由 `bin/ssot/gen-help-docs.py` 于 {reg['generated_at']} 生成*")
    return "\n".join(lines)


def main() -> int:
    reg = load_registry()

    cli_ref_path = WORKSPACE / "docs" / "CLI-REFERENCE.md"
    outputs = {
        WORKSPACE / "projects" / "cockpit" / "CAPABILITY-MAP.md": gen_capability_map(reg),
        cli_ref_path: gen_cli_reference(reg, _extract_frontmatter(cli_ref_path)),
        WORKSPACE / "docs" / "INDEX-MCP.md": gen_mcp_index(reg),
    }
    for path, content in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        # 时间戳稳定: 仅内容 (忽略 ISO 时间戳) 变化时才写
        if path.exists():
            old = path.read_text(encoding="utf-8")
            iso_pattern = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z"
            old_no_ts = re.sub(iso_pattern, "TIMESTAMP", old)
            new_no_ts = re.sub(iso_pattern, "TIMESTAMP", content)
            if old_no_ts == new_no_ts:
                print(f"⏭️  {path.relative_to(WORKSPACE)} (无变化)")
                continue
        path.write_text(content, encoding="utf-8")
        print(f"✅ {path.relative_to(WORKSPACE)}")

    print(f"\n📊 生成完成: {reg['totals']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
