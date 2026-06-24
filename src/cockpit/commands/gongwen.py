"""cockpit.commands.gongwen — 公文写作门户引导 (产品走查 v5 #V5-11 C 方案).

C 方案: cockpit 作为门户加轻量公文引导命令 (保持 KISS, 不实现公文逻辑);
公文写作能力保持在 @公文 域独立演进 (国资委第13号令规范). 参见全局 CLAUDE.md §3 路由.
理由: 公文是专业垂直域 (模板/规范/审批流), 塞进通用 cockpit 会耦合违 SRP;
但 cockpit 作为门户应能发现引导 — 这就是这扇门 (B 方案能力留在 @公文 域独立).
"""

from __future__ import annotations

from argparse import Namespace

from .base import _get_console, _panel

# 公文常见文种 (国资委第13号令) — 仅引导描述, 非写作逻辑实现
_GONGWEN_TYPES: list[tuple[str, str]] = [
    ("通知", "发布、传达要求下级机关执行的事项"),
    ("报告", "向上级汇报工作、反映情况、回复询问"),
    ("请示", "向上级请求指示、批准"),
    ("纪要", "记载会议主要情况和议定事项"),
    ("函", "不相隶属机关之间商洽工作、询问和答复问题"),
]


def cmd_gongwen(_args: Namespace) -> int:
    """公文写作门户引导 — 列文种/规范/入口, 引导用户到 @公文 域 (不实现写作逻辑)."""
    console = _get_console()
    console.print(_panel("[bold cyan]📄 公文写作门户[/]", "cyan"))

    console.print("\n[bold]📝 常见文种 (国资委第13号令):[/]")
    for name, desc in _GONGWEN_TYPES:
        console.print(f"  [cyan]·[/] [bold]{name}[/] — {desc}")

    console.print("\n[bold]📐 规范要素:[/]")
    console.print("  [dim]·[/] 标题 / 主送机关 / 正文 / 落款 / 成文日期 / 印章")
    console.print("  [dim]·[/] 详细规范见 @公文 域 (国资委13号令《公文处理办法》)")

    console.print("\n[bold green]🚪 写作入口:[/]")
    console.print("  [cyan]·[/] 公文规范域: ~/Documents/公文/ (模板与规范 SSOT)")
    console.print("  [cyan]·[/] 工作文档域: ~/Documents/@工作文档/ (卫健委 / 国转中心)")
    console.print("  [cyan]·[/] 写作 skill: content-creator (起草) → wechat-publisher (发布)")

    console.print("\n[dim]💡 cockpit 只做门户引导; 公文写作能力在 @公文 域独立演进 (保持解耦, 专业逻辑留给垂直域)。[/]")
    return 0
