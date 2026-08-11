"""Small keyboard-only overlays shared by the compute cockpit."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Static


class OverlayScreen(ModalScreen[None]):
    BINDINGS = [Binding("escape", "close", "Close", show=False)]
    DEFAULT_CSS = """
    OverlayScreen {
        align: center middle;
        background: $background 70%;
    }
    OverlayScreen > Vertical {
        width: 72;
        max-width: 92%;
        height: auto;
        max-height: 80%;
        padding: 1 2;
        border: round $accent;
        background: $surface;
    }
    OverlayScreen Static {
        width: 1fr;
        height: auto;
    }
    OverlayScreen Input {
        margin-top: 1;
    }
    """

    def action_close(self) -> None:
        self.dismiss(None)


class JumpScreen(ModalScreen[str | None]):
    BINDINGS = [Binding("escape", "close", "Close", show=False)]
    DEFAULT_CSS = OverlayScreen.DEFAULT_CSS.replace("OverlayScreen", "JumpScreen")
    _choices = {
        "1": "overview",
        "2": "nodes",
        "3": "models",
        "4": "routes",
        "5": "jobs",
        "6": "performance",
        "7": "logs",
        "8": "settings",
    }

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static(
                "[b]快速跳转[/b]\n"
                "1 总览  2 节点  3 模型  4 路由\n"
                "5 任务  6 性能  7 日志  8 设置\n\nEsc 关闭"
            )
        )

    def on_key(self, event: object) -> None:
        key = getattr(event, "key", None)
        if key in self._choices:
            self.dismiss(self._choices[key])

    def action_close(self) -> None:
        self.dismiss(None)


class SearchScreen(OverlayScreen):
    def compose(self) -> ComposeResult:
        yield Vertical(
            Static("[b]搜索当前资源[/b]\n输入仅用于本地页面过滤，不发送到后端。"),
            Input(placeholder="节点、模型或任务 ID", id="search-input"),
        )


class CommandScreen(ModalScreen[str | None]):
    BINDINGS = [Binding("escape", "close", "Close", show=False)]
    DEFAULT_CSS = OverlayScreen.DEFAULT_CSS.replace("OverlayScreen", "CommandScreen")

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static("[b]命令面板[/b]\n查询直接执行；R1/R2 操作必须经过确认门。"),
            Input(placeholder="例如：models load local/model", id="command-input"),
        )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        command = event.value.strip()
        self.dismiss(command or None)

    def action_close(self) -> None:
        self.dismiss(None)


class HelpScreen(OverlayScreen):
    def compose(self) -> ComposeResult:
        yield Vertical(
            Static(
                "[b]键盘帮助[/b]\n"
                "g 跳转   / 搜索   : 命令   r 刷新\n"
                "? 帮助   q 退出   Esc 关闭浮层\n\n"
                "LIVE / STALE 始终使用文字显示，颜色不是唯一状态提示。"
            )
        )


class ConfirmationScreen(ModalScreen[bool]):
    BINDINGS = [
        Binding("y", "accept", "Confirm", show=False),
        Binding("n", "reject", "Reject", show=False),
        Binding("escape", "reject", "Reject", show=False),
    ]
    DEFAULT_CSS = OverlayScreen.DEFAULT_CSS.replace("OverlayScreen", "ConfirmationScreen")

    def __init__(
        self,
        *,
        action: str,
        risk: str,
        impact: str,
        rollback: str,
    ) -> None:
        super().__init__()
        self._action = action
        self._risk = risk
        self._impact = impact
        self._rollback = rollback

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static(
                f"[b]{self._risk} 确认[/b]\n"
                f"Action: {self._action}\n"
                f"Impact: {self._impact}\n"
                f"Rollback: {self._rollback}\n\n"
                "y 确认 · n/Esc 拒绝"
            )
        )

    def action_accept(self) -> None:
        self.dismiss(True)

    def action_reject(self) -> None:
        self.dismiss(False)
