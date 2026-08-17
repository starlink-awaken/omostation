"""asset_cli — Forge 资产清册 (Unified Asset Model v3/v4)

一个实体类型，多个维度。每个 Asset 同时拥有：
- 身份维度: id, name, type, status
- 能力维度: capabilities, access, source, cost_model (来自 Forge tools-registry)
- 运维维度: port, bind, host, health_endpoint (来自 portctl/registry)
- 调度维度: schedule, script_path, deliver_to (来自 cron)
- 项目维度: project_path, build_cmd, language (来自 Workspace 项目)

是 tools-registry.json (能力) + assets/registry.json (运维) 的统一 SSOT。

v4 新增: entities 结构 (9 个 category)，每个 category 有独立的 schema 和 items。
支持 --category 按 v4 category 查询。

实体类型 (type 字段):
  agent      AI 代理/Coding Agent          Claude Code
  mcp        MCP 协议服务                   KOS MCP
  cli        命令行工具                     Kos Indexer
  api        API/远程服务                   SiliconFlow
  service    网络服务 (有端口)               bos-daemon
  daemon     守护进程 (可自动启动)           agent-runtime
  webapp     Web/桌面应用                   Obsidian
  cron_job   定时作业                       日常摘要
  project    代码项目                       agora/agentmesh
  script     CLI 脚本                      port-watch.sh
  monitor    监控项                        drift-check
  route      路由映射                       /v1/chat → model-gateway
  pipeline   自动化管线                     知识摄取管线
  plugin     Cowork 插件/Skill              daily-health-check

v4 categories:
  service / tool / cron / infrastructure / project / data_store
  / configuration / solution / event

六条宪法:
  1. assets/registry.json 是 SSOT
  2. tools-registry.json 由 forge asset export tools 生成
  3. 同一个实体只有一条记录
  4. 不用的字段留空/不传，不分表
  5. ID 使用 kebab-case 命名
  6. status 生命周期: candidate → active → stale → deprecated → archived
"""

from __future__ import annotations

import fcntl
import json
import os
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import cast

from forge.asset_print import _print_category_items, _print_detailed, _print_summary
from forge.forge_config import ASSET_REGISTRY as REGISTRY_FILE  # type: ignore[import-not-found]

# ── 路径 ──
from forge.forge_config import ASSETS_DIR, FORGE_ROOT
from forge.forge_config import REGISTRY as TOOLS_FILE

HISTORY_FILE = ASSETS_DIR / "history.jsonl"

# ── 实体类型列表 ──
ASSET_TYPES = [
    "agent",
    "mcp",
    "cli",
    "api",
    "service",
    "daemon",
    "webapp",
    "cron_job",
    "project",
    "script",
    "monitor",
    "route",
    "pipeline",
    "plugin",
    "orchestrator",
    "feed",
]

# ── 实体类型 → v4 分类映射 ──
_TYPE_TO_V4_CAT = {
    "agent": "tool",
    "mcp": "tool",
    "cli": "tool",
    "api": "tool",
    "service": "service",
    "webapp": "tool",
    "daemon": "service",
    "cron_job": "cron",
    "project": "project",
    "script": "tool",
    "monitor": "service",
    "route": "service",
    "pipeline": "tool",
    "plugin": "tool",
    "orchestrator": "service",
    "feed": "service",
}

# ── v4 分类列表 ──
V4_CATEGORIES = [
    "service",
    "tool",
    "cron",
    "infrastructure",
    "project",
    "data_store",
    "configuration",
    "solution",
    "event",
]

# Forge original types → unified asset types
_TYPE_NORMALIZE = {
    "agent": "agent",
    "mcp": "mcp",
    "cli": "cli",
    "api": "api",
    "service": "service",
    "webapp": "webapp",
    "daemon": "daemon",
    "pipeline": "pipeline",
    "skill": "plugin",
    "plugin": "plugin",
    "gateway": "service",
    "orchestrator": "daemon",
    "feed": "service",
    "automation": "pipeline",
    "database": "service",
}


def _normalize_type(raw: str) -> str:
    return _TYPE_NORMALIZE.get(raw, "service")


# ── v3/v4 兼容数据装载 ──


