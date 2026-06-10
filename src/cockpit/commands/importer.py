"""cockpit.commands.importer — import command handler."""

from __future__ import annotations

import argparse
from pathlib import Path
from urllib import error as urlerror
from urllib import request as urlrequest

from .base import (
    _get_console,
    _get_data_access,
    _get_err,
    _looks_like_url,
    _normalize_import_content,
    _notify_pipeline_error,
    _notify_pipeline_success,
    _panel,
    _short,
)


def cmd_import(args: argparse.Namespace) -> int:
    source = (getattr(args, "source", "") or "").strip()
    if not source:
        _get_err().print("[red]❌ 请提供要导入的 URL 或文件路径[/red]")
        _notify_pipeline_error("导入", "empty source")
        return 1
    _get_console().print(_panel(f"[bold cyan]📥 导入内容[/bold cyan]\n{source}", "cyan"))
    try:
        if _looks_like_url(source):
            with urlrequest.urlopen(source, timeout=10) as response:  # noqa: S310
                raw_text = response.read().decode("utf-8", errors="replace")
                resolved_source = response.geturl()
        else:
            path = Path(source).expanduser()
            if not path.exists() or not path.is_file():
                _get_err().print(f"[red]❌ 未找到要导入的文件: {source}[/red]")
                _notify_pipeline_error("导入", source)
                return 1
            raw_text = path.read_text(encoding="utf-8", errors="replace")
            resolved_source = str(path)
    except urlerror.URLError as exc:
        _get_err().print(f"[red]❌ 无法读取 URL: {source}[/red]\n[yellow]{exc}[/yellow]")
        _notify_pipeline_error("导入", source)
        return 1
    except OSError as exc:
        _get_err().print(f"[red]❌ 读取内容失败: {source}[/red]\n[yellow]{exc}[/yellow]")
        _notify_pipeline_error("导入", source)
        return 1
    title, body = _normalize_import_content(source, raw_text)
    if not body:
        _get_err().print("[red]❌ 导入内容为空，无法保存[/red]")
        _notify_pipeline_error("导入", source)
        return 1
    full_text = f"Source: {resolved_source}\n\n{body}"
    research_id = _get_data_access().save_research(
        topic=title, summary=_short(body, 200), full_text=full_text, source_count=1
    )
    _notify_pipeline_success("导入", title)
    _get_console().print(
        _panel(
            f"[bold green]✅ 导入完成[/bold green]\nID {research_id} · {title}\n[dim]{resolved_source}[/dim]", "green"
        )
    )
    _get_console().print(
        _panel(
            "下一步:\n"
            f"- `workspace research --open {research_id}`\n"
            f'- `workspace research --ask {research_id} "继续追问"\n'
            f"- `workspace research --publish {research_id} --style brief`\n"
            f"- `workspace research --tag {research_id} --labels 标签1 标签2`\n"
            "- `workspace research --list`",
            "cyan",
        )
    )
    return 0
