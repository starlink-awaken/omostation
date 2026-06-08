"""cockpit.commands.research — all research command handlers.

Uses _get_xxx() lazy accessors for monkeypatch compatibility.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from rich import box
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from .base import (
    _compare_focus,
    _find_cli,
    _fmt_time,
    _get_console,
    _get_data_access,
    _get_err,
    _looks_like_research_failure,
    _notify_research_complete,
    _panel,
    _print_research_help_suggestions,
    _render_markdown_block,
    _render_publish_content,
    _research_progress,
    _run_ollama,
    _run_ollama_stream,
    _short,
    _topic_text,
)


def _audit_research_record(record: dict[str, Any]) -> str | None:
    summary = str(record.get("summary") or "").strip()
    full_text = str(record.get("full_text") or "").strip()
    combined = f"{summary}\n{full_text}".lower()
    if not summary and not full_text:
        return "empty content"
    if "traceback" in combined or "modulenotfounderror" in combined or "importerror" in combined:
        return "traceback / import error"
    if not full_text:
        return "empty content"
    return None


def _heat_char(val: int, max_val: int) -> str:
    if val == 0:
        return "[dim]·[/]"
    ratio = val / max(1, max_val)
    if ratio > 0.5:
        return f"[red]{val}[/]"
    elif ratio > 0.2:
        return f"[yellow]{val}[/]"
    else:
        return f"[green]{val}[/]"


def cmd_research(args: argparse.Namespace) -> int:
    topic = _topic_text(args.topic)
    if not topic:
        _get_console().print("\n[red]Error: 请指定研究主题[/]")
        _print_research_help_suggestions()
        return 1
    _get_console().print(_panel(f"[bold cyan]🔍 研究任务[/bold cyan]\n{topic}", "cyan"))
    start = time.time()

    # 三级降级：minerva → ollama → 缓存回答
    output: str = ""
    source: str = ""
    minerva = _find_cli("minerva")
    if minerva:
        try:
            with Progress(
                SpinnerColumn(style="cyan"),
                TextColumn("[bold]{task.description}[/bold]"),
                BarColumn(bar_width=None),
                TimeElapsedColumn(),
                console=_get_console(),
                transient=False,
            ) as progress:
                task = progress.add_task(f"[cyan]minerva 引擎研究中 · {_short(topic, 40)}", total=None)
                result = subprocess.run(
                    [minerva, "research", topic],
                    capture_output=True,
                    text=True,
                    timeout=os.environ.get("MINERVA_TIMEOUT", 180),
                )
                progress.update(task, description="minerva 引擎研究完成")
            raw = (result.stdout or result.stderr or "").strip()
            if result.returncode == 0 and raw and not _looks_like_research_failure(raw):
                output = raw
                source = "minerva"
            else:
                _get_err().print(f"[yellow]⚠️ minerva rc={result.returncode} — 降级 ollama[/yellow]")
        except subprocess.TimeoutExpired as e:
            _get_err().print(f"[red]⚠️ minerva 超时 ({e.timeout}s) — 降级 ollama[/red]")
        except FileNotFoundError:
            _get_err().print("[yellow]⚠️ minerva 未安装 — 降级 ollama[/yellow]")
        except Exception as e:
            _get_err().print(f"[yellow]⚠️ minerva 异常 ({type(e).__name__}) — 降级 ollama[/yellow]")

    if not output:
        use_stream = getattr(args, "stream", False)
        ollama_timeout = int(os.environ.get("OLLAMA_TIMEOUT", "120"))
        if use_stream:
            _get_console().print(f"[yellow]⏳ ollama 流式生成中 ({_short(topic, 30)})...[/]")
            ollama_out = _run_ollama_stream(
                f"请对以下主题进行简要研究分析，用中文输出:\n\n{topic}",
                timeout=ollama_timeout,
            )
        else:
            with Progress(
                SpinnerColumn(style="yellow"),
                TextColumn("[bold]{task.description}[/bold]"),
                BarColumn(bar_width=None),
                TimeElapsedColumn(),
                console=_get_console(),
                transient=False,
            ) as progress:
                progress.add_task(f"[yellow]ollama 降级研究中 · {_short(topic, 40)}", total=None)
                ollama_out = _run_ollama(f"请对以下主题进行简要研究分析，用中文输出:\n\n{topic}", timeout=ollama_timeout)
        if ollama_out:
            output = f"[ollama 回复] {ollama_out}\n\n---\n⚠️ **注意：此为 ollama 降级回复，非 minerva 研究引擎结果。**"
            source = "ollama"

    if not output:
        _get_err().print("[yellow]⚠️ 研究引擎均不可用，生成本地回答...[/yellow]")
        output = (
            f"关于 **{topic}** 的简要分析。\n\n"
            f"由于 minerva 研究引擎和 ollama 均不可用，当前无法生成真实研究结果。\n"
            f"请确认研究环境配置后重试。\n\n"
            f"---\n⚠️ **注意：此为降级回答，未调用真实研究引擎。**"
        )
        source = "cache"

    elapsed = time.time() - start
    research_id = _get_data_access().save_research(
        topic=topic,
        summary=_short(output, 200),
        full_text=output,
        source_count=len(source) and 1 or 0,  # 1 for minerva/ollama, 0 for cache fallback
    )
    _notify_research_complete(topic)
    source_label = {"minerva": "minerva 引擎", "ollama": "ollama（降级）", "cache": "本地缓存（降级）"}.get(
        source, source
    )
    style = "green" if source == "minerva" else "yellow"
    # 清洗 LLM 思考过程后显示完整内容
    cleaned = output
    if source != "minerva":
        from .base import _strip_thinking

        cleaned = _strip_thinking(output)
    # 构建摘要元信息面板
    meta_lines = (
        f"[bold]主题[/bold]: {topic}\n"
        f"[bold]ID[/bold]: {research_id}  [bold]来源[/bold]: {source_label}  [bold]耗时[/bold]: {elapsed:.1f}s"
    )
    _get_console().print(_panel(meta_lines, style=style, title="✅ 研究完成"))
    # 将完整内容渲染为 Rich Markdown（限制过长内容以保持可读性）
    display = (
        cleaned
        if len(cleaned) < 6000
        else f"{cleaned[:5000]}\n\n---\n*内容过长，已截断前 5000 字符。使用 `workspace research --open {research_id}` 查看完整内容。*"
    )
    _render_markdown_block(f"研究内容 · {_short(topic, 60)}", display, style=style)
    _get_console().print(
        _panel(
            "[bold]下一步[/bold]\n"
            f"- `workspace research --open {research_id}`  — 查看完整研究\n"
            f'- `workspace research --ask {research_id} "继续提问"`  — 深入追问\n'
            f"- `workspace research --publish {research_id} --style brief`  — 发布为报告\n"
            f"- `workspace research --dossier {research_id}`  — 查看关系网络",
            "cyan",
        )
    )
    return 0


def cmd_research_search(args: argparse.Namespace) -> int:
    import sqlite3

    keyword = (args.search or "").strip()
    if not keyword:
        _get_err().print("[red]❌ 请指定搜索关键词[/red]")
        return 1
    try:
        results = _get_data_access().search_research(keyword, limit=args.limit)
    except sqlite3.OperationalError:
        results = []
    if not results:
        _get_console().print(f'\n[yellow]没有找到匹配 "{keyword}" 的研究。[/]')
        _get_console().print("[dim]试试:[/]")
        _get_console().print('  [cyan]workspace research --search "关键词"[/]  — 换个关键词')
        _get_console().print("  [cyan]workspace research --list[/]           — 浏览所有研究")
        _get_console().print()
        return 0
    table = Table(title=f"研究全文搜索 · {keyword}", box=box.ROUNDED, header_style="bold cyan", show_lines=False)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("主题", style="bold")
    table.add_column("创建时间", style="dim", no_wrap=True)
    table.add_column("来源", style="green", justify="right", no_wrap=True)
    table.add_column("命中片段", style="yellow")
    for r in results:
        table.add_row(
            str(r["id"]),
            r["topic"],
            _fmt_time(r["created_at"]),
            str(r["source_count"] or 0),
            r.get("snippet") or _short(r.get("summary"), 100),
        )
    _get_console().print(table)
    return 0


def cmd_research_list(args: argparse.Namespace) -> int:
    status = getattr(args, "status", "all")
    include_archived = status in ("archived", "all")
    results = _get_data_access().list_research(limit=args.limit, include_archived=include_archived)
    if status == "active":
        results = [r for r in results if r.get("archived_at") is None]
    elif status == "archived":
        results = [r for r in results if r.get("archived_at") is not None]
    if not results:
        if status == "active":
            msg = "[dim]没有活跃的研究记录。试试：[cyan]workspace research --status all[/cyan] 查看全部，或 [cyan]workspace research <主题>[/cyan] 发起新的研究。[/dim]"
        elif status == "archived":
            msg = "[dim]没有已归档的研究记录。[/dim]"
        else:
            msg = "[dim]还没有研究记录。试试：workspace research <主题>[/dim]"
        _get_console().print(_panel(msg, "yellow"))
        return 0
    output_json = getattr(args, "json", False)
    if output_json:
        import json as _json

        _get_console().print(_json.dumps(results, ensure_ascii=False, indent=2, default=str))
        return 0
    table = Table(title="研究历史", box=box.ROUNDED, header_style="bold cyan", show_lines=False)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("主题", style="bold")
    table.add_column("创建时间", style="dim", no_wrap=True)
    table.add_column("来源", style="green", justify="right", no_wrap=True)
    table.add_column("追问", style="yellow", justify="right", no_wrap=True)
    table.add_column("Agent", style="magenta", no_wrap=True)
    table.add_column("摘要", style="dim")
    for r in results:
        full = _get_data_access().get_research(r["id"])
        follow_ups = len(full.get("follow_ups", [])) if full else 0
        agent = r.get("agent", "") or ""
        table.add_row(
            str(r["id"]),
            r["topic"],
            _fmt_time(r["created_at"]),
            str(r["source_count"] or 0),
            str(follow_ups),
            agent,
            _short(r["summary"], 80),
        )
    _get_console().print(table)
    _print_research_help_suggestions()
    return 0


def cmd_research_open(args: argparse.Namespace) -> int:
    result = _get_data_access().get_research(args.research_id)
    if not result:
        recent = _get_data_access().list_research(limit=3)
        msg = f"[red]Error:[/] 未找到 ID={args.research_id} 的研究记录。"
        if recent:
            ids = "、".join(f"[cyan][{r['id']}]{r['topic']}[/]" for r in recent)
            msg += f"\n[yellow]最近的研究: {ids}[/]"
        _get_console().print(f"\n{msg}\n")
        return 1
    output_json = getattr(args, "json", False)
    if output_json:
        import json as _json

        _get_console().print(_json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 0
    header = (
        f"[bold]{result['topic']}[/bold]\n[dim]{_fmt_time(result['created_at'])} · {result['source_count']} 来源[/dim]"
    )
    _get_console().print(_panel(header, "cyan", title=f"研究 #{result['id']}"))
    _render_markdown_block("全文", result.get("full_text") or "[无全文]", style="green")
    follow_ups = result.get("follow_ups") or []
    if follow_ups:
        follow_table = Table(title="追问", box=box.ROUNDED, header_style="bold yellow")
        follow_table.add_column("时间", style="dim", no_wrap=True)
        follow_table.add_column("问题", style="bold")
        follow_table.add_column("答复", style="green")
        for item in follow_ups:
            follow_table.add_row(_fmt_time(item["timestamp"]), _short(item["question"], 60), _short(item["answer"], 90))
        _get_console().print(follow_table)
    _get_console().print(
        _panel(
            "下一步:\n"
            f'- `workspace research --ask {args.research_id} "继续提问"\n'
            f"- `workspace research --dossier {args.research_id}`\n"
            f"- `workspace research --timeline {args.research_id}`\n"
            f"- `workspace research --publish {args.research_id} --style brief`",
            "cyan",
        )
    )
    return 0


def cmd_research_ask(args: argparse.Namespace) -> int:
    research = _get_data_access().get_research(args.research_id)
    if not research:
        recent = _get_data_access().list_research(limit=3)
        msg = f"[red]Error:[/] 未找到 ID={args.research_id} 的研究记录。"
        if recent:
            ids = "、".join(f"[cyan][{r['id']}]{r['topic']}[/]" for r in recent)
            msg += f"\n[yellow]最近的研究: {ids}[/]"
        _get_console().print(f"\n{msg}\n")
        return 1
    question = _topic_text(args.question)
    _get_console().print(
        _panel(f"[bold cyan]💬 追问[/bold cyan]\n{question}\n[dim]基于: {research['topic']}[/dim]", "cyan")
    )
    answer_quality: str = "degraded"
    answer: str = ""
    minerva = _find_cli("minerva")
    if minerva:
        question_with_context = f"{question} (based on: {research['topic']})"
        with Progress(
            SpinnerColumn(style="cyan"),
            TextColumn("[bold]{task.description}[/bold]"),
            TimeElapsedColumn(),
            console=_get_console(),
            transient=True,
        ) as progress:
            progress.add_task("正在调用 minerva 生成真实追问答复", total=None)
            result = subprocess.run(
                [minerva, "research", question_with_context], capture_output=True, text=True, timeout=120
            )
        raw_answer = (result.stdout or result.stderr or "").strip()
        if result.returncode == 0 and raw_answer and "ModuleNotFoundError" not in raw_answer:
            answer_quality = "real"
            answer = raw_answer
        else:
            answer_quality = "degraded"
            _get_err().print("[yellow]⚠️ minerva 执行失败，尝试 ollama 降级...[/yellow]")
            ollama_out = _run_ollama(
                f"基于以下研究主题回答问题（用中文简洁回答）:\n\n研究: {research['topic']}\n问题: {question}"
            )
            if ollama_out:
                answer = (
                    f"[ollama 回复] {ollama_out}\n\n---\n⚠️ **注意：此为 ollama 降级回复，非 minerva 研究引擎结果。**"
                )
            else:
                answer = (
                    f"[降级回复] 基于研究 **{research['topic']}** 对问题 **{question}** 的简要分析。\n\n"
                    "- 先确认已有事实边界，再扩展推理。\n"
                    "- 把追问结果当作原研究的一个子章节最合适。\n\n"
                    "---\n⚠️ **注意：此为降级回答，未调用真实研究引擎。**\n"
                    "请确认 `minerva` 可用后再试。"
                )
    else:
        answer_quality = "degraded"
        _research_progress("正在关联上下文并生成答复")
        ollama_out = _run_ollama(
            f"基于以下研究主题回答问题（用中文简洁回答）:\n\n研究: {research['topic']}\n问题: {question}"
        )
        if ollama_out:
            answer = f"[ollama 回复] {ollama_out}\n\n---\n⚠️ **注意：此为 ollama 降级回复，非 minerva 研究引擎结果。**"
        else:
            answer = (
                f"[降级回复] 基于研究 **{research['topic']}** 对问题 **{question}** 的简要分析。\n\n"
                "- 先确认已有事实边界，再扩展推理。\n"
                "- 把追问结果当作原研究的一个子章节最合适。\n\n"
                "---\n⚠️ **注意：此为降级回答，未调用真实研究引擎。**\n"
                "请确认 `minerva` 可用后再试。"
            )
    if answer_quality == "degraded":
        source = "ollama" if answer.startswith("[ollama") else "本地缓存"
        _get_console().print(
            _panel(
                f"[bold yellow]⚠️ 降级回答[/bold yellow]（{source}）\n"
                f"未调用 minerva 研究引擎。{'已通过 ollama 生成实时回复。' if 'ollama' in source else ''}\n"
                "请确认 `minerva` 可用后再试以获得真实研究回答。",
                "yellow",
            )
        )
    _get_data_access().add_follow_up(args.research_id, question, answer)
    _notify_research_complete(research["topic"])
    quality_label = "（真实研究）" if answer_quality == "real" else "（降级回答）"
    style = "green" if answer_quality == "real" else "yellow"
    _render_markdown_block(f"💬 追问已回答 · ID {args.research_id} {quality_label}", answer, style=style)
    lines = [
        f"- `workspace research --open {args.research_id}`",
        f"- `workspace research --dossier {args.research_id}`",
        f"- `workspace research --timeline {args.research_id}`",
    ]
    if answer_quality == "degraded":
        lines.append("- `workspace status` 检查系统状态")
    _get_console().print(_panel("下一步:\n" + "\n".join(lines), "cyan"))
    return 0


def cmd_research_publish(args: argparse.Namespace) -> int:
    research_id = int(getattr(args, "publish", 0) or 0)
    style = str(getattr(args, "style", "report") or "report")
    result = _get_data_access().get_research(research_id)
    if not result:
        _get_console().print(f"\n[red]Error:[/] 未找到 ID={research_id} 的研究记录。\n")
        return 1
    safe_topic = str(result["topic"]).replace(" ", "_").replace("/", "_")[:40]
    date = datetime.fromtimestamp(float(result["created_at"])).strftime("%Y%m%d")
    output_dir = Path.home() / "Desktop" / "workspace-published"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{date}_{safe_topic}.md"
    content = _render_publish_content(result, style)
    output_path.write_text(content, encoding="utf-8")
    _get_data_access().save_published_report(research_id, style, str(output_path))
    _get_console().print(
        _panel(
            f"[bold green]✅ 已发布到[/bold green]\n{output_path}\n\n下一步:\n- `workspace research --open {result['id']}`\n- `workspace research --export markdown --open {result['id']}`",
            "green",
        )
    )
    return 0


def cmd_research_dossier(args: argparse.Namespace) -> int:
    research_id = int(getattr(args, "dossier", 0) or 0)
    dossier = _get_data_access().get_research_dossier(research_id)
    if dossier is None:
        _get_console().print(f"\n[red]Error:[/] 未找到 ID={research_id} 的研究记录。\n")
        return 1
    record = dossier["record"]
    _get_console().print(
        _panel(f"[bold cyan]🗂 研究 Dossier[/bold cyan]\nID {record['id']} · {record['topic']}", "cyan")
    )
    summary_table = Table(box=box.ROUNDED, header_style="bold cyan")
    summary_table.add_column("字段", style="bold")
    summary_table.add_column("值")
    summary_table.add_row("摘要", str(record.get("summary") or "暂无摘要"))
    summary_table.add_row("来源数", str(record.get("source_count") or 0))
    summary_table.add_row("标签", ", ".join(record.get("tags") or []) or "暂无标签")
    summary_table.add_row("Agent", record.get("agent", "") or "未指定")
    summary_table.add_row("归档状态", "已归档" if record.get("archived_at") else "活跃")
    summary_table.add_row("创建时间", _fmt_time(float(record["created_at"])))
    _get_console().print(summary_table)
    rel_table = Table(title="关系视图", box=box.ROUNDED, header_style="bold cyan")
    rel_table.add_column("方向", style="bold")
    rel_table.add_column("ID", style="cyan", no_wrap=True)
    rel_table.add_column("主题")
    rel_table.add_column("关系类型", style="green")
    for parent in dossier["parents"]:
        rel_table.add_row("parent", str(parent["id"]), str(parent["topic"]), str(parent["relation_type"]))
    for child in dossier["children"]:
        rel_table.add_row("child", str(child["id"]), str(child["topic"]), str(child["relation_type"]))
    if dossier["parents"] or dossier["children"]:
        _get_console().print(rel_table)
    else:
        _get_console().print(_panel("[dim]暂无关系记录[/dim]", "yellow"))
    if dossier["publications"]:
        pub_table = Table(title="发布产物", box=box.ROUNDED, header_style="bold green")
        pub_table.add_column("样式", style="green")
        pub_table.add_column("发布时间", style="dim")
        pub_table.add_column("路径")
        for item in dossier["publications"]:
            pub_table.add_row(str(item["style"]), _fmt_time(float(item["published_at"])), str(item["output_path"]))
        _get_console().print(pub_table)
    else:
        _get_console().print(_panel("[dim]暂无发布产物[/dim]", "yellow"))
    _get_console().print(
        _panel(
            "下一步:\n"
            f"- `workspace research --open {research_id}`\n"
            f'- `workspace research --ask {research_id} "继续提问"`\n'
            f"- `workspace research --publish {research_id} --style brief`\n"
            "- `workspace status`",
            "cyan",
        )
    )
    return 0


def cmd_research_timeline(args: argparse.Namespace) -> int:
    research_id = int(getattr(args, "timeline", 0) or 0)
    record = _get_data_access().get_research(research_id)
    if record is None:
        _get_console().print(f"\n[red]Error:[/] 未找到 ID={research_id} 的研究记录。\n")
        return 1
    timeline = _get_data_access().get_research_timeline(research_id)
    _get_console().print(
        _panel(f"[bold cyan]🕰 研究 Timeline[/bold cyan]\nID {record['id']} · {record['topic']}", "cyan")
    )
    agent = record.get("agent", "") or ""
    if agent:
        _get_console().print(_panel(f"[magenta]Agent: {agent}[/magenta]", "magenta"))
    table = Table(box=box.ROUNDED, header_style="bold cyan")
    table.add_column("时间", style="dim", no_wrap=True)
    table.add_column("事件", style="green", no_wrap=True)
    table.add_column("描述")
    for item in timeline:
        table.add_row(_fmt_time(float(item["created_at"])), str(item["event_type"]), str(item["description"]))
    _get_console().print(table)
    _get_console().print(
        _panel(
            "下一步:\n"
            f"- `workspace research --open {research_id}`\n"
            f"- `workspace research --dossier {research_id}`\n"
            f"- `workspace research --publish {research_id} --style brief`\n"
            "- `workspace status`",
            "cyan",
        )
    )
    return 0


def cmd_research_tag(args: argparse.Namespace) -> int:
    research_id = int(getattr(args, "tag", 0) or 0)
    labels = list(getattr(args, "labels", []) or [])
    if research_id <= 0 or not labels:
        _get_err().print("[red]❌ 请提供研究 ID 和至少一个标签[/red]")
        return 1
    updated = _get_data_access().set_research_tags(research_id, labels)
    if not updated:
        _get_err().print(f"[red]❌ 未找到 ID={research_id} 的研究记录[/red]")
        return 1
    _get_console().print(
        _panel(f"[bold green]✅ 已更新标签[/bold green]\nID {research_id}\n标签: {', '.join(updated)}", "green")
    )
    _get_console().print(
        _panel(
            "下一步:\n"
            f"- `workspace research --open {research_id}`\n"
            f"- `workspace research --dossier {research_id}`\n"
            "- `workspace research --list`",
            "cyan",
        )
    )
    return 0


def cmd_research_rename(args: argparse.Namespace) -> int:
    research_id = int(getattr(args, "rename", 0) or 0)
    new_title = " ".join(getattr(args, "new_title", []) or []).strip()
    if research_id <= 0 or not new_title:
        _get_err().print("[red]❌ 请提供研究 ID 和新标题[/red]")
        return 1
    renamed = _get_data_access().rename_research(research_id, new_title)
    if not renamed:
        _get_err().print(f"[red]❌ 未找到 ID={research_id} 的研究记录[/red]")
        return 1
    _get_console().print(
        _panel(f"[bold green]✅ 已重命名[/bold green]\nID {research_id}\n新标题: {new_title}", "green")
    )
    _get_console().print(
        _panel(
            "下一步:\n"
            f"- `workspace research --open {research_id}`\n"
            f"- `workspace research --dossier {research_id}`\n"
            "- `workspace research --list`",
            "cyan",
        )
    )
    return 0


def _get_all_active_ids() -> list[int]:
    """获取所有活跃研究 ID 列表（用于 --all-active 批量操作）。"""
    all_research = _get_data_access().list_research(limit=5000)
    return [r["id"] for r in all_research if r.get("archived_at") is None]


def _show_active_ids_hint(missing_ids: list[int]) -> None:
    """当操作的目标 ID 不存在时，列出最近活跃的 ID 方便用户选择。"""
    _get_err().print(f"[red]❌ 未找到这些研究 ID: {', '.join(str(i) for i in missing_ids)}[/red]")
    try:
        recent = _get_data_access().list_research(limit=10)
        if recent:
            lines = "\n".join(f"  [cyan]{r['id']:>4}[/]  {_short(r['topic'], 50)}" for r in recent)
            _get_console().print("[yellow]最近的研究记录:[/yellow]\n" + lines)
    except Exception:
        pass


def cmd_research_archive(args: argparse.Namespace) -> int:
    ids = list(dict.fromkeys(getattr(args, "archive", []) or []))
    if not ids and getattr(args, "all_active", False):
        ids = _get_all_active_ids()
        if not ids:
            _get_console().print(_panel("[dim]没有活跃的研究记录需要归档[/dim]", "yellow"))
            return 0
        _get_console().print(f"[yellow]准备归档全部 {len(ids)} 条活跃研究...[/yellow]")
    if not ids:
        _get_err().print("[red]❌ 请提供研究 ID 进行归档（或用 --all-active 归档全部活跃研究）[/red]")
        return 1
    archived, missing = _get_data_access().archive_research(ids)
    if not archived and missing:
        _show_active_ids_hint(missing)
        return 1
    lines = [
        f"[bold green]✅ 已归档 {len(archived)} 条研究记录[/bold green]",
        f"ID: {', '.join(str(item) for item in archived)}",
        "",
        "下一步:",
        "- `workspace research --list`",
        "- `workspace research --timeline <ID>`",
    ]
    if missing:
        lines.insert(2, f"[yellow]未找到这些研究 ID: {', '.join(str(item) for item in missing)}[/yellow]")
    _get_console().print(_panel("\n".join(lines), "green"))
    return 0


def cmd_research_unarchive(args: argparse.Namespace) -> int:
    ids = list(dict.fromkeys(getattr(args, "unarchive", []) or []))
    if not ids and getattr(args, "all_active", False):
        _get_err().print("[red]❌ --all-active 用于 --archive（归档全部活跃研究）[/red]")
        return 1
    if not ids:
        _get_err().print("[red]❌ 请提供研究 ID 进行恢复归档[/red]")
        return 1
    restored, missing = _get_data_access().restore_archived_research(ids)
    if not restored and missing:
        _get_err().print(f"[red]❌ 未找到这些研究 ID: {', '.join(str(item) for item in missing)}[/red]")
        return 1
    lines = [
        f"[bold green]✅ 已恢复归档 {len(restored)} 条研究记录[/bold green]",
        f"ID: {', '.join(str(item) for item in restored)}",
        "",
        "下一步:",
        "- `workspace research --list`",
        "- `workspace research --timeline <ID>`",
    ]
    if missing:
        lines.insert(2, f"[yellow]未找到这些研究 ID: {', '.join(str(item) for item in missing)}[/yellow]")
    _get_console().print(_panel("\n".join(lines), "green"))
    return 0


def cmd_research_compare(args: argparse.Namespace) -> int:
    ids = list(dict.fromkeys(getattr(args, "compare", []) or []))
    if len(ids) < 2:
        _get_err().print("[red]❌ 请至少提供两个研究 ID 进行对比[/red]")
        return 1
    records: list[dict[str, Any]] = []
    missing: list[int] = []
    for research_id in ids:
        record = _get_data_access().get_research(research_id)
        if record is None:
            missing.append(research_id)
        else:
            records.append(record)
    if missing:
        recent = _get_data_access().list_research(limit=3)
        msg = f"[red]Error:[/] 未找到这些研究 ID: {', '.join(str(item) for item in missing)}"
        if recent:
            ids_hint = "、".join(f"[cyan][{r['id']}]{r['topic']}[/]" for r in recent)
            msg += f"\n[yellow]最近的研究: {ids_hint}[/]"
        _get_console().print(f"\n{msg}\n")
        return 1
    _get_console().print(
        _panel(f"[bold cyan]🧩 研究对比[/bold cyan]\n对比 ID: {', '.join(str(item['id']) for item in records)}", "cyan")
    )
    table = Table(box=box.ROUNDED, header_style="bold cyan", show_lines=False)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("主题", style="bold")
    table.add_column("时间", style="dim", no_wrap=True)
    table.add_column("来源", style="green", justify="right", no_wrap=True)
    table.add_column("追问", style="yellow", justify="right", no_wrap=True)
    table.add_column("摘要")
    for record in records:
        created_at = record.get("created_at")
        created_at_value = float(created_at) if isinstance(created_at, int | float | str) else 0.0
        follow_ups_raw = record.get("follow_ups")
        follow_up_count = len(follow_ups_raw) if isinstance(follow_ups_raw, list) else 0
        table.add_row(
            str(record["id"]),
            str(record["topic"]),
            _fmt_time(created_at_value),
            str(record.get("source_count") or 0),
            str(follow_up_count),
            _short(str(record.get("summary") or ""), 70),
        )
    _get_console().print(table)
    focus = _compare_focus(records)
    actions = "\n".join(f"- `workspace research --open {record['id']}`" for record in records)
    _get_console().print(_panel(f"[bold]共同关注[/bold]: {focus}\n\n[bold]建议下一步[/bold]:\n{actions}", "green"))
    return 0


def cmd_research_merge(args: argparse.Namespace) -> int:
    ids = list(dict.fromkeys(getattr(args, "merge", []) or []))
    if len(ids) < 2:
        _get_err().print("[red]❌ 请至少提供两个研究 ID 进行合并[/red]")
        return 1
    records: list[dict[str, Any]] = []
    missing: list[int] = []
    for research_id in ids:
        record = _get_data_access().get_research(research_id)
        if record is None:
            missing.append(research_id)
        else:
            records.append(record)
    if missing:
        recent = _get_data_access().list_research(limit=3)
        msg = f"[red]Error:[/] 未找到这些研究 ID: {', '.join(str(item) for item in missing)}"
        if recent:
            ids_hint = "、".join(f"[cyan][{r['id']}]{r['topic']}[/]" for r in recent)
            msg += f"\n[yellow]最近的研究: {ids_hint}[/]"
        _get_console().print(f"\n{msg}\n")
        return 1
    focus = _compare_focus(records)
    merged_topic = f"Merged: {' + '.join(str(record['topic']) for record in records)}"
    merged_summary = f"共同关注: {focus}"
    total_sources = sum(int(record.get("source_count") or 0) for record in records)
    sections: list[str] = []
    for record in records:
        summary = str(record.get("summary") or "")
        full_text = str(record.get("full_text") or summary)
        sections.append(f"## {record['topic']}\n\n{full_text.strip()}")
    merged_body = (
        f"# {merged_topic}\n\n"
        f"合并研究 ID: {', '.join(str(item['id']) for item in records)}\n"
        f"共同关注: {focus}\n\n" + "\n\n".join(sections)
    )
    merged_id = _get_data_access().save_research(
        topic=merged_topic, summary=merged_summary, full_text=merged_body, source_count=total_sources
    )
    _get_data_access().add_research_relations([int(record["id"]) for record in records], merged_id, "merge")
    _get_console().print(
        _panel(
            f"[bold green]✅ 合并完成[/bold green]\nID {merged_id} · {merged_topic}\n\n"
            f"[bold]共同关注[/bold]: {focus}\n"
            f"[bold]总来源数[/bold]: {total_sources}\n\n"
            f"下一步:\n- `workspace research --open {merged_id}`\n- `workspace research --compare {' '.join(str(item['id']) for item in records)}`",
            "green",
        )
    )
    return 0


def cmd_research_digest(args: argparse.Namespace) -> int:
    ids = list(dict.fromkeys(getattr(args, "digest", []) or []))
    if len(ids) < 2:
        _get_err().print("[red]❌ 请至少提供两个研究 ID 生成 digest[/red]")
        return 1
    records: list[dict[str, Any]] = []
    missing: list[int] = []
    for research_id in ids:
        record = _get_data_access().get_research(research_id)
        if record is None:
            missing.append(research_id)
        else:
            records.append(record)
    if missing:
        recent = _get_data_access().list_research(limit=3)
        msg = f"[red]Error:[/] 未找到这些研究 ID: {', '.join(str(item) for item in missing)}"
        if recent:
            ids_hint = "、".join(f"[cyan][{r['id']}]{r['topic']}[/]" for r in recent)
            msg += f"\n[yellow]最近的研究: {ids_hint}[/]"
        _get_console().print(f"\n{msg}\n")
        return 1
    focus = _compare_focus(records)
    digest_topic = f"Digest: {' + '.join(str(record['topic']) for record in records)}"
    total_sources = sum(int(record.get("source_count") or 0) for record in records)
    topic_lines = "\n".join(f"- {record['topic']}" for record in records)
    overview_lines = "\n".join(
        f"- {record['topic']}: {_short(str(record.get('summary') or ''), 90)}" for record in records
    )
    difference_lines = "\n".join(
        f"- {record['topic']} 更侧重: {_short(str(record.get('summary') or str(record.get('full_text') or '')), 100)}"
        for record in records
    )
    next_steps = "\n".join(
        f"- `workspace research --open {record['id']}` 深入查看《{record['topic']}》" for record in records
    )
    next_steps += f"\n- `workspace research --compare {' '.join(str(record['id']) for record in records)}` 查看并列差异"
    digest_summary = f"共同关注: {focus}"
    digest_body = (
        f"# {digest_topic}\n\n"
        f"研究范围: {', '.join(str(record['id']) for record in records)}\n"
        f"共同关注: {focus}\n"
        f"总来源数: {total_sources}\n\n"
        f"## 核心主题\n{topic_lines}\n\n"
        f"## 研究速览\n{overview_lines}\n\n"
        f"## 关键差异\n{difference_lines}\n\n"
        f"## 下一步\n{next_steps}"
    )
    digest_id = _get_data_access().save_research(
        topic=digest_topic, summary=digest_summary, full_text=digest_body, source_count=total_sources
    )
    _get_data_access().add_research_relations([int(record["id"]) for record in records], digest_id, "digest")
    _get_console().print(
        _panel(
            f"[bold green]✅ Digest 已生成[/bold green]\nID {digest_id} · {digest_topic}\n\n"
            f"[bold]共同关注[/bold]: {focus}\n"
            f"[bold]总来源数[/bold]: {total_sources}\n\n"
            f"下一步:\n- `workspace research --open {digest_id}`\n- `workspace research --merge {' '.join(str(record['id']) for record in records)}`",
            "green",
        )
    )
    return 0


def cmd_research_audit(args: argparse.Namespace) -> int:
    limit = int(getattr(args, "limit", 50) or 50)
    records = _get_data_access().list_research(limit=max(limit, 1))
    issues: list[tuple[dict[str, Any], str]] = []
    for item in records:
        full = _get_data_access().get_research(int(item["id"]))
        if not full:
            continue
        issue = _audit_research_record(full)
        if issue:
            issues.append((full, issue))
    if not issues:
        _get_console().print(_panel("[bold green]✅ 未发现可疑研究记录[/bold green]", "green"))
        return 0
    _get_console().print(_panel(f"[bold yellow]⚠️ 发现 {len(issues)} 条可疑研究记录[/bold yellow]", "yellow"))
    table = Table(box=box.ROUNDED, header_style="bold yellow", show_lines=False)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("主题", style="bold")
    table.add_column("时间", style="dim", no_wrap=True)
    table.add_column("问题", style="red")
    table.add_column("建议")
    for record, issue in issues:
        table.add_row(
            str(record["id"]),
            str(record["topic"]),
            _fmt_time(float(record["created_at"])),
            issue,
            f"workspace research --open {record['id']} / --quarantine {record['id']}",
        )
    _get_console().print(table)
    return 0


def cmd_research_quarantine(args: argparse.Namespace) -> int:
    ids = list(dict.fromkeys(getattr(args, "quarantine", []) or []))
    if not ids:
        _get_err().print("[red]❌ 请至少提供一个研究 ID 进行隔离[/red]")
        return 1
    quarantined, missing = _get_data_access().quarantine_research(ids)
    if not quarantined and missing:
        _show_active_ids_hint(missing)
        return 1
    lines = [
        f"[bold green]✅ 已隔离 {len(quarantined)} 条研究记录[/bold green]",
        f"ID: {', '.join(str(item) for item in quarantined)}",
        "",
        "下一步:",
        "- `workspace research --audit`",
        "- `workspace research --list`",
    ]
    if missing:
        lines.insert(2, f"[yellow]未找到这些研究 ID: {', '.join(str(item) for item in missing)}[/yellow]")
    _get_console().print(_panel("\n".join(lines), "green"))
    return 0


def cmd_research_restore(args: argparse.Namespace) -> int:
    ids = list(dict.fromkeys(getattr(args, "restore", []) or []))
    if not ids:
        _get_err().print("[red]❌ 请至少提供一个研究 ID 进行恢复[/red]")
        return 1
    restored, missing = _get_data_access().restore_research(ids)
    if not restored and missing:
        _get_err().print(f"[red]❌ 未找到这些研究 ID: {', '.join(str(item) for item in missing)}[/red]")
        return 1
    lines = [
        f"[bold green]✅ 已恢复 {len(restored)} 条研究记录[/bold green]",
        f"ID: {', '.join(str(item) for item in restored)}",
        "",
        "下一步:",
        "- `workspace research --list`",
        "- `workspace research --audit`",
    ]
    if missing:
        lines.insert(2, f"[yellow]未找到这些研究 ID: {', '.join(str(item) for item in missing)}[/yellow]")
    _get_console().print(_panel("\n".join(lines), "green"))
    return 0


def cmd_research_export(args: argparse.Namespace) -> int:
    result = _get_data_access().get_research(args.research_id)
    if not result:
        _get_console().print(f"[red]Error: Research ID {args.research_id} not found[/]")
        return 1
    fmt = args.export.lower()
    if fmt not in {"markdown", "text", "json"}:
        _get_console().print(f"[red]Error: unsupported export format {args.export!r}（支持: markdown/text/json）[/]")
        return 1
    created_at = datetime.fromtimestamp(result["created_at"])
    body = result.get("full_text", result.get("summary", ""))
    if fmt == "json":
        import json as _json

        dossier = _get_data_access().get_research_dossier(result["id"])
        pub_count = len(dossier.get("publications", [])) if dossier else 0
        hl = _get_data_access().compute_half_life(result["id"])
        _get_console().print(
            _json.dumps(
                {
                    "id": result["id"],
                    "topic": result["topic"],
                    "created_at": result["created_at"],
                    "source_count": result.get("source_count", 0),
                    "agent": result.get("agent", ""),
                    "archived": result.get("archived_at") is not None,
                    "follow_up_count": len(result.get("follow_ups") or []),
                    "published_count": pub_count,
                    "decay": hl.get("decay", 0),
                    "summary": result.get("summary", "")[:500],
                },
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )
        return 0
    safe_topic = result["topic"].replace(" ", "_").replace("/", "_")[:30]
    date = datetime.fromtimestamp(result["created_at"]).strftime("%Y%m%d")
    filename = f"{date}_{safe_topic}.{fmt}"
    output_dir = Path.home() / "Desktop"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename
    if fmt == "markdown":
        content = f"""# {result["topic"]}

