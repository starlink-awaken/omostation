"""cockpit.commands.knowledge — KOS 知识检索治理入口.

暴露 KOS (5193 篇索引) 的核心能力:
  search   — 语义搜索 (通过 kos_proxy HTTP)
  status   — KOS 服务健康 (REST API port 8766)
  stats    — 索引覆盖率/新鲜度统计

设计: KISS — 通过 kos_proxy 复用已有 HTTP 通道, 不重写 KOS 逻辑.
DRY: 复用 cockpit.kos_proxy 的 _get_client / KOS_API_URL 配置.
"""

from __future__ import annotations

import argparse
import json
import os
from urllib import request as urlrequest
from urllib.error import URLError

from .base import _get_console, _get_err, _panel

KOS_API_URL = os.environ.get("KOS_API_URL", "http://localhost:8766")


def _safe_urlopen(url: str, timeout: float = 5.0):
    """只允许 http/https 的内部 urlopen 包装."""
    if not url.startswith(("http://", "https://")):
        raise ValueError(f"不支持的 URL scheme: {url}")
    return urlrequest.urlopen(url, timeout=timeout)  # noqa: S310


def _kos_available() -> bool:
    """探测 KOS REST API 是否在线 (且确实是 KOS, 非 runtime 抢端口)."""
    try:
        with _safe_urlopen(f"{KOS_API_URL}/api/v1/health", timeout=2.0) as resp:
            if resp.status != 200:
                return False
            import json as _json

            data = _json.loads(resp.read().decode("utf-8", errors="replace"))
            # KOS 健康响应有 status/version 字段; runtime 抢端口时返回 {"agents":0,"nodes":0}
            return bool(data.get("version") or data.get("documents") is not None or data.get("indexed"))
    except (URLError, OSError, ValueError, KeyError):
        return False


def _kos_port_conflict() -> str | None:
    """若端口被非 KOS 服务占用, 返回占用者信息 (帮助诊断)."""
    try:
        with _safe_urlopen(f"{KOS_API_URL}/health", timeout=2.0) as resp:
            if resp.status == 200:
                import json as _json

                data = _json.loads(resp.read().decode("utf-8", errors="replace"))
                if not (data.get("version") or data.get("documents") is not None):
                    return f"端口被非 KOS 服务占用 (响应: {data})"
    except (URLError, OSError, ValueError):
        pass
    return None


