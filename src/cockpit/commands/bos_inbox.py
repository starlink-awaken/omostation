"""BOS Inbox 多源私有知识神经网 Cockpit CLI 命令。"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from rich.panel import Panel
from rich.table import Table

from cockpit.cli import console, err


def _get_inbox_paths() -> tuple[Path, Path]:
    doc_root = Path(os.environ.get("BOS_DOCUMENTS_ROOT", str(Path.home() / "Documents")))
    return doc_root / "@公共" / "_runtime", doc_root / "_inbox"


def cmd_bos_inbox(args: Any) -> int:
    """处理 omo bos-inbox [status|search|pending] 子命令。"""
    subcmd = getattr(args, "inbox_cmd", "status") or "status"
    output_format = getattr(args, "global_output", "tty") or "tty"

    if subcmd == "status":
        return _cmd_inbox_status(output_format=output_format)
    elif subcmd == "search":
        query = getattr(args, "query", "") or ""
        if not query:
            err.print("[red]请提供搜索关键词: omo bos-inbox search <query>[/red]")
            return 1
        return _cmd_inbox_search(query)
    elif subcmd == "pending":
        source = getattr(args, "source", "seeyon_oa") or "seeyon_oa"
        return _cmd_inbox_pending(source)
    elif subcmd == "watch":
        return _cmd_inbox_watch()
    elif subcmd == "archive":
        filename = getattr(args, "filename", "") or ""
        reason = getattr(args, "reason", "resolved") or "resolved"
        return _cmd_inbox_archive(filename, reason)
    else:
        err.print(f"[red]未知子命令: {subcmd}[/red]")
        return 1


def _cmd_inbox_status(output_format: str = "tty") -> int:
    runtime_dir, inbox_dir = _get_inbox_paths()
    files = [
        ("vector_store.json (嵌入向量库)", runtime_dir / "vector_store.json"),
        ("致远 OA 待办公文 (seeyon_oa)", inbox_dir / "2026-07-31-auto-seeyon-oa-pending.md"),
        ("网易邮箱大师正文 (netease_mailmaster)", inbox_dir / "2026-07-31-auto-netease-mailmaster.md"),
        ("Apple Mail 邮件正文 (apple_mail)", inbox_dir / "2026-07-31-auto-apple-mail.md"),
    ]
    data = []
    for label, fpath in files:
        if fpath.exists():
            stat = fpath.stat()
            mtime_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime))
            data.append({"source": label, "exists": "✅ Yes", "size": str(stat.st_size), "mtime": mtime_str})
        else:
            data.append({"source": label, "exists": "❌ No", "size": "0", "mtime": "N/A"})

    from cockpit.commands.base import render_command_result

    render_command_result(
        title="🧠 BOS Inbox 多源私有知识神经网运行状态",
        data=data,
        output_format=output_format,
        columns=["source", "exists", "size", "mtime"],
    )
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
                    content_snip[:80] + "..." if len(content_snip) > 80 else content_snip,
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
        "apple_mail": "2026-07-31-auto-apple-mail.md",
    }
    fname = fname_map.get(source, "2026-07-31-auto-seeyon-oa-pending.md")
    fpath = inbox_dir / fname
    if not fpath.exists():
        err.print(f"[red]快照文件不存在: {fpath}[/red]")
        return 1

    content = fpath.read_text(encoding="utf-8")
    console.print(Panel(content[:1500] + "\n...\n[dim](已截断)[/dim]", title=f"📋 [{source}] 最新未决记录预览"))
    return 0


def _cmd_inbox_watch() -> int:
    """监听 BOS Inbox 紧急待办事宜及核心提醒 (Event-Driven Watcher v2.0)。"""
    _, inbox_dir = _get_inbox_paths()
    table = Table(
        title="⚡️ BOS Inbox 紧急待办与事件侦测 (Event-Driven Watch v2.0)",
        show_header=True,
    )
    table.add_column("文件名 (File)", style="cyan", width=34)
    table.add_column("优先级标识 (Priority)", style="red", width=16)
    table.add_column("触发词 (Reasons)", style="yellow", width=16)
    table.add_column("最新更新时间 (Modified)", style="magenta", width=20)
    table.add_column("内容预览 (Snippet)", style="white")

    matched = 0
    urgent_keywords = [
        "priority: HIGH",
        "priority: URGENT",
        "[URGENT]",
        "紧急",
        "急件",
        "加急",
        "特急",
        "催办",
    ]
    if inbox_dir.exists():
        for file_path in inbox_dir.glob("*.md"):
            try:
                content = file_path.read_text(encoding="utf-8")
                reasons = [k for k in urgent_keywords if k in content]
                if reasons:
                    mtime_str = time.strftime(
                        "%Y-%m-%d %H:%M:%S",
                        time.localtime(file_path.stat().st_mtime),
                    )
                    snip = content[:80].replace("\n", " ")
                    priority_str = (
                        "🔴 URGENT"
                        if any(u in reasons for u in ["priority: URGENT", "[URGENT]", "特急"])
                        else "🟠 HIGH"
                    )
                    table.add_row(
                        file_path.name,
                        priority_str,
                        ",".join(reasons[:2]),
                        mtime_str,
                        snip,
                    )
                    matched += 1
            except Exception:  # noqa: S112
                continue

    if matched == 0:
        console.print("[green]✅ 当前无紧急(URGENT/HIGH)工单或待办项。[/green]")
    else:
        console.print(table)
        console.print(
            f"[bold red]⚠️ 发现 {matched} 份高优先级工单，请立即调度处理！(可执行 omo bos-inbox archive 归档)[/bold red]"
        )
    return 0


def _cmd_inbox_archive(filename: str, reason: str) -> int:
    """按文件名或 all 批量归档 Inbox 待办事宜至冷归档区。"""
    _, inbox_dir = _get_inbox_paths()
    if not filename:
        err.print("[red]请提供待归档文件名: omo bos-inbox archive <filename|all>[/red]")
        return 1

    doc_root = Path(os.environ.get("BOS_DOCUMENTS_ROOT", str(Path.home() / "Documents")))
    archive_dir = doc_root / "_knowledge" / "archive" / "inbox"
    archive_dir.mkdir(parents=True, exist_ok=True)

    target_files = []
    if filename == "all":
        if inbox_dir.exists():
            target_files = list(inbox_dir.glob("*.md"))
    else:
        f = inbox_dir / filename
        if f.exists():
            target_files = [f]

    if not target_files:
        err.print(f"[yellow]未在 Inbox 中找到匹配的单据: {filename}[/yellow]")
        return 1

    archived_count = 0
    for src in target_files:
        try:
            content = src.read_text(encoding="utf-8")
            meta = (
                f"\n\n---\n"
                f"archive_ts: {time.strftime('%Y-%m-%dT%H:%M:%S+08:00', time.localtime())}\n"
                f"archive_reason: {reason}\n"
            )
            dst = archive_dir / src.name
            dst.write_text(content + meta, encoding="utf-8")
            src.unlink()
            archived_count += 1
            console.print(f"[green]✅ 已归档: {src.name} -> {dst}[/green]")
        except Exception as exc:
            err.print(f"[red]归档失败 {src.name}: {exc}[/red]")

    console.print(f"[bold green]成功归档 {archived_count} 份 Inbox 待办文件！[/bold green]")
    return 0
