"""
cockpit.tui.widgets.research_list — 研究课题列表面板

功能:
  · j/k 或方向键导航
  · / 激活实时模糊搜索
  · Enter 触发 TopicSelected 事件，更新右侧详情面板
  · 每个条目显示: 状态 Emoji + 主题名 + 追问数
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Input, ListView, ListItem, Label
from textual.message import Message
from textual.binding import Binding
from textual import on

from cockpit.tui.data_loader import load_research_topics


class ResearchListPanel(Widget):
    """左侧研究课题列表面板."""

    BINDINGS = [
        Binding("j", "cursor_down", "下", show=False),
        Binding("k", "cursor_up", "上", show=False),
        Binding("slash", "focus_search", "搜索"),
        Binding("enter", "select_topic", "展开详情", show=False),
    ]

    CSS = """
    ResearchListPanel {
        layout: vertical;
    }

    #list-header {
        background: #21262d;
        color: #58a6ff;
        text-style: bold;
        padding: 0 1;
        height: 1;
    }

    #search-input {
        height: 1;
        background: #0d1117;
        border: none;
        border-bottom: solid #30363d;
        color: #c9d1d9;
        padding: 0 1;
        display: none;
    }

    #search-input.visible {
        display: block;
    }

    #topic-list {
        height: 1fr;
        background: transparent;
        border: none;
        scrollbar-background: #161b22;
        scrollbar-color: #30363d;
    }

    ListItem {
        background: transparent;
        padding: 0 1;
        height: 2;
    }

    ListItem:hover {
        background: #1c2128;
    }

    ListItem.-highlight {
        background: #1c2128;
        border-left: solid #58a6ff;
    }

    .topic-name {
        color: #c9d1d9;
    }

    .topic-meta {
        color: #8b949e;
        text-style: italic;
    }
    """

    class TopicSelected(Message):
        """课题被选中事件."""
        def __init__(self, topic: dict) -> None:
            self.topic = topic
            super().__init__()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._all_topics: list[dict] = []
        self._filtered: list[dict] = []

    def compose(self) -> ComposeResult:
        yield Label("📚 研究课题", id="list-header")
        yield Input(placeholder="  🔍 模糊搜索...", id="search-input")
        yield ListView(id="topic-list")

    def on_mount(self) -> None:
        self.refresh_topics()

    def refresh_topics(self) -> None:
        """从 OMO 存储加载课题列表."""
        self._all_topics = load_research_topics()
        self._filtered = list(self._all_topics)
        self._render_list(self._filtered)

    def _render_list(self, topics: list[dict]) -> None:
        lv = self.query_one("#topic-list", ListView)
        lv.clear()
        for t in topics:
            status_icon = _status_icon(t.get("status", "active"))
            name = t.get("topic", "未知主题")
            ask_count = t.get("ask_count", 0)
            display = f"{status_icon} {name[:26]}"
            meta = f"   ↳ {ask_count} 追问" if ask_count else ""
            item = ListItem(
                Label(display, classes="topic-name"),
                Label(meta, classes="topic-meta") if meta else Label(""),
            )
            item.data = t  # 挂载原始数据
            lv.append(item)

    def action_cursor_down(self) -> None:
        self.query_one("#topic-list", ListView).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one("#topic-list", ListView).action_cursor_up()

    def action_focus_search(self) -> None:
        inp = self.query_one("#search-input", Input)
        inp.add_class("visible")
        inp.focus()

    def action_select_topic(self) -> None:
        lv = self.query_one("#topic-list", ListView)
        if lv.highlighted_child and hasattr(lv.highlighted_child, "data"):
            self.post_message(self.TopicSelected(lv.highlighted_child.data))

    @on(Input.Changed, "#search-input")
    def on_search_changed(self, event: Input.Changed) -> None:
        query = event.value.lower().strip()
        if not query:
            self._filtered = list(self._all_topics)
        else:
            self._filtered = [
                t for t in self._all_topics
                if query in t.get("topic", "").lower()
            ]
        self._render_list(self._filtered)

    @on(Input.Submitted, "#search-input")
    def on_search_submitted(self, _) -> None:
        inp = self.query_one("#search-input", Input)
        inp.remove_class("visible")
        self.query_one("#topic-list", ListView).focus()

    @on(ListView.Selected)
    def on_list_selected(self, event: ListView.Selected) -> None:
        if hasattr(event.item, "data"):
            self.post_message(self.TopicSelected(event.item.data))


def _status_icon(status: str) -> str:
    return {
        "active": "✅",
        "archived": "📦",
        "quarantined": "🔒",
        "stale": "⏳",
    }.get(status, "📄")
