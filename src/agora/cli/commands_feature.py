"""Feature Gate & Proxy Group CLI commands.

Usage:
    agora feature list       — 查看所有 feature groups 和 BOS domains 状态
    agora feature enable GROUP  — 启用一个组
    agora feature disable GROUP — 禁用一个组
    agora feature domain enable DOMAIN    — 启用一个 BOS 域
    agora feature domain disable DOMAIN   — 禁用一个 BOS 域

    agora proxy group enable GROUP     — 启用一个 proxy 组（同 feature enable）
    agora proxy group disable GROUP    — 禁用一个 proxy 组
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from agora.cli.output import OutputFormatter
from agora.mcp_proxy.feature_gate import FeatureGate
from agora.mcp import mcp_bootstrap


def _get_gate() -> FeatureGate:
    """获取 FeatureGate 实例并从代理配置加载。"""
    gate = FeatureGate.get_instance()
    config_path = mcp_bootstrap.get_data_dir() / "agora-proxy-services.json"
    if config_path.exists():
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
            gate.load(data)
        except (json.JSONDecodeError, OSError):
            gate.load()
    else:
        gate.load()
    return gate


def cmd_feature_list(_args) -> int:
    """List all feature groups and BOS domains with their current state."""
    gate = _get_gate()
    status = gate.status()
    out = OutputFormatter(json_mode=False)

    # ── Env overrides ──
    if status["env_overrides"]:
        out.print_panel(
            "\n".join(f"  {k}={v}" for k, v in status["env_overrides"].items()),
            title="🌐 环境变量覆盖生效中",
            style="yellow",
        )

    # ── Feature Groups ──
    group_rows = []
    for gname, ginfo in status["groups"].items():
        enabled = ginfo["enabled"]
        icon = "✅" if enabled else "⛔"
        desc = ginfo["description"]
        count = ginfo["service_count"]
        group_rows.append([icon, gname, f"{count} services", desc])

    out.print_table(
        ["", "Group", "Scope", "Description"],
        group_rows,
        title=f"📦 Feature Groups ({len(group_rows)})",
    )

    # ── BOS Domains ──
    domain_rows = []
    for dname, dinfo in status["domains"].items():
        enabled = dinfo["enabled"]
        icon = "🟢" if enabled else "🔴"
        desc = dinfo["description"]
        domain_rows.append([icon, dname, desc])

    out.print_table(
        ["", "Domain", "Description"],
        domain_rows,
        title=f"🌐 BOS Domains ({len(domain_rows)})",
    )

    out.print_info(f"Config path: {status['config_path']}")
    return 0


def cmd_feature_enable(args) -> int:
    """Enable a feature group by name."""
    gate = _get_gate()
    group_name = args.group_name
    ok = gate.set_group_enabled(group_name, True)
    if not ok:
        print(f"❌ Unknown group: '{group_name}'")
        print(f"   Available: {', '.join(gate.status()['groups'].keys())}")
        return 1
    print(f"✅ Group '{group_name}' enabled")
    return 0


def cmd_feature_disable(args) -> int:
    """Disable a feature group by name."""
    gate = _get_gate()
    group_name = args.group_name
    ok = gate.set_group_enabled(group_name, False)
    if not ok:
        print(f"❌ Unknown group: '{group_name}'")
        print(f"   Available: {', '.join(gate.status()['groups'].keys())}")
        return 1
    print(f"⛔ Group '{group_name}' disabled")
    return 0


def cmd_domain_enable(args) -> int:
    """Enable a BOS domain."""
    gate = _get_gate()
    domain = args.domain_name
    gate.set_domain_enabled(domain, True)
    print(f"🟢 Domain '{domain}' enabled")
    return 0


def cmd_domain_disable(args) -> int:
    """Disable a BOS domain."""
    gate = _get_gate()
    domain = args.domain_name
    gate.set_domain_enabled(domain, False)
    print(f"🔴 Domain '{domain}' disabled")
    return 0


def cmd_proxy_group_enable(args) -> int:
    """Enable a proxy group (alias for feature enable)."""
    args.group_name = args.name
    return cmd_feature_enable(args)


def cmd_proxy_group_disable(args) -> int:
    """Disable a proxy group (alias for feature disable)."""
    args.group_name = args.name
    return cmd_feature_disable(args)


def cmd_proxy_group_list(_args) -> int:
    """List proxy groups (alias for feature list)."""
    return cmd_feature_list(_args)