Date: {created_at.strftime("%Y-%m-%d %H:%M")}
Sources: {result.get("source_count", 0)}

{body}

---
Generated by Workspace CLI
"""
    else:
        content = f"Title: {result['topic']}\nDate: {created_at.strftime('%Y-%m-%d %H:%M')}\n\n{body}"
    output_path.write_text(content, encoding="utf-8")
    _get_console().print(f"[green]Exported to [bold]{output_path}[/][/]")
    return 0


def cmd_research_agent(args: argparse.Namespace) -> int:
    if args.tag and args.agent:
        research_id = int(args.tag)
        ok = _get_data_access().set_research_agent(research_id, args.agent)
        if not ok:
            _get_err().print(f"[red]❌ 未找到 ID={research_id} 的研究记录[/red]")
            return 1
        _get_console().print(
            _panel(f"[bold green]✅ 研究 #{research_id} 的 Agent 已标记为: {args.agent}[/bold green]", "green")
        )
        return 0
    if args.agent and not args.tag:
        results = _get_data_access().list_research(limit=args.limit or 50)
        filtered = [r for r in results if r.get("agent", "") == args.agent]
        if not filtered:
            _get_console().print(f"[yellow]没有找到 Agent 为 '{args.agent}' 的研究记录[/yellow]")
            return 0
        table = Table(title=f"Agent: {args.agent}", box=box.ROUNDED, header_style="bold cyan")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("主题", style="bold")
        table.add_column("时间", style="dim", no_wrap=True)
        table.add_column("来源", style="green", justify="right")
        table.add_column("摘要", style="dim")
        for r in filtered:
            table.add_row(
                str(r["id"]),
                r["topic"],
                _fmt_time(r["created_at"]),
                str(r["source_count"] or 0),
                _short(r["summary"], 80),
            )
        _get_console().print(table)
        return 0
    return 1


def cmd_research_heatmap(args: argparse.Namespace) -> int:
    from datetime import datetime

    results = _get_data_access().list_research(limit=100, include_archived=True)
    if not results:
        _get_console().print("[yellow]暂无研究记录[/]")
        return 0
    now_ts = time.time()
    weeks_back = 8
    week_data: dict[int, dict[str, Any]] = {}
    for i in range(weeks_back):
        week_start = now_ts - (weeks_back - i) * 7 * 86400
        week_label = datetime.fromtimestamp(week_start).strftime("%m/%d")
        week_data[i] = {"label": week_label, "created": 0, "follow_ups": 0, "published": 0}
    for r in results:
        created = float(r["created_at"])
        week_idx = min(weeks_back - 1, max(0, int((now_ts - created) / (7 * 86400))))
        if week_idx < weeks_back:
            week_data[week_idx]["created"] += 1
        fups = r.get("follow_ups", [])
        if isinstance(fups, list):
            for fup in fups:
                if isinstance(fup, dict) and "timestamp" in fup:
                    ts = float(fup["timestamp"])
                    wi = min(weeks_back - 1, max(0, int((now_ts - ts) / (7 * 86400))))
                    if wi < weeks_back:
                        week_data[wi]["follow_ups"] += 1
    max_created = max(w["created"] for w in week_data.values()) or 1
    max_fups = max(w["follow_ups"] for w in week_data.values()) or 1
    table = Table(title="📊 研究活跃度热力图 (近8周)", box=box.ROUNDED)
    table.add_column("周", style="cyan")
    table.add_column("新研究", justify="center")
    table.add_column("追问", justify="center")
    for i in range(weeks_back - 1, -1, -1):
        w = week_data[i]
        table.add_row(w["label"], _heat_char(w["created"], max_created), _heat_char(w["follow_ups"], max_fups))
    _get_console().print(table)
    _get_console().print("[dim]颜色: [green]低[/] [yellow]中[/] [red]高[/] · 追问含 follow-up · 近8周统计[/dim]")
    return 0


def cmd_research_health(args: argparse.Namespace) -> int:
    """显示所有活跃研究的健康状态报告（基于半衰期衰减）。"""
    results = _get_data_access().list_research(limit=100)

    good: list[tuple[dict[str, Any], dict[str, Any]]] = []
    fair: list[tuple[dict[str, Any], dict[str, Any]]] = []
    stale: list[tuple[dict[str, Any], dict[str, Any]]] = []

    for r in results:
        if r.get("archived_at") is not None:
            continue
        hl = _get_data_access().compute_half_life(int(r["id"]))
        decay = hl.get("decay", 0.0)
        if not isinstance(decay, (int, float)):
            decay = 0.0
        if decay >= 0.7:
            good.append((r, hl))
        elif decay >= 0.3:
            fair.append((r, hl))
        else:
            stale.append((r, hl))

    total = len(good) + len(fair) + len(stale)
    _get_console().print(
        _panel(
            f"[bold cyan]🩺 研究健康报告[/bold cyan]\n"
            f"[green]● 健康 {len(good)}[/green] · "
            f"[yellow]● 待关注 {len(fair)}[/yellow] · "
            f"[red]● 已衰减 {len(stale)}[/red] · "
            f"共 {total} 活跃研究",
            "cyan",
        )
    )

    if total == 0:
        _get_console().print("[yellow]暂无活跃研究记录[/yellow]")
        return 0

    def _render_group(title: str, items: list, style: str) -> None:
        if not items:
            return
        table = Table(box=box.ROUNDED, header_style=f"bold {style}")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("主题", style="bold")
        table.add_column("衰减", style=style, justify="right")
        table.add_column("静默天数", style="dim", justify="right")
        table.add_column("追问", style="yellow", justify="right")
        table.add_column("发布", style="green", justify="right")
        table.add_column("建议", style="dim")
        for r2, hl2 in items:
            d = hl2.get("decay", 0)
            pct = f"{d * 100:.0f}%"
            days = f"{hl2.get('days_since_active', 0):.0f}d"
            fup_count = hl2.get("follow_up_count", 0)
            pub_count = hl2.get("published_count", 0)
            rid = r2["id"]
            if d < 0.3:
                suggestion = f"可归档或追问 #{rid}"
            elif d < 0.7:
                suggestion = f"建议追问 #{rid}"
            else:
                suggestion = "✅ 状态良好"
            table.add_row(
                str(rid),
                _short(str(r2.get("topic", "")), 32),
                pct,
                days,
                str(fup_count),
                str(pub_count),
                suggestion,
            )
        _get_console().print(_panel(f"[bold {style}]{title}[/bold {style}]", style))
        _get_console().print(table)

    _render_group("健康（衰减 < 30%）", good, "green")
    _render_group("待关注（衰减 30%-70%）", fair, "yellow")
    _render_group("已衰减（衰减 > 70%）", stale, "red")

    if stale or fair:
        tips = ["[bold]💡 保鲜建议[/bold]", ""]
        if stale:
            tips.append("- 已衰减研究 → 可发起追问延续活性或归档已无用记录")
        if fair:
            tips.append("- 待关注研究 → 发起新追问保持研究活性")
        tips.append("- `workspace research --audit` 扫描问题记录")
        tips.append("- `workspace research --heatmap` 查看活跃度趋势")
        _get_console().print(_panel("\n".join(tips), "yellow"))
    return 0


def cmd_research_follow_up(args: argparse.Namespace) -> int:
    """列出所有有待追问（pending follow-up）的活跃研究。"""
    results = _get_data_access().list_research(limit=100)
    now_ts = time.time()

    pending: list[dict[str, Any]] = []  # 有未回答的追问
    all_answered: list[dict[str, Any]] = []  # 追问全部已回答
    no_fups: list[dict[str, Any]] = []  # 无追问记录

    for r in results:
        if r.get("archived_at") is not None:
            continue
        fups = r.get("follow_ups") or []
        if not isinstance(fups, list):
            fups = []
        has_pending = any(isinstance(f, dict) and not f.get("answer", "").strip() for f in fups)
        if has_pending:
            pending.append(r)
        elif fups:
            all_answered.append(r)
        else:
            no_fups.append(r)

    total = len(pending) + len(all_answered) + len(no_fups)
    _get_console().print(
        _panel(
            f"[bold cyan]💬 追问工作台[/bold cyan]\n"
            f"[yellow]{len(pending)} 待追问[/yellow] · "
            f"[green]{len(all_answered)} 已回答[/green] · "
            f"[dim]{len(no_fups)} 无需追问[/dim] · "
            f"共 {total} 活跃研究",
            "cyan",
        )
    )

    if not pending:
        _get_console().print("[green]✅ 所有活跃研究的追问都已处理[/green]")
        return 0

    table = Table(box=box.ROUNDED, header_style="bold yellow")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("主题", style="bold")
    table.add_column("待追问", style="yellow", justify="right")
    table.add_column("已回答", style="green", justify="right")
    table.add_column("最近追问", style="dim")
    table.add_column("活跃天数", style="dim", justify="right")
    for r in pending:
        fups = r.get("follow_ups") or []
        if not isinstance(fups, list):
            fups = []
        pending_count = sum(1 for f in fups if isinstance(f, dict) and not f.get("answer", "").strip())
        answered_count = sum(1 for f in fups if isinstance(f, dict) and f.get("answer", "").strip())
        last_q = ""
        for f in reversed(fups):
            if isinstance(f, dict) and f.get("question"):
                last_q = str(f["question"])[:40]
                break
        days_active = max(0, int((now_ts - float(r.get("created_at", now_ts))) / 86400))
        table.add_row(
            str(r["id"]),
            _short(str(r.get("topic", "")), 40),
            str(pending_count),
            str(answered_count),
            last_q,
            f"{days_active}d",
        )
    _get_console().print(table)

    # 显示快捷操作
    actions = "\n".join(
        f'- `workspace research --ask {r["id"]} "你的问题"`  [dim]对 #{r["id"]} 发起新追问[/dim]' for r in pending[:5]
    )
    _get_console().print(
        _panel(
            f"[bold]快捷操作[/bold]（前 5 条待追问）:\n{actions}\n\n"
            f"        [dim]全部查看: workspace research --open <ID>[/dim]",
            "yellow",
        )
    )
    return 0


def cmd_research_backup(args: argparse.Namespace) -> int:
    """全量备份所有研究数据到 JSON 文件。"""
    da = _get_data_access()
    data = da.export_backup()
    output_path = getattr(args, "output", None) or str(Path.home() / "Desktop" / "workspace_backup.json")

    import json as _json

    try:
        Path(output_path).write_text(
            _json.dumps(data, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
    except (OSError, PermissionError) as e:
        _get_err().print(f"[red]❌ 写入备份文件失败: {e}[/red]")
        return 1

    count = len(data.get("research", []))
    _get_console().print(
        _panel(
            f"[bold green]✅ 备份完成[/bold green]\n"
            f"文件: [cyan]{output_path}[/cyan]\n"
            f"研究: {count} 条 · "
            f"关系: {len(data.get('relations', []))} 条 · "
            f"发布: {len(data.get('published_reports', []))} 条 · "
            f"事件: {len(data.get('events', []))} 条",
            "green",
        )
    )
    return 0


def cmd_research_backup_restore(args: argparse.Namespace) -> int:
    """从备份 JSON 文件恢复研究数据。"""
    file_path = getattr(args, "backup_restore", None)
    if not file_path:
        _get_err().print("[red]❌ 请指定备份文件路径[/red]")
        return 1

    p = Path(file_path)
    if not p.exists():
        _get_err().print(f"[red]❌ 备份文件不存在: {file_path}[/red]")
        return 1

    import json as _json

    try:
        data = _json.loads(p.read_text(encoding="utf-8"))
    except (_json.JSONDecodeError, OSError) as e:
        _get_err().print(f"[red]❌ 读取备份文件失败: {e}[/red]")
        return 1

    if not isinstance(data, dict) or "version" not in data:
        _get_err().print("[red]❌ 无效的备份文件格式（缺少 version 字段）[/red]")
        return 1

    da = _get_data_access()
    stats = da.import_backup(data)

    _get_console().print(
        _panel(
            f"[bold green]✅ 恢复完成[/bold green]\n"
            f"研究: [cyan]{stats['research']}[/cyan] 条导入 · "
            f"[yellow]{stats['skipped']}[/yellow] 条跳过\n"
            f"关系: {stats['relations']} 条 · "
            f"发布: {stats['published_reports']} 条 · "
            f"事件: {stats['events']} 条",
            "green",
        )
    )
    return 0
