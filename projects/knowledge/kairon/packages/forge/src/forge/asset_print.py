#!/usr/bin/env python3
# ruff: noqa
"""Forge Asset Print Helpers — 资产列表/详情/分类打印.

从 asset_cli.py 抽出 (God Module 拆 wave 9 终章, asset_cli.py 1280->~1080).
_print_summary/_print_detailed/_print_category_items 三个打印函数 (~200 LOC).
依赖 _port_check/_resolve_process/_get_item_id (从 asset_cli import).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path


def _helpers():
    """延迟 import asset_cli helpers 解循环 (asset_cli import asset_print 时 asset_cli 未加载完)."""
    from forge.asset_cli import _get_item_id, _port_check, _resolve_process

    return _get_item_id, _port_check, _resolve_process


def _print_summary(assets: list[dict]) -> None:
    _g, _pc, _rp = _helpers()  # 解包 helpers (延迟 import 解循环)
    print(f"\n  Forge Asset — 统一摘要 ({datetime.now().strftime('%H:%M')})")
    print(f"  {'─' * 40}")
    icons = {
        "agent": "🤖",
        "mcp": "🔌",
        "cli": "💻",
        "api": "🌐",
        "service": "🔌",
        "daemon": "⚙️",
        "webapp": "🖥️",
        "cron_job": "⏰",
        "project": "📁",
        "script": "📜",
        "monitor": "👁️",
        "route": "🔗",
        "pipeline": "🔧",
        "plugin": "🧩",
    }
    by_type: dict[str, int] = {}
    for a in assets:
        t = a.get("type", "unknown")
        by_type[t] = by_type.get(t, 0) + 1
    for t in sorted(by_type):
        print(f"  {icons.get(t, '•')} {t:<12s} {by_type[t]:>3}")
    print(f"  {'─' * 40}")
    print(f"  总计 {len(assets)}")
    with_port = [a for a in assets if a.get("port")]
    online = sum(1 for a in with_port if _pc(a["port"])[0])
    if with_port:
        print(f"  服务在线: {online}/{len(with_port)} ({online / len(with_port) * 100:.0f}%)")


def _print_detailed(assets: list[dict], filter_type: str) -> None:
    _g, _pc, _rp = _helpers()  # 解包 helpers (延迟 import 解循环)
    if not assets:
        print(f"  无 {filter_type} 类型资产")
        return

    if filter_type in ("service", "daemon", "mcp", "api", "agent"):
        print(f"  {'ID':<24} {'端口':>6} {'状态':<6} {'进程'}")
        print(f"  {'─' * 65}")
        for a in assets:
            port = a.get("port") or 0
            online, host = _pc(port) if port else (False, "")
            status = "✅" if online else "❌"
            proc = _rp(port) if online else ""
            name = a.get("id", a.get("name", "?"))
            port_str = str(port) if port else "—"
            print(f"  {name:<24} {port_str:>6} {status:<6} {proc}")

    elif filter_type == "cron_job":
        print(f"  {'ID':<28} {'调度':<18} {'状态':<6} {'脚本'}")
        print(f"  {'─' * 65}")
        for a in assets:
            sched = a.get("schedule", "?")
            lst = a.get("last_status", "never")
            icon = "✅" if lst == "ok" else "❌"
            script = str(a.get("script_path", ""))[:30]
            print(f"  {a.get('id', '?'):<28} {sched:<18} {icon:<6} {script}")

    elif filter_type == "project":
        print(f"  {'ID':<22} {'语言':<10} {'路径'}")
        print(f"  {'─' * 65}")
        for a in assets:
            path = Path(a.get("project_path", "")).expanduser()
            exists = "✅" if path.exists() else "❌"
            print(f"  {a.get('id', '?'):<22} {a.get('language', '?'):<10} {path} {exists}")

    elif filter_type == "route":
        print(f"  {'路径':<32} {'目标':<22} {'方法'}")
        print(f"  {'─' * 65}")
        for a in assets:
            print(f"  {a.get('id', '?'):<32} {a.get('target', ''):<22} {a.get('method', 'ANY')}")

    elif filter_type in ("script", "pipeline", "plugin", "webapp", "cli", "monitor"):
        print(f"  {'ID':<28} {'状态':<8} {'备注'}")
        print(f"  {'─' * 65}")
        for a in assets:
            status_icon = "✅" if a.get("status") == "active" else "⏸️"
            notes = (a.get("notes", "") or "")[:40]
            print(f"  {a.get('id', '?'):<28} {status_icon:<8} {notes}")


def _print_category_items(cat_data: dict, category: str) -> None:
    _g, _pc, _rp = _helpers()  # 解包 helpers (延迟 import 解循环)
    """Print items from a v4 category with appropriate schema-aware columns."""
    items = cat_data.get("items", [])
    if not items:
        print(f"  ➤ {category}: 无条目")
        return

    print(f"  ➤ {category} ({len(items)} 条目)")
    print(f"  {'─' * 68}")

    if category == "service":
        print(f"  {'ID':<24} {'端口':>6} {'协议':<6} {'描述'}")
        print(f"  {'─' * 68}")
        for item in items:
            iid = _g(item)
            port = item.get("port", "—")
            proto = item.get("protocol", "—")
            desc = (item.get("description") or "")[:30]
            print(f"  {iid:<24} {str(port):>6} {proto:<6} {desc}")

    elif category == "tool":
        print(f"  {'名称':<28} {'状态':<8} {'类型':<12} {'来源'}")
        print(f"  {'─' * 68}")
        for item in items:
            name = item.get("name", "?")
            status = item.get("status", "?")
            t = item.get("type", "?")
            provider = item.get("forge_id", "") if "forge_id" in item else ""
            print(f"  {name:<28} {status:<8} {t:<12} {provider}")

    elif category == "cron":
        print(f"  {'名称':<28} {'调度':<18} {'状态':<6} {'脚本'}")
        print(f"  {'─' * 68}")
        for item in items:
            name = item.get("name", "?")
            sched = item.get("schedule", "?")
            lst = item.get("last_status", "never")
            icon = "✅" if lst == "ok" else "❌"
            script = str(item.get("script", ""))[:20]
            print(f"  {name:<28} {sched:<18} {icon:<6} {script}")

    elif category == "project":
        print(f"  {'ID':<22} {'语言':<10} {'状态':<8} {'描述'}")
        print(f"  {'─' * 68}")
        for item in items:
            iid = _g(item)
            lang = item.get("language", "—")
            st = item.get("status", "—")
            desc = (item.get("description") or "")[:20]
            print(f"  {iid:<22} {lang:<10} {st:<8} {desc}")

    else:
        print(f"  {'ID':<24} {'其他字段'}")
        print(f"  {'─' * 68}")
        for item in items:
            iid = _g(item)
            extra = ", ".join(f"{k}={v}" for k, v in list(item.items())[:4] if k not in ("id", "name"))
            print(f"  {iid:<24} {extra}")
