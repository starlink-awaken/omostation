#!/usr/bin/env python3
"""Ecosystem Expander — 生态化服务扩展.

扩展服务生态:
- 注册新工具到服务注册表
- 创建 BOS URI
- 连接到编排器
- 扩展 MCP 工具

Usage:
    python3 bin/gac/ecosystem-expander.py --register-all
    python3 bin/gac/ecosystem-expander.py --generate-bos-uris
    python3 bin/gac/ecosystem-expander.py --status
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# New services to register
NEW_SERVICES = [
    {
        "id": "orchestrator.unified",
        "enabled": True,
        "scheduler": "manual",
        "trigger": "cli",
        "program": {"interpreter": "stable-python3", "entrypoint": "bin/gac/unified-orchestrator.py"},
        "description": "统一编排引擎 — 连接所有组件",
        "bos_uri": "bos://governance/orchestrator",
        "tags": ["orchestrator", "governance"],
    },
    {
        "id": "evolution.auto",
        "enabled": True,
        "scheduler": "cron",
        "trigger": "schedule",
        "schedule": "0 8 * * *",
        "program": {"interpreter": "stable-python3", "entrypoint": "bin/gac/auto-evolution-engine.py"},
        "description": "自动进化引擎 — 端到端进化循环",
        "bos_uri": "bos://governance/auto-evolution",
        "tags": ["evolution", "governance"],
    },
    {
        "id": "signal.scene-connector",
        "enabled": True,
        "scheduler": "manual",
        "trigger": "cli",
        "program": {"interpreter": "stable-python3", "entrypoint": "bin/gac/signal-scene-connector.py"},
        "description": "信号→场景卡连接器",
        "bos_uri": "bos://governance/signal-scene",
        "tags": ["signal", "scene", "governance"],
    },
    {
        "id": "decision.inbox-sla",
        "enabled": True,
        "scheduler": "manual",
        "trigger": "cli",
        "program": {"interpreter": "stable-python3", "entrypoint": "bin/gac/decision-inbox-sla.py"},
        "description": "决策收件箱 SLA 管理",
        "bos_uri": "bos://governance/decision-inbox",
        "tags": ["decision", "inbox", "governance"],
    },
    {
        "id": "proposal.adoption",
        "enabled": True,
        "scheduler": "manual",
        "trigger": "cli",
        "program": {"interpreter": "stable-python3", "entrypoint": "bin/bc-os/proposal-adoption-tracker.py"},
        "description": "提案采纳跟踪器",
        "bos_uri": "bos://governance/proposal-adoption",
        "tags": ["proposal", "adoption", "evolution"],
    },
    {
        "id": "cleanup.dormant",
        "enabled": True,
        "scheduler": "manual",
        "trigger": "cli",
        "program": {"interpreter": "stable-python3", "entrypoint": "bin/gac/dormant-cleanup-scanner.py"},
        "description": "休眠模块清理扫描",
        "bos_uri": "bos://governance/dormant-cleanup",
        "tags": ["cleanup", "maintenance"],
    },
    {
        "id": "retro.reference",
        "enabled": True,
        "scheduler": "manual",
        "trigger": "cli",
        "program": {"interpreter": "stable-python3", "entrypoint": "bin/gac/retro-reference-engine.py"},
        "description": "复盘引用引擎",
        "bos_uri": "bos://governance/retro-reference",
        "tags": ["retro", "reference", "knowledge"],
    },
    {
        "id": "governance.dashboard",
        "enabled": True,
        "scheduler": "manual",
        "trigger": "cli",
        "program": {"interpreter": "stable-python3", "entrypoint": "bin/gac/unified-governance-view.py"},
        "description": "统一治理仪表盘",
        "bos_uri": "bos://governance/dashboard",
        "tags": ["dashboard", "governance"],
    },
]


def register_services() -> dict:
    """Register new services."""
    results = []
    for svc in NEW_SERVICES:
        # Use cockpit bos resolve to register
        result = subprocess.run(
            ["python3", str(REPO / "bin/cockpit"), "bos", "resolve", svc["bos_uri"]],
            capture_output=True, text=True, timeout=10, check=False,
        )
        results.append({
            "id": svc["id"],
            "bos_uri": svc["bos_uri"],
            "registered": result.returncode == 0,
        })

    return {"ok": True, "registered": len([r for r in results if r["registered"]]), "total": len(results)}


def generate_bos_uris() -> list[dict]:
    """Generate BOS URI entries for new services."""
    bos_entries = []
    for svc in NEW_SERVICES:
        bos_entries.append({
            "action": svc["id"].replace(".", "_"),
            "command": ["python3", svc["program"]["entrypoint"]],
            "description": svc["description"],
            "domain": "governance",
            "package": svc["id"].replace(".", "-"),
            "status": "active",
            "transport": "cli",
            "uri": svc["bos_uri"],
        })
    return bos_entries


def get_status() -> dict:
    """Get ecosystem status."""
    # Count BOS URIs
    services_file = REPO / ".omo/_truth/registry/services.yaml"
    total_bos = 0
    if services_file.exists():
        content = services_file.read_text(encoding="utf-8")
        total_bos = content.count("bos://")

    # Count tools
    gac_dir = REPO / "bin/gac"
    total_tools = len([f for f in gac_dir.glob("*.py") if not f.name.startswith("_")]) if gac_dir.exists() else 0

    return {
        "total_bos_uris": total_bos,
        "total_gac_tools": total_tools,
        "new_services": len(NEW_SERVICES),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Ecosystem Expander")
    parser.add_argument("--register-all", action="store_true", help="Register all new services")
    parser.add_argument("--generate-bos-uris", action="store_true", help="Generate BOS URIs")
    parser.add_argument("--status", action="store_true", help="Show status")
    args = parser.parse_args()

    if args.register_all:
        result = register_services()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    if args.generate_bos_uris:
        entries = generate_bos_uris()
        print(json.dumps(entries, indent=2, ensure_ascii=False))
        return 0

    if args.status:
        status = get_status()
        print(json.dumps(status, indent=2, ensure_ascii=False))
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
