"""
cockpit.tui.widgets.command_palette — VSCode 风格浮动命令面板

功能:
  · SSOT COMMAND_CATALOG 驱动，65 个命令零重复定义
  · 实时模糊匹配 (输入 'res pub' → research publish)
  · Enter 触发 CommandExecuted 事件
  · Esc / 失焦自动关闭
"""

from __future__ import annotations

import subprocess
import sys

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Input, Label, ListItem, ListView


class CommandPalette(Widget):
    """VSCode 风格浮动命令面板."""

    BINDINGS = [
        Binding("escape", "close_palette", "关闭", show=False),
    ]

    CSS = """
    CommandPalette {
        layout: vertical;
        background: #161b22;
        border: solid #58a6ff;
        padding: 1 2;
    }

    #palette-title {
        color: #58a6ff;
        text-style: bold;
        padding: 0 0 1 0;
    }

    #palette-input {
        background: #0d1117;
        border: solid #30363d;
        color: #c9d1d9;
        margin-bottom: 1;
    }

    #palette-list {
        background: transparent;
        border: none;
        height: auto;
        max-height: 12;
    }

    ListItem {
        background: transparent;
        padding: 0 1;
        height: 1;
    }

    ListItem.-highlight {
        background: #1c2128;
    }

    .cmd-name {
        color: #58a6ff;
        text-style: bold;
    }

    .cmd-sep {
        color: #30363d;
    }

    .cmd-summary {
        color: #8b949e;
    }

    #palette-hint {
        color: #8b949e;
        text-style: italic;
        padding: 1 0 0 0;
    }
    """

    class CommandExecuted(Message):
        """命令已执行事件."""

        def __init__(self, command_name: str) -> None:
            self.command_name = command_name
            super().__init__()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._catalog: list[dict] = []
        self._filtered: list[dict] = []

    def compose(self) -> ComposeResult:
        yield Label("⚡ COMMAND PALETTE", id="palette-title")
        yield Input(placeholder="输入命令名称（支持模糊匹配，如 'res pub'）...", id="palette-input")
        yield ListView(id="palette-list")
        yield Label("↑↓ 选择  ·  Enter 执行  ·  Esc 关闭", id="palette-hint")

    def on_mount(self) -> None:
        self._load_catalog()
        self._filtered = list(self._catalog)
        self._render_list(self._filtered)
        self.query_one("#palette-input", Input).focus()

    def _load_catalog(self) -> None:
        """从 COMMAND_CATALOG 加载命令元数据."""
        try:
            from cockpit.commands.registry import COMMAND_CATALOG

            self._catalog = [
                {
                    "name": meta.name,
                    "summary": meta.summary,
                    "category": meta.category,
                }
                for meta in COMMAND_CATALOG.values()
            ]
        except Exception:
            self._catalog = []

    def _render_list(self, items: list[dict]) -> None:
        lv = self.query_one("#palette-list", ListView)
        lv.clear()
        for item in items[:12]:  # 最多显示 12 条
            name = item["name"]
            summary = item["summary"][:35] if item["summary"] else ""
            row = ListItem(
                Label(f"[bold cyan]{name}[/]  [dim]—[/]  [dim]{summary}[/]"),
            )
            row.data = item
            lv.append(row)

    @on(Input.Changed, "#palette-input")
    def on_input_changed(self, event: Input.Changed) -> None:
        """实时模糊匹配：支持空格分词多段模式（如 'res pub'）."""
        tokens = event.value.lower().split()
        if not tokens:
            self._filtered = list(self._catalog)
        else:
            self._filtered = [
                cmd
                for cmd in self._catalog
                if all(t in cmd["name"].lower() or t in cmd["summary"].lower() for t in tokens)
            ]
        self._render_list(self._filtered)

    @on(Input.Submitted, "#palette-input")
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """回车选中当前高亮条目并执行."""
        lv = self.query_one("#palette-list", ListView)
        if lv.highlighted_child and hasattr(lv.highlighted_child, "data"):
            self._execute(lv.highlighted_child.data)

    @on(ListView.Selected)
    def on_list_selected(self, event: ListView.Selected) -> None:
        if hasattr(event.item, "data"):
            self._execute(event.item.data)

    def _execute(self, cmd_data: dict) -> None:
        """异步后台执行命令，通知父应用."""
        cmd_name = cmd_data["name"]
        self.post_message(self.CommandExecuted(cmd_name))
        # 异步调用底层 CLI（非阻塞，日志渲染由父应用 StatusBar 负责）
        try:
            subprocess.Popen(
                [sys.executable, "-m", "cockpit", cmd_name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass

    def action_close_palette(self) -> None:
        self.add_class("hidden")
        self.app.query_one("#research-list").focus()
