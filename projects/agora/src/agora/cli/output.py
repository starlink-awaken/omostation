"""统一输出库 — Agora CLI | v1.0
===================================
对标 kubectl / gh / docker 风格，提供:
- 彩色表格/列表/键值对输出
- --json 模式自动切换
- 进度条支持
- 统一符号约定 (✅/❌/⚠️/ℹ️/⏳)

用法:
    from agora.cli.output import OutputFormatter

    out = OutputFormatter(json_mode=getattr(args, 'json', False))
    out.print_table(["名称", "状态"], [["my-svc", "active"], ...])
    out.print_success("注册成功")
    out.print_error("服务未找到", suggestion="使用 'agora list' 查看")
"""

from __future__ import annotations

import json as _json
import sys
from typing import Any

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text  # noqa: F401
    from rich.theme import Theme
    from rich.progress import Progress, SpinnerColumn, TextColumn

    _RICH = True
except ImportError:
    _RICH = False


class OutputFormatter:
    """统一 CLI 输出格式化器。

    根据 json_mode 自动切换:
    - json_mode=False: 彩色终端表格/列表
    - json_mode=True:  原始 JSON 输出（管道友好）
    """

    def __init__(self, json_mode: bool = False):
        self.json_mode = json_mode
        if _RICH:
            theme = Theme(
                {
                    "success": "green",
                    "error": "red bold",
                    "warning": "yellow",
                    "info": "blue",
                    "dim": "dim",
                    "highlight": "cyan",
                    "header": "bold cyan",
                }
            )
            self.console = Console(theme=theme)
        else:
            self.console = None

    def supports_color(self) -> bool:
        """终端是否支持颜色"""
        if self.console is None:
            return False
        return self.console.color_system is not None

    def _uses_rich(self) -> bool:
        """Rich Console 可用 (即使 color_system 为 None 也支持表格渲染)"""
        return self.console is not None

    # ── 图标约定 ──
    def _icon(self, name: str) -> str:
        """返回图标（无颜色终端用文本）"""
        mapping = {
            "success": "✓" if not self.supports_color() else "",
            "error": "✗" if not self.supports_color() else "",
            "warning": "!" if not self.supports_color() else "",
            "info": "i" if not self.supports_color() else "",
            "progress": "…" if not self.supports_color() else "",
        }
        return mapping.get(name, "")

    # ── 基本输出 ──
    def print_success(self, msg: str) -> None:
        if self.json_mode:
            self.print_json({"status": "success", "message": msg})
        elif self.supports_color():
            self.console.print(f"[success]{self._icon('success')} {msg}[/success]")
        else:
            print(f"{self._icon('success')} {msg}")

    def print_error(self, msg: str, suggestion: str = "") -> None:
        if self.json_mode:
            self.print_json({"status": "error", "message": msg, "hint": suggestion})
        elif self.supports_color():
            self.console.print(f"[error]{self._icon('error')} Error: {msg}[/error]")
            if suggestion:
                self.console.print(f"  [dim]Hint: {suggestion}[/dim]")
        else:
            print(f"{self._icon('error')} Error: {msg}", file=sys.stderr)
            if suggestion:
                print(f"  Hint: {suggestion}", file=sys.stderr)

    def print_warning(self, msg: str) -> None:
        if self.json_mode:
            self.print_json({"status": "warning", "message": msg})
        elif self.supports_color():
            self.console.print(f"[warning]{self._icon('warning')} {msg}[/warning]")
        else:
            print(f"{self._icon('warning')} {msg}")

    def print_info(self, msg: str) -> None:
        if not self.json_mode:
            if self.supports_color():
                self.console.print(f"[info]{msg}[/info]")
            else:
                print(f"{self._icon('info')} {msg}")

    def print_progress(self, msg: str) -> None:
        if not self.json_mode:
            if self.supports_color():
                self.console.print(f"[highlight]⏳ {msg}...[/highlight]")
            else:
                print(f"{self._icon('progress')} {msg}...")

    # ── 表格 ──
    def print_table(
        self,
        headers: list[str],
        rows: list[list[Any]],
        title: str = "",
        caption: str = "",
    ) -> None:
        """表格输出，自动截断长字段"""
        if self.json_mode:
            result = [dict(zip(headers, [str(c) for c in row])) for row in rows]
            self.print_json({"table": result, "title": title, "count": len(rows)})
            return

        if not rows:
            self.print_info(f"(空) — {title}" if title else "(空)")
            return

        if self._uses_rich() or self.supports_color():
            import rich.table
            import rich.text

            table = (
                rich.table.Table(title=title, caption=caption, caption_style="dim")
                if title
                else rich.table.Table(caption=caption)
            )
            for h in headers:
                table.add_column(h, overflow="fold", max_width=60)
            for row in rows:
                rich_row: list[Any] = []
                for cell in row:
                    s = str(cell)
                    if "[" in s and "]" in s:
                        rich_row.append(rich.text.Text.from_markup(s))
                    else:
                        rich_row.append(s)
                table.add_row(*rich_row)
            self.console.print(table)
        else:
            # 回退到 ASCII 表格
            if title:
                print(f"\n{title}")
            widths = [
                max(len(h), max((len(str(r[i])) for r in rows), default=0))
                for i, h in enumerate(headers)
            ]
            header_line = " | ".join(h.ljust(w) for h, w in zip(headers, widths))
            sep = "-+-".join("-" * w for w in widths)
            print(header_line)
            print(sep)
            for row in rows:
                print(" | ".join(str(c).ljust(w) for c, w in zip(row, widths)))
            print()

    # ── JSON ──
    def print_json(self, data: Any) -> None:
        """格式化 JSON 输出"""
        print(_json.dumps(data, ensure_ascii=False, indent=2, default=str))

    # ── 列表 ──
    def print_list(
        self,
        items: list[dict[str, Any]],
        key_field: str = "name",
        description_field: str = "description",
        title: str = "",
    ) -> None:
        """简洁列表输出"""
        if self.json_mode:
            self.print_json({"items": items, "title": title, "count": len(items)})
            return

        if not items:
            self.print_info(f"(空) — {title}" if title else "(空)")
            return

        if self.supports_color():
            if title:
                self.console.print(f"\n[bold]{title}[/bold]")
            for item in items:
                key = str(item.get(key_field, ""))
                desc = str(item.get(description_field, "")) if description_field else ""
                if desc:
                    self.console.print(
                        f"  [highlight]{key}[/highlight]  [dim]{desc}[/dim]"
                    )
                else:
                    self.console.print(f"  [highlight]{key}[/highlight]")
            if title:
                self.console.print(f"  [dim]共 {len(items)} 项[/dim]\n")
        else:
            if title:
                print(f"\n{title}")
            for item in items:
                key = str(item.get(key_field, ""))
                desc = str(item.get(description_field, "")) if description_field else ""
                print(f"  {key}  {desc}" if desc else f"  {key}")
            if title:
                print(f"  共 {len(items)} 项\n")

    # ── 键值对 ──
    def print_key_value(self, data: dict[str, Any], title: str = "") -> None:
        """键值对详情输出"""
        if self.json_mode:
            self.print_json({"details": data, "title": title})
            return

        if self.supports_color():
            if title:
                self.console.print(f"\n[bold]{title}[/bold]")
            max_k = max(len(k) for k in data) if data else 10
            for k, v in data.items():
                self.console.print(f"  [dim]{k.ljust(max_k)}[/dim]  {v}")
            if title:
                self.console.print()
        else:
            if title:
                print(f"\n{title}")
            max_k = max(len(k) for k in data) if data else 10
            for k, v in data.items():
                print(f"  {k.ljust(max_k)}  {v}")
            if title:
                print()

    # ── 标题/分隔 ──
    def print_header(self, title: str) -> None:
        """标题栏"""
        if self.json_mode:
            return
        if self.supports_color():
            self.console.print(f"\n[header]═══ {title} ═══[/header]\n")
        else:
            print(f"\n═══ {title} ═══\n")

    def print_divider(self) -> None:
        """分隔线"""
        if not self.json_mode:
            print()

    def print_section(self, title: str) -> None:
        """小节标题"""
        if self.json_mode:
            return
        if self.supports_color():
            self.console.print(f"\n[bold]── {title} ──[/bold]")
        else:
            print(f"\n── {title} ──")

    def print_panel(
        self, content: str, title: str = "", style: str = "highlight"
    ) -> None:
        """面板输出 — 用于汇总卡片"""
        if self.json_mode:
            return
        if self._uses_rich() or self.supports_color():
            try:
                from rich.markdown import Markdown

                self.console.print(
                    Panel(Markdown(content), title=title, border_style=style)
                )
            except ImportError:
                self.console.print(Panel(content, title=title, border_style=style))
        else:
            if title:
                print(f"\n── {title} ──")
            print(content.rstrip())

    def print_health_bar(self, ratio: float, width: int = 10) -> str:
        """返回彩色健康条 Rich markup (用于表格单元格)"""
        filled = int(ratio * width)
        if ratio >= 0.9:
            color = "green"
        elif ratio >= 0.7:
            color = "yellow"
        else:
            color = "red"
        return f"[{color}]{'█' * filled}[/]{'░' * (width - filled)}"

    # ── 进度条 ──
    def create_progress(self) -> Progress | None:
        """创建进度条上下文"""
        if not _RICH or self.json_mode:
            return None
        return Progress(
            SpinnerColumn(), TextColumn("[progress.description]{task.description}")
        )


def output_result(data: Any, json_mode: bool = False, **kwargs) -> None:
    """便捷函数：按 json_mode 自动选择 JSON 或文本输出"""
    out = OutputFormatter(json_mode)
    if json_mode:
        out.print_json(data)
    elif isinstance(data, dict) and "rows" in kwargs:
        out.print_table(list(data.keys()), list(data.values()), **kwargs)
    elif isinstance(data, list) and data and isinstance(data[0], dict):
        out.print_list(data, **kwargs)
    elif isinstance(data, dict):
        out.print_key_value(data, **kwargs)
    else:
        print(data)


# 便捷别名
print_success = OutputFormatter().print_success
print_error = OutputFormatter().print_error
print_warning = OutputFormatter().print_warning
print_info = OutputFormatter().print_info
