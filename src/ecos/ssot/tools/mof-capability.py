#!/usr/bin/env python3
"""
织星 MOF — 能力生命周期管理 (mof-capability)
=============================================
统一管理 Skills·MCPTools·Agents·Workflows 的全生命周期。

用法:
    mof capability list              列出所有能力
    mof capability list --type Skill  按类型筛选
    mof capability health             健康检查
    mof capability stats              统计
    mof capability deprecate <id> <reason>  废弃能力
"""

import sys
import yaml
from pathlib import Path

HOME = Path.home()
L0_M1 = HOME / "Workspace" / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m1"
CAPABILITY_TYPES = ["skill", "mcptool", "agent", "workflow"]


def load_capabilities(m2type: str = None) -> list[dict]:
    types = [m2type.lower()] if m2type else CAPABILITY_TYPES
    caps = []
    for t in types:
        ndir = L0_M1 / t
        if not ndir.exists():
            continue
        for f in sorted(ndir.glob("*.yaml")):
            try:
                data = yaml.safe_load(open(f))
                if isinstance(data, dict):
                    data["_m2type"] = t
                    caps.append(data)
            except Exception:
                pass
    return caps


def cmd_list(args: list[str]):
    m2type = None
    status_filter = None
    for a in args:
        if a.startswith("--type="):
            m2type = a.split("=", 1)[1]
        elif a.startswith("--status="):
            status_filter = a.split("=", 1)[1]

    caps = load_capabilities(m2type)
    if status_filter:
        caps = [c for c in caps if c.get("status") == status_filter]

    print(f"{'类型':12s} {'状态':10s} {'名称':50s}")
    print("-" * 75)
    for c in sorted(caps, key=lambda x: (x["_m2type"], x.get("status", ""), x.get("name", ""))):
        mtype = c["_m2type"]
        status = c.get("status", "?")
        name = (c.get("name", "?"))[:50]
        icon = {"active": "🟢", "defined": "📋", "deprecated": "⚠️", "archived": "🗄️"}.get(status, "❓")
        print(f"  {icon} {mtype:10s} {status:10s} {name}")

    print(f"\n  总计: {len(caps)} 项")


def cmd_health():
    """健康检查 — 检查能力是否在线"""
    caps = load_capabilities()
    
    active = sum(1 for c in caps if c.get("status") == "active")
    deprecated = sum(1 for c in caps if c.get("status") == "deprecated")
    archived = sum(1 for c in caps if c.get("status") == "archived")
    other = len(caps) - active - deprecated - archived
    
    print("═══ 能力健康 ═══")
    print(f"  活跃:     {active}")
    print(f"  废弃:     {deprecated} (需清理)")
    print(f"  归档:     {archived}")
    print(f"  其他:     {other}")
    print(f"  总计:     {len(caps)}")
    
    # Check for capabilities without successor
    deprecated_no_successor = [
        c for c in caps 
        if c.get("status") == "deprecated" 
        and not (c.get("properties", {}) or {}).get("successor")
    ]
    if deprecated_no_successor:
        print("\n  ⚠️ 废弃但无 successor:")
        for c in deprecated_no_successor:
            print(f"     {c['_m2type']}: {c.get('name', '?')[:50]}")


def cmd_stats():
    caps = load_capabilities()
    
    by_type = {}
    by_status = {}
    for c in caps:
        t = c["_m2type"]
        s = c.get("status", "?")
        by_type[t] = by_type.get(t, 0) + 1
        by_status[s] = by_status.get(s, 0) + 1
    
    print("═══ 能力统计 ═══")
    print("\n按类型:")
    for t in CAPABILITY_TYPES:
        if t in by_type:
            print(f"  {t:15s}: {by_type[t]:4d}")
    
    print("\n按状态:")
    for s, c in sorted(by_status.items()):
        icon = {"active": "🟢", "defined": "📋", "deprecated": "⚠️", "archived": "🗄️"}.get(s, "❓")
        print(f"  {icon} {s:12s}: {c:4d}")
    
    # Coverage: which types have M1 nodes
    print("\n类型覆盖:")
    for t in CAPABILITY_TYPES:
        ndir = L0_M1 / t
        count = len(list(ndir.glob("*.yaml"))) if ndir.exists() else 0
        icon = "✅" if count > 0 else "⚠️"
        print(f"  {icon} {t:15s}: {count} M1 节点")


def cmd_deprecate(args: list[str]):
    if len(args) < 2:
        print("用法: mof capability deprecate <id> <reason>")
        return
    
    cap_id = args[0]
    reason = " ".join(args[1:])
    
    for t in CAPABILITY_TYPES:
        fp = L0_M1 / t / f"{cap_id}.yaml"
        if fp.exists():
            data = yaml.safe_load(open(fp))
            data["status"] = "deprecated"
            props = data.get("properties", {}) or {}
            props["deprecation_reason"] = reason
            data["properties"] = props
            data["description"] = f"[DEPRECATED: {reason}] {data.get('description', '')}"
            with open(fp, 'w') as f:
                yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
            print(f"✅ {cap_id} → deprecated: {reason}")
            return
    
    print(f"❌ 未找到: {cap_id}")


def main():
    if len(sys.argv) < 2:
        print("用法: mof capability <list|health|stats|deprecate>")
        return
    
    cmd = sys.argv[1]
    args = sys.argv[2:]
    
    if cmd == "list":
        cmd_list(args)
    elif cmd == "health":
        cmd_health()
    elif cmd == "stats":
        cmd_stats()
    elif cmd == "deprecate":
        cmd_deprecate(args)
    else:
        print(f"未知子命令: {cmd}")


if __name__ == "__main__":
    main()
