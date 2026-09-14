#!/usr/bin/env python3
# ruff: noqa

"""
KOS ↔ Metacog Bridge (Phase 4.4)

Links KOS domain registry to Metacog cognitive cell framework.
Derives domain-specific protocols from meta-protocol v2.2.

Usage:
    python3 metacog-bridge.py derive <domain>  — Generate domain protocol
    python3 metacog-bridge.py map              — Show KOS→Metacog mapping
"""

import json
import sys
from typing import Any, Dict
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
# sys.path.insert(0, str(SCRIPT_DIR))  # removed
from kos.config import get_vault_ops_dir  # type: ignore[unused-ignore, import-not-found]

VAULT_OPS_DIR = get_vault_ops_dir()
# sys.path.insert(0, str(VAULT_OPS_DIR))  # removed

from kos.config import get_workspace_manifest

# Metacog application layers that map to KOS domains
METACOG_APPS: dict[str, Any] = {
    "gongwen": {
        "app": "professional-work",
        "cell": {"K": "制度规范、公文模板、统计数据", "P": "公文写作→Agent执行", "B": "政务语境、组织边界"},
        "protocol": "domain-protocol-gongwen.md",
    },
    "guozhuan": {
        "app": "organizational-navigation",
        "cell": {"K": "wiki系统、政策法规、方案方法论", "P": "ALE三层框架→策略执行", "B": "借调边界、信息墙"},
        "protocol": "domain-protocol-guozhuan.md",
    },
    "obsidian": {
        "app": "ai-agent",
        "cell": {"K": "全部个人知识、governance系统", "P": "vault-ops→自动化维护", "B": "个人边界、自由探索"},
        "protocol": "domain-protocol-obsidian.md",
    },
    "family": {
        "app": "family-education",
        "cell": {"K": "家庭文件", "P": "只读索引", "B": "隐私优先"},
        "protocol": "domain-protocol-family.md",
    },
    "wpsnote": {
        "app": "health",
        "cell": {"K": "富文本笔记", "P": "MCP工具→标签路由", "B": "采集边界"},
        "protocol": "domain-protocol-wpsnote.md",
    },
}

# Metacog meta-protocol operations
META_OPS = {
    "op1": "未来回望 — 从目标状态反推当前行动",
    "op2": "多视角分析 — 从不同角色立场审视问题",
    "op3": "反事实检验 — 如果关键假设不成立会怎样",
    "op4": "闭环验证 — 执行→检查→修正循环",
    "op5": "过程审计 — 审视决策过程而非结果",
    "op6": "自我进化 — 从经验中提取可复用模式",
    "op7": "知识优先 — 行动前先检索已有知识",
}


def show_mapping() -> dict[str, Any]:
    """Show KOS→Metacog domain mapping."""
    manifest = get_workspace_manifest()
    domains = manifest.get("domains", {})

    result: dict[str, Any] = {"mappings": [], "meta_operations": META_OPS}

    for domain_id, meta in METACOG_APPS.items():
        domain_info = domains.get(domain_id, {})
        result["mappings"].append(
            {
                "kos_domain": domain_id,
                "metacog_app": meta["app"],
                "cognitive_cell": meta["cell"],
                "protocol_file": meta["protocol"],
                "description": domain_info.get("description", ""),
            }
        )

    return result


def derive_protocol(domain: str) -> str:
    """Generate a domain-specific protocol from Metacog meta-protocol."""
    if domain not in METACOG_APPS:
        return f"Unknown domain: {domain}. Available: {list(METACOG_APPS.keys())}"

    meta = METACOG_APPS[domain]
    manifest = get_workspace_manifest()
    zone = manifest["zones"].get(domain, {})
    label = zone.get("label", domain)

    protocol = f"""# Domain Protocol: {label} ({domain})

> Derived from Metacog meta-protocol v2.2 | {datetime.now().strftime("%Y-%m-%d")}

## Cognitive Cell
- **K (Knowledge)**: {meta["cell"]["K"]}
- **P (Processor)**: {meta["cell"]["P"]}
- **B (Boundary)**: {meta["cell"]["B"]}

## Derived Operations

### op1: Future Retrospection
回望目标状态，反推当前最优先级行动。

### op2: Multi-Perspective Analysis
从 {label} 域的角色视角分析问题。

### op3: Counterfactual Verification
如果域内关键假设不成立，影响评估。

### op4: Closed-Loop Verification
执行→检查→修正的标准闭环。

### op5: Process Audit
审视 {label} 域内的决策过程。

### op6: Self-Evolution
从本域经验中提取可复用模式。

### op7: Knowledge-First
在本域内行动前先检索已有知识。

## Domain-Specific Rules
- Identity: {zone.get("identity", "N/A")}
- Agent Entry: {zone.get("agentEntry", "CLAUDE.md")}
- Primary Formats: {zone.get("primaryFormats", ["md"])}
- Write Policy: {zone.get("defaultWritePolicy", "readonly")}
"""
    return protocol


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps(show_mapping(), ensure_ascii=False, indent=2))  # type: ignore[no-untyped-call]
    elif sys.argv[1] == "map":
        print(json.dumps(show_mapping(), ensure_ascii=False, indent=2))  # type: ignore[no-untyped-call]
    elif sys.argv[1] == "derive" and len(sys.argv) > 2:
        domain = sys.argv[2]
        print(derive_protocol(domain))
    else:
        print(json.dumps(show_mapping(), ensure_ascii=False, indent=2))  # type: ignore[no-untyped-call]
