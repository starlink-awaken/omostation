"""
cockpit.tui.widgets.status_bar — 底部状态栏

展示:
  · 实时系统健康状态 (Agora / KOS)
  · 当前选中课题
  · 最近执行的命令
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Label
from textual.containers import Horizontal


class StatusBar(Widget):
    """底部系统状态栏."""

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
        yield Label("🟢 Agora SSE  ● KOS", id="health-indicator")
        yield Label("", id="cmd-indicator")

    def set_running_command(self, cmd: str) -> None:
        """显示正在执行的命令."""
        self.query_one("#cmd-indicator", Label).update(
            f"⚡ 执行中: [cyan]{cmd}[/]"
        )
        # 3 秒后自动清除
        self.set_timer(3.0, self._clear_command)

    def _clear_command(self) -> None:
        try:
            self.query_one("#cmd-indicator", Label).update("")
        except Exception:
            pass
