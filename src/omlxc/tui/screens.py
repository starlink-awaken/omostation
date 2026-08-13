"""Small keyboard-only overlays shared by the compute cockpit."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label, Static

_OVERLAY_CSS = """
OverlayScreen {
    align: center middle;
    background: $background 75%;
}
OverlayScreen > Vertical {
    width: 68;
    max-width: 90%;
    height: auto;
    max-height: 85%;
    padding: 1 2;
    border: round #1a4d80;
    background: #07111e;
}
OverlayScreen Static {
    width: 1fr;
    height: auto;
    margin-bottom: 1;
}
OverlayScreen Input {
    margin-top: 1;
    border: solid #1a4d80;
    background: #0b1a2e;
    color: #7dd3f5;
}
OverlayScreen Input:focus {
    border: solid #2a7ab5;
}
OverlayScreen Label {
    color: #5a7a9a;
}
"""

_JUMP_CSS = _OVERLAY_CSS.replace("OverlayScreen", "JumpScreen")
_CMD_CSS = _OVERLAY_CSS.replace("OverlayScreen", "CommandScreen")
_CONFIRM_CSS = _OVERLAY_CSS.replace("OverlayScreen", "ConfirmationScreen")


class OverlayScreen(ModalScreen[None]):
    BINDINGS = [Binding("escape", "close", "Close", show=False)]
    DEFAULT_CSS = _OVERLAY_CSS

    def action_close(self) -> None:
        self.dismiss(None)


class JumpScreen(ModalScreen[str | None]):
    BINDINGS = [Binding("escape", "close", "Close", show=False)]
    DEFAULT_CSS = _JUMP_CSS
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
            Static("[bold #7dd3f5]⟡  快速跳转[/bold #7dd3f5]\n"),
            Static(
                "[#2a7ab5]1[/#2a7ab5] [#c8d8ec]总览[/#c8d8ec]    "
                "[#2a7ab5]2[/#2a7ab5] [#c8d8ec]节点[/#c8d8ec]    "
                "[#2a7ab5]3[/#2a7ab5] [#c8d8ec]模型[/#c8d8ec]    "
                "[#2a7ab5]4[/#2a7ab5] [#c8d8ec]路由[/#c8d8ec]\n"
                "[#2a7ab5]5[/#2a7ab5] [#c8d8ec]任务[/#c8d8ec]    "
                "[#2a7ab5]6[/#2a7ab5] [#c8d8ec]性能[/#c8d8ec]    "
                "[#2a7ab5]7[/#2a7ab5] [#c8d8ec]日志[/#c8d8ec]    "
                "[#2a7ab5]8[/#2a7ab5] [#c8d8ec]设置[/#c8d8ec]"
            ),
            Label("[bright_black]Esc 关闭[/bright_black]"),
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
            Static("[bold #7dd3f5]⟡  搜索当前资源[/bold #7dd3f5]"),
            Static("[#5a7a9a]输入仅用于本地页面过滤，不发送到后端。[/#5a7a9a]"),
            Input(placeholder="节点、模型或任务 ID …", id="search-input"),
        )


class CommandScreen(ModalScreen[str | None]):
    BINDINGS = [Binding("escape", "close", "Close", show=False)]
    DEFAULT_CSS = _CMD_CSS

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static("[bold #7dd3f5]⟡  命令面板[/bold #7dd3f5]"),
            Static(
                "[#5a7a9a]查询直接执行；[/#5a7a9a]"
                "[yellow]R1/R2[/yellow] [#5a7a9a]操作必须经过确认门。[/#5a7a9a]"
            ),
            Input(placeholder="例如：load local/model  或  cancel job-id", id="command-input"),
        )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        command = event.value.strip()
        self.dismiss(command or None)

    def action_close(self) -> None:
        self.dismiss(None)


class HelpScreen(OverlayScreen):
    def compose(self) -> ComposeResult:
        yield Vertical(
            Static("[bold #7dd3f5]✦  键盘帮助[/bold #7dd3f5]\n"),
            Static(
                "[#2a7ab5]g[/#2a7ab5]  跳转页面    "
                "[#2a7ab5]/[/#2a7ab5]  搜索        "
                "[#2a7ab5]:[/#2a7ab5]  命令面板\n"
                "[#2a7ab5]r[/#2a7ab5]  刷新        "
                "[#2a7ab5]?[/#2a7ab5]  本帮助      "
                "[#2a7ab5]q[/#2a7ab5]  退出\n"
                "[#2a7ab5]Esc[/#2a7ab5]  关闭当前浮层"
            ),
            Label("\n[#5a7a9a]LIVE / STALE 始终以文字显示，颜色不是唯一状态提示。[/#5a7a9a]"),
        )


class ConfirmationScreen(ModalScreen[bool]):
    BINDINGS = [
        Binding("y", "accept", "Confirm", show=False),
        Binding("n", "reject", "Reject", show=False),
        Binding("escape", "reject", "Reject", show=False),
    ]
    DEFAULT_CSS = _CONFIRM_CSS

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
        risk_color = "red" if self._risk == "R2" else "yellow"
        yield Vertical(
            Static(f"[bold {risk_color}]⚠  {self._risk} 确认[/bold {risk_color}]\n"),
            Static(
                f"[#5a7a9a]Action  [/#5a7a9a][#c8d8ec]{self._action}[/#c8d8ec]\n"
                f"[#5a7a9a]Impact  [/#5a7a9a][yellow]{self._impact}[/yellow]\n"
                f"[#5a7a9a]Rollback[/#5a7a9a][#c8d8ec]{self._rollback}[/#c8d8ec]"
            ),
            Label("\n[green]y[/green] 确认    [red]n[/red] / [red]Esc[/red] 拒绝"),
        )

    def action_accept(self) -> None:
        self.dismiss(True)

    def action_reject(self) -> None:
        self.dismiss(False)
