"""BOS Inbox 多源私有知识神经网 Cockpit CLI 命令。"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from rich.table import Table
from rich.panel import Panel

from cockpit.cli import console, err


def _get_inbox_paths() -> tuple[Path, Path]:
    doc_root = Path(os.environ.get("BOS_DOCUMENTS_ROOT", str(Path.home() / "Documents")))
    return doc_root / "@公共" / "_runtime", doc_root / "_inbox"


def cmd_bos_inbox(args: Any) -> int:
    """处理 omo bos-inbox [status|search|pending] 子命令。"""
    subcmd = getattr(args, "inbox_cmd", "status") or "status"

    if subcmd == "status":
        return _cmd_inbox_status()
    elif subcmd == "search":
        query = getattr(args, "query", "") or ""
        if not query:
            err.print("[red]请提供搜索关键词: omo bos-inbox search <query>[/red]")
            return 1
        return _cmd_inbox_search(query)
    elif subcmd == "pending":
        source = getattr(args, "source", "seeyon_oa") or "seeyon_oa"
        return _cmd_inbox_pending(source)
    else:
        err.print(f"[red]未知子命令: {subcmd}[/red]")
        return 1


def _cmd_inbox_status() -> int:
    runtime_dir, inbox_dir = _get_inbox_paths()
    table = Table(title="🧠 BOS Inbox 多源私有知识神经网运行状态", show_header=True)
    table.add_column("数据来源 (Source)", style="cyan")
    table.add_column("存在性 (Exists)", style="green")
    table.add_column("大小 (Bytes)", style="yellow")
    table.add_column("更新时间 (Modified Time)", style="magenta")

    files = [
        ("vector_store.json (嵌入向量库)", runtime_dir / "vector_store.json"),
        ("致远 OA 待办公文 (seeyon_oa)", inbox_dir / "2026-07-31-auto-seeyon-oa-pending.md"),
        ("网易邮箱大师正文 (netease_mailmaster)", inbox_dir / "2026-07-31-auto-netease-mailmaster.md"),
        ("Apple Mail 邮件正文 (apple_mail)", inbox_dir / "2026-07-31-auto-apple-mail.md"),
    ]

    for label, fpath in files:
        if fpath.exists():
            stat = fpath.stat()
            mtime_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime))
            table.add_row(label, "✅ Yes", str(stat.st_size), mtime_str)
        else:
            table.add_row(label, "❌ No", "0", "N/A")

    console.print(table)
    return 0


def _cmd_inbox_search(query: str) -> int:
    runtime_dir, _ = _get_inbox_paths()
    vec_file = runtime_dir / "vector_store.json"
    if not vec_file.exists():
        err.print("[red]vector_store.json 未找到，请先执行定时抓取引擎[/red]")
        return 1

    try:
        data = json.loads(vec_file.read_text(encoding="utf-8"))
        meta_dict = data.get("metadata", {})
        query_lower = query.lower()
        matched = 0

        table = Table(title=f"🔍 神经网查询结果: '{query}'", show_header=True)
        table.add_column("ID", style="dim", width=12)
        table.add_column("来源 (Source)", style="cyan", width=16)
        table.add_column("标题 (Title)", style="yellow")
        table.add_column("摘要 (Snippet)", style="white")

        for item_id, item_meta in meta_dict.items():
            content_snip = str(item_meta.get("content_snippet", ""))
            title = str(item_meta.get("title", ""))
            if query_lower in content_snip.lower() or query_lower in title.lower() or query_lower in item_id.lower():
                table.add_row(
                    item_id[:10],
                    str(item_meta.get("source", "N/A")),
                    title[:40],
                    content_snip[:80] + "..." if len(content_snip) > 80 else content_snip
                )
                matched += 1
                if matched >= 10:
                    break

        console.print(table)
        console.print(f"[green]共寻获 {matched} 条匹配记忆[/green]")
        return 0
    except Exception as exc:
        err.print(f"[red]查询发生解析异常: {exc}[/red]")
        return 1


def _cmd_inbox_pending(source: str) -> int:
    _, inbox_dir = _get_inbox_paths()
    fname_map = {
        "seeyon_oa": "2026-07-31-auto-seeyon-oa-pending.md",
        "netease_mailmaster": "2026-07-31-auto-netease-mailmaster.md",
        "apple_mail": "2026-07-31-auto-apple-mail.md"
    }
    fname = fname_map.get(source, "2026-07-31-auto-seeyon-oa-pending.md")
    fpath = inbox_dir / fname
    if not fpath.exists():
        err.print(f"[red]快照文件不存在: {fpath}[/red]")
        return 1

    content = fpath.read_text(encoding="utf-8")
    console.print(Panel(content[:1500] + "\n...\n[dim](已截断)[/dim]", title=f"📋 [{source}] 最新未决记录预览"))
    return 0
