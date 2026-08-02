"""
cockpit.tui.app — Textual 全屏 TUI 应用主程序 (Phase 2 升级版)

特性:
  · 极客 Vim 键盘流：j/k/s/f// 快捷键支持与导航
  · 深空暗色自适应主题 CSS
  · Phase 2 新增：嵌入式命令输出可视化对话框 (CommandLogModal)
  · Phase 2 新增：网络探针后台轮询健康状态指示 (Agora / KOS 内存库)
  · Phase 2 新增：watchfiles 本地底层状态变更通知与列表重绘
"""

from __future__ import annotations

import logging

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Footer, Header

from cockpit.tui.file_watcher import watch_state_directory
from cockpit.tui.widgets import (
    CommandLogModal,
    CommandPalette,
    DetailPanel,
    ResearchListPanel,
    StatusBar,
)

logger = logging.getLogger(__name__)

COCKPIT_CSS = """
Screen {
    background: #0d1117;
    color: #c9d1d9;
}

/* ── Header ── */
Header {
    background: #161b22;
    color: #58a6ff;
    dock: top;
    height: 1;
}

/* ── 主操作区左/右布局 ── */
#main-layout {
    height: 1fr;
    layout: horizontal;
}

#research-list {
    width: 38%;
    border-right: solid #21262d;
}

#detail-panel {
    width: 62%;
    padding: 1 2;
}

/* ── 命令浮动面板 ── */
CommandPalette {
    dock: top;
    height: auto;
    max-height: 15;
    background: #161b22;
    border: solid #58a6ff;
    margin: 1 10;
}

CommandPalette.hidden {
    display: none;
}
"""


class CockpitTUIApp(App):
    """🛰️ Cockpit 极客终端交互控制台 (NextGen TUI Engine Phase 2)."""

    TITLE = "🛸 Cockpit Workspace"
    SUB_TITLE = "COMMAND CENTER · PHASE 2"
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
        """初始化应用状态，绑定探针定时器与后台目录监视器."""
        self.query_one(ResearchListPanel).focus()
        # 初始及每 15 秒扫描系统真实服务端口状态
        self._probe_health_timer()
        self.set_interval(15.0, self._probe_health_timer)
        # 启动 watchfiles 工作区被动感知
        self._start_file_watcher()

    def _probe_health_timer(self) -> None:
        """定时或主动请求状态栏执行探针刷新."""
        try:
            self.query_one(StatusBar).refresh_health_probe()
        except Exception as e:
            logger.debug("Health probe timer error: %s", e)

    @work(thread=True, exclusive=True)
    def _start_file_watcher(self) -> None:
        """后台独立线程运行 watchfiles 监控区变化."""

        def _on_change():
            self.call_from_thread(self._on_state_changed_main_thread)

        watch_state_directory(_on_change)

    def _on_state_changed_main_thread(self) -> None:
        """由 watchfiles 主线程安全回调：重载底层列表信息."""
        try:
            self.query_one(ResearchListPanel).refresh_topics()
            self.notify("🔔 收到系统底层变更广播，课题卡片已自动重绘", severity="information", timeout=2)
        except Exception:
            pass

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
        """主动触发数据与在线服务探针刷新."""
        self.query_one(ResearchListPanel).refresh_topics()
        self._probe_health_timer()
        self.notify("🔄 课题及系统健康信息已刷新", severity="information")

    def action_show_galaxy(self) -> None:
        """切换到 BOS 星系拓扑视图."""
        self.notify("🌌 BOS 星系拓扑 (Phase 3 拓扑计算准备中...)", severity="warning")

    def action_show_help(self) -> None:
        """显示全部键盘流操作提示."""
        self.notify(
            "j/k: 导航  |  s: 多维热度排序  |  f: 状态筛选  |  Enter: 展开  |  /: 搜索  |  :: 命令执行卡片  |  q: 退出",
            severity="information",
            timeout=6,
        )

    @on(ResearchListPanel.TopicSelected)
    def on_topic_selected(self, event: ResearchListPanel.TopicSelected) -> None:
        """响应课题选中事件，更新详情面板."""
        self.query_one(DetailPanel).show_topic(event.topic_data)

    @on(CommandPalette.CommandExecuted)
    def on_command_executed(self, event: CommandPalette.CommandExecuted) -> None:
        """收到命令选择执行事件，关闭面板并启动后台运行卡片."""
        self.query_one(CommandPalette).add_class("hidden")
        self.query_one(ResearchListPanel).focus()
        # 1. 顶部/底部提示指令名称
        self.query_one(StatusBar).set_running_command(event.command_name)
        # 2. Phase 2 嵌入式查看 stdout/stderr，不破坏 TUI 屏显
        self.push_screen(CommandLogModal(event.command_name))
