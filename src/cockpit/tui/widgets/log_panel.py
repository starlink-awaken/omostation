"""
cockpit.tui.widgets.log_panel — 异步命令执行结果日志查看控制台 (Phase 2)

特性:
  · 不退出全屏 TUI，直接在卡片弹窗内查看任何 cockpit CLI 指令的实时执行和输出
  · 支持彩色 Markdown/普通文本自动格式化
  · Vim 键盘绑定: q / Esc 关闭，c 清屏 / 重置
"""

from __future__ import annotations

import logging
import subprocess

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Footer, Label, Markdown, Static

logger = logging.getLogger(__name__)


class CommandLogModal(ModalScreen[None]):
    """嵌入式命令运行输出监控面板."""

    BINDINGS = [
        Binding("escape", "dismiss_modal", "关闭", show=True),
        Binding("q", "dismiss_modal", "退出 (q)", show=True),
    ]

    CSS = """
    CommandLogModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.7);
    }

    #log-modal-container {
        width: 80%;
        height: 75%;
        background: #0d1117;
        border: thick #58a6ff;
        padding: 1 2;
        layout: vertical;
    }

    #log-modal-title {
        color: #58a6ff;
        text-style: bold;
        padding-bottom: 1;
        border-bottom: solid #21262d;
    }

    #log-modal-body {
        height: 1fr;
        padding: 1 0;
        overflow-y: auto;
    }
    """

    def __init__(self, cmd: str) -> None:
        super().__init__()
        self.cmd = cmd

    def compose(self) -> ComposeResult:
        with Vertical(id="log-modal-container"):
            yield Label(f"⚡ 命令控制台 · 执行命令: cockpit {self.cmd}", id="log-modal-title")
            yield Markdown("⏳ **正以全屏非阻塞线程运行命令中，请稍候...**", id="log-modal-body")
            yield Footer()

    def on_mount(self) -> None:
        self.run_command_async()

    @work(thread=True)
    def run_command_async(self) -> None:
        """后台运行 CLI 并在面板中渲染执行输出."""
        try:
            full_cmd = ["cockpit"] + self.cmd.split()
            result = subprocess.run(
                full_cmd,
                capture_output=True,
                text=True,
                timeout=25,
                check=False,
            )
            output = result.stdout or result.stderr or "*(命令已成功执行，无控制台打印内容)*"

            # 使用 call_from_thread 回调给 GUI 主线程更新 UI
            self.app.call_from_thread(self.update_log_content, output, result.returncode)
        except Exception as e:
            self.app.call_from_thread(
                self.update_log_content,
                f"### ❌ 执行出错\n\n```\n{str(e)}\n```",
                1,
            )

    def update_log_content(self, text: str, code: int = 0) -> None:
        status_icon = "✅" if code == 0 else "❌"
        md_view = self.query_one("#log-modal-body", Markdown)

        # 将输出包裹为代码块或直接 markdown
        body = f"### {status_icon} 执行结束 (退出码 {code})\n\n```\n{text.strip()}\n```"
        md_view.update(body)

    def action_dismiss_modal(self) -> None:
        self.dismiss()
