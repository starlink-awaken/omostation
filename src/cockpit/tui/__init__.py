"""
cockpit.tui — 极客终端交互控制台 (NextGen TUI Engine)

设计原则:
  · Textual (asyncio + CSS-in-Terminal) 作为核心引擎
  · SSOT COMMAND_CATALOG 驱动，零重复定义
  · 优雅降级：若 textual 未安装，透明回退到 Rich 静态版面
  · Vim 键盘流 + VSCode 风格浮动命令面板

用法:
  cockpit tui                    # 启动全屏 TUI
  cockpit status --output tui    # 通过 output 切面进入 TUI
"""

__all__ = [
    "launch",
    "is_tui_available",
    "launch_swarm_top",
    "render_swarm_status",
    "SwarmStateCollector",
    "SovereignCockpitApp",
    "CockpitTUIApp",
]


def launch_swarm_top() -> int:
    """启动 Multi-Agent Swarm 实时监控大盘 (omo-top)。"""
    if is_tui_available():
        from cockpit.tui.swarm_app import SwarmObservabilityApp

        app = SwarmObservabilityApp()
        app.run()
        return 0
    else:
        from cockpit.tui.swarm_cli import main as cli_main

        cli_main()
        return 0


def render_swarm_status() -> None:
    """渲染 Multi-Agent Swarm 单次快照 (omo-status)。"""
    from cockpit.tui.swarm_cli import main as cli_main

    cli_main()


def is_tui_available() -> bool:
    """检测 Textual 是否可用（用于优雅降级判断）."""
    try:
        import importlib.util

        return importlib.util.find_spec("textual") is not None
    except Exception:
        return False


def launch(args=None) -> int:
    """启动 TUI 控制台入口，自动检测并降级."""
    if is_tui_available():
        from cockpit.tui.app import CockpitTUIApp

        app = CockpitTUIApp()
        app.run()
        return 0
    else:
        # 优雅降级：打印提示并回落到 Rich 静态版
        from rich.console import Console
        from rich.panel import Panel

        c = Console()
        c.print(
            Panel(
                "[bold yellow]⚠️  TUI 增强模式需要安装 textual[/bold yellow]\n\n"
                "安装方式:\n"
                "  [cyan]pip install textual[/]\n\n"
                "当前已回落至静态版面（功能完整，体验降级）。\n"
                "运行 [cyan]cockpit status[/] 查看当前研究工作台。",
                title="🛸 Cockpit TUI",
                border_style="yellow",
            )
        )
        return 0
