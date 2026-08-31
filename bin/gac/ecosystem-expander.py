#!/usr/bin/env python3
"""Ecosystem Expander — 生态化服务扩展."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

NEW_SERVICES = [
    {"id": "orchestrator.unified", "bos_uri": "bos://governance/orchestrator", "description": "统一编排引擎"},
    {"id": "evolution.auto", "bos_uri": "bos://governance/auto-evolution", "description": "自动进化引擎"},
    {"id": "signal.scene-connector", "bos_uri": "bos://governance/signal-scene", "description": "信号→场景连接器"},
    {"id": "decision.inbox-sla", "bos_uri": "bos://governance/decision-inbox", "description": "决策收件箱SLA"},
    {"id": "proposal.adoption", "bos_uri": "bos://governance/proposal-adoption", "description": "提案采纳跟踪"},
    {"id": "cleanup.dormant", "bos_uri": "bos://governance/dormant-cleanup", "description": "休眠模块清理"},
    {"id": "retro.reference", "bos_uri": "bos://governance/retro-reference", "description": "复盘引用引擎"},
    {"id": "governance.dashboard", "bos_uri": "bos://governance/dashboard", "description": "统一治理仪表盘"},
]


def get_status() -> dict:
    services_file = REPO / ".omo" / "_truth" / "registry/services.yaml"
    total_bos = 0
    if services_file.exists():
        content = services_file.read_text(encoding="utf-8")
        total_bos = content.count("bos://")

    gac_dir = REPO / "bin/gac"
    total_tools = len([f for f in gac_dir.glob("*.py") if not f.name.startswith("_")]) if gac_dir.exists() else 0

    return {"total_bos_uris": total_bos, "total_gac_tools": total_tools, "new_services": len(NEW_SERVICES)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Ecosystem Expander")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()

    if args.status:
        print(json.dumps(get_status(), indent=2, ensure_ascii=False))
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
