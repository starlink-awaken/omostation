"""cockpit.commands.decide — 决策收件箱 CLI 入口.

与 agent 运行时对齐的决策收件箱: 收集多渠道意图 → 结构化决策列表 → 驱动生命周期.
HITL proposals (.omo/_knowledge/hitl-proposals/hitl-*.yaml) 也纳入 decide list/approve/reject.

Usage:
    cockpit decide list               — 列出待决策项
    cockpit decide add <title>        — 手动添加决策项
    cockpit decide approve <id>       — 批准决策
    cockpit decide reject <id>        — 拒绝决策
    cockpit decide status             — 收件箱状态概览
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

from ..data_index import resolve_workspace_root
from .base import _get_console
from .scenario import (
    _decision_inbox_add_intent,
    _decision_inbox_create_journey,
    _decision_inbox_create_scene,
    _decision_inbox_list,
    _decision_inbox_set_status,
)

_DEFAULT_SCENE_NAME = "General decisions"
_DEFAULT_JOURNEY_NAME = "Inbox"


def _canonical_items(root: Path) -> tuple[list[dict[str, Any]], str | None]:
    result = _decision_inbox_list(root)
    if not result.get("ok"):
        return [], str(result.get("error") or "canonical decision inbox unavailable")
    items: list[dict[str, Any]] = []
    for scene in result.get("scenes", []):
        if not isinstance(scene, dict):
            continue
        for journey in scene.get("journeys", []):
            if not isinstance(journey, dict):
                continue
            for intent in journey.get("intents", []):
                if isinstance(intent, dict):
                    items.append(intent)
    return items, None


def _find_item(items: list[dict[str, Any]], item_id: str) -> dict[str, Any] | None:
    return next(
        (item for item in items if str(item.get("id", "")).startswith(item_id) or item.get("id") == item_id),
        None,
    )


def _ensure_default_target(root: Path) -> tuple[str | None, str | None, str | None]:
    result = _decision_inbox_list(root)
    if not result.get("ok"):
        return None, None, str(result.get("error") or "canonical decision inbox unavailable")
    scenes = [scene for scene in result.get("scenes", []) if isinstance(scene, dict)]
    if not scenes:
        created = _decision_inbox_create_scene(
            root,
            name=_DEFAULT_SCENE_NAME,
            description="Compatibility entry for cockpit decide",
            priority="P2",
        )
        if not created.get("ok"):
            return None, None, str(created.get("error") or "failed to create default decision scene")
        scenes = [created["scene"]]
    scene = scenes[0]
    scene_id = str(scene.get("id") or "")
    journeys = [journey for journey in scene.get("journeys", []) if isinstance(journey, dict)]
    if not journeys:
        created = _decision_inbox_create_journey(root, scene_id=scene_id, name=_DEFAULT_JOURNEY_NAME)
        if not created.get("ok"):
            return None, None, str(created.get("error") or "failed to create default decision journey")
        journeys = [created["journey"]]
    journey_id = str(journeys[0].get("id") or "")
    if not scene_id or not journey_id:
        return None, None, "canonical decision scene or journey has no id"
    return scene_id, journey_id, None


def _item_title(item: dict[str, Any]) -> str:
    structured = item.get("structured")
    if isinstance(structured, dict) and structured.get("title"):
        return str(structured["title"])
    return str(item.get("raw_content") or item.get("title") or "(无标题)")


def _update_status(console: Any, item_id: str, status: str) -> int:
    root = resolve_workspace_root()
    items, error = _canonical_items(root)
    if error:
        console.print(f"[red]❌ 无法读取决策收件箱:[/] {error}")
        return 1
    item = _find_item(items, item_id)
    if item is None:
        console.print(f"[red]❌ 未找到决策项: {item_id}[/]")
        return 1
    result = _decision_inbox_set_status(root, intent_id=str(item["id"]), status=status)
    if not result.get("ok"):
        console.print(f"[red]❌ 决策状态更新失败:[/] {result.get('error', 'unknown error')}")
        return 1
    mark = "✓" if status == "approved" else "✗"
    color = "green" if status == "approved" else "yellow"
    label = "已批准" if status == "approved" else "已拒绝"
    console.print(f"[{color}]{mark} {label}:[/] {item['id']} — {_item_title(item)}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    console = _get_console()
    items, error = _canonical_items(resolve_workspace_root())
    if error:
        console.print(f"[red]❌ 无法读取决策收件箱:[/] {error}")
        return 1
    pending = [item for item in items if item.get("status") == "pending"]

    # Also scan HITL proposals
    proposals_dir = resolve_workspace_root() / ".omo" / "_knowledge" / "hitl-proposals"
    hitl_pending: list[dict[str, Any]] = []
    if proposals_dir.exists():
        for f in sorted(proposals_dir.glob("hitl-*.yaml")):
            try:
                p = yaml.safe_load(f.read_text())
                if p and p.get("status") == "pending":
                    hitl_pending.append(p)
            except Exception:
                continue

    if not pending and not hitl_pending:
        console.print("[green]✓ 收件箱为空 — 没有待决策项[/]")
        return 0

    if pending:
        console.print(f"[bold]决策收件箱 ({len(pending)} 项待处理):[/]\n")
        for item in pending:
            console.print(f"  [cyan]{str(item.get('id', '?'))[:8]}[/] {_item_title(item)}")
            if item.get("source"):
                console.print(f"    [dim]来源: {item['source']}[/]")

    if hitl_pending:
        console.print(f"\n[bold]HITL 待审批提案 ({len(hitl_pending)} 项):[/]\n")
        for p in hitl_pending:
            console.print(f"  [magenta]{p['proposal_id'][:18]}[/] {p.get('title', '(untitled)')}")
            console.print(f"    [dim]bet={p.get('bet_id')} expires={p.get('expires_at')}[/]")
            # v1.1: show notification state
            notified_at = p.get("notified_at")
            channels = p.get("notification_channels", [])
            if notified_at:
                console.print(f"    [dim]notified={notified_at} channels={','.join(channels) or '(none)'}[/]")
            else:
                console.print(f"    [dim]notified=(not yet) channels=(none)[/]")
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    console = _get_console()
    title = " ".join(args.title) if isinstance(args.title, list) else str(args.title)
    if not title:
        console.print("[red]❌ 缺少标题: cockpit decide add <title>[/]")
        return 1

    root = resolve_workspace_root()
    scene_id, journey_id, error = _ensure_default_target(root)
    if error:
        console.print(f"[red]❌ 无法添加决策项:[/] {error}")
        return 1
    result = _decision_inbox_add_intent(
        root,
        scene_id=scene_id or "",
        source="manual",
        raw_content=title,
        priority="P3",
        journey_id=journey_id,
    )
    if not result.get("ok"):
        console.print(f"[red]❌ 无法添加决策项:[/] {result.get('error', 'unknown error')}")
        return 1
    item = result.get("intent", {})
    console.print(f"[green]✓ 已添加决策项:[/] {item.get('id', '?')} — {title}")
    return 0


def _is_hitl_id(item_id: str) -> bool:
    """Check if an ID matches a HITL proposal file on disk."""
    proposals_dir = resolve_workspace_root() / ".omo" / "_knowledge" / "hitl-proposals"
    if not proposals_dir.exists():
        return False
    matches = list(proposals_dir.glob(f"{item_id}*.yaml"))
    return len(matches) > 0


def _hitl_update(proposal_id: str, action: str) -> int:
    """Delegate approve/reject to hitl-proposal CLI."""
    console = _get_console()
    root = resolve_workspace_root()
    hitl_script = root / "bin" / "hitl-proposal.py"
    if not hitl_script.exists():
        console.print("[red]❌ hitl-proposal.py not found in bin/[/]")
        return 1
    result = subprocess.run(
        [sys.executable, str(hitl_script), action, proposal_id],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        console.print(f"[red]❌ HITL {action} failed:[/] {result.stderr.strip()}")
        return 1
    console.print(f"[green]✓ HITL {action}d:[/] {result.stdout.strip()}")
    return 0


def cmd_approve(args: argparse.Namespace) -> int:
    item_id = str(args.id)
    if item_id.startswith("hitl-") or _is_hitl_id(item_id):
        return _hitl_update(item_id, "approve")
    return _update_status(_get_console(), item_id, "approved")


def cmd_reject(args: argparse.Namespace) -> int:
    item_id = str(args.id)
    if item_id.startswith("hitl-") or _is_hitl_id(item_id):
        return _hitl_update(item_id, "reject")
    return _update_status(_get_console(), item_id, "rejected")


def cmd_status(args: argparse.Namespace) -> int:
    console = _get_console()
    items, error = _canonical_items(resolve_workspace_root())
    if error:
        console.print(f"[red]❌ 无法读取决策收件箱:[/] {error}")
        return 1

    # HITL proposals
    proposals_dir = resolve_workspace_root() / ".omo" / "_knowledge" / "hitl-proposals"
    hitl_pending = hitl_approved = hitl_rejected = 0
    if proposals_dir.exists():
        for f in proposals_dir.glob("hitl-*.yaml"):
            try:
                p = yaml.safe_load(f.read_text())
                s = p.get("status", "")
                if s == "pending":
                    hitl_pending += 1
                elif s == "approved":
                    hitl_approved += 1
                elif s in ("rejected", "expired"):
                    hitl_rejected += 1
            except Exception:
                continue

    pending = [i for i in items if i.get("status") == "pending"]
    approved = [i for i in items if i.get("status") == "approved"]
    rejected = [i for i in items if i.get("status") == "rejected"]

    console.print("[bold]决策收件箱状态:[/]")
    console.print(f"  待处理: [yellow]{len(pending)}[/]")
    console.print(f"  已批准: [green]{len(approved)}[/]")
    console.print(f"  已拒绝: [red]{len(rejected)}[/]")
    console.print(f"  总计: {len(items)}")
    if hitl_pending or hitl_approved or hitl_rejected:
        console.print(f"\n[HITL 提案] 待审批: [yellow]{hitl_pending}[/]  已批准: [green]{hitl_approved}[/]  已拒绝/过期: [red]{hitl_rejected}[/]")
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
