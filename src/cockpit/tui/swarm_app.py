"""
cockpit.tui.swarm_app — Textual 1.x 全屏 Multi-Agent 实时协作监控大盘 (bin/omo-top)

特性:
- 4 象限实时互动综览 (Overview)
- 1~4 快捷键深潜 Tab 视图 (Agents/Locks, Submodules, Logs)
- 毫秒级本地状态解析 + 异步后台探测
- 深空暗色主题与呼吸灯状态指示
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Grid, Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    DataTable,
    Footer,
    Header,
    Label,
    RichLog,
    Static,
    TabbedContent,
    TabPane,
)

from cockpit.tui.swarm_collector import SwarmGlobalState, SwarmStateCollector

logger = logging.getLogger(__name__)

SWARM_TUI_CSS = """
Screen {
    background: #0d1117;
    color: #c9d1d9;
}

Header {
    background: #161b22;
    color: #58a6ff;
    dock: top;
    height: 1;
}

/* 顶部 Stat Cards Bar */
#stat-bar {
    height: 4;
    layout: horizontal;
    background: #161b22;
    border-bottom: solid #30363d;
    padding: 0 1;
}

.stat-card {
    width: 1fr;
    height: 100%;
    border: round #30363d;
    background: #0d1117;
    margin: 0 1;
    padding: 0 1;
}

.stat-card:hover {
    border: round #58a6ff;
}

.stat-title {
    color: #8b949e;
    text-style: bold;
}

.stat-value {
    color: #58a6ff;
    text-style: bold;
}

/* Tab 容器 */
TabbedContent {
    height: 1fr;
}

TabPane {
    padding: 0 1;
}

/* 4 象限 Grid 布局 */
#overview-grid {
    layout: grid;
    grid-size: 2 2;
    grid-gutter: 1;
    height: 100%;
}

.quadrant-panel {
    border: round #30363d;
    background: #161b22;
    padding: 0 1;
    height: 100%;
}

.panel-header {
    background: #21262d;
    color: #58a6ff;
    text-style: bold;
    padding: 0 1;
    margin-bottom: 1;
}

/* DataTable 自适应 */
DataTable {
    background: #0d1117;
    border: none;
    height: 1fr;
}