def cmd_knowledge_search(args: argparse.Namespace) -> int:
    """cockpit knowledge search <query> — KOS 语义搜索."""
    query = getattr(args, "query", None)
    if not query:
        _get_err().print('[red]❌ 请提供搜索词: cockpit knowledge search "借调政策"[/red]')
        return 1

    console = _get_console()
    limit = getattr(args, "limit", 5)

    if not _kos_available():
        console.print(f"[yellow]⚠️  KOS 服务未在线 ({KOS_API_URL})[/yellow]")
        console.print("[dim]   启动: cd projects/knowledge/kairon/packages/kos && uv run kos serve[/dim]")
        console.print(f'[dim]   或降级使用: cockpit search "{query}"[/dim]')
        return 1

    import urllib.parse

    encoded = urllib.parse.quote(query)
    url = f"{KOS_API_URL}/api/v1/search?q={encoded}&mode=hybrid&limit={limit}"
    try:
        with _safe_urlopen(url, timeout=30.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (URLError, OSError, json.JSONDecodeError) as exc:
        _get_err().print(f"[red]❌ KOS 搜索失败: {exc}[/red]")
        return 1

    results = data.get("results") or data.get("documents") or []
    if not results:
        console.print(f'[yellow]🔍 未找到与 "{query}" 相关的知识[/yellow]')
        return 0

    console.print(
        _panel(
            f"[bold cyan]📚 KOS 知识搜索 · {len(results)} 条结果[/bold cyan]\n[dim]查询: {query}[/]",
            "cyan",
        )
    )

    from rich import box as rich_box
    from rich.table import Table

    table = Table(box=rich_box.ROUNDED, header_style="bold cyan")
    table.add_column("#", style="dim", width=3)
    table.add_column("标题", style="bold", no_wrap=False)
    table.add_column("相关度", style="green", width=8)
    table.add_column("来源", style="dim", no_wrap=False)

    for i, r in enumerate(results, 1):
        title = r.get("title") or r.get("doc_id") or "未知"
        score = r.get("score") or r.get("similarity") or 0
        source = r.get("source") or r.get("path") or ""
        score_pct = f"{float(score) * 100:.0f}%" if isinstance(score, (int, float)) else "—"
        table.add_row(str(i), str(title)[:60], score_pct, str(source)[:40])
    console.print(table)
    return 0


def cmd_knowledge_status(args: argparse.Namespace) -> int:
    """cockpit knowledge status — KOS 服务健康状态."""
    console = _get_console()

    if not _kos_available():
        console.print(f"[red]❌ KOS 服务离线 ({KOS_API_URL})[/red]")
        console.print("[dim]   启动: cd projects/knowledge/kairon/packages/kos && uv run kos serve[/dim]")
        return 1

    try:
        with _safe_urlopen(f"{KOS_API_URL}/health", timeout=5.0) as resp:
            health = json.loads(resp.read().decode("utf-8"))
    except (URLError, OSError, json.JSONDecodeError) as exc:
        _get_err().print(f"[red]❌ 获取 KOS 健康状态失败: {exc}[/red]")
        return 1

    console.print(
        _panel(
            f"[bold green]✅ KOS 服务在线[/bold green]\n"
            f"端点: {KOS_API_URL}\n"
            f"状态: {health.get('status', 'unknown')}\n"
            f"版本: {health.get('version', 'unknown')}",
            "green",
        )
    )
    return 0


def cmd_knowledge_stats(args: argparse.Namespace) -> int:
    """cockpit knowledge stats — KOS 索引统计."""
    console = _get_console()

    if not _kos_available():
        console.print(f"[red]❌ KOS 服务离线 ({KOS_API_URL})[/red]")
        return 1

    try:
        with _safe_urlopen(f"{KOS_API_URL}/api/v1/stats", timeout=10.0) as resp:
            stats = json.loads(resp.read().decode("utf-8"))
    except (URLError, OSError, json.JSONDecodeError) as exc:
        _get_err().print(f"[red]❌ 获取 KOS 统计失败: {exc}[/red]")
        return 1

    from rich import box as rich_box
    from rich.table import Table

    console.print(_panel("[bold cyan]📊 KOS 索引统计[/bold cyan]", "cyan"))
    table = Table(box=rich_box.ROUNDED, header_style="bold cyan")
    table.add_column("指标", style="cyan")
    table.add_column("值", style="bold")
    for key, val in stats.items():
        if isinstance(val, (dict, list)):
            val = json.dumps(val, ensure_ascii=False)[:60]
        table.add_row(str(key), str(val))
    console.print(table)
    return 0


def cmd_knowledge(args: argparse.Namespace) -> int:
    """cockpit knowledge — KOS 知识检索治理入口."""
    sub = getattr(args, "knowledge_command", None)
    if sub == "search":
        return cmd_knowledge_search(args)
    if sub == "status":
        return cmd_knowledge_status(args)
    if sub == "stats":
        return cmd_knowledge_stats(args)

    # 无子命令: 显示概览
    console = _get_console()
    console.print(_panel("[bold cyan]📚 KOS 知识检索 (5193 篇索引)[/bold cyan]", "cyan"))
    if _kos_available():
        console.print("[green]✅ KOS 服务在线[/green]")
    else:
        console.print(f"[yellow]⚠️  KOS 服务离线 ({KOS_API_URL})[/yellow]")
        conflict = _kos_port_conflict()
        if conflict:
            console.print(f"[red]   {conflict}[/red]")
            console.print("[dim]   端口冲突: runtime 服务抢占了 8766 (port-registry 归属 kos-rest-api)[/dim]")
            console.print("[dim]   解决: 停 runtime 服务, 或 KOS 改用其他端口 + 改 KOS_API_URL 环境变量[/dim]")
    console.print("\n[bold]可用子命令:[/]")
    console.print('  [cyan]cockpit knowledge search "查询词"[/]  — 语义搜索')
    console.print("  [cyan]cockpit knowledge status[/]            — 服务健康")
    console.print("  [cyan]cockpit knowledge stats[/]             — 索引统计")
    return 0
