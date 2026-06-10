"""cockpit.commands.status — status, demo, daily, dashboard, help commands."""

from __future__ import annotations

import argparse
import subprocess
import time
from datetime import datetime
from pathlib import Path

from rich import box
from rich.panel import Panel
from rich.table import Table

from .base import (
    _discover_services,
    _find_cli,
    _fmt_time,
    _get_console,
    _get_data_access,
    _get_err,
    _http_health,
    _panel,
    _research_progress,
    _run_ollama,
    _short,
)


def _render_workbench(cycle: int | None = None, interval: float | None = None) -> None:
    import sqlite3

    c = _get_console()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    title = "[bold cyan]🛠️ 工作台[/bold cyan]"
    if cycle is not None:
        title += f"  [dim]第 {cycle} 次刷新 · 间隔 {interval:.1f}s[/dim]"
    c.print(_panel(f"{title}\n[dim]{ts} · 从这开始今天的工作[/dim]", "cyan"))
    c.print(
        _panel(
            "[bold]⚡ 快速行动[/bold]    "
            "[cyan]research <主题>[/]   "
            "[cyan]import <路径|URL>[/]   "
            "[cyan]daily[/]   "
            "[cyan]demo[/]   "
            "[dim]|[/dim]   "
            "[cyan]contracts validate[/]   "
            "[cyan]profile[/]   "
            "[cyan]dashboard[/]",
            "bright_blue",
        )
    )
    services = _discover_services()
    healthy_count = 0
    dots: list[str] = []
    for name, port, cli_name, url, desc in services:
        cli_ok = True if cli_name is None else bool(_find_cli(cli_name))
        http_ok = _http_health(url, timeout=3.0) if url else False
        if http_ok:
            healthy_count += 1
        color = "green" if http_ok else ("yellow" if cli_ok or not url else "red")
        dot = f"[{color}]●[/]"
        label = f"[dim]{name}[/]"
        dots.append(f"{dot} {label}")
    total_services = len(services)
    health_symbol = (
        "[green]🟢 全部正常[/green]"
        if healthy_count == total_services
        else "[yellow]🟡 部分异常[/yellow]"
        if healthy_count > 0
        else "[red]🔴 全部离线[/red]"
    )
    status_line = f"[bold]系统状态:[/bold] {health_symbol}  ({'  '.join(dots)})"
    db_path = Path.home() / ".workspace" / "data.db"
    active_count = 0
    archived_count = 0
    quarantined_count = 0
    follow_up_count = 0
    if db_path.exists():
        try:
            conn = sqlite3.connect(str(db_path))
            active_count = conn.execute(
                "SELECT COUNT(*) FROM research WHERE quarantined_at IS NULL AND archived_at IS NULL"
            ).fetchone()[0]
            archived_count = conn.execute("SELECT COUNT(*) FROM research WHERE archived_at IS NOT NULL").fetchone()[0]
            quarantined_count = conn.execute(
                "SELECT COUNT(*) FROM research WHERE quarantined_at IS NOT NULL"
            ).fetchone()[0]
            follow_up_count = conn.execute(
                "SELECT COALESCE(SUM(json_array_length(follow_ups)), 0) FROM research WHERE quarantined_at IS NULL AND archived_at IS NULL"
            ).fetchone()[0]
            conn.close()
        except sqlite3.Error:
            pass
    stats_line = (
        f"[bold]研究:[/bold] "
        f"[green]{active_count}[/green] 活跃  "
        f"[dim]{archived_count}[/dim] 归档  "
        f"[dim]{quarantined_count}[/dim] 隔离  "
        f"[bold]追问:[/bold] [cyan]{follow_up_count}[/cyan] 条"
    )
    # 半衰期概览
    hl_active = hl_stale = hl_critical = 0
    for r in _get_data_access().list_research(limit=100):
        hl = _get_data_access().compute_half_life(r["id"])
        d = hl.get("decay", 0)
        if d < 0.25:
            hl_critical += 1
        elif d < 0.5:
            hl_stale += 1
        else:
            hl_active += 1
    hl_line = (
        f"[bold]半衰期:[/bold] [green]{hl_active}[/] 活跃  [yellow]{hl_stale}[/] 需保鲜  [red]{hl_critical}[/] 荒废"
    )
    c.print(_panel(f"{status_line}\n{stats_line}\n{hl_line}", "bright_blue"))
    recent = _get_data_access().list_research(limit=5)
    if recent:
        wb_table = Table(
            title="📋 今日工作台 · 点击即可继续", box=box.ROUNDED, header_style="bold cyan", show_lines=True
        )
        wb_table.add_column("ID", style="cyan", no_wrap=True, width=4)
        wb_table.add_column("主题", style="bold", no_wrap=True, width=28)
        wb_table.add_column("状态", width=10)
        wb_table.add_column("来源", justify="right", width=5)
        wb_table.add_column("追问", justify="right", width=5)
        wb_table.add_column("快速操作", width=38)
        for r in recent:
            rid = r["id"]
            src = str(r.get("source_count", 0))
            fups = str(len(r.get("follow_ups") or []))
            timeline = _get_data_access().get_research_timeline(rid)
            last_active = max((float(item.get("created_at", 0)) for item in timeline), default=float(r["created_at"]))
            days_since = (time.time() - last_active) / 86400
            if r.get("archived_at"):
                status_badge = "[dim]📦 已归档[/dim]"
            elif days_since >= 7:
                status_badge = "[yellow]📦 可归档[/yellow]"
            elif days_since >= 3:
                status_badge = "[yellow]🧊 待保鲜[/yellow]"
            else:
                status_badge = "[green]✅ 活跃[/green]"
            actions = f"[cyan]open {rid}[/]  [cyan]ask {rid}[/]  [cyan]pub {rid}[/]  [cyan]dos {rid}[/]"
            wb_table.add_row(str(rid), r["topic"], status_badge, src, fups, actions)
        c.print(wb_table)
        c.print(
            _panel(
                "[dim]💡 提示:[/dim] [cyan]workspace research --open <ID>[/] 查看详情  ·  "
                "[cyan]workspace research --publish <ID> --style brief[/] 发布报告  ·  "
                "[cyan]workspace research --dossier <ID>[/] 查看关系",
                "dim",
            )
        )
    else:
        c.print(
            _panel(
                "[dim]📭 工作台空空如也 — 开始你的第一个研究：[/dim]\n"
                '[cyan]workspace research "你的主题"[/]  或  [cyan]workspace import <路径|URL>[/]  或  [cyan]workspace demo[/]',
                "yellow",
            )
        )
    recs: list[str] = []
    if active_count == 0:
        recs.append('[cyan]workspace research "你的主题"[/] — 发起第一个研究')
        recs.append("[cyan]workspace import ~/Desktop/note.md[/] — 从材料导入")
        recs.append("[cyan]workspace demo[/] — 快速体验完整旅程")
    elif active_count == 1 and recent:
        latest = recent[0]
        recs.append(f"[cyan]workspace research --open {latest['id']}[/] — 继续'{latest['topic']}'")
        recs.append(f'[cyan]workspace research --ask {latest["id"]} "追问"[/] — 深入挖掘')
        recs.append(f"[cyan]workspace research --publish {latest['id']} --style brief[/] — 发布为报告")
    else:
        recs.append("[cyan]workspace research --list[/] — 浏览所有活跃研究")
        recs.append("[cyan]workspace daily[/] — 今日研究简报")
        recs.append("[cyan]workspace research --audit[/] — 治理审计")
    if healthy_count < total_services:
        recs.append("[yellow]⚠️ 部分服务离线 — 检查系统状态[/yellow]")
    c.print(_panel("[bold]🎯 推荐操作[/bold]\n" + "\n".join(f"  {r}" for r in recs), "cyan"))


