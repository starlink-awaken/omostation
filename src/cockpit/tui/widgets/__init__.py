"""cockpit.tui.widgets — 自定义 UI 组件集合 (Textual 扩展)."""

from cockpit.tui.widgets.command_palette import CommandPalette, CommandPalette as _CP
from cockpit.tui.widgets.detail_panel import DetailPanel
from cockpit.tui.widgets.log_panel import CommandLogModal
from cockpit.tui.widgets.research_list import ResearchListPanel
from cockpit.tui.widgets.status_bar import StatusBar

CommandExecuted = _CP.CommandExecuted

__all__ = [
    "CommandPalette",
    "CommandExecuted",
    "DetailPanel",
    "CommandLogModal",
    "ResearchListPanel",
    "StatusBar",
]
