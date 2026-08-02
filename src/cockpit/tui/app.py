"""
cockpit.tui.app — CockpitTUIApp 主应用 (Textual 全屏极客控制台)

布局:
  ┌─────────────────────────────────────────────────────────────┐
  │  Header: 🛰️ COCKPIT WORKSPACE COMMAND CENTER  [系统健康]     │
  ├────────────────────┬────────────────────────────────────────┤
  │  ResearchList      │  DetailPanel                           │
  │  (j/k 导航)        │  (时间线 + 追问记录 + 卡片关系)         │
  ├────────────────────┴────────────────────────────────────────┤
  │  Footer: 快捷键提示                                          │
  └─────────────────────────────────────────────────────────────┘
  [浮动叠加] CommandPalette (: 或 Ctrl+P 召唤)
"""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Header, Footer, Static, Label
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual import on

from cockpit.tui.widgets.research_list import ResearchListPanel
from cockpit.tui.widgets.detail_panel import DetailPanel
from cockpit.tui.widgets.command_palette import CommandPalette
from cockpit.tui.widgets.status_bar import StatusBar

COCKPIT_CSS = """
/* ── 全局配色：深邃太空暗色主题 ── */
Screen {
    background: #0d1117;
    color: #c9d1d9;
}

/* ── 主布局容器 ── */
#main-layout {
    height: 1fr;
    background: #0d1117;
}

/* ── 研究列表左栏 ── */
ResearchListPanel {
    width: 38;
    min-width: 32;
    border-right: solid #21262d;
    background: #161b22;
}

/* ── 详情右栏 ── */
DetailPanel {
    width: 1fr;
    background: #0d1117;
    padding: 0 1;
}

/* ── 状态栏 ── */
StatusBar {
    height: 3;
    background: #161b22;
    border-top: solid #21262d;
    padding: 0 2;
    color: #8b949e;
}

/* ── 浮动命令面板 ── */
CommandPalette {
    background: #161b22;
    border: solid #58a6ff;
    padding: 1 2;
    width: 60;
    height: auto;
    max-height: 20;
    offset: 20 5;
    layer: floating;
}

CommandPalette.hidden {
    display: none;
}

/* ── Header ── */
Header {
    background: #1c2128;
    color: #58a6ff;
    text-style: bold;
    height: 3;
}

/* ── Footer ── */
Footer {
    background: #161b22;
    color: #8b949e;
    height: 2;
}
"""


class CockpitTUIApp(App):
    """🛰️ Cockpit 极客终端交互控制台 (NextGen TUI Engine)."""

    TITLE = "🛸 Cockpit Workspace"
    SUB_TITLE = "COMMAND CENTER"
    CSS = COCKPIT_CSS
    BINDINGS = [
        Binding("q", "quit", "退出", priority=True),
        Binding("colon", "toggle_palette", "命令面板"),
        Binding("ctrl+p", "toggle_palette", "命令面板", show=False),
        Binding("g", "show_galaxy", "星系拓扑"),
        Binding("r", "refresh_data", "刷新"),
        Binding("?", "show_help", "帮助"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main-layout"):
            yield ResearchListPanel(id="research-list")
            yield DetailPanel(id="detail-panel")
        yield StatusBar(id="status-bar")
        yield CommandPalette(id="command-palette", classes="hidden")
        yield Footer()

    def on_mount(self) -> None:
        """初始化时聚焦研究列表."""
        self.query_one(ResearchListPanel).focus()

    def action_toggle_palette(self) -> None:
        """召唤 / 关闭浮动命令面板."""
        palette = self.query_one(CommandPalette)
        if "hidden" in palette.classes:
            palette.remove_class("hidden")
            palette.focus()
        else:
            palette.add_class("hidden")
            self.query_one(ResearchListPanel).focus()

    def action_refresh_data(self) -> None:
        """触发数据刷新."""
        self.query_one(ResearchListPanel).refresh_topics()
        self.notify("🔄 数据已刷新", severity="information")

    def action_show_galaxy(self) -> None:
        """切换到 BOS 星系拓扑视图 (Phase 3 占位)."""
        self.notify("🌌 BOS 星系拓扑 (Phase 3, Coming Soon)", severity="warning")

    def action_show_help(self) -> None:
        """显示快捷键帮助."""
        self.notify(
            "j/k: 导航  |  Enter: 展开详情  |  /: 搜索  |  :: 命令面板  |  g: 星系  |  q: 退出",
            severity="information",
            timeout=5,
        )

    @on(ResearchListPanel.TopicSelected)
    def on_topic_selected(self, event: ResearchListPanel.TopicSelected) -> None:
        """响应课题选中事件，更新详情面板."""
        self.query_one(DetailPanel).show_topic(event.topic)

    @on(CommandPalette.CommandExecuted)
    def on_command_executed(self, event: CommandPalette.CommandExecuted) -> None:
        """收到命令执行事件，关闭面板并执行."""
        self.query_one(CommandPalette).add_class("hidden")
        self.query_one(ResearchListPanel).focus()
        # 推送到 StatusBar 显示执行中状态
        self.query_one(StatusBar).set_running_command(event.command_name)
