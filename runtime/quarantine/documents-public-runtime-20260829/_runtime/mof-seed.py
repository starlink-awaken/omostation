#!/usr/bin/env python3
"""mof-seed.py — 从 l4-kernel registry.py 生成 MOF M1 domain YAML 文件

用法: python3 mof-seed.py [--dry-run] [--force]
    默认幂等: 文件已存在则跳过。
    --force: 覆盖已有文件。
    --dry-run: 只秀不写。

路径从 registry.py 的 Domain 定义推导; 如 registry.py 不可达
也可从 DOMAIN-INDEX.md AUTOGEN 表格反向提取。

部署: cd ~/Documents && python3 @公共/_runtime/mof-seed.py
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import date
from pathlib import Path

DOCS_ROOT = Path(__file__).resolve().parents[2]
WS_ROOT = Path(os.environ.get("WORKSPACE_ROOT", DOCS_ROOT.parent / "Workspace"))

REGISTRY = WS_ROOT / "projects/l4-kernel/src/l4_kernel/registry.py"
DOMAIN_INDEX = DOCS_ROOT / "@驾驶舱/_control/DOMAIN-INDEX.md"
MOF_DOMAIN_DIR = WS_ROOT / "projects/ecos/src/ecos/ssot/mof/m1/domain"

# MOF 已知额外节点 (非 registry 主域)
MOF_EXTRA_ACTIVE = {"work-contracts", "kos"}
MOF_EXTRA_DEPRECATED = {"agora-dashboard", "family-shared"}

# 简写名称映射 (id → 中文名)
NAME_MAP = {
    "cockpit": "驾驶舱", "vault": "学习进化", "personal": "个人",
    "shared": "公共", "family": "家庭生活", "creative": "创意创作",
    "opc": "OPC", "work-docs": "工作文档", "work-weijian": "卫健委",
    "work-guozhuan": "国转中心", "work-liyongke": "规自委",
    "obsidian-vault": "Obsidian Vault",
    "ai-config": "AI Config", "agents-config": "Agents Config",
    "icloud-sharedconf": "iCloud SharedConf",
    "minerva": "Minerva Engine", "knowledge-engine": "Knowledge Engine",
    "l4-kernel": "L4 Kernel",
    "bin": "bin Dir", "toolbox-tools": "ToolBox Tools",
    "sharedwork": "SharedWork", "ecos-workbench": "eCOS Workbench",
    "omo-governance": "OMO Governance", "spaces": "Spaces",
    "runtime": "Runtime",
    "shareddisk": "SharedDisk",
    "sharedmodel": "SharedModel", "model-volume": "Model Volume",
    "work-contracts": "合同法规",
    "agora-dashboard": "Agora Dashboard",
    "family-shared": "FamilyShared",
}


def parse_registry() -> list[dict]:
    """从 registry.py 提取域数据, 回退到 DOMAIN-INDEX."""
    if REGISTRY.exists():
        text = REGISTRY.read_text(encoding="utf-8")
        blocks = re.findall(
            r'Domain\(\s*id="([^"]+)",\s*name="([^"]+)",\s*domain_type="([^"]+)",'
            r".*?governance_tier=(\d+)", text, re.DOTALL)
        paths = dict(re.findall(
            r'id="([^"]+)",.*?path=((?:Path\.home\(\)|Path\("[^"]*"\))[^\n]*?),\n', text, re.DOTALL))
        out = []
        for did, name, dtype, tier in blocks:
            raw = paths.get(did, "")
            p = raw.replace('Path.home()', "~").replace(' / ', "/").replace('"', "")
            p = p.replace("Path(", "").replace(")", "")
            out.append({"id": did, "name": name, "type": dtype, "tier": int(tier), "path": p})
        return out

    # 回退: 从 DOMAIN-INDEX AUTOGEN 表格解析
    print(f"⚠️  registry.py 不可达 ({REGISTRY}), 从 DOMAIN-INDEX 回退解析", file=sys.stderr)
    if not DOMAIN_INDEX.exists():
        print(f"❌ DOMAIN-INDEX 也不存在: {DOMAIN_INDEX}", file=sys.stderr)
        sys.exit(1)
    text = DOMAIN_INDEX.read_text(encoding="utf-8")
    lines = text.splitlines()
    current_type = None
    out = []
    for line in lines:
        tm = re.match(r"^###\s*\S*\s*(\w+)\s*\((\d+)\)", line)
        if tm:
            current_type = tm.group(1)
        dm = re.match(r"^\| ([a-z0-9-]+) \| (.+?) \| (\d+) \| (.+?) \|", line)
        if dm and current_type:
            did = dm.group(1)
            name = dm.group(2).strip()
            tier = int(dm.group(3))
            path = dm.group(4).strip()
            out.append({"id": did, "name": name, "type": current_type, "tier": tier, "path": path})
    return out


def mof_yaml(domain: dict, state_history: list | None = None) -> str:
    """生成 MOF M1 YAML 内容。"""
    did = domain["id"]
    mof_id = f"DOMAIN-{did}"
    name = domain.get("name", NAME_MAP.get(did, did))
    dtype = domain["type"]
    tier = domain["tier"]
    path = domain.get("path", "")
    status = domain.get("status", "active")
    desc = domain.get("description", f"{name} 域 — {dtype} · Tier {tier}")

    lines = [
        f"# MOF M1 — {name}",
        f"# 生成于 {date.today()} · mof-seed.py",
        "",
        f"id: {mof_id}",
        f"status: {status}",
        "",
        f"# === 元信息 ===",
        f"domain_type: {dtype}",
        f"governance_tier: {tier}",
        f"path: {path}",
        f"description: \"{desc}\"",
        "",
        f"# === 标签 ===",
        "tags:",
        f"  - {dtype}",
        f"  - tier-{tier}",
        "",
    ]
    if state_history:
        lines.append("# === 状态历史 ===")
        for sh in state_history:
            lines.append(f"  - date: \"{sh['date']}\"")
            lines.append(f"    from: {sh['from']}")
            lines.append(f"    to: {sh['to']}")
            lines.append(f"    reason: \"{sh['reason']}\"")
        lines.append("")

    lines.append(f"# 生成自 mof-seed.py · {date.today()}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="从 registry.py 生成 MOF M1 domain YAML")
    ap.add_argument("--dry-run", action="store_true", help="只秀不写")
    ap.add_argument("--force", action="store_true", help="覆盖已有文件")
    args = ap.parse_args()

    domains = parse_registry()
    print(f"📋 registry.py: {len(domains)} 个域")

    # 额外节点
    for eid in MOF_EXTRA_ACTIVE:
        domains.append({"id": eid, "name": NAME_MAP.get(eid, eid),
                        "type": "document", "tier": 3, "path": "",
                        "status": "active",
                        "description": f"{NAME_MAP.get(eid, eid)} — 子域/文件库"})
    for eid in MOF_EXTRA_DEPRECATED:
        domains.append({"id": eid, "name": NAME_MAP.get(eid, eid),
                        "type": "document", "tier": 3, "path": "",
                        "status": "deprecated",
                        "description": f"{NAME_MAP.get(eid, eid)} — 已弃用",
                        "state_history": [
                            {"date": "2026-07-01", "from": "active",
                             "to": "deprecated",
                             "reason": "已收编/废弃"}
                        ]})

    mof_dir = MOF_DOMAIN_DIR
    if not args.dry_run:
        mof_dir.mkdir(parents=True, exist_ok=True)
    print(f"📁 MOF 目录: {mof_dir}")
    print()

    created = 0
    skipped = 0
    for d in domains:
        did = d["id"]
        fpath = mof_dir / f"DOMAIN-{did}.yaml"
        if fpath.exists() and not args.force:
            print(f"  ⏭️  DOMAIN-{did}.yaml  已存在")
            skipped += 1
            continue

        yaml_text = mof_yaml(d, d.get("state_history"))
        if args.dry_run:
            print(f"  [DRY-RUN] → DOMAIN-{did}.yaml")
            print("─" * 50)
            print(yaml_text)
            print("─" * 50)
        else:
            fpath.write_text(yaml_text, encoding="utf-8")
            print(f"  ✅ DOMAIN-{did}.yaml  {'覆盖' if args.force and fpath.exists() else '创建'}")
        created += 1

    summary = f"{'[DRY-RUN] ' if args.dry_run else ''}MOF M1: {created} 创建/更新, {skipped} 跳过, {len(domains)} 总计"
    print(f"\n{'=' * len(summary)}")
    print(summary)
    print(f"📂 {mof_dir}")
    print()

    if created > 0 and not args.dry_run:
        print("下一步: cd ~/Documents && python3 @公共/_runtime/domain-sync.py")
        print("         → 三源对账应通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