def cmd_status(args: argparse.Namespace) -> int:
    output_json = bool(getattr(args, "json", False))
    if output_json:
        import json as _json
        import sqlite3

        services = _discover_services()
        svc_status = []
        for name, port, cli_name, url, desc in services:
            http_ok = _http_health(url, timeout=3.0) if url else False
            cli_ok = True if cli_name is None else bool(_find_cli(cli_name))
            svc_status.append(
                {
                    "name": name,
                    "port": port,
                    "healthy": http_ok,
                    "cli_available": cli_ok,
                    "description": desc,
                }
            )
        db_path = Path.home() / ".workspace" / "data.db"
        stats = {"active": 0, "archived": 0, "quarantined": 0, "follow_ups": 0}
        if db_path.exists():
            try:
                conn = sqlite3.connect(str(db_path))
                stats["active"] = conn.execute(
                    "SELECT COUNT(*) FROM research WHERE quarantined_at IS NULL AND archived_at IS NULL"
                ).fetchone()[0]
                stats["archived"] = conn.execute(
                    "SELECT COUNT(*) FROM research WHERE archived_at IS NOT NULL"
                ).fetchone()[0]
                stats["quarantined"] = conn.execute(
                    "SELECT COUNT(*) FROM research WHERE quarantined_at IS NOT NULL"
                ).fetchone()[0]
                stats["follow_ups"] = conn.execute(
                    "SELECT COALESCE(SUM(json_array_length(follow_ups)), 0) FROM research WHERE quarantined_at IS NULL AND archived_at IS NULL"
                ).fetchone()[0]
                conn.close()
            except sqlite3.Error:
                pass
        recent_research = _get_data_access().list_research(limit=5)
        _get_console().print(
            _json.dumps(
                {
                    "status": "ok",
                    "services": svc_status,
                    "research_stats": stats,
                    "recent_research": recent_research,
                },
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )
        return 0
    watch = bool(getattr(args, "watch", False))
    interval = float(getattr(args, "interval", 5.0))
    if interval <= 0:
        _get_err().print("[red]❌ 刷新间隔必须大于 0 秒[/red]")
        return 1
    if not watch:
        _render_workbench()
        return 0

    # ── 增强版 watch 模式：变化检测 + 增量通知 ──
    _get_console().print(
        _panel(
            f"[bold cyan]实时监控模式[/bold cyan]\n每 {interval:.1f} 秒自动刷新一次，按 Ctrl+C 停止",
            "cyan",
        )
    )
    time.sleep(0.1)
    cycle = 1
    prev_hash: str | None = None
    try:
        while True:
            _get_console().clear()
            _render_workbench(cycle=cycle, interval=interval)
            # 计算当前状态 hash，检测变化
            cur_services = _discover_services()
            cur_health = [
                (name, _http_health(url, timeout=3.0) if url else False) for name, _, _, url, _ in cur_services
            ]
            cur_active = len(_get_data_access().list_research(limit=1000))
            cur_hash = str({"s": cur_health, "a": cur_active})
            if prev_hash is not None and cur_hash != prev_hash:
                # 检测到状态变化
                changed_services = [
                    f"[green]🟢 {name}[/]" if healthy else f"[red]🔴 {name}[/]" for name, healthy in cur_health
                ]
                _get_console().print(f"[bold yellow]⚡ 状态变化检测:[/bold yellow] {'  '.join(changed_services)}")
            prev_hash = cur_hash
            _get_console().print("[dim]按 Ctrl+C 停止监控[/dim]")
            time.sleep(interval)
            cycle += 1
    except KeyboardInterrupt:
        _get_console().print("\n[yellow]监控已停止[/yellow]")
        return 0


def cmd_demo(_: argparse.Namespace) -> int:
    c = _get_console()
    c.print()
    c.print(
        _panel(
            "[bold cyan]🎮 Workspace 快速演示[/bold cyan]\n"
            "[dim]带你体验研究对象如何形成、如何继续、如何发布、如何复盘。[/dim]",
            "cyan",
        )
    )
    c.print()

    # ── 尝试真实研究执行 ─────────────────────────────────────────────
    topic = "transformer architecture overview"
    output: str = ""
    demo_mode = True
    _research_progress("正在通过 ollama 生成真实研究内容")
    ollama_out = _run_ollama("请用中文简要介绍 Transformer 架构的核心创新和主要变体，100-200字")
    if ollama_out:
        output = ollama_out
        demo_mode = False

    if not output:
        # 回退到演示文本
        output = (
            f"# 演示研究\n\n关于 **{topic}** 的基础分析。\n\n"
            "Transformer 的核心是自注意力机制（self-attention），它允许模型在处理序列时关注所有位置的信息。\n\n"
            "关键变体：BERT（编码器）、GPT（解码器）、T5（编码器-解码器）。"
        )

    # ── Step 1: 形成研究对象 ─────────────────────────────────────────
    c.print(
        Panel(
            "[bold]Step 1 / 4 — 形成研究对象[/bold]\n\n"
            "一切从导入或发起研究开始。内容进入系统后，立刻变成一个"
            "[bold]可持续使用的研究对象[/bold]。",
            title="📥 导入外部材料",
            border_style="cyan",
            box=box.ROUNDED,
        )
    )
    _research_progress("正在导入研究素材")
    research_id = _get_data_access().save_research(
        topic=topic, summary=_short(output, 200), full_text=output, source_count=1
    )
    source_label = "ollama（真实）" if not demo_mode else "演示文本"
    c.print(
        _panel(
            f"[bold green]✅ 已导入研究对象 #{research_id}[/bold green]\n"
            f"主题: {topic}\n"
            f"来源: {source_label}\n"
            f"状态: [bold]活跃[/bold]（可继续追问、可发布、可治理）",
            "green",
        )
    )
    c.print()
    c.print(
        Panel(
            "[bold]Step 2 / 4 — 继续追问[/bold]\n\n"
            "已有研究不是终点。你可以基于它继续追问，或在系统里打标签以便后续归类。\n"
            "所有结果都会追加到原研究记录上，不会丢失上下文。",
            title="💬 继续研究",
            border_style="cyan",
            box=box.ROUNDED,
        )
    )
    _research_progress("正在追问")
    demo_question = "为什么 Transformer 能取代 RNN？"

    # 尝试真实追问
    demo_answer: str = ""
    demo_ask_degraded = True
    if not demo_mode:
        ollama_out = _run_ollama(
            f"基于以下研究主题回答问题（用中文简洁回答，50-100字）:\n\n研究: {topic}\n问题: {demo_question}"
        )
        if ollama_out:
            demo_answer = ollama_out
            demo_ask_degraded = False

    if not demo_answer:
        demo_answer = (
            f"[降级回复] 基于研究 **{topic}** 对问题 **{demo_question}** 的简要分析。\n\n"
            "Transformer 通过自注意力机制实现了 O(1) 路径长度的序列建模，解决了 RNN 梯度消失和无法并行的问题。\n\n"
            "---\n⚠️ *此为演示回答。在实际使用中，此结果将由研究引擎生成。*"
        )

    _get_data_access().add_follow_up(research_id, demo_question, demo_answer)
    c.print(_panel(f"[bold cyan]💬 追问[/bold cyan]\n{demo_question}\n[dim]基于: {topic}[/dim]", "cyan"))
    ask_label = "（真实）" if not demo_ask_degraded else "（演示文本）"
    c.print(_panel(f"{demo_answer}", "yellow", title=f"💬 追问回答{ask_label}"))
    c.print()
    c.print(
        Panel(
            "[bold]Step 3 / 4 — 发布为产物[/bold]\n\n"
            "研究对象可以发布为正式报告，产物落到桌面上的专用目录。\n"
            "每次发布都会被记录到对象的时间线和档案中。",
            title="📤 发布研究",
            border_style="cyan",
            box=box.ROUNDED,
        )
    )
    _research_progress("正在发布")
    publish_dir = Path.home() / "Desktop" / "workspace-published"
    publish_dir.mkdir(parents=True, exist_ok=True)
    style = "brief"
    publish_path = publish_dir / f"demo-{topic.replace(' ', '-')[:40]}.md"
    publish_path.write_text(f"# {topic}\n\n{output}\n\n---\n追问: {demo_question}\n回答: {demo_answer}\n")
    _get_data_access().save_published_report(research_id, style, str(publish_path))
    c.print(_panel(f"[bold green]✅ 已发布为 {style} 报告[/bold green]\n{publish_path}", "green"))
    c.print()
    c.print(
        Panel(
            "[bold]Step 4 / 4 — 复盘研究对象[/bold]\n\n"
            "研究对象不是一次性的。系统会记录它完整的生命周期：\n"
            "· 从哪来（来源）\n"
            "· 继续过什么（追问）\n"
            "· 发布过什么（产物）\n"
            "· 当前状态（活跃/已归档）\n\n"
            "这一切都可以通过 [bold]dossier[/bold] 和 [bold]timeline[/bold] 回顾。",
            title="📋 复盘回顾",
            border_style="cyan",
            box=box.ROUNDED,
        )
    )
    _research_progress("正在生成研究对象档案")
    dossier = _get_data_access().get_research_dossier(research_id)
    if dossier:
        dv = dossier.get("record", {})
        dp = dossier.get("parents", [])
        dc = dossier.get("children", [])
        dg = dossier.get("publications", [])
        research_obj = _get_data_access().get_research(research_id)
        follow_up_count = len(research_obj.get("follow_ups", [])) if research_obj else 0
        summary_lines = [
            f"ID: {dv.get('id')}",
            f"主题: {dv.get('topic')}",
            f"状态: {'🟢 活跃' if not dv.get('archived_at') else '🔴 已归档'}",
            f"来源数: {dv.get('source_count', 0)}",
            f"追问: {follow_up_count} 条",
        ]
        if dp:
            summary_lines.append(f"上游研究: {len(dp)} 条")
        if dc:
            summary_lines.append(f"派生研究: {len(dc)} 条")
        if dg:
            summary_lines.append(f"发布产物: {len(dg)} 次")
        c.print(_panel("\n".join(summary_lines), "green", title="📦 研究对象摘要"))
    _research_progress("正在生成时间线")
    tl = _get_data_access().get_research_timeline(research_id)
    if tl:
        tl_table = Table(title="⏱ 研究时间线", box=box.ROUNDED, header_style="bold cyan")
        tl_table.add_column("事件", style="bold", no_wrap=True)
        tl_table.add_column("时间", style="dim", no_wrap=True)
        tl_table.add_column("说明", style="dim")
        for item in tl[:6]:
            tl_table.add_row(
                item.get("event_type", "—"), _fmt_time(item.get("created_at", 0)), item.get("description", "")[:60]
            )
        c.print(tl_table)
    c.print()
    c.print(
        _panel(
            "[bold green]🎉 演示完成[/bold green]\n\n"
            f"[bold]你刚刚体验了一条完整的研究闭环：[/bold]\n"
            f"  {research_id} 条研究对象 → {demo_question[:20]}... → 发布为 {style} → 可复盘\n\n"
            f"[bold]这就是 workspace 的产品逻辑：[/bold]\n"
            "  输入 → 研究对象 → 持续追问 → 发布 → 复盘\n\n"
            "[bold cyan]现在就开始用：[/bold cyan]\n"
            '  · `workspace research "你的研究主题"` — 发起全新研究\n'
            "  · `workspace import 文章.md` — 从现有材料导入\n"
            "  · `workspace dashboard` — 在 Web 中浏览研究\n"
            "  · `workspace daily` — 每日研究简报",
            "green",
        )
    )
    c.print("[dim]演示完成。试试以下命令继续探索：[/dim]")
    c.print("[dim]  · [cyan]workspace status[/] — 打开工作台[/dim]")
    c.print("[dim]  · [cyan]workspace daily[/] — 今日站会[/dim]")
    c.print('[dim]  · [cyan]workspace research "你的主题"[/] — 发起真研究[/dim]')
    return 0


def cmd_help(_: argparse.Namespace) -> int:
    _get_console().print(
        _panel(
            "[bold cyan]🧭 Workspace 产品地图[/bold cyan]\n\n"
            "[bold]📖 核心概念[/bold]\n"
            "  workspace 是一个研究对象管理系统。你输入内容 → 形成研究对象 → "
            "持续追问 → 发布为产物 → 复盘回顾。一切都有记忆，一切都可追溯。\n\n"
            "[bold]🚀 快速开始[/bold]\n"
            "  [cyan]workspace demo[/]           — 5 分钟体验完整闭环\n"
            "  [cyan]workspace status[/]          — 打开工作台\n"
            '  [cyan]workspace research "主题"[/] — 发起你的第一个研究\n\n'
            "[bold]📋 所有命令[/bold]\n"
            "  [cyan]research[/]      深度研究（发起/查看/追问/发布/归档）\n"
            "  [cyan]import[/]        从外部导入（文件/URL）\n"
            "  [cyan]status[/]        工作台仪表盘\n"
            "  [cyan]daily[/]         今日站会简报\n"
            "  [cyan]demo[/]          快速体验旅程\n"
            "  [cyan]quickstart[/]    新用户快速上手向导\n"
            "  [cyan]init[/]          初始化向导（同 quickstart）\n"
            "  [cyan]contracts[/]     契约验证（validate/list/export-research）\n"
            "  [cyan]governance[/]    架构治理（calibrate/rechain/evolve）\n"
            "  [cyan]dashboard[/]     Web 仪表盘\n"
            "  [cyan]help[/]          查看产品地图\n\n"
            "[bold]🔄 完整用户旅程[/bold]\n"
            "  import → research → open → ask → publish → dossier → timeline → daily\n\n"
            "[bold]💡 最佳实践[/bold]\n"
            "  · 新用户：[cyan]workspace demo[/] 体验全流程\n"
            "  · 日常：[cyan]workspace daily[/] 查看今日研究\n"
            "  · 深入：[cyan]workspace research --dossier <ID>[/] 看关系网络\n"
            "  · 发布：[cyan]workspace research --publish <ID> --style brief[/]\n"
            "  · 治理：[cyan]workspace governance calibrate[/] 系统健康评分",
            "cyan",
        )
    )
    return 0


def cmd_daily(args: argparse.Namespace) -> int:
    output_json = bool(getattr(args, "json", False))
    c = _get_console()
    cutoff = time.time() - args.days * 86400
    results = _get_data_access().list_research(limit=50)
    recent = [r for r in results if r["created_at"] >= cutoff]
    date_str = datetime.now().strftime("%Y-%m-%d")
    if output_json:
        import json as _json

        items = []
        for r in recent:
            dossier = _get_data_access().get_research_dossier(r["id"])
            publications = dossier.get("publications", []) if dossier else []
            hl = _get_data_access().compute_half_life(r["id"])
            items.append(
                {
                    "id": r["id"],
                    "topic": r["topic"],
                    "created_at": r["created_at"],
                    "archived": r.get("archived_at") is not None,
                    "follow_up_count": len(r.get("follow_ups") or []),
                    "published_count": len(publications),
                    "decay": hl.get("decay", 0),
                }
            )
        c.print(
            _json.dumps(
                {
                    "date": date_str,
                    "days": args.days,
                    "total": len(recent),
                    "items": items,
                },
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )
        return 0
    if not recent:
        c.print(
            _panel(
                f"[bold cyan]📅 {date_str} 今日站会[/]\n\n"
                f"[dim]📭 过去 {args.days} 天没有新研究。[/dim]\n\n"
                "[bold]🎯 现在可以：[/bold]\n"
                '  [cyan]workspace research "你的主题"[/] — 发起新研究\n'
                "  [cyan]workspace import ~/Desktop/note.md[/] — 导入材料\n"
                "  [cyan]workspace demo[/] — 快速体验",
                "yellow",
            )
        )
        return 0
    stats = {"total": len(recent), "follow_ups": 0, "published": 0}
    # 追问数量从已获取的 research 记录中计算
    stats["follow_ups"] = sum(len(r.get("follow_ups") or []) for r in recent)
    # 发布数量通过 IDataAccess 查询
    for r in recent:
        dossier = _get_data_access().get_research_dossier(r["id"])
        if dossier:
            stats["published"] += len(dossier.get("publications", []))
    now = time.time()
    c.print(
        _panel(
            f"[bold cyan]📅 {date_str} 今日站会[/bold cyan]  [dim]过去 {args.days} 天 · {stats['total']} 项研究[/dim]",
            "cyan",
        )
    )
    active_count = sum(1 for r in recent if r.get("archived_at") is None)
    no_fup_count = sum(1 for r in recent if r.get("archived_at") is None and not r.get("follow_ups"))
    stale_count = sum(1 for r in recent if r.get("archived_at") is None and (now - r["created_at"]) > 72 * 3600)
    fup_mark = f"[yellow]{no_fup_count} 待追问[/yellow]" if no_fup_count else "[green]0 待追问[/green]"
    stale_mark = f"[red]{stale_count} 待保鲜[/red]" if stale_count else "[dim]0 待保鲜[/dim]"
    c.print(
        _panel(
            f"[bold]研究[/bold]: [green]{stats['total']}[/green] 项  "
            f"[bold]追问[/bold]: [cyan]{stats['follow_ups']}[/cyan] 条  "
            f"[bold]发布[/bold]: [green]{stats['published']}[/green] 篇  "
            f"[bold]活跃[/bold]: [green]{active_count}[/green]  "
            f"[bold]归档[/bold]: [dim]{sum(1 for r in recent if r.get('archived_at') is not None)}[/dim]  "
            f"{fup_mark}  {stale_mark}",
            "bright_blue",
        )
    )
    # ── 系统健康 ──
    try:
        import subprocess

        health_out = subprocess.run(["agora", "health"], capture_output=True, text=True, timeout=10).stdout
        for line in health_out.splitlines():
            s = line.strip()
            if (
                s.startswith("Healthy:")
                or s.startswith("CPU:")
                or s.startswith("Memory:")
                or s.startswith("Disk:")
                or s.startswith("Load")
            ):
                s = s.replace("System Health:", "").strip()
                c.print(f"[dim]💻 系统: {s}[/dim]")
                break
    except Exception:
        pass
    table = Table(title="📋 行动清单", box=box.ROUNDED, header_style="bold cyan", show_lines=True)
    table.add_column("ID", style="cyan", no_wrap=True, width=4)
    table.add_column("主题", style="bold", width=26)
    table.add_column("状态", width=8)
    table.add_column("衰变", width=8)
    table.add_column("追问", width=5)
    table.add_column("操作", width=40)
    for r in recent:
        rid = r["id"]
        age_hours = (now - r["created_at"]) / 3600
        if age_hours < 24:
            age_mark = "[green]🆕 新[/green]"
        elif age_hours < 72:
            age_mark = "[yellow]🔥 热[/yellow]"
        else:
            age_mark = "[dim]🧊 冷[/dim]"
        if r.get("archived_at") is None and age_hours >= 72:
            timeline = _get_data_access().get_research_timeline(rid)
            last_active = max((float(item.get("created_at", 0)) for item in timeline), default=float(r["created_at"]))
            days_since_active = (now - last_active) / 86400
            if days_since_active >= 3:
                age_mark = "[yellow]🧊 待保鲜[/yellow]"
        archived = r.get("archived_at") is not None
        status = "[dim]已归档[/dim]" if archived else age_mark
        # 半衰期衰减值
        hl = _get_data_access().compute_half_life(rid)
        decay = hl.get("decay", 0)
        if archived:
            decay_mark = "[dim]-[/dim]"
        elif decay >= 0.75:
            decay_mark = f"[green]{decay:.2f}[/]"
        elif decay >= 0.5:
            decay_mark = f"[yellow]{decay:.2f}[/]"
        elif decay >= 0.25:
            decay_mark = f"[bright_yellow]{decay:.2f}[/]"
        else:
            decay_mark = f"[red]{decay:.2f}[/]"
        fup_count = len(r.get("follow_ups") or [])
        actions = f"[cyan]open {rid}[/]  [cyan]ask {rid}[/]  [cyan]pub {rid}[/]"
        table.add_row(str(rid), r["topic"], status, decay_mark, str(fup_count), actions)
    c.print(table)
    unpub = [r for r in recent if r.get("archived_at") is None]
    no_fup = [r for r in unpub if not r.get("follow_ups")]
    recs = []
    if no_fup:
        recs.append(f'[cyan]workspace research --ask {no_fup[0]["id"]} "追问"[/] — 深入尚未追问的研究')
    if unpub:
        recs.append(f"[cyan]workspace research --publish {unpub[0]['id']} --style brief[/] — 发布重点研究")
        recs.append(f"[cyan]workspace research --dossier {unpub[0]['id']}[/] — 查看研究关系网")
    recs.append("[cyan]workspace research --audit[/] — 检查待治理对象")
    recs.append(f"[cyan]workspace research --open {recent[0]['id']}[/] — 继续最近研究")
    c.print(_panel("[bold]🎯 优先级推荐[/bold]\n" + "\n".join(f"  {r}" for r in recs), "cyan"))
    return 0


def cmd_dashboard(args: argparse.Namespace) -> int:
    import webbrowser

    c = _get_console()
    port = "8765"
    _cockpit_root = Path(__file__).resolve().parent.parent
    agora_dir = str(_cockpit_root / "agora")
    venv_python = _cockpit_root / "agora/.venv/bin/python"
    uvicorn_cli = _find_cli("uvicorn")

    def _print_dashboard_fixes() -> None:
        c.print("[yellow]试试:[/]")
        c.print("  [cyan]workspace status[/]  — 检查服务状态")
        c.print("  [cyan]workspace demo[/]    — 在 CLI 中体验")
        c.print(
            "  [cyan]cd agora && .venv/bin/python -m uvicorn agora.web.app:app --host 127.0.0.1 --port 8765[/]  — 手动启动"
        )

    if not uvicorn_cli and not venv_python.exists():
        c.print("[yellow]uvicorn 未安装。试试:[/]")
        c.print("  [cyan]cd agora && pip install uvicorn fastapi[/]")
        _print_dashboard_fixes()
        return 1
    if venv_python.exists():
        cmd = [str(venv_python), "-m", "uvicorn", "agora.web.app:app", "--host", "127.0.0.1", "--port", port]
    else:
        assert uvicorn_cli is not None
        cmd = [uvicorn_cli, "agora.web.app:app", "--host", "127.0.0.1", "--port", port]
    try:
        proc = subprocess.Popen(cmd, cwd=agora_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2)
        url = f"http://localhost:{port}"
        try:
            from urllib import request as urlrequest

            r = urlrequest.urlopen(url, timeout=3)  # noqa: S310
            if getattr(r, "status", 200) != 200:
                c.print(f"[red]Dashboard returned HTTP {r.status}[/]")
                _print_dashboard_fixes()
                proc.terminate()
                return 1
        except Exception:
            c.print(f"[red]无法连接到 Dashboard :{port}[/]")
            _print_dashboard_fixes()
            proc.terminate()
            return 1
        webbrowser.open(url)
        c.print(f"[green]✅ Dashboard 已启动: [cyan]{url}[/][/]")
        c.print("[dim]按 Ctrl+C 停止服务[/]")
        try:
            proc.wait()
        except KeyboardInterrupt:
            proc.terminate()
            c.print("\n[yellow]Dashboard 已停止[/]")
    except FileNotFoundError:
        c.print("[red]❌ 无法启动 Dashboard — uvicorn 未安装[/]")
        c.print("[yellow]试试:[/]")
        c.print("  [cyan]cd agora && pip install uvicorn fastapi[/]")
        _print_dashboard_fixes()
        return 1
    return 0
