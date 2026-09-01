"""cockpit.commands.im_triage — render IM triage pending cards (BET-Y1Q4-T2-02).

Reads triage results from .omo/state/im-triage/*.json (written by the agora
bos://im/session/triage gateway) and renders today's pending-approval cards.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

ACTION_LABELS = {
    "query": "🔍 查阅",
    "draft": "📝 拟稿",
    "approve": "✅ 审批",
    "urge": "⏰ 催办",
}


def _state_dir(ws: Path) -> Path:
    return ws / ".omo" / "state" / "im-triage"


def _ws() -> Path:
    cur = Path(__file__).resolve()
    for parent in cur.parents:
        if (parent / "docs" / "project-registry.yaml").is_file():
            return parent
    return Path.cwd()


def _load_cards(state_dir: Path) -> list[dict]:
    cards: list[dict] = []
    if not state_dir.is_dir():
        return cards
    for f in sorted(state_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        cards.extend(data.get("cards", []))
    return cards


def cmd_im_triage(args: argparse.Namespace) -> int:
    """Render pending IM task cards (all parked in pending_approval — red line)."""
    cards = _load_cards(_state_dir(_ws()))
    if not cards:
        console.print(
            "[yellow]暂无 IM 待办卡片（.omo/state/im-triage/ 无产物）[/yellow]\n"
            "[dim]生成方式: python -m agora.server.tools_bos.im test_session_ingress 后由网关落盘[/dim]"
        )
        return 0

    table = Table(title=f"📱 IM 待办卡片 ({len(cards)} 张, 全部待审批)", box=None)
    table.add_column("优先", style="cyan")
    table.add_column("动作")
    table.add_column("来源")
    table.add_column("内容", style="white", max_width=42)
    table.add_column("截止", justify="right")
    for card in cards:
        action = ACTION_LABELS.get(card.get("action", ""), card.get("action", "?"))
        priority = card.get("priority", "normal")
        style = "bold red" if priority == "high" else "dim"
        deadline = card.get("deadline_hint_days")
        deadline_s = f"{deadline:.0f}天" if deadline is not None else "—"
        table.add_row(
            "🔴 高" if priority == "high" else "⚪ 普通",
            action,
            f"{card.get('platform', '?')}/{card.get('sender', '?')}",
            card.get("payload", "")[:42],
            deadline_s,
            style=style if priority == "high" else "",
        )
    console.print(table)
    console.print(
        Panel(
            f"[dim]生成时间: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')} | "
            f"红线: 所有卡片停在 pending_approval, 须经夏明星确认后外发[/dim]",
            title="⚠️ 红线提示",
        )
    )
    return 0