RichLog {
    background: #0d1117;
    border: round #30363d;
    padding: 0 1;
    height: 1fr;
}
"""


class SwarmObservabilityApp(App):
    """Multi-Agent Swarm 终端全屏监控大盘。"""

    TITLE = "🛰️  OMOSTATION SWARM OBSERVABILITY"
    SUB_TITLE = "Multi-Agent Control Plane"
    CSS = SWARM_TUI_CSS

    BINDINGS = [
        Binding("1", "switch_tab('tab-overview')", "Overview", show=True),
        Binding("2", "switch_tab('tab-agents')", "Agents & Locks", show=True),
        Binding("3", "switch_tab('tab-subs')", "Submodules Radar", show=True),
        Binding("4", "switch_tab('tab-logs')", "A2A Event Stream", show=True),
        Binding("5", "switch_tab('tab-compute')", "Compute HUD", show=True),
        Binding("r", "refresh_now", "Refresh", show=True),
        Binding("space", "toggle_pause", "Pause/Resume", show=True),
        Binding("q", "quit", "Quit", show=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.collector = SwarmStateCollector()
        self.paused = False
        self.current_state: SwarmGlobalState | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        # 顶部 Stat Cards Bar
        with Horizontal(id="stat-bar"):
            with Container(classes="stat-card", id="card-agents"):
                yield Label("● AGENT SWARM", classes="stat-title")
                yield Label("Loading...", id="val-agents", classes="stat-value")
            with Container(classes="stat-card", id="card-locks"):
                yield Label("🔒 CONCURRENCY LOCKS", classes="stat-title")
                yield Label("Loading...", id="val-locks", classes="stat-value")
            with Container(classes="stat-card", id="card-bets"):
                yield Label("📈 3Y BET LEDGER", classes="stat-title")
                yield Label("Loading...", id="val-bets", classes="stat-value")
            with Container(classes="stat-card", id="card-subs"):
                yield Label("🧭 SUBMODULE RADAR", classes="stat-title")
                yield Label("Loading...", id="val-subs", classes="stat-value")

        # TabbedContent 分页
        with TabbedContent(id="tabs"):
            with TabPane("[1] 4-Quadrant Overview", id="tab-overview"):
                with Grid(id="overview-grid"):
                    with Vertical(classes="quadrant-panel"):
                        yield Label("🤖 Agent Swarm Health", classes="panel-header")
                        yield DataTable(id="dt-overview-agents")
                    with Vertical(classes="quadrant-panel"):
                        yield Label("📈 BET Tracks Progress", classes="panel-header")
                        yield DataTable(id="dt-overview-bets")
                    with Vertical(classes="quadrant-panel"):
                        yield Label("🧭 Submodule Pointers", classes="panel-header")
                        yield DataTable(id="dt-overview-subs")
                    with Vertical(classes="quadrant-panel"):
                        yield Label("💬 Recent A2A Stream", classes="panel-header")
                        yield DataTable(id="dt-overview-msgs")

            with TabPane("[2] Agents & Locks", id="tab-agents"):
                with Vertical():
                    yield Label("● Active Agents Detail", classes="panel-header")
                    yield DataTable(id="dt-full-agents")
                    yield Label("🔒 Active Concurrency Locks", classes="panel-header")
                    yield DataTable(id="dt-full-locks")

            with TabPane("[3] Submodules Radar", id="tab-subs"):
                with Vertical():
                    yield Label("🧭 19 Submodules Full Radar", classes="panel-header")
                    yield DataTable(id="dt-full-subs")

            with TabPane("[4] Live Event Logs", id="tab-logs"):
                with Vertical():
                    yield Label("💬 A2A Realtime Communication Stream", classes="panel-header")
                    yield RichLog(id="log-a2a", wrap=True, highlight=True, markup=True)

            with TabPane("[5] Compute HUD", id="tab-compute"):
                from cockpit.tui.widgets.compute_hud import ComputeHUDWidget

                with VerticalScroll():
                    yield ComputeHUDWidget(id="widget-compute-hud")

        yield Footer()

    def on_mount(self) -> None:
        """初始化表格列并启动 2s 定时轮询。"""
        # 初始化各个 DataTable 列
        dt_oa = self.query_one("#dt-overview-agents", DataTable)
        dt_oa.add_columns("AGENT", "STATE", "ACTION", "SEEN")

        dt_ob = self.query_one("#dt-overview-bets", DataTable)
        dt_ob.add_columns("TRACK", "PROGRESS", "DONE")

        dt_os = self.query_one("#dt-overview-subs", DataTable)
        dt_os.add_columns("MODULE", "SHA", "STATUS")

        dt_om = self.query_one("#dt-overview-msgs", DataTable)
        dt_om.add_columns("ROUTE", "ACTION/EVENT")

        dt_fa = self.query_one("#dt-full-agents", DataTable)
        dt_fa.add_columns("AGENT", "STATUS", "CURRENT ACTION", "LAST TICK ISO", "AGE")

        dt_fl = self.query_one("#dt-full-locks", DataTable)
        dt_fl.add_columns("LOCK NAME", "AGE (SEC)", "STATUS")

        dt_fs = self.query_one("#dt-full-subs", DataTable)
        dt_fs.add_columns("NAME", "LOCAL SHA", "REMOTE SHA", "PATH", "STATUS")

        # 首次加载
        self.fetch_data_worker()
        # 启动定时器（每 2 秒一次）
        self.set_interval(2.0, self.periodic_refresh)

    def periodic_refresh(self) -> None:
        if not self.paused:
            self.fetch_data_worker()

    @work(exclusive=True, thread=True)
    def fetch_data_worker(self) -> None:
        """后台线程异步采集数据，不阻塞 UI 渲染。"""
        try:
            state = self.collector.collect_all(probe_remote_submodules=False)
            self.call_from_thread(self.update_ui, state)
        except Exception as e:
            logger.debug("Fetch worker error: %s", e)

    def update_ui(self, state: SwarmGlobalState) -> None:
        """主线程更新所有 UI 组件。"""
        self.current_state = state

        # 1. 更新顶部 Stat Cards
        st_agents = f"{state.agents.healthy_count}/{state.agents.total_agents} Active"
        self.query_one("#val-agents", Label).update(
            f"[green]{st_agents}[/green]" if state.agents.healthy_count > 0 else f"[yellow]{st_agents}[/yellow]"
        )

        st_locks = f"{state.locks.active_runs} Runs / {state.locks.stale_locks} Stale"
        self.query_one("#val-locks", Label).update(
            f"[cyan]{st_locks}[/cyan]" if state.locks.stale_locks == 0 else f"[yellow]{st_locks}[/yellow]"
        )

        st_bets = f"{state.bets.done_count}/{state.bets.total_bets} ({state.bets.overall_percent}%)"
        self.query_one("#val-bets", Label).update(f"[green]{st_bets}[/green]")

        st_subs = f"{state.submodules.aligned_count}/{state.submodules.total_submodules} Aligned"
        self.query_one("#val-subs", Label).update(
            f"[cyan]{st_subs}[/cyan]" if state.submodules.drifted_count == 0 else f"[red]{st_subs}[/red]"
        )

        # 2. 更新 Overview Grid 表格
        dt_oa = self.query_one("#dt-overview-agents", DataTable)
        dt_oa.clear()
        for a in state.agents.agents:
            st = "[green]● active[/green]" if a.status == "healthy" else "[yellow]◌ stale[/yellow]"
            age = f"{int(a.seconds_ago)}s" if a.seconds_ago >= 0 else "?"
            dt_oa.add_row(a.name, Text.from_markup(st), a.action, age)

        dt_ob = self.query_one("#dt-overview-bets", DataTable)
        dt_ob.clear()
        for tr in state.bets.tracks[:8]:
            bar = "█" * int(tr.percent / 10) + "░" * (10 - int(tr.percent / 10))
            color = "green" if tr.percent >= 70 else "yellow"
            dt_ob.add_row(
                tr.track,
                Text.from_markup(f"[{color}]{bar}[/] {tr.percent}%"),
                f"{tr.done}/{tr.total}",
            )

        dt_os = self.query_one("#dt-overview-subs", DataTable)
        dt_os.clear()
        for sub in state.submodules.items[:8]:
            st = "[green]● ok[/green]" if sub.drift_status == "aligned" else "[red]✖ drift[/red]"
            dt_os.add_row(sub.name, sub.current_sha, Text.from_markup(st))

        dt_om = self.query_one("#dt-overview-msgs", DataTable)
        dt_om.clear()
        for m in state.recent_messages[:8]:
            dt_om.add_row(f"{m.from_agent}→{m.to_agent}", m.summary[:30])

        # 3. 更新 Full Agents & Locks 页
        dt_fa = self.query_one("#dt-full-agents", DataTable)
        dt_fa.clear()
        for a in state.agents.agents:
            st = "[green]HEALTHY[/green]" if a.status == "healthy" else "[yellow]STALE[/yellow]"
            dt_fa.add_row(
                a.name,
                Text.from_markup(st),
                a.action,
                a.last_seen_iso,
                f"{int(a.seconds_ago)}s ago",
            )

        dt_fl = self.query_one("#dt-full-locks", DataTable)
        dt_fl.clear()
        if state.locks.details:
            for lk in state.locks.details:
                st = "[yellow]STALE[/yellow]" if lk.get("stale") else "[green]ACTIVE[/green]"
                dt_fl.add_row(lk.get("name", "?"), f"{int(lk.get('age_seconds', 0))}s", Text.from_markup(st))
        else:
            dt_fl.add_row("No active file locks in .omo/state/locks", "-", "[dim]CLEAN[/dim]")

        # 4. 更新 Full Submodules Radar 页
        dt_fs = self.query_one("#dt-full-subs", DataTable)
        dt_fs.clear()
        for s in state.submodules.items:
            st = "[green]ALIGNED[/green]" if s.drift_status == "aligned" else "[bold red]DRIFTED[/bold red]"
            dt_fs.add_row(s.name, s.current_sha, s.remote_sha, s.path, Text.from_markup(st))

        # 5. 更新 A2A Event Stream Logs
        rlog = self.query_one("#log-a2a", RichLog)
        rlog.clear()
        for m in state.recent_messages:
            color = "cyan"
            if m.msg_type == "broadcast":
                color = "yellow"
            elif m.msg_type == "reply":
                color = "green"
            elif m.msg_type == "alert":
                color = "red"

            time_short = m.ts_iso[11:19] if len(m.ts_iso) >= 19 else m.ts_iso
            rlog.write(
                f"[dim]{time_short}[/dim] [{color}]{m.msg_type.upper()}[/{color}] "
                f"[bold white]{m.from_agent} → {m.to_agent}[/bold white]: {m.summary}"
            )

    def action_switch_tab(self, tab_id: str) -> None:
        """快捷键切换 Tab。"""
        self.query_one("#tabs", TabbedContent).active = tab_id

    def action_refresh_now(self) -> None:
        """立即强制刷新。"""
        self.notify("Refreshing swarm state...", timeout=1.0)
        self.fetch_data_worker()

    def action_toggle_pause(self) -> None:
        """暂停/继续自刷新。"""
        self.paused = not self.paused
        status_msg = "PAUSED (press Space to resume)" if self.paused else "RESUMED (2s auto-refresh)"
        self.notify(status_msg, timeout=1.5)


def main() -> None:
    app = SwarmObservabilityApp()
    app.run()


if __name__ == "__main__":
    main()
