"""cockpit.commands.quickstart — 快速开始向导 (onboarding / init)"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib import request as urlrequest

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .base import _get_console, _panel


def _check_python() -> str | None:
    v = sys.version_info
    if v.major < 3 or (v.major == 3 and v.minor < 10):
        return f"需要 Python 3.10+，当前: {v.major}.{v.minor}.{v.micro}"
    return None


def _check_cli_tools() -> dict[str, bool]:
    tools = ["minerva", "git", "ollama", "pip3", "uvicorn", "agora"]
    return {t: bool(shutil.which(t)) for t in tools}


def _check_ollama_running() -> bool:
    try:
        req = urlrequest.Request("http://localhost:11434/api/tags", method="GET")
        resp = urlrequest.urlopen(req, timeout=3)  # noqa: S310
        return resp.status == 200
    except Exception:
        return False


def _check_workspace_db() -> dict:
    db_path = Path.home() / ".workspace" / "data.db"
    if not db_path.exists():
        return {"exists": False, "research_count": 0}
    try:
        import sqlite3

        conn = sqlite3.connect(str(db_path))
        count = conn.execute("SELECT COUNT(*) FROM research").fetchone()[0]
        conn.close()
        return {"exists": True, "research_count": count}
    except sqlite3.Error:
        return {"exists": True, "research_count": -1}


def _ensure_workspace_db() -> bool:
    """确保 workspace 数据库已初始化。"""
    db_path = Path.home() / ".workspace" / "data.db"
    if db_path.exists():
        return True
    db_path.parent.mkdir(parents=True, exist_ok=True)
    # 创建一条欢迎研究以初始化数据库
    try:
        from cockpit.storage import get_data_access

        get_data_access().save_research(
            topic="欢迎使用 Workspace",
            summary="这是您的第一条研究记录。Workspace 已准备就绪！",
            full_text='恭喜您成功初始化 Workspace 环境！\n\n您可以通过以下命令开始使用：\n- `workspace research "主题"` 发起新研究\n- `workspace research --list` 浏览记录\n- `workspace demo` 体验完整闭环',
            source_count=1,
        )
        return True
    except Exception:
        return False


def _auto_fix(c: Console, args: argparse.Namespace) -> int:
    """自动修复检测到的问题。"""
    c.print(_panel("[bold cyan]🔧 自动修复模式[/bold cyan]", "cyan"))
    issues: list[str] = []
    fixes: list[str] = []

    # 1. 检查 ollama 是否安装但未运行
    ollama_found = bool(shutil.which("ollama"))
    if ollama_found:
        ollama_running = _check_ollama_running()
        if not ollama_running:
            fixes.append("启动 ollama 服务...")
            c.print("  [yellow]⚠️  ollama 已安装但未运行，正在尝试启动...[/yellow]")
            try:
                subprocess.Popen(
                    ["ollama", "serve"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                # 等待启动 (带进度指示)
                from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    TimeElapsedColumn(),
                    transient=True,
                ) as progress:
                    task = progress.add_task("[yellow]等待 ollama 启动...[/]", total=30)
                    for i in range(30):
                        time.sleep(1)
                        progress.update(task, advance=1)
                        if _check_ollama_running():
                            c.print("  [green]✅ ollama 启动成功[/green]")
                            fixes.append("ollama 服务已启动")
                            break
                    else:
                        c.print("  [red]❌ ollama 启动超时，请手动执行: ollama serve[/red]")
                        issues.append("ollama 启动失败")
            except Exception as e:
                c.print(f"  [red]❌ ollama 启动失败: {e}[/red]")
                issues.append(f"ollama 启动失败: {e}")
        else:
            c.print("  [green]✅ ollama 运行中[/green]")

        # 2. 检查并拉取默认模型
        if _check_ollama_running():
            default_model = args.model or "llama3.2"
            try:
                req = urlrequest.Request("http://localhost:11434/api/tags", method="GET")
                resp = urlrequest.urlopen(req, timeout=5)  # noqa: S310
                import json as _json

                tags = _json.loads(resp.read().decode())
                models = [m["name"] for m in tags.get("models", [])]
                already_have = any(default_model in m for m in models)
                if already_have:
                    c.print(f"  [green]✅ 模型 {default_model} 已就绪[/green]")
                else:
                    c.print(f"  [yellow]⏳ 正在拉取模型 {default_model}（首次拉取可能需要几分钟）...[/yellow]")
                    fixes.append(f"拉取模型 {default_model}")
                    with Progress(
                        SpinnerColumn(style="yellow"),
                        TextColumn("[bold]{task.description}[/bold]"),
                        TimeElapsedColumn(),
                        console=c,
                        transient=False,
                    ) as progress:
                        progress.add_task(f"[yellow]ollama pull {default_model}", total=None)
                        result = subprocess.run(
                            ["ollama", "pull", default_model],
                            capture_output=True,
                            text=True,
                            timeout=600,
                        )
                    if result.returncode == 0:
                        c.print(f"  [green]✅ 模型 {default_model} 拉取完成[/green]")
                    else:
                        c.print(f"  [yellow]⚠️  模型拉取失败: {result.stderr.strip() or result.stdout.strip()}[/yellow]")
                        issues.append(f"模型 {default_model} 未拉取")
            except Exception as e:
                c.print(f"  [yellow]⚠️  检查模型状态异常: {e}[/yellow]")
                issues.append(f"模型检查异常: {e}")

    # 3. 创建 ~/.workspace 目录并初始化数据库
    if _ensure_workspace_db():
        c.print("  [green]✅ workspace 数据库就绪[/green]")
    else:
        c.print("  [yellow]⚠️  数据库初始化异常，请检查权限[/yellow]")
        issues.append("数据库初始化失败")

    # 4. 总结
    c.print()
    if not issues:
        c.print(
            _panel(
                "[bold green]✅ 自动修复完成！所有问题已处理[/bold green]\n\n"
                "现在可以开始使用:\n"
                '- [cyan]workspace research "主题"[/]  — 发起研究\n'
                "- [cyan]workspace status[/]  — 查看工作台\n"
                "- [cyan]workspace demo[/]  — 体验完整闭环",
                "green",
            )
        )
        c.print()
    else:
        fix_list = "\n".join(f"  [green]✅ {f}[/green]" for f in fixes)
        issue_list = "\n".join(f"  [red]❌ {i}[/red]" for i in issues)
        c.print(
            _panel(
                f"[bold yellow]⚠️  部分修复完成[/bold yellow]\n\n"
                f"已处理:\n{fix_list}\n\n"
                f"未解决:\n{issue_list}\n\n"
                f"请手动处理上述问题后重试 'workspace quickstart --fix'",
                "yellow",
            )
        )
    return 0 if not issues else 1


def cmd_quickstart(args: argparse.Namespace) -> int:
    c = _get_console()
    if getattr(args, "fix", False):
        return _auto_fix(c, args)
    c.print()
    c.print(
        Panel.fit(
            "[bold cyan]🧭 欢迎使用 Workspace！[/bold cyan]\n\n"
            "研究对象管理系统 — 让你的每一个研究和想法都有记忆、可追溯。\n\n"
            "[dim]输入 → 研究 → 追问 → 发布 → 复盘[/dim]",
            border_style="cyan",
            box=box.ROUNDED,
        )
    )
    c.print()

    # ── 第 1 步：环境核验 ──
    c.print(_panel("[bold]Step 1/4 — 环境核验[/bold]", "cyan", title="🔍"))
    issues: list[str] = []
    py_issue = _check_python()
    if py_issue:
        issues.append(py_issue)
    else:
        c.print("  [green]✅ Python[/green]  " + ".".join(str(v) for v in sys.version_info[:3]))
    tools = _check_cli_tools()
    for name, found in sorted(tools.items(), key=lambda x: (not x[1], x[0])):
        if name == "minerva" and found:
            c.print(f"  [green]✅ {name}[/green]  — 深度研究引擎")
        elif name == "ollama" and found:
            ollama_running = _check_ollama_running()
            if ollama_running:
                c.print("  [green]✅ ollama[/green]  — 本地 LLM（运行中）")
            else:
                c.print("  [yellow]⚠️  ollama[/yellow]  — 已安装但未运行（研究降级不可用）")
        elif found:
            c.print(f"  [green]✅ {name}[/green]")
        else:
            c.print(f"  [dim]⭕ {name}[/dim]  — 可选，未安装")
    cockpit_db = _check_workspace_db()
    if cockpit_db["exists"]:
        c.print(f"  [green]✅ workspace 数据库[/green]  — {cockpit_db['research_count']} 条研究记录")
    else:
        c.print("  [dim]⭕ workspace 数据库[/dim]  — 首次使用，尚无研究记录")
    c.print()

    # ── 第 2 步：推荐配置 ──
    c.print(_panel("[bold]Step 2/4 — 推荐配置[/bold]", "cyan", title="⚙️"))
    recs: list[str] = []
    if not tools.get("minerva"):
        recs.append("[yellow]🔸 建议安装 minerva 以获得真实深度研究能力[/yellow]")
        recs.append("   pip install -e /path/to/minerva")
    if not tools.get("ollama"):
        recs.append("[yellow]🔸 ollama 未安装，研究将回退到本地缓存回答[/yellow]")
        recs.append("   访问 https://ollama.com 安装并启动")
    else:
        ollama_running = _check_ollama_running()
        if not ollama_running:
            recs.append("[yellow]🔸 ollama 已安装但未运行，请启动：ollama serve[/yellow]")
    if not recs:
        recs.append("[green]✅ 所有推荐工具就绪，可以开始使用！[/green]")
    for r in recs:
        c.print(f"  {r}")
    c.print()

    # ── 第 3 步：快速上手指南 ──
    c.print(_panel("[bold]Step 3/4 — 快速上手指南[/bold]", "cyan", title="🚀"))
    guide = Table(box=box.ROUNDED, header_style="bold cyan")
    guide.add_column("步骤", style="bold", width=8)
    guide.add_column("命令", width=40)
    guide.add_column("说明", width=40)
    guide.add_row(
        "1",
        "[cyan]workspace demo[/]",
        "体验研究闭环（5 分钟）",
    )
    guide.add_row(
        "2",
        '[cyan]workspace research "主题"[/]',
        "发起你的第一个研究",
    )
    guide.add_row(
        "3",
        "[cyan]workspace research --list[/]",
        "浏览所有研究记录",
    )
    guide.add_row(
        "4",
        "[cyan]workspace status[/]",
        "查看工作台仪表板",
    )
    guide.add_row(
        "5",
        "[cyan]workspace daily[/]",
        "每日研究简报",
    )
    c.print(guide)
    c.print()

    # ── 第 4 步：下一步 ──
    c.print(_panel("[bold]Step 4/4 — 下一步[/bold]", "cyan", title="🎯"))
    c.print(r"  [bold]核心旅程:[/bold]")
    c.print(r"    import → research → open → ask → publish → dossier → timeline")
    c.print()
    c.print(r"  [bold]学习资源:[/bold]")
    c.print(r"    [cyan]workspace help[/]     — 产品地图与完整命令列表")
    c.print(r"    [cyan]workspace demo[/]     — 交互式演示")
    c.print()
    c.print(
        _panel(
            "[bold green]🎉 配置完成！现在就开始使用 workspace[/bold green]\n\n"
            '[cyan]workspace research "你的第一个研究主题"[/]',
            "green",
        )
    )
    return 0
