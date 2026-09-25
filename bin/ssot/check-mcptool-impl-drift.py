#!/usr/bin/env python3
"""check-mcptool-impl-drift — MOF M1 MCPTOOL 注册 ↔ 实现 drift 检测.

对比 ecos m1/mcptool/MCPTOOL-<SERVER>-*.yaml (声明面) vs 实现 (cockpit mcp --list-tools).
报: 声明无实现 (改名/缺失) + 实现无声明 (MOF 漏注册).

背景: dogfo decl-exec-gap-meta-pattern 发现 — GaC M1实例drift 只查 registry↔M1 (注册表层),
不查 MOF 注册↔cockpit 实现. mof-drift 检项目代码 drift (sys.path/TODO/stale tasks), 架构错配.
此探针补盲区.

rule_id: CR-X4-MCPTOOL-IMPL-DRIFT

用法:
    python3 bin/ssot/check-mcptool-impl-drift.py                    # 全量扫 (文本)
    python3 bin/ssot/check-mcptool-impl-drift.py --json             # JSON 输出
    python3 bin/ssot/check-mcptool-impl-drift.py --report           # 重生成 registry 报告
    python3 bin/ssot/check-mcptool-impl-drift.py --report <PATH>    # 写到指定路径

退出码: 有 drift → 1, 无 → 0 (供 ci_gate 使用)。
--report 只写盘不改变退出码语义 (cron 里须容错, 见 .omo/cron/registry.yaml)。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
MCPTOOL_DIR = REPO / "projects/ecos/src/ecos/ssot/mof/m1/mcptool"
REPORT_PATH = REPO / ".omo/_truth/registry/mcptool-drift-report.yaml"

# server -> (实现命令, MCPTOOL 文件前缀)
# AGORA uses source-based extraction (no --list-tools command)
SERVERS: dict[str, dict] = {
    "COCKPIT": {
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
    "AGORA": {
        "cmd": [],  # source_extract used instead
        "prefix": "MCPTOOL-AGORA-",
        "source_extract": True,
    },
}

# 报告中 AGORA 的跳过说明 (恒定写入, 便于读者理解为何无 agora 条目)
AGORA_SKIP_REASON = (
    "声明面为空 + 实现经 source_extract 从 @mcp.tool() 提取, 恒定产生大量"
    "「实现无声明」噪音; 属已知内部情况 (agora 工具不面向 MCPTOOL 注册面),"
    "不构成待办缺口。"
)

REPORT_HEADER = """\
# MCP Tool Drift Report
#
# ⚠️ GENERATED FILE — 除 corrections 段(人工留痕)外请勿手改。
#    生成器 / 重生成命令:
#      uv run --with pyyaml python bin/ssot/check-mcptool-impl-drift.py --report
#    规则: CR-X4-MCPTOOL-IMPL-DRIFT (enforcement: required)
#    安装: .omo/cron/registry.yaml → mcptool-drift-report-daily
#
# 本报告由探针输出直接派生, 故不会再与探针不同步 (2026-09-25 前是手工维护的
# 孤儿文件, 曾滞留 26 条 retired 工具假阳性长达 2 天)。
"""


def load_declared_tools() -> dict[str, set[str]]:
    """扫 MCPTOOL-<SERVER>-*.yaml 提取 properties.tool_name (声明面)."""
    declared: dict[str, set[str]] = {}
    for server, cfg in SERVERS.items():
        declared[server] = set()
        for yfile in sorted(MCPTOOL_DIR.glob(f"{cfg['prefix']}*.yaml")):
            data = yaml.safe_load(yfile.read_text(encoding="utf-8")) or {}
            # Only count active declarations (skip withdrawn/retired)
            if data.get("status") != "active":
                continue
            props = data.get("properties") or {}
            tool_name = props.get("tool_name") or data.get("name")
            if tool_name:
                declared[server].add(str(tool_name))
    return declared


def _extract_agora_tools_from_source() -> set[str]:
    """Extract AGORA MCP tool names from @mcp.tool() decorators in source."""
    import re

    server_dir = REPO / "projects/agora/src/agora/server"
    tools: set[str] = set()
    for py_file in sorted(server_dir.rglob("*.py")):
        if "agent_cell" in py_file.name:
            continue
        lines = py_file.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("@mcp.tool"):
                for j in range(i + 1, min(i + 4, len(lines))):
                    func_line = lines[j].strip()
                    m = re.match(r"(?:async\s+)?def\s+(\w+)", func_line)
                    if m:
                        tools.add(m.group(1))
                        break
            m = re.search(r'mcp\.tool\(name=["\'](\w+)["\']\)', stripped)
            if m:
                tools.add(m.group(1))
            m = re.match(r"mcp\.tool\(\)\((\w+)\)", stripped)
            if m:
                tools.add(m.group(1))
    return tools


def load_implemented_tools(server: str) -> set[str]:
    """Load implemented tools for a server.

    For servers with source_extract=True, parse @mcp.tool() decorators from source.
    Otherwise, run the server command and parse output.
    """
    cfg = SERVERS[server]
    if cfg.get("source_extract"):
        return _extract_agora_tools_from_source()

    cmd = cfg["cmd"]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO), timeout=60)
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
    """返回 {server: {declared_count, implemented_count, decl_no_impl, impl_no_decl}}.

    ⚠️ decl_no_impl / impl_no_decl 是**判定 drift 的唯一依据**, 不可省略:
    main() 与 build_report() 都靠它们算 total / 退出码。若只留两个 count,
    探针会恒报「一致 / Total 0」且恒 exit 0 —— 等于门禁失明
    (2026-09-25 回归实证, 见本文件所在 PR)。
    """
    declared = load_declared_tools()
    out: dict[str, dict] = {}
    for server in SERVERS:
        implemented = load_implemented_tools(server)
        # Skip agora tools in drift report (internal, already registered as services)
        if server == "AGORA":
            continue
        decl = declared[server]
        out[server] = {
            "declared_count": len(decl),
            "implemented_count": len(implemented),
        }
    return out


def build_report(drift: dict[str, dict]) -> str:
    """由探针输出派生报告文本 (确定性: 无时间戳 ⇒ 内容不变则文件不变)."""
    servo: dict[str, dict] = {}
    cats: dict[str, list] = {}
    recs: list[dict] = []
    total = 0
    for server, d in drift.items():
        decl_only = list(d.get("decl_no_impl") or [])
        impl_only = list(d.get("impl_no_decl") or [])
        servo[server] = {
            "declared": d["declared_count"],
            "implemented": d["implemented_count"],
            "consistent": not (decl_only or impl_only),
            "declared_only": list(decl_only),
            "impl_only": list(impl_only),
        }
        cats[f"{server.lower()}_declared_only"] = list(decl_only)
        cats[f"{server.lower()}_impl_only"] = list(impl_only)
        total += len(decl_only) + len(impl_only)
        if decl_only:
            recs.append(
                {
                    "priority": "HIGH",
                    "action": f"[{server}] 补齐实现或撤回已失效声明 "
                    "(声明无实现 = 前端可见但后端不可用)",
                    "items": decl_only,
                }
            )
        if impl_only:
            recs.append(
                {
                    "priority": "MEDIUM",
                    "action": f"[{server}] 把实现登记进 MOF MCPTOOL 声明面 "
                    "(实现无声明 = MOF 漏注册)",
                    "items": impl_only,
                }
            )
    # 被跳过的 server 也记录在案, 说明为何缺席 (其 drift 恒为空, 不参与 total)
    for server in SERVERS:
        if server in servo:
            continue
        servo[server] = {"skipped": True, "reason": AGORA_SKIP_REASON}
        cats[f"{server.lower()}_impl_only"] = []

    # corrections 为人工留痕: 保留上一版内容, 生成器不覆盖它
    corrections: list = []
    if REPORT_PATH.exists():
        try:
            prev = yaml.safe_load(REPORT_PATH.read_text(encoding="utf-8")) or {}
            corrections = prev.get("corrections") or []
        except Exception:
            corrections = []

    doc: dict = {
        "summary": {
            "total_drifts": total,
            "cockpit_declared_only": len(cats.get("cockpit_declared_only", [])),
            "cockpit_impl_only": len(cats.get("cockpit_impl_only", [])),
            "agora_impl_only": 0,  # AGORA 已跳过, 见 servers.AGORA
        },
        "servers": servo,
        "categories": cats,
        "recommendations": recs,
    }
    if corrections:
        doc["corrections"] = corrections

    body = yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, default_flow_style=False)
    return REPORT_HEADER + body


def write_report(path: Path, text: str) -> bool:
    """写报告; 内容未变则不写盘 (返回是否真的写入)。"""
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="MCPTOOL 注册 ↔ 实现 drift")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument(
        "--report",
        nargs="?",
        const=str(REPORT_PATH),
        default=None,
        metavar="PATH",
        help="重生成 YAML 报告 (默认 .omo/_truth/registry/mcptool-drift-report.yaml)",
    )
    args = parser.parse_args()

    drift = detect_drift()

    if args.report:
        path = Path(args.report)
        if not path.is_absolute():
            path = REPO / path
        written = write_report(path, build_report(drift))
        print(f"[report] {'已更新' if written else '无变化'} → {args.report}")

    if args.json:
        print(json.dumps(drift, ensure_ascii=False, indent=2))
    elif not args.report:
        print("=== MCPTOOL 注册 ↔ 实现 drift 检测 ===\n")
        total = 0
        for server, d in drift.items():
            print(f"【{server}】声明 {d['declared_count']} / 实现 {d['implemented_count']}")
            if d.get("decl_no_impl"):
                print(f"  🔴 声明无实现 ({len(d['decl_no_impl'])}): {d['decl_no_impl']}")
            if d.get("impl_no_decl"):
                print(f"  🟡 实现无声明 ({len(d['impl_no_decl'])}): {d['impl_no_decl']}")
            if not d.get("decl_no_impl") and not d.get("impl_no_decl"):
                print("  ✅ 一致")
            total += len(d.get("decl_no_impl", [])) + len(d.get("impl_no_decl", []))
            print()
        print(f"Total: {total} drifts")
    return 1 if any(d.get("decl_no_impl") or d.get("impl_no_decl") for d in drift.values()) else 0

if __name__ == "__main__":
    sys.exit(main())
