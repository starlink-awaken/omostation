#!/usr/bin/env python3
"""
KOS Domain Onboarding Engine (Phase 4.1)

Plug-and-play new domain registration. Takes a path and generates:
  - CLAUDE.md entry point
  - workspace-manifest.json zone entry
  - Cowork MEMORY domain file

Usage:
    python3 domain-onboard.py /path/to/new/domain "My Domain" --identity "Role description"
"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
VAULT_OPS_DIR = SCRIPT_DIR.parent / "vault-ops" / "obsidian-vault"
# sys.path.insert(0, str(VAULT_OPS_DIR))  # removed by replace_imports.py

MANIFEST_PATH = VAULT_OPS_DIR.parents[0] / "memory" / "REGISTRY" / "workspace-manifest.json"


def slugify(name: str) -> str:
    """Convert domain name to kebab-case ID."""
    import re

    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def generate_claude_md(domain_name: str, domain_id: str, identity: str, root_path: str) -> str:
    """Generate a CLAUDE.md entry point for a new domain."""
    return f"""# CLAUDE.md — {domain_name}

> KOS Domain: {domain_id} | Auto-generated {datetime.now().strftime("%Y-%m-%d")}

## 我是谁
{identity}

## 域信息
- **KOS ID**: {domain_id}
- **根路径**: {root_path}
- **创建时间**: {datetime.now().strftime("%Y-%m-%d")}

## Agent 行为规则
- 读写范围：本目录及子目录
- 输出格式：优先 Markdown，其次根据内容类型
- 每次会话开始时读本文件

## 目录结构
（待填充——Agent 首次进入时自动扫描）
"""


def register_domain(
    manifest_path: str,
    domain_id: str,
    root_path: str,
    label: str,
    identity: str,
    formats: list | None = None,
) -> dict:  # type: ignore[type-arg]
    """Register a new domain in workspace-manifest.json."""
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    zone_entry = {
        "label": label,
        "role": "source",
        "absolutePath": root_path,
        "authoritative": True,
        "indexable": True,
        "defaultWritePolicy": "managed",
        "scope": "external",
        "agentEntry": "CLAUDE.md",
        "identity": identity,
        "primaryFormats": formats or ["md"],
        "governance": "kos-managed",
        "onboarded": datetime.now().isoformat()[:10],
    }

    if "zones" not in manifest:
        manifest["zones"] = {}
    manifest["zones"][domain_id] = zone_entry

    if "domains" not in manifest:
        manifest["domains"] = {}
    manifest["domains"][domain_id] = {
        "zoneId": domain_id,
        "description": label,
    }

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=4)

    return {"status": "registered", "domain": domain_id, "zones_total": len(manifest["zones"])}


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: python3 domain-onboard.py <path> <name> [--identity <role>]")
        print("Example: python3 domain-onboard.py ~/NewVault 'Research Papers' --identity 'Researcher'")
        sys.exit(1)

    root_path = Path(sys.argv[1]).expanduser().resolve()
    domain_name = sys.argv[2]
    domain_id = slugify(domain_name)
    identity = "User"

    if "--identity" in sys.argv:
        idx = sys.argv.index("--identity")
        identity = sys.argv[idx + 1]

    print(f"🚀 Onboarding domain: {domain_name} ({domain_id})")
    print(f"   Path: {root_path}")

    # 1) Generate CLAUDE.md
    claude_md = generate_claude_md(domain_name, domain_id, identity, str(root_path))
    claude_path = root_path / "CLAUDE.md"
    if not claude_path.exists():
        claude_path.write_text(claude_md, encoding="utf-8")
        print("   ✅ Created CLAUDE.md")
    else:
        print("   ⚠️  CLAUDE.md already exists, skipping")

    # 2) Register in manifest
    result = register_domain(str(MANIFEST_PATH), domain_id, str(root_path), domain_name, identity)
    print(f"   ✅ Registered in manifest (total zones: {result['zones_total']})")

    # 3) Auto-index the new domain
    print(f"   🔍 Running initial index for {domain_id}...")
    indexer_path = SCRIPT_DIR / "kos-indexer.py"
    if indexer_path.exists():
        subprocess.run([sys.executable, str(indexer_path), "index", "--domain", domain_id], capture_output=True)
        print("   ✅ Domain indexed")
    else:
        print("   ⚠️  kos-indexer.py not found, skipping auto-index")

    # 4) Print Cowork MEMORY template
    print(f"\n📋 Add to Cowork MEMORY (domain-{domain_id}.md):")
    print(f"""---
name: domain-{domain_id}
description: {domain_name}域状态快照
type: reference
domain: {domain_id}
updated: {datetime.now().strftime("%Y-%m-%d")}
---

# {domain_name}域

## 域入口
- **根路径**: {root_path}
- **Agent 入口**: CLAUDE.md
- **角色**: {identity}

## 最近状态
- 创建时间: {datetime.now().strftime("%Y-%m-%d")}
- 文档数: 待扫描
""")


if __name__ == "__main__":
    main()
