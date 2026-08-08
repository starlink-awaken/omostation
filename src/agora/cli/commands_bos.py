"""`agora bos` 子命令 — BOS URI 注册表管理。"""

from __future__ import annotations

import json


def cmd_bos_list(args) -> int:
    """列出所有 BOS URI 路由。"""
    from agora.mcp.resolver.services import POC_SERVICES

    if not POC_SERVICES:
        print("BOS 注册表为空")
        return 0

    by_domain: dict[str, list[dict]] = {}
    for s in POC_SERVICES:
        by_domain.setdefault(s.domain, []).append(
            {
                "uri": s.uri,
                "transport": s.transport,
                "unimplemented": "[UNIMPLEMENTED]" in (s.description or ""),
            }
        )

    total = len(POC_SERVICES)
    for domain in sorted(by_domain):
        services = by_domain[domain]
        print(f"\n  {domain} ({len(services)}):")
        for svc in sorted(services, key=lambda x: x["uri"]):
            marker = " ⚠️" if svc["unimplemented"] else ""
            print(f"    {svc['uri']}  [{svc['transport']}]{marker}")

    print(f"\n  Total: {total}")
    return 0


def cmd_bos_info(args) -> int:
    """BOS 注册表统计信息。"""
    from agora.mcp.resolver.bos_registry import registry_info

    info = registry_info()
    if getattr(args, "json", False):
        print(json.dumps(info, indent=2, ensure_ascii=False))
        return 0

    print("\n  BOS 注册表统计")
    print(f"  {'=' * 40}")
    print(f"  总路由数:   {info['total']}")
    print("  域分布:")
    for domain, count in sorted(info["domains"].items()):
        print(f"    {domain}: {count}")
    print("  传输类型:")
    for t, count in sorted(info["transports"].items()):
        print(f"    {t}: {count}")
    if info.get("unimplemented"):
        print(f"  未实现路由: {len(info['unimplemented'])}")
        for uri in info["unimplemented"]:
            print(f"    ⚠️  {uri}")
    return 0


def cmd_bos_validate(args) -> int:
    """校验 YAML 注册表完整性。"""
    from agora.mcp.resolver.bos_registry import validate_registry

    errors = validate_registry()
    for err in errors:
        if err.startswith("✅"):
            print(f"\n  {err}")
        else:
            print(f"  ❌ {err}")

    if any(not e.startswith("✅") for e in errors):
        return 1
    return 0


def cmd_bos_export(args) -> int:
    """导出注册表为 JSON。"""
    from agora.mcp.resolver.services import POC_SERVICES

    services = []
    for s in POC_SERVICES:
        entry: dict[str, object] = {
            "uri": s.uri,
            "domain": s.domain,
            "action": s.action,
            "transport": s.transport,
        }
        if s.package:
            entry["package"] = s.package
        if s.command:
            entry["command"] = list(s.command)
        if s.http_url:
            entry["http_url"] = s.http_url
        if s.module_path:
            entry["module_path"] = s.module_path
        if s.func_name:
            entry["func_name"] = s.func_name
        if s.description:
            entry["description"] = s.description
        services.append(entry)

    indent = 2 if getattr(args, "pretty", False) else None
    print(json.dumps(services, indent=indent, ensure_ascii=False))
    return 0
