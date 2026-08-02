"""
cockpit.tui.widgets.status_bar — 底部状态栏 (Phase 2 升级版)

展示:
  · 实时动态系统健康状态 (调用 health_probe 监测 Agora / KOS 实际存活度)
  · 当前选中的研究课题或运行任务
  · 最近执行的命令及输出日志指示
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Label

from cockpit.tui.health_probe import probe_system_health


class StatusBar(Widget):
    """底部系统状态栏 (集成系统服务在线探针)."""

    CSS = """
    StatusBar {
        height: 2;
        background: #161b22;
        border-top: solid #21262d;
        layout: horizontal;
        align: left middle;
        padding: 0 2;
    }

    #health-indicator {
        color: #3fb950;
        margin-right: 3;
    }

    #cmd-indicator {
        color: #8b949e;
        margin-left: 2;
    }
    """

    def compose(self) -> ComposeResult:
        yield Label("🟢 Agora SSE  ● KOS Memory", id="health-indicator")
        yield Label("", id="cmd-indicator")

    def set_running_command(self, cmd: str) -> None:
        """显示正在执行的命令."""
        self.query_one("#cmd-indicator", Label).update(
            f"⚡ 执行中: [cyan]{cmd}[/]"
        )

    def set_idle_command(self, msg: str = "就绪") -> None:
        """重置命令状态指示."""
        self.query_one("#cmd-indicator", Label).update(f"[dim]{msg}[/]")

    def refresh_health_probe(self) -> None:
        """异步/定时调用服务健康探针."""
        try:
            status = probe_system_health()
            label_text = status.get("summary_label", "⚪ Agora  ⚪ KOS")
            self.query_one("#health-indicator", Label).update(label_text)
        except Exception:
            self.query_one("#health-indicator", Label).update("⚪ 探针降级")
