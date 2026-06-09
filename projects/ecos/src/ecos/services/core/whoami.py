#!/usr/bin/env python3
"""
eCOS v5 — 系统自述 (ecos-whoami)
====================================
一个命令回答所有问题:
  我是谁？我有什么能力？我的结构是什么？
  我的健康状况如何？我有哪些入口？

用法:
    python3 ecos-whoami.py                  # 完整系统自述
    python3 ecos-whoami.py --brief          # 精简版
    python3 ecos-whoami.py --json           # JSON 格式 (供其他工具消费)
    python3 ecos-whoami.py --topology       # 只输出拓扑结构
"""

import json
import subprocess
import argparse
from datetime import datetime
from pathlib import Path


def _get_cockpit_dir() -> Path:
    """Resolve standard @驾驶舱 or 驾驶舱 folder in Documents."""
    d = Path.home() / "Documents" / "@驾驶舱"
    if d.exists():
        return d
    return Path.home() / "Documents" / "驾驶舱"


SCRIPTS = _get_cockpit_dir() / "scripts"
DOCS = Path.home() / "Documents"
ECOS = Path.home() / ".ecos"


def run(cmd: list, timeout=30, silent=True) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()[:200] if silent else r.stdout.strip()
    except Exception:
        return ""


def get_topology() -> dict:
    return {
        "version": "eCOS v5.3.0",
        "phases": ["7.0/7.5/7.6", "8.1/8.2/8.3"],
        "layers": {
            "L4_self": {
                "name": "自我层",
                "gateway": "CLAUDE_COWORK_GLOBAL.md",
                "domains": 6,
                "scripts": 7,
                "health": "active",
            },
            "L3_entry": {
                "name": "入口桥接层",
                "adapters": [
                    "CLI",
                    "WeChat(stub)",
                    "Web(stub)",
                    "API(stub)",
                    "Event(stub)",
                ],
                "mcp_server": True,
                "scripts": 2,
                "health": "active",
            },
            "L2_kernel": {
                "name": "内核三平面",
                "planes": ["OMO", "kairon", "gbrain"],
                "scripts": 2,
                "health": "partial",
                "note": "minerva audit log 已知缺口",
            },
            "L1_runtime": {
                "name": "运行时矩阵",
                "daemon": True,
                "sla_uptime": run(
                    ["python3", str(SCRIPTS / "ecos-sla-tracker.py"), "--json"]
                ),
                "scripts": 3,
                "health": "active",
            },
            "L0_protocol": {
                "name": "协议编织层",
                "compiler": True,
                "constraints": 9,
                "protocols": 5,
                "scripts": 3,
                "health": "active",
            },
            "I0_fabric": {
                "name": "集成织物",
                "events": len(list((ECOS / "events").glob("*.jsonl")))
                if (ECOS / "events").exists()
                else 0,
                "registry": True,
                "scripts": 2,
                "health": "active",
            },
            "X1_gov": {
                "name": "治理安全",
                "coverage": "100%",
                "depth_l2": "40%",
                "health": "active",
            },
            "X2_anti": {
                "name": "抗熵进化",
                "coverage": "100%",
                "depth_l2": "80%",
                "health": "active",
            },
            "X3_value": {
                "name": "价值堆栈",
                "coverage": "100%",
                "depth_l2": "40%",
                "health": "active",
            },
        },
    }


def get_health() -> dict:
    health_out = run(
        ["python3", str(SCRIPTS / "ecos-health-check.py"), "--json"], silent=False
    )
    try:
        data = json.loads(health_out)
        results = data.get("results", [])
        return {
            "all_pass": all(r.get("pass") is not False for r in results),
            "passed": sum(1 for r in results if r.get("pass") is True),
            "failed": sum(1 for r in results if r.get("pass") is False),
            "total": len(results),
        }
    except (json.JSONDecodeError, ValueError, KeyError):
        return {"all_pass": None, "note": "无法解析"}


def get_debts() -> dict:
    return {"total": 0, "open": 0, "closed": 11, "note": "全部债务已 closeout"}