def _get_items(reg: dict) -> list[dict]:
    """Get flat list of items from either v3 (assets) or v4 (entities) registry."""
    if reg.get("version") == 4 and "entities" in reg:
        items = []
        for cat, cat_data in reg["entities"].items():
            for item in cat_data.get("items", []):
                item["_category"] = cat
                items.append(item)
        return items
    return cast("list[dict]", reg.get("assets", []))


def _get_entities(reg: dict) -> dict:
    """Get entities dict from v4 registry."""
    if reg.get("version") == 4 and "entities" in reg:
        return cast("dict", reg["entities"])
    return {}


def _get_item_id(item: dict) -> str:
    """Get the identifier for an item (supports both id and name)."""
    return cast("str", item.get("id") or item.get("name", "?"))


# ── 数据 ──


def _default() -> dict:
    return {
        "version": 3,
        "unified": True,
        "created": datetime.now().isoformat(),
        "updated": "",
        "assets": [],
    }


def _load() -> dict:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    if not REGISTRY_FILE.exists():
        reg = _default()
        _save(reg)
        return reg
    with REGISTRY_FILE.open("rb") as f:
        fcntl.flock(f, fcntl.LOCK_SH)
        return cast("dict", json.load(f))


def _save(reg: dict) -> None:
    reg["updated"] = datetime.now().isoformat()
    tmp = REGISTRY_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(reg, indent=2, ensure_ascii=False) + "\n")
    if REGISTRY_FILE.exists():
        with REGISTRY_FILE.open("rb") as lock_f:
            fcntl.flock(lock_f, fcntl.LOCK_EX)
            tmp.rename(REGISTRY_FILE)
    else:
        tmp.rename(REGISTRY_FILE)


def _log(action: str, name: str, detail: dict | None = None) -> None:
    entry = {"time": datetime.now().isoformat(), "action": action, "name": name, **(detail or {})}
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY_FILE.open("a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _find(assets: list[dict], name: str) -> int | None:
    for i, a in enumerate(assets):
        if a.get("id") == name or a.get("name") == name:
            return i
    return None


# ── 端口检测 ──


def _port_check(port: int) -> tuple[bool, str]:
    for host in ["127.0.0.1", "0.0.0.0"]:  # noqa: S104
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.3)
            r = s.connect_ex((host, port))
            s.close()
            if r == 0:
                return True, host
        except Exception:  # noqa: S112  # defensive fallback
            continue
    return False, ""


def _resolve_process(port: int) -> str:
    try:
        r = subprocess.run(["lsof", "-ti", f":{port}", "-sTCP:LISTEN"], capture_output=True, text=True, timeout=3)
        pid = r.stdout.strip().split("\n")[0]
        if not pid:
            return ""
        r2 = subprocess.run(["ps", "-p", pid, "-o", "comm="], capture_output=True, text=True, timeout=2)
        return f"{r2.stdout.strip() or 'unknown'} (PID {pid})"
    except Exception:
        return ""


# ════════════════════════════════════════════════════════════════
# Commands
# ════════════════════════════════════════════════════════════════


def cmd_list(args: list[str]) -> None:
    """List assets, optionally filtered by type and/or --category."""
    reg = _load()
    has_v4 = reg.get("version") == 4 and "entities" in reg

    filter_type = None
    filter_category = None
    i = 0
    while i < len(args):
        if args[i].startswith("--"):
            if args[i] == "--category" and i + 1 < len(args):
                filter_category = args[i + 1]
                i += 2
            else:
                print(f"未知参数: {args[i]}")
                return
        else:
            filter_type = args[i]
            i += 1

    # ── --category 模式 (v4 entities) ──
    if filter_category:
        entities = _get_entities(reg)
        if not entities:
            print("错误: registry 不是 v4 格式，没有 entities 数据")
            return
        if filter_category not in entities:
            print(f"未知分类: {filter_category}")
            print(f"可用分类: {', '.join(entities.keys())}")
            return
        _print_category_items(entities[filter_category], filter_category)
        return

    # ── 传统模式 (flat assets list by type) ──
    if not has_v4:
        assets = reg.get("assets", [])
    else:
        assets = _get_items(reg)

    if filter_type:
        if filter_type not in ASSET_TYPES and filter_type not in ("all", "full"):
            print(f"未知类型: {filter_type}")
            print(f"可用: {', '.join(ASSET_TYPES)}")
            return
        filtered = [a for a in assets if a.get("type") == filter_type] if filter_type not in ("all", "full") else assets
        _print_detailed(filtered, filter_type)
    else:
        _print_summary(assets)


