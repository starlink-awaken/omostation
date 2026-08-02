"""
cockpit.tui.widgets.research_list — 左侧研究课题列表面板 (Phase 2 升级版)

特性:
  · 支持 Vim j/k 极速上下浏览
  · 支持 / 触发局部模糊过滤
  · Phase 2 新增 s 快捷键循环多维排序 (活跃度 / 字典序 / 状态)
  · Phase 2 新增 f 快捷键循环多维状态筛选 (全部 / active / draft / done)
  · 自定义 TopicSelected 消息，选中时自动广播给 DetailPanel
"""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Input, Label, ListItem, ListView

from cockpit.tui.data_loader import load_research_topics


class ResearchListPanel(Widget):
    """左侧研究课题列表与多维过滤器."""

    class TopicSelected(Message):
        """当用户选中某个课题时触发事件."""

        def __init__(self, topic_data: dict) -> None:
            self.topic_data = topic_data
            self.topic = topic_data
            super().__init__()

    BINDINGS = [
        Binding("j", "cursor_down", "下", show=False),
        Binding("k", "cursor_up", "上", show=False),
        Binding("slash", "focus_search", "搜索", show=True),
        Binding("s", "toggle_sort", "排序", show=True),
        Binding("f", "toggle_filter", "过滤", show=True),
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

    ListItem.-selected {
        background: #1f6feb;
        color: #ffffff;
    }

    .topic-name {
        text-style: bold;
    }

    .topic-meta {
        color: #8b949e;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._all_topics: list[dict] = []
        self._filtered: list[dict] = []
        self._sort_modes = [("ask_count", "热度"), ("topic", "名称"), ("status", "状态")]
        self._sort_idx = 0
        self._filter_modes = [("ALL", "全部"), ("active", "活跃"), ("draft", "草稿"), ("done", "归类")]
        self._filter_idx = 0

    def compose(self) -> ComposeResult:
        yield Label("📚 研究课题  [热度 | 全部]", id="list-header")
        yield Input(placeholder="🔍 输入关键字...", id="search-input")
        yield ListView(id="topic-list")

    def on_mount(self) -> None:
        self.refresh_topics()

    def refresh_topics(self) -> None:
        """从 OMO 存储加载课题列表并应用当前的过滤排序策略."""
        self._all_topics = load_research_topics()
        self.apply_filter_and_sort()

    def apply_filter_and_sort(self, query: str = "") -> None:
        """核心处理函数：状态筛选 + 关键字搜索 + 多维度自动排序."""
        sort_field, sort_label = self._sort_modes[self._sort_idx]
        filter_status, filter_label = self._filter_modes[self._filter_idx]

        # 1. 状态筛选
        topics = self._all_topics
        if filter_status != "ALL":
            topics = [t for t in topics if t.get("status", "active") == filter_status]

        # 2. 搜索框关键字符匹配
        if query:
            topics = [t for t in topics if query in t.get("topic", "").lower()]

        # 3. 排序规则
        if sort_field == "ask_count":
            topics = sorted(topics, key=lambda x: x.get("ask_count", 0), reverse=True)
        else:
            topics = sorted(topics, key=lambda x: str(x.get(sort_field, "")))

        self._filtered = topics
        self._render_list(self._filtered)

        # 4. 更新 header 标签提示
        header = self.query_one("#list-header", Label)
        header.update(f"📚 研究课题  [{sort_label} | {filter_label}] ({len(topics)})")

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
            item.data = t
            lv.append(item)

    def action_cursor_down(self) -> None:
        self.query_one("#topic-list", ListView).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one("#topic-list", ListView).action_cursor_up()

    def action_focus_search(self) -> None:
        inp = self.query_one("#search-input", Input)
        inp.add_class("visible")
        inp.focus()

    def action_toggle_sort(self) -> None:
        """循环多维排序键."""
        self._sort_idx = (self._sort_idx + 1) % len(self._sort_modes)
        self.apply_filter_and_sort()

    def action_toggle_filter(self) -> None:
        """循环筛选状态标签."""
        self._filter_idx = (self._filter_idx + 1) % len(self._filter_modes)
        self.apply_filter_and_sort()

    def action_select_topic(self) -> None:
        lv = self.query_one("#topic-list", ListView)
        if lv.highlighted_child and hasattr(lv.highlighted_child, "data"):
            self.post_message(self.TopicSelected(lv.highlighted_child.data))

    @on(Input.Changed, "#search-input")
    def on_search_changed(self, event: Input.Changed) -> None:
        query = event.value.lower().strip()
        self.apply_filter_and_sort(query=query)

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
        "active": "🟢",
        "draft": "🟡",
        "done": "✅",
        "archived": "📦",
    }.get(status, "⚪")