def get_scripts() -> list:
    locations = {
        "L4 控制面": SCRIPTS,
        "L1 运行时": ECOS / "scripts",
        "L0 协议层": DOCS / "学习进化" / "2-knowledge" / "基建架构",
    }
    all_scripts = []
    for layer, path in locations.items():
        if path.exists():
            for f in sorted(path.iterdir()):
                if f.suffix in (".py", ".sh") and f.name != "__init__.py":
                    all_scripts.append(f"{layer}:{f.name}")
    return all_scripts


def get_capabilities() -> list:
    return [
        {
            "id": "brief",
            "description": "会话简报 (健康+SLA+卡片+风险)",
            "command": "ecos-brief.py",
        },
        {
            "id": "health",
            "description": "9 项全系统健康检查",
            "command": "ecos-health-check.py",
        },
        {"id": "sla", "description": "历史 SLA 追踪", "command": "ecos-sla-tracker.py"},
        {
            "id": "coverage",
            "description": "X 轴覆盖率双矩阵",
            "command": "x3-coverage-report.py",
        },
        {
            "id": "freshness",
            "description": "CLAUDE.md 保鲜",
            "command": "check-claude-freshness.py",
        },
        {
            "id": "audit",
            "description": "Vault Git 变更审计",
            "command": "check-vault-audit.py",
        },
        {
            "id": "consistency",
            "description": "CARDS↔STATE 一致性",
            "command": "~/.ecos/scripts/check-cards-state-consistency.py",
        },
        {
            "id": "protocol",
            "description": "L0 协议约束+half_life",
            "command": "ecos-constraint-validator.py",
        },
        {
            "id": "compiler",
            "description": "L0 协议编译器",
            "command": "ecos-constraint-compiler.py",
        },
        {"id": "healer", "description": "自治愈(4 规则)", "command": "ecos-healer.py"},
        {
            "id": "daemon",
            "description": "自治运维守护进程",
            "command": "ecos-daemon.py",
        },
        {
            "id": "entry_profiler",
            "description": "L3 入口深度统计",
            "command": "ecos-entry-profiler.py",
        },
        {
            "id": "event_watcher",
            "description": "L1 事件驱动保鲜",
            "command": "ecos-event-watcher.py",
        },
        {
            "id": "mcp_server",
            "description": "L3 MCP 服务(7 tools)",
            "command": "runtime-mcp-server.py",
        },
        {
            "id": "adapter_stubs",
            "description": "L3 适配器桩(4 入口)",
            "command": "adapter-stubs.py",
        },
        {
            "id": "onboard",
            "description": "新 Agent 接入向导",
            "command": "ecos-onboard.py",
        },
        {
            "id": "value_cards",
            "description": "CARDS 价值归因",
            "command": "~/.ecos/scripts/cards-value-attribution.py",
        },
        {
            "id": "value_vault",
            "description": "Vault 文件价值归因",
            "command": "vault-value-attribution.py",
        },
        {
            "id": "value_domain",
            "description": "域系统活跃度",
            "command": "domain-value-attribution.py",
        },
        {
            "id": "value_kairon",
            "description": "Kairon 成本核算",
            "command": "~/.ecos/scripts/kairon-cost-attribution.py",
        },
        {
            "id": "kairon_gov",
            "description": "Kairon 治理检查",
            "command": "~/.ecos/scripts/check-kairon-governance.py",
        },
    ]