def cmd_categories(args: list[str]) -> None:
    """List all v4 categories with item counts."""
    reg = _load()
    entities = _get_entities(reg)
    if not entities:
        print("错误: registry 不是 v4 格式（没有 entities 数据）")
        print(f"当前 version: {reg.get('version', 'unknown')}")
        print("请先升级到 v4 或使用 'forge asset list' 查看 v3 摘要")
        return

    total = 0
    print("\n  Forge Registry v4 — 分类统计")
    print(f"  {'─' * 40}")
    for cat in sorted(entities.keys()):
        count = len(entities[cat].get("items", []))
        total += count
        print(f"  • {cat:<20s} {count:>4} 条目")
    print(f"  {'─' * 40}")
    print(f"  总计 {total} 条目 (9 个分类)")


def cmd_register(args: list[str]) -> None:
    """Register or update an asset from JSON."""
    if len(args) < 1:
        print("用法: forge asset register '<json>'")
        print("  必填: id, name, type")
        print("  可选: 所有维度字段 (capabilities/port/schedule/project_path/...)")
        sys.exit(1)
    try:
        data = json.loads(args[0])
    except json.JSONDecodeError as e:
        print(f"JSON 解析失败: {e}")
        sys.exit(1)

    missing = [f for f in ("id", "name", "type") if f not in data]
    if missing:
        print(f"缺少必填字段: {', '.join(missing)}")
        sys.exit(1)
    if data["type"] not in ASSET_TYPES:
        print(f"未知类型: {data['type']}")
        sys.exit(1)

    reg = _load()
    assets = reg.setdefault("assets", [])
    idx = _find(assets, data["id"])

    if idx is not None:
        old = assets[idx]
        old.update(data)
        old["updated"] = datetime.now().strftime("%Y-%m-%d")
        assets[idx] = old
        _dual_write_entity(reg, data, "update")
        _save(reg)
        _log("update", data["id"], {"type": data["type"]})
        print(f"🔄 已更新 {data['type']}/{data['id']}")
    else:
        if "added" not in data:
            data["added"] = datetime.now().strftime("%Y-%m-%d")
        if "updated" not in data:
            data["updated"] = datetime.now().strftime("%Y-%m-%d")
        assets.append(data)
        _dual_write_entity(reg, data, "register")
        _save(reg)
        _log("register", data["id"], {"type": data["type"]})
        print(f"✅ 已注册 {data['type']}/{data['id']}")


def _dual_write_entity(reg: dict, data: dict, action: str) -> None:
    """同步写入 v4 entities（如果 registry 版本为 4）。"""
    if reg.get("version") != 4 or "entities" not in reg:
        return
    cat = _TYPE_TO_V4_CAT.get(data["type"])
    if not cat:
        return
    entities = reg["entities"]
    cat_data = entities.setdefault(cat, {"$schema": {}, "items": []})
    items = cat_data["items"]
    entry = {k: v for k, v in data.items() if k != "_category"}
    eidx = next((i for i, e in enumerate(items) if e.get("id") == data["id"] or e.get("name") == data["id"]), None)
    if eidx is not None:
        items[eidx].update(entry)
    else:
        items.append(entry)


def cmd_remove(args: list[str]) -> None:
    if not args:
        print("用法: forge asset remove <id>")
        sys.exit(1)
    name = args[0]
    reg = _load()
    assets = reg.get("assets", [])
    before = len(assets)
    reg["assets"] = [a for a in assets if a.get("id") != name and a.get("name") != name]
    if len(reg["assets"]) == before:
        print(f"⚠️  未找到 '{name}'")
        sys.exit(1)
    # 同步移除 entities 条目
    _dual_remove_entity(reg, name)
    _save(reg)
    _log("remove", name, {})
    print(f"🗑️  已移除 {name}")


def _dual_remove_entity(reg: dict, name: str) -> None:
    """从 v4 entities 中同步移除条目。"""
    if reg.get("version") != 4 or "entities" not in reg:
        return
    for cat_data in reg["entities"].values():
        items = cat_data.get("items", [])
        cat_data["items"] = [e for e in items if e.get("id") != name and e.get("name") != name]


