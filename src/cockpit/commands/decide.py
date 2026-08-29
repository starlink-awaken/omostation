"""cockpit.commands.decide — 决策收件箱 CLI 入口.

与 agent 运行时对齐的决策收件箱: 收集多渠道意图 → 结构化决策列表 → 驱动生命周期.

Usage:
    cockpit decide list               — 列出待决策项
    cockpit decide add <title>        — 手动添加决策项
    cockpit decide approve <id>       — 批准决策
    cockpit decide reject <id>        — 拒绝决策
    cockpit decide status             — 收件箱状态概览
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ..data_index import resolve_workspace_root
from .base import _get_console

INBOX_PATH = Path(".omo/state/decision-inbox.json")


def _load_inbox() -> dict:
    root = resolve_workspace_root()
    path = root / INBOX_PATH
    if not path.exists():
        return {"items": [], "version": "1.0"}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"items": [], "version": "1.0"}


def _save_inbox(data: dict) -> None:
    # CR-DIRECT-IO: .omo/state writes must go through the omo broker helpers,
    # not direct Path mutation (contract_gatekeeper).
    from omo.omo_io import ensure_parent_dir, write_text_atomic

    root = resolve_workspace_root()
    path = root / INBOX_PATH
    ensure_parent_dir(path)
    write_text_atomic(path, json.dumps(data, indent=2, ensure_ascii=False))


def cmd_list(args: argparse.Namespace) -> int:
    console = _get_console()
    data = _load_inbox()
    items = data.get("items", [])
    pending = [i for i in items if i.get("status") == "pending"]
    if not pending:
        console.print("[green]✓ 收件箱为空 — 没有待决策项[/]")
        return 0
    console.print(f"[bold]决策收件箱 ({len(pending)} 项待处理):[/]\n")
    for item in pending:
        console.print(f"  [cyan]{item.get('id', '?')[:8]}[/] {item.get('title', '(无标题)')}")
        if item.get("source"):
            console.print(f"    [dim]来源: {item['source']}[/]")
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    console = _get_console()
    title = " ".join(args.title) if isinstance(args.title, list) else str(args.title)
    if not title:
        console.print("[red]❌ 缺少标题: cockpit decide add <title>[/]")
        return 1

    data = _load_inbox()
    item = {
        "id": f"dec-{len(data.get('items', [])) + 1:04d}",
        "title": title,
        "status": "pending",
        "source": "manual",
        "created": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
    }
    data.setdefault("items", []).append(item)
    _save_inbox(data)
    console.print(f"[green]✓ 已添加决策项:[/] {item['id']} — {title}")
    return 0


def cmd_approve(args: argparse.Namespace) -> int:
    console = _get_console()
    data = _load_inbox()
    item_id = args.id
    for item in data.get("items", []):
        if item.get("id", "").startswith(item_id) or item.get("id") == item_id:
            item["status"] = "approved"
            item["decided_at"] = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
            _save_inbox(data)
            console.print(f"[green]✓ 已批准:[/] {item['id']} — {item.get('title', '')}")
            return 0
    console.print(f"[red]❌ 未找到决策项: {item_id}[/]")
    return 1


def cmd_reject(args: argparse.Namespace) -> int:
    console = _get_console()
    data = _load_inbox()
    item_id = args.id
    for item in data.get("items", []):
        if item.get("id", "").startswith(item_id) or item.get("id") == item_id:
            item["status"] = "rejected"
            item["decided_at"] = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
            _save_inbox(data)
            console.print(f"[yellow]✗ 已拒绝:[/] {item['id']} — {item.get('title', '')}")
            return 0
    console.print(f"[red]❌ 未找到决策项: {item_id}[/]")
    return 1


def cmd_status(args: argparse.Namespace) -> int:
    console = _get_console()
    data = _load_inbox()
    items = data.get("items", [])
    pending = [i for i in items if i.get("status") == "pending"]
    approved = [i for i in items if i.get("status") == "approved"]
    rejected = [i for i in items if i.get("status") == "rejected"]

    console.print("[bold]决策收件箱状态:[/]")
    console.print(f"  待处理: [yellow]{len(pending)}[/]")
    console.print(f"  已批准: [green]{len(approved)}[/]")
    console.print(f"  已拒绝: [red]{len(rejected)}[/]")
    console.print(f"  总计: {len(items)}")
    return 0


def cmd_decide(args: argparse.Namespace) -> int:
    """决策收件箱 — 根据 decide_action 分发到对应处理函数."""
    action = getattr(args, "decide_action", None)
    if action == "list":
        return cmd_list(args)
    if action == "add":
        return cmd_add(args)
    if action == "approve":
        return cmd_approve(args)
    if action == "reject":
        return cmd_reject(args)
    if action == "status":
        return cmd_status(args)
    # Default: show help
    console = _get_console()
    console.print("[bold]决策收件箱 (cockpit decide)[/]\n")
    console.print("  decide list               — 列出待决策项")
    console.print("  decide add <title>        — 手动添加决策项")
    console.print("  decide approve <id>       — 批准决策")
    console.print("  decide reject <id>        — 拒绝决策")
    console.print("  decide status             — 收件箱状态概览")
    return 0