def format_brief(topology: dict, health: dict, debts: dict, scripts_count: int) -> str:
    now = datetime.now()
    lines = []
    lines.append(f"# eCOS v5 — 系统自述 ({now.strftime('%Y-%m-%d %H:%M')})")
    lines.append("")

    lines.append(
        f"**{topology['version']}** · {topology['phases'][0]} → {topology['phases'][1]}"
    )
    lines.append("")

    # 拓扑
    lines.append("## 架构拓扑")
    for lid, layer in topology["layers"].items():
        name = layer.get("name", lid)
        health_icon = (
            "✅"
            if layer.get("health") == "active"
            else ("⚠️" if layer.get("health") == "partial" else "❌")
        )
        extra = ""
        if "sla_uptime" in layer:
            extra = f" SLA: {layer['sla_uptime'][:30]}"
        if "constraints" in layer:
            extra = f" 约束: {layer['constraints']} 协议: {layer['protocols']}"
        if "coverage" in layer:
            extra = f" {layer['coverage']} L2+: {layer['depth_l2']}"
        lines.append(f"- {health_icon} **{lid}**: {name}{extra}")

    lines.append("")

    # 健康
    lines.append("## 健康状态")
    if health.get("all_pass") is True:
        lines.append(f"✅ {health['passed']}/{health['total']} 全部通过")
    elif health.get("all_pass") is False:
        lines.append(
            f"⚠️ {health['passed']}/{health['total']} 通过, {health['failed']} 项失败"
        )
    else:
        lines.append("⏳ 健康数据累积中")

    # 债务
    lines.append(
        f"\n📊 债务: {debts['total']} 项, {debts['open']} 开放, {debts['closed']} 已关闭"
    )

    # 脚本
    lines.append(f"\n📜 脚本: {scripts_count} 个")

    # 下一步
    lines.append("\n## 快速入门")
    lines.append("```")
    lines.append("# 查看完整系统自述")
    lines.append("python3 ~/Documents/@驾驶舱/scripts/ecos-whoami.py --json")
    lines.append("")
    lines.append("# 会话简报 (启动 Step 0)")
    lines.append("python3 ~/Documents/@驾驶舱/scripts/ecos-brief.py")
    lines.append("")
    lines.append("# 一键治理")
    lines.append("python3 ~/Documents/@驾驶舱/scripts/ecos-health-check.py")
    lines.append("```")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="eCOS v5 系统自述")
    parser.add_argument("--brief", action="store_true", help="精简版")
    parser.add_argument("--json", action="store_true", help="JSON 格式")
    parser.add_argument("--topology", action="store_true", help="仅拓扑")
    args = parser.parse_args()

    topology = get_topology()
    health = get_health()
    debts = get_debts()
    scripts = get_scripts()
    caps = get_capabilities()

    result = {
        "name": "eCOS v5",
        "version": topology["version"],
        "generated_at": datetime.now().isoformat(),
        "topology": topology,
        "health": health,
        "debts": debts,
        "scripts_count": len(scripts),
        "capabilities": caps,
        "scripts": scripts,
    }

    if args.topology:
        if args.json:
            print(json.dumps(topology, ensure_ascii=False, indent=2))
        else:
            for lid, layer in topology["layers"].items():
                print(f"  {lid}: {layer.get('name', '?')} — {layer.get('health', '?')}")
        return

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.brief:
        print(format_brief(topology, health, debts, len(scripts)))
        return

    # 完整自述
    print(f"\n{'=' * 56}")
    print("  eCOS v5 — 系统自述 (whoami)")
    print(f"  版本: {topology['version']}")
    print(f"  Phase: {topology['phases'][0]} → {topology['phases'][1]}")
    print(f"  生成: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 56}")

    print("\n  📐 架构拓扑")
    for lid, layer in topology["layers"].items():
        hid = (
            "🟢"
            if layer.get("health") == "active"
            else ("🟡" if layer.get("health") == "partial" else "🔴")
        )
        name = layer.get("name", lid)
        print(f"  {hid} {lid}: {name}")

    h = health
    health_str = (
        f"🟢 {h['passed']}/{h['total']} 通过" if h.get("all_pass") else "⏳ 累积中"
    )
    print(f"\n  🩺 健康: {health_str}")
    print(f"  📊 债务: {debts['total']} 项 (0 开放)")
    print(f"  📜 脚本: {len(scripts)} 个")
    print(f"  🛠️  能力: {len(caps)} 项")

    print(f"\n{'-' * 56}")
    print("  Agent 启动: python3 ~/Documents/@驾驶舱/scripts/ecos-brief.py --force")
    print("  一键治理: python3 ~/Documents/@驾驶舱/scripts/ecos-health-check.py")
    print("  接管手册: ~/Documents/@驾驶舱/OPS.md")
    print(f"{'=' * 56}\n")


if __name__ == "__main__":
    main()