def cmd_check(args: list[str]) -> None:
    """Check health status of assets."""
    reg = _load()
    assets = _get_items(reg)
    filter_name = args[0] if args else None

    for a in assets:
        name = a.get("id", a.get("name", "?"))
        if filter_name and name != filter_name:
            continue
        atype = a.get("type", a.get("_category", "?"))
        port = a.get("port") or 0

        if port:
            online, host = _port_check(port)
            proc = _resolve_process(port) if online else ""
            print(f"{'✅' if online else '❌'} {name:<24} type={atype:<10} port={port} {proc}")
        elif a.get("schedule"):
            lst = a.get("last_status", "never")
            icon = "✅" if lst == "ok" else "❌"
            print(f"{icon} {name:<24} type={atype:<10} schedule={a.get('schedule', '?')}")
        elif a.get("script"):
            lst = a.get("last_status", "never")
            icon = "✅" if lst == "ok" else "❌"
            print(f"{icon} {name:<24} type={atype:<10} script={a.get('script', '?')}")
        elif a.get("project_path"):
            path = Path(a["project_path"]).expanduser()
            exists = path.exists()
            print(f"{'✅' if exists else '❌'} {name:<24} type={atype:<10} {'exists' if exists else 'missing'}")
        elif atype == "monitor" or atype == "infrastructure":
            print(f"  • {name:<24} type={atype:<10}")
        elif atype == "route":
            print(f"  • {name:<24} type={atype:<10} path={a.get('path', '?')} → {a.get('target', '?')}")
        else:
            print(f"  • {name:<24} type={atype:<10} (registered)")


def cmd_scan(args: list[str]) -> None:
    """Auto-discover unregistered assets."""
    print("🔍 自动发现资产...")
    reg = _load()
    assets = _get_items(reg)

    {a.get("id") or a.get("name") for a in assets if a.get("id") or a.get("name")}

    # 1. Port scan
    try:
        r = subprocess.run(["lsof", "-iTCP", "-sTCP:LISTEN", "-P", "-n"], capture_output=True, text=True, timeout=10)
        listening: set[int] = set()
        for line in r.stdout.strip().split("\n")[1:]:
            parts = line.split()
            if len(parts) < 9:
                continue
            addr = parts[-1] if parts[-1].startswith("*") or ":" in parts[-1] else parts[-2]
            try:
                port = int(addr.split(":")[-1])
            except ValueError:
                continue
            if 1024 <= port < 60000:
                listening.add(port)

        known_ports = {a["port"] for a in assets if a.get("port")}
        new_ports = listening - known_ports
        if new_ports:
            print(f"  🆕 {len(new_ports)} 个未注册端口")
            for p in sorted(new_ports)[:5]:
                proc = _resolve_process(p)
                print(f"     {p} ({proc})")
    except Exception:
        pass

    # 2. Scripts
    known_scripts = {
        a.get("id") or a.get("name") for a in assets if a.get("type") == "script" or a.get("_category") == "cron"
    }
    for f in sorted(Path.home().glob(".hermes/scripts/*.py")):
        if f.stem not in known_scripts:
            print(f"  🆕 script: {f.stem}")
    for f in sorted(Path.home().glob(".hermes/scripts/*.sh")):
        if f.stem not in known_scripts:
            print(f"  🆕 script: {f.stem}")

    # 3. Projects
    known_projects = {
        a.get("id") or a.get("name") for a in assets if a.get("type") == "project" or a.get("_category") == "project"
    }
    workspace = Path.home() / "Workspace"
    if workspace.exists():
        for item in sorted(workspace.iterdir()):
            if item.is_dir() and not item.name.startswith(".") and item.name not in known_projects:
                if (
                    (item / "setup.py").exists()
                    or (item / "pyproject.toml").exists()
                    or (item / "package.json").exists()
                ):
                    print(f"  🆕 project: {item.name}")


