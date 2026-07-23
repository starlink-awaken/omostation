"""cockpit.commands.importer — import command handler.

URL 导入优先走 kairon/kronos 多层抓取（native_http → scrapling → jina → browser），
失败再降级到 urllib；本地文件仍直接读盘。
"""

from __future__ import annotations

import argparse
import json
import subprocess
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


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[5]


def _try_kronos_fetch(url: str, timeout: int = 30) -> tuple[str, str] | None:
    """Call kronos execute_fetch via uv. Return (text, method) or None on failure."""
    project = _workspace_root() / "projects" / "kairon" / "packages" / "kronos"
    if not project.is_dir():
        return None

    # JSON payload on stdout; keep snippet small for import body.
    code = (
        "import json\n"
        "from kronos.fetcher.errors import execute_fetch\n"
        f"r = execute_fetch({url!r}, timeout={int(timeout)})\n"
        "print(json.dumps({"
        '"ok": bool(r.get("ok")), '
        '"method": r.get("method") or "", '
        '"title": r.get("title") or "", '
        '"text": (r.get("markdown") or r.get("text") or r.get("content") or "")[:200000], '
        '"error": r.get("error") or ""'
        "}))\n"
    )
    try:
        proc = subprocess.run(
            ["uv", "run", "--project", str(project), "python", "-c", code],
            capture_output=True,
            text=True,
            timeout=timeout + 20,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None

    if proc.returncode != 0:
        return None

    line = (proc.stdout or "").strip().splitlines()
    if not line:
        return None
    try:
        payload = json.loads(line[-1])
    except json.JSONDecodeError:
        return None
    if not payload.get("ok"):
        return None
    text = str(payload.get("text") or "").strip()
    if not text:
        return None
    method = str(payload.get("method") or "kronos")
    title = str(payload.get("title") or "").strip()
    if title and not text.lower().startswith(title.lower()):
        text = f"# {title}\n\n{text}"
    return text, f"kronos/{method}"


def _fetch_url_raw(url: str, timeout: int = 30) -> tuple[str, str, str]:
    """Fetch URL content. Returns (raw_text, resolved_source, method_tag).

    Raises urlerror.URLError when all strategies fail.
    """
    kronos = _try_kronos_fetch(url, timeout=timeout)
    if kronos is not None:
        text, method = kronos
        return text, url, method

    try:
        with urlrequest.urlopen(url, timeout=min(timeout, 15)) as response:  # noqa: S310
            raw_text = response.read().decode("utf-8", errors="replace")
            resolved = response.geturl()
    except urlerror.URLError:
        raise
    except OSError as exc:
        raise urlerror.URLError(str(exc)) from exc
    return raw_text, resolved, "urllib"


def cmd_import(args: argparse.Namespace) -> int:
    source = (getattr(args, "source", "") or "").strip()
    if not source:
        _get_err().print("[red]❌ 请提供要导入的 URL 或文件路径[/red]")
        _notify_pipeline_error("导入", "empty source")
        return 1
    _get_console().print(_panel(f"[bold cyan]📥 导入内容[/bold cyan]\n{source}", "cyan"))
    method_tag = "file"
    try:
        if _looks_like_url(source):
            raw_text, resolved_source, method_tag = _fetch_url_raw(source)
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
    full_text = f"Source: {resolved_source}\nFetch: {method_tag}\n\n{body}"
    research_id = _get_data_access().save_research(
        topic=title, summary=_short(body, 200), full_text=full_text, source_count=1
    )
    _notify_pipeline_success("导入", title)
    _get_console().print(
        _panel(
            f"[bold green]✅ 导入完成[/bold green]\n"
            f"ID {research_id} · {title}\n"
            f"[dim]{resolved_source} · via {method_tag}[/dim]",
            "green",
        )
    )
    _get_console().print(
        _panel(
            "下一步:\n"
            f"- `cockpit research --open {research_id}`\n"
            f'- `cockpit research --ask {research_id} "继续追问"\n'
            f"- `cockpit research --publish {research_id} --style brief`\n"
            f"- `cockpit research --tag {research_id} --labels 标签1 标签2`\n"
            "- `cockpit research --list`\n"
            "- URL 抓取默认走 `kronos`；也可直接: `cockpit kairon kronos fetch <url>`",
            "cyan",
        )
    )
    return 0
