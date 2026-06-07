#!/usr/bin/env python3
"""
织星 MOF — 实体解析服务 (mof-entity)
=====================================
跨域实体解析——同一个实体在多个域的表示，统一查询。

基于 L0 Entity M1 节点的 identity 字段，以及 M2 本体映射的 resolution_keys。

用法:
    python3 mof-entity.py resolve "夏明星"     # 跨域查询
    python3 mof-entity.py list                  # 列出所有实体
    python3 mof-entity.py stats                 # 实体统计
    python3 mof-entity.py --json                # JSON 输出
"""

import sys, json, yaml
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
L0_M1 = HOME / "Workspace" / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m1" / "entity"
ONTO_FILE = HOME / "Workspace" / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "ontology.yaml"


def load_entities() -> list[dict]:
    if not L0_M1.exists():
        return []
    entities = []
    for f in sorted(L0_M1.glob("*.yaml")):
        try:
            data = yaml.safe_load(open(f))
            if isinstance(data, dict) and data.get("type") == "Entity":
                entities.append(data)
        except:
            pass
    return entities


def load_resolution_keys() -> list[dict]:
    if not ONTO_FILE.exists():
        return []
    onto = yaml.safe_load(open(ONTO_FILE))
    er = onto.get("m2_ontology", onto).get("entity_resolution", {})
    return er.get("resolution_keys", [])


def build_index(entities: list[dict]) -> dict:
    """构建实体索引: {identity_key: [entity]}"""
    index = {}
    for e in entities:
        eid = e.get("id", "")
        name = e.get("name", "")
        props = e.get("properties", {}) or {}
        identity = props.get("identity", {})
        sources = props.get("sources", [])
        domain = e.get("domain", "?")
        
        # Index by name
        if name:
            index.setdefault(name.lower(), []).append(e)
        
        # Index by identity keys
        for k, v in identity.items():
            key = f"{k}:{v}".lower()
            index.setdefault(key, []).append(e)
        
        # Index by domain
        index.setdefault(f"domain:{domain}", []).append(e)
        
        # Index by entity_type
        etype = props.get("entity_type", "")
        if etype:
            index.setdefault(f"type:{etype}", []).append(e)
    
    return index


def resolve(query: str, entities: list[dict], index: dict) -> dict:
    """解析实体——查询跨域出现"""
    q = query.lower().strip()
    
    # Direct matches
    matches = index.get(q, [])
    
    # Fuzzy: partial name match
    if not matches:
        for key, ents in index.items():
            if q in key:
                matches.extend(ents)
    
    # Deduplicate
    seen = set()
    unique = []
    for e in matches:
        eid = e.get("id", "")
        if eid not in seen:
            seen.add(eid)
            unique.append(e)
    
    if not unique:
        # Try searching by name substring
        for e in entities:
            name = (e.get("name", "") or "").lower()
            if q in name:
                unique.append(e)
    
    result = {
        "query": query,
        "found": len(unique),
        "entities": [],
    }
    
    for e in unique:
        props = e.get("properties", {}) or {}
        entity_info = {
            "id": e.get("id", ""),
            "name": e.get("name", ""),
            "domain": e.get("domain", ""),
            "entity_type": props.get("entity_type", "?"),
            "status": e.get("status", ""),
            "sources": props.get("sources", []),
            "identity": props.get("identity", {}),
            "description": e.get("description", "")[:100],
        }
        result["entities"].append(entity_info)
    
    # Add resolution info
    domains = set(e["domain"] for e in result["entities"])
    result["cross_domain"] = len(domains) > 1
    result["domains"] = sorted(domains)
    
    return result


def format_resolve(result: dict) -> str:
    lines = ["=" * 64, f"  实体解析: {result['query']}", "=" * 64,
             f"  找到: {result['found']} 个实体",
             f"  跨域: {'是' if result['cross_domain'] else '否'} ({', '.join(result['domains'])})", ""]
    
    for e in result["entities"]:
        lines.append(f"  📍 {e['name']} [{e['entity_type']}] — {e['domain']}")
        lines.append(f"     ID: {e['id']}")
        if e.get("description"):
            lines.append(f"     描述: {e['description'][:80]}")
        if e.get("identity"):
            lines.append(f"     身份键: {e['identity']}")
        if e.get("sources"):
            lines.append(f"     来源: {', '.join(e['sources'][:3])}")
        if e.get("status"):
            lines.append(f"     状态: {e['status']}")
        lines.append("")
    
    return "\n".join(lines)


def format_list(entities: list[dict]) -> str:
    lines = ["=" * 64, f"  实体清单 ({len(entities)} 个)", "=" * 64, ""]
    
    by_domain = {}
    for e in entities:
        domain = e.get("domain", "?")
        by_domain.setdefault(domain, []).append(e)
    
    for domain in sorted(by_domain.keys()):
        lines.append(f"## {domain} ({len(by_domain[domain])})")
        for e in by_domain[domain][:10]:
            props = e.get("properties", {}) or {}
            etype = props.get("entity_type", "?")
            name = e.get("name", "?")[:50]
            lines.append(f"  - [{etype:12s}] {name}")
        if len(by_domain[domain]) > 10:
            lines.append(f"  ... 还有 {len(by_domain[domain]) - 10} 个")
        lines.append("")
    
    return "\n".join(lines)


def format_stats(entities: list[dict]) -> str:
    lines = ["=" * 64, "  实体统计", "=" * 64, ""]
    
    by_domain = {}
    by_type = {}
    for e in entities:
        domain = e.get("domain", "?")
        by_domain[domain] = by_domain.get(domain, 0) + 1
        etype = (e.get("properties", {}) or {}).get("entity_type", "?")
        by_type[etype] = by_type.get(etype, 0) + 1
    
    lines.append("按域:")
    for d, c in sorted(by_domain.items(), key=lambda x: -x[1]):
        lines.append(f"  {d:25s}: {c:4d}")
    
    lines.append("\n按类型:")
    for t, c in sorted(by_type.items(), key=lambda x: -x[1]):
        lines.append(f"  {t:25s}: {c:4d}")
    
    lines.append(f"\n总计: {len(entities)} 实体")
    return "\n".join(lines)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("action", nargs="?", default="stats",
                       choices=["resolve", "list", "stats"])
    parser.add_argument("query", nargs="?", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    entities = load_entities()
    index = build_index(entities)

    if args.action == "resolve" and args.query:
        result = resolve(args.query, entities, index)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(format_resolve(result))
    elif args.action == "list":
        print(format_list(entities))
    else:
        print(format_stats(entities))


if __name__ == "__main__":
    main()