def cmd_export(args: list[str]) -> None:
    """Export assets in various formats."""
    target = args[0] if args else "agora"
    reg = _load()
    assets = _get_items(reg)

    if target == "tools" or target == "tools-registry":
        # Generate tools-registry.json from unified assets
        tools = []
        for a in assets:
            if a.get("type") in ("agent", "mcp", "cli", "api", "service", "webapp", "pipeline", "skill", "plugin"):
                tool = {
                    "id": a["id"] if "id" in a else a["name"],
                    "name": a["name"],
                    "type": a.get("type", "service"),
                    "status": a.get("status", "active")
                    if a.get("status") in ("active", "deprecated", "evaluating", "archived", "candidate")
                    else "active",
                    "capabilities": a.get("capabilities", []),
                    "access": a.get("access", {"method": "mcp", "location": "unknown"}),
                    "source": a.get("source", {"type": "service", "provider": "", "version_tracking": False}),
                    "cost_model": a.get("cost_model", "unknown"),
                    "health": "ok" if a.get("port") and _port_check(a["port"])[0] else "unknown",
                    "notes": a.get("notes", ""),
                    "added": a.get("added", "2026-05"),
                    "updated": a.get("updated", datetime.now().strftime("%Y-%m-%d")),
                }
                if a.get("category"):
                    tool["category"] = a["category"]
                if a.get("telemetry"):
                    tool["telemetry"] = a["telemetry"]
                if a.get("install"):
                    tool["install"] = a["install"]
                if a.get("_discovery"):
                    tool["_discovery"] = a["_discovery"]
                tools.append(tool)

        output = {
            "schema_version": "1.2",
            "last_updated": datetime.now().strftime("%Y-%m-%d"),
            "description": "Generated by forge asset export tools from unified registry",
            "tools": tools,
        }
        FORGE_ROOT.mkdir(parents=True, exist_ok=True)
        TOOLS_FILE.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")
        print(f"✅ 已生成 tools-registry.json ({len(tools)} 工具)")

    elif target == "agora":
        # Generate agora-services.json format
        services = []
        for a in assets:
            port = a.get("port", 0)
            if not port:
                continue
            services.append(
                {
                    "name": a["name"],
                    "description": a.get("notes", ""),
                    "protocol": "mcp" if a.get("type") in ("mcp", "agent") else "http",
                    "mcp_endpoint": f"http://localhost:{port}/mcp" if port else f"stdio://{a['id']}",
                    "health_endpoint": f"http://localhost:{port}/health" if port else "",
                    "port": port,
                    "tags": a.get("tags", a.get("capabilities", [])),
                    "instances": [],
                }
            )
        output = {"services": services, "source": "forge-asset", "generated": datetime.now().isoformat()}
        print(json.dumps(output, indent=2, ensure_ascii=False))

    elif target == "json":
        # Full JSON dump
        print(json.dumps(reg, indent=2, ensure_ascii=False))

    else:
        print(f"未知导出目标: {target}")
        print("可用: tools, agora, json")


