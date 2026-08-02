"""
cockpit.tui.widgets.detail_panel — 研究课题详情右栏面板

功能:
  · 展示研究课题的完整上下文：摘要、状态、时间线、追问历史
  · 内容以 Rich Markdown 渲染（Textual 原生支持）
  · 快捷键: a(ask), p(publish), o(open in editor)
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Markdown, Label
from textual.containers import ScrollableContainer
from textual.binding import Binding


_EMPTY_MD = """
# 📋 研究详情

> 从左侧列表选择一个研究课题开始。
> 使用 **j / k** 上下导航，**Enter** 展开详情。

---

**快捷键提示**:

| 键 | 动作 |
|---|---|
| `j` / `k` | 在课题列表上下移动 |
| `/` | 激活实时模糊搜索 |
| `:` 或 `Ctrl+P` | 打开命令面板 |
| `a` | 对当前课题追问 (ask) |
| `p` | 发布当前课题 (publish) |
| `g` | 切换 BOS 星系拓扑视图 |
| `?` | 显示所有快捷键 |
| `q` | 退出 TUI |
"""


class DetailPanel(Widget):
    """右侧研究课题详情面板."""

    BINDINGS = [
        Binding("a", "ask_topic", "追问"),
        Binding("p", "publish_topic", "发布"),
    ]

    CSS = """
    DetailPanel {
        layout: vertical;
        padding: 1 2;
    }

    #detail-content {
        height: 1fr;
        background: transparent;
    }

    Markdown {
        background: transparent;
        color: #c9d1d9;
    }

    Markdown h1 {
        color: #58a6ff;
        text-style: bold;
    }

    Markdown h2 {
        color: #3fb950;
        text-style: bold;
    }

    Markdown code {
        background: #21262d;
        color: #f0883e;
    }

    Markdown blockquote {
        color: #8b949e;
        border-left: solid #30363d;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._current_topic: dict | None = None

    def compose(self) -> ComposeResult:
        with ScrollableContainer(id="detail-content"):
            yield Markdown(_EMPTY_MD)

    def show_topic(self, topic: dict) -> None:
        """渲染指定课题的详情卡片."""
        self._current_topic = topic
        md = self._build_markdown(topic)
        self.query_one(Markdown).update(md)

    def _build_markdown(self, topic: dict) -> str:
        name = topic.get("topic", "未知主题")
        status = topic.get("status", "active")
        research_id = topic.get("id", "?")
        ask_count = topic.get("ask_count", 0)
        created = topic.get("created_at", "未知")
        updated = topic.get("updated_at", "未知")
        summary = topic.get("summary", "")

        status_label = {
            "active": "✅ 活跃",
            "archived": "📦 已归档",
            "quarantined": "🔒 隔离",
            "stale": "⏳ 半衰",
        }.get(status, status)

        ask_section = ""
        asks = topic.get("asks", [])
        if asks:
            ask_lines = "\n".join(
                f"  {i+1}. {a.get('query', '')[:60]}"
                for i, a in enumerate(asks[:5])
            )
            ask_section = f"\n## 💬 近期追问记录\n\n{ask_lines}\n"

        return f"""# {name}

---

**ID**: `{research_id}`  |  **状态**: {status_label}  |  **追问数**: {ask_count}

**创建**: {created}  |  **最后更新**: {updated}

## 📝 摘要

{summary or '> 暂无摘要'}

{ask_section}

---

> **快捷键**: `a` — 追问  ·  `p` — 发布  ·  `: research open {research_id}` — 命令面板打开
"""

    def action_ask_topic(self) -> None:
        if self._current_topic:
            rid = self._current_topic.get("id", "")
            self.app.notify(
                f"💬 ask {rid} — 在命令面板中输入追问内容",
                severity="information",
            )

    def action_publish_topic(self) -> None:
        if self._current_topic:
            rid = self._current_topic.get("id", "")
            self.app.notify(
                f"📤 publish {rid} — 正在发布... (使用命令面板输入 'publish')",
                severity="information",
            )