def cmd_import(args: list[str]) -> None:
    """Import assets from external sources."""
    source = args[0] if args else ""
    reg = _load()
    assets = reg.setdefault("assets", [])

    if source == "tools":
        # Import from tools-registry.json
        if not TOOLS_FILE.exists():
            print("⚠️  tools-registry.json 不存在")
            sys.exit(1)
        tools_data = json.loads(TOOLS_FILE.read_text())
        count = 0
        for t in tools_data.get("tools", []):
            # Map tool → unified asset
            asset = {
                "id": t["id"],
                "name": t["name"],
                # Normalize Forge types to unified asset types
                "type": _normalize_type(t.get("type", "service")),
                "status": t.get("status", "active"),
                "capabilities": t.get("capabilities", []),
                "access": t.get("access"),
                "source": t.get("source"),
                "cost_model": t.get("cost_model"),
                "telemetry": t.get("telemetry"),
                "install": t.get("install"),
                "_discovery": t.get("_discovery"),
                "category": t.get("category", []),
                "notes": t.get("notes", ""),
                "added": t.get("added", "2026-05"),
                "updated": t.get("updated", datetime.now().strftime("%Y-%m-%d")),
            }
            idx = _find(assets, t["id"])
            if idx is None:
                assets.append(asset)
                count += 1
        _save(reg)
        print(f"✅ 已导入 {count} 个工具到统一注册表 ({len(assets)} 总计)")

    elif source == "cron":
        # Import known cron jobs
        crons = [
            {
                "id": "wf-001-kos-index",
                "name": "WF-001 KOS每日索引",
                "type": "cron_job",
                "schedule": "0 2 * * *",
                "script_path": "wf-001.sh",
                "last_status": "ok",
            },
            {
                "id": "wf-002-minerva",
                "name": "WF-002 Minerva研究",
                "type": "cron_job",
                "schedule": "3 3 * * 0",
                "script_path": "wf-002.sh",
                "last_status": "error",
            },
            {
                "id": "wf-003-health",
                "name": "WF-003 系统健康",
                "type": "cron_job",
                "schedule": "0 10 * * *",
                "script_path": "wf-003.sh",
                "last_status": "ok",
            },
            {
                "id": "wf-005-handoff",
                "name": "WF-005 HANDOFF",
                "type": "cron_job",
                "schedule": "12 */2 * * *",
                "script_path": "wf-005.sh",
                "last_status": "ok",
            },
            {
                "id": "wf-006-perception",
                "name": "WF-006 感知管道",
                "type": "cron_job",
                "schedule": "0 * * * *",
                "script_path": "wf-006.sh",
                "last_status": "ok",
            },
            {
                "id": "wf-007-security",
                "name": "WF-007 安全",
                "type": "cron_job",
                "schedule": "0 */6 * * *",
                "script_path": "wf-007.sh",
                "last_status": "ok",
            },
            {
                "id": "wf-008-kanban",
                "name": "WF-008 Kanban",
                "type": "cron_job",
                "schedule": "*/5 * * * *",
                "script_path": "wf-008.sh",
                "last_status": "ok",
            },
            {
                "id": "wf-009-committee",
                "name": "WF-009 委员会",
                "type": "cron_job",
                "schedule": "0 9 * * 1",
                "script_path": "wf-009.sh",
                "last_status": "error",
            },
            {
                "id": "wf-010-constitution",
                "name": "WF-010 宪法",
                "type": "cron_job",
                "schedule": "22 4 * * *",
                "script_path": "wf-010.sh",
                "last_status": "ok",
            },
            {
                "id": "wf-011-digest",
                "name": "WF-011 每日摘要",
                "type": "cron_job",
                "schedule": "0 7 * * *",
                "script_path": "ecos-daily-digest.sh",
                "last_status": "ok",
            },
            {
                "id": "wf-013-knowledge-gap",
                "name": "WF-013 知识缺口",
                "type": "cron_job",
                "schedule": "42 12 * * *",
                "script_path": "ecos-knowledge-gap.sh",
                "last_status": "ok",
            },
            {
                "id": "wf-014-wps-sync",
                "name": "WF-014 WPS同步",
                "type": "cron_job",
                "schedule": "0 1 * * *",
                "script_path": "wpsnote-kos-sync.py",
                "last_status": "ok",
            },
            {
                "id": "wf-015-swarm-guardian",
                "name": "WF-015 Swarm",
                "type": "cron_job",
                "schedule": "18 10 * * 1,3,5",
                "script_path": "wf-015.sh",
                "last_status": "error",
            },
            {
                "id": "codexbar-quota",
                "name": "CodexBar配额",
                "type": "cron_job",
                "schedule": "5 * * * *",
                "script_path": "codexbar-quota.sh",
                "last_status": "ok",
            },
            {
                "id": "ecos-watchdog",
                "name": "eCOS Watchdog",
                "type": "cron_job",
                "schedule": "every 5m",
                "script_path": "ecos-watchdog.sh",
                "last_status": "ok",
            },
            {
                "id": "daily-todo",
                "name": "Daily TODO",
                "type": "cron_job",
                "schedule": "45 8 * * *",
                "script_path": "daily-todo.sh",
                "last_status": "ok",
            },
            {
                "id": "git-sync",
                "name": "Git Sync",
                "type": "cron_job",
                "schedule": "30 18 * * *",
                "script_path": "workspace-git-sync.py",
                "last_status": "ok",
            },
            {
                "id": "event-watcher",
                "name": "EventWatcher",
                "type": "cron_job",
                "schedule": "*/5 8-22 * * *",
                "script_path": "hermes-event-watcher.py",
                "last_status": "ok",
            },
            {
                "id": "daily-summary",
                "name": "Agent Runtime 摘要",
                "type": "cron_job",
                "schedule": "37 8 * * *",
                "script_path": "daily-summary.sh",
                "last_status": "ok",
            },
            {
                "id": "drift-check",
                "name": "Drift Check",
                "type": "cron_job",
                "schedule": "0 5 * * *",
                "script_path": "arcnode-drift-check",
                "last_status": "error",
            },
            {
                "id": "evolution-daily",
                "name": "Evolution Daily",
                "type": "cron_job",
                "schedule": "0 6 * * *",
                "script_path": "evolution-daily",
                "last_status": "ok",
            },
            {
                "id": "sniff-fix",
                "name": "Sniff Auto Fix",
                "type": "cron_job",
                "schedule": "5 6 * * *",
                "script_path": "arcnode-sniff-deps",
                "last_status": "error",
            },
            {
                "id": "dep-aging",
                "name": "Dep Aging",
                "type": "cron_job",
                "schedule": "10 6 * * *",
                "script_path": "arcnode-dep-aging",
                "last_status": "ok",
            },
            {
                "id": "constitution-sync",
                "name": "Constitution Sync",
                "type": "cron_job",
                "schedule": "20 6 * * *",
                "script_path": "arcnode-sync-constitution",
                "last_status": "ok",
            },
            {
                "id": "bwg-watchdog",
                "name": "BWG Watchdog",
                "type": "cron_job",
                "schedule": "*/15 7-23 * * *",
                "script_path": "bwg-watchdog",
                "last_status": "ok",
            },
            {
                "id": "freshness-watch",
                "name": "研究保鲜",
                "type": "cron_job",
                "schedule": "0 8 * * *",
                "script_path": "freshness-watch",
                "last_status": "error",
            },
            {
                "id": "health-monitor",
                "name": "健康监控",
                "type": "cron_job",
                "schedule": "0 9 * * *",
                "script_path": "health-monitor",
                "last_status": "error",
            },
            {
                "id": "port-watch",
                "name": "端口监控",
                "type": "cron_job",
                "schedule": "every 30m",
                "script_path": "asset-watch.sh",
                "last_status": "ok",
            },
            {
                "id": "auto-archive",
                "name": "Auto Archive",
                "type": "cron_job",
                "schedule": "0 3 * * 0",
                "script_path": "auto-archive",
                "last_status": "never",
            },
            {
                "id": "resolve-review",
                "name": "Resolve Review",
                "type": "cron_job",
                "schedule": "0 9 * * 1",
                "script_path": "arcnode-resolve-review",
                "last_status": "never",
            },
            {
                "id": "graph-update",
                "name": "Graph Auto Update",
                "type": "cron_job",
                "schedule": "0 7 * * 1",
                "script_path": "graph-auto-update",
                "last_status": "never",
            },
            {
                "id": "gov-report",
                "name": "Governance Report",
                "type": "cron_job",
                "schedule": "30 9 * * 1",
                "script_path": "weekly-governance-report",
                "last_status": "never",
            },
            {
                "id": "dual-baseline",
                "name": "双基线",
                "type": "cron_job",
                "schedule": "5 9 * * 1",
                "script_path": "dual-baseline",
                "last_status": "never",
            },
        ]
        for c in crons:
            idx = _find(assets, c["id"])
            if idx is None:
                assets.append(c)
        _save(reg)
        print(f"✅ 导入 {len(crons)} 个 cron 作业")

    elif source == "services":
        # Import services from portctl
        services = [
            {
                "id": "agentmesh-gateway",
                "name": "agentmesh Gateway",
                "type": "service",
                "port": 3000,
                "bind": "0.0.0.0",  # noqa: S104
                "host": "localhost",
                "tags": ["runtime", "gateway"],
            },
            {"id": "agentmesh-pulse", "name": "agentmesh Pulse", "type": "daemon", "port": 31337, "bind": "127.0.0.1"},
            {
                "id": "agora-mcp",
                "name": "Agora MCP",
                "type": "service",
                "port": int(os.environ.get("AGORA_MCP_PORT", "7430")),
                "bind": "127.0.0.1",
                "tags": ["agora", "mcp"],
            },
            {
                "id": "agora-dashboard",
                "name": "Agora Dashboard",
                "type": "webapp",
                "port": int(os.environ.get("AGORA_DASHBOARD_PORT", "7430")),
                "bind": "0.0.0.0",  # noqa: S104
            },
            {
                "id": "minerva",
                "name": "Minerva",
                "type": "webapp",
                "port": int(os.environ.get("MINERVA_PORT", "8765")),
                "bind": "0.0.0.0",  # noqa: S104
            },
            {
                "id": "bos-daemon",
                "name": "B-OS Daemon",
                "type": "service",
                "port": int(os.environ.get("BOS_DAEMON_PORT", 7420)),
                "bind": "0.0.0.0",  # noqa: S104
                "tags": ["bos", "mcp"],
            },
            {
                "id": "bos-web",
                "name": "B-OS Web",
                "type": "webapp",
                "port": int(os.environ.get("BOS_WEB_PORT", 8082)),
                "bind": "0.0.0.0",  # noqa: S104  # BOS service bind config (data, not socket.bind)
            },
            {
                "id": "bos-metrics",
                "name": "B-OS Metrics",
                "type": "service",
                "port": int(os.environ.get("BOS_METRICS_PORT", 9090)),
                "bind": "0.0.0.0",  # noqa: S104  # BOS service bind config (data, not socket.bind)
            },
            {
                "id": "agent-runtime",
                "name": "Agent Runtime",
                "type": "daemon",
                "port": int(os.environ.get("AGENT_RUNTIME_PORT", 9876)),
                "bind": "127.0.0.1",
            },
            {
                "id": "hermes-mcp",
                "name": "Hermes MCP",
                "type": "service",
                "port": int(os.environ.get("HERMES_MCP_PORT", 7423)),
                "bind": "127.0.0.1",
            },
            {
                "id": "ollama",
                "name": "Ollama",
                "type": "service",
                "port": int(os.environ.get("OLLAMA_PORT", 11434)),
                "bind": "127.0.0.1",
            },
            {"id": "clash", "name": "Clash", "type": "service", "port": 7890, "bind": "0.0.0.0"},  # noqa: S104
        ]
        for s in services:
            idx = _find(assets, str(s["id"]))
            if idx is None:
                assets.append(s)
        _save(reg)
        print(f"✅ 导入 {len(services)} 个服务")

    else:
        print(f"未知导入源: {source}")
        print("可用: tools, cron, services")


def cmd_watch(args: list[str]) -> None:
    interval = int(args[0]) if args else 30
    print(f"👁️  Asset 监控 (每 {interval}s)")
    try:
        while True:
            reg = _load()
            assets = _get_items(reg)
            now = datetime.now().strftime("%H:%M:%S")
            with_port = [a for a in assets if a.get("port")]
            online = sum(1 for a in with_port if _port_check(a["port"])[0])
            total_assets = len(assets)
            total_port = len(with_port)
            print(
                f"\r[{now}] 资产: {total_assets} | 在线: {online}/{total_port} ({online / total_port * 100:.0f}%)     ",
                end="",
            )
            sys.stdout.flush()
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n")


# ════════════════════════════════════════════════════════════════
# CLI Entry
# ════════════════════════════════════════════════════════════════


def run(args: list[str]) -> int:
    if not args or args[0] in ("-h", "--help", "help"):
        print(f"""Forge Asset — 统一资产清册 (v3/v4)

用法: forge asset <子命令> [参数]

子命令:
  list [type]         列出资产。type=agent|mcp|cli|api|service|daemon|webapp|cron_job|project|script|monitor|route|pipeline|plugin|all
  list --category X   按 v4 category 列出 (service|tool|cron|infrastructure|project|data_store|configuration|solution|event)
  categories          列出所有 v4 category 及其条目数
  register '<json>'   注册/更新资产 (必填: id, name, type)
  remove <id>         移除资产
  check [name]        检查资产健康状态
  scan                自动发现未注册资产
  export tools        生成 tools-registry.json (向后兼容)
  export agora        导出 agora 服务格式
  import tools        从 tools-registry.json 导入
  import cron         导入所有 cron 作业
  import services     导入所有服务
  watch [sec]         持续监控

所有数据统一存储在: {REGISTRY_FILE}
""")
        return 0

    cmd = args[0]
    cmd_args = args[1:]

    cmds = {
        "list": cmd_list,
        "ls": cmd_list,
        "categories": cmd_categories,
        "cats": cmd_categories,
        "list-categories": cmd_categories,
        "register": cmd_register,
        "add": cmd_register,
        "remove": cmd_remove,
        "rm": cmd_remove,
        "check": cmd_check,
        "scan": cmd_scan,
        "export": cmd_export,
        "import": cmd_import,
        "watch": cmd_watch,
    }

    if cmd not in cmds:
        print(f"未知命令: {cmd}")
        return 1

    cmds[cmd](cmd_args)
    return 0


if __name__ == "__main__":
    sys.exit(run(sys.argv[1:]))
