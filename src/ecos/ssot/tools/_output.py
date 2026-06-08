"""统一输出库 — ecos MOF 工具链 | v1.2
============================================
优先从 agora.cli.output 导入 (rich 支持), 回退到 ANSI 独立实现。

用法:
    from _output import OutputFormatter, print_success, print_error
"""

from __future__ import annotations

import json as _json
import sys
from typing import Any

# 尝试从 agora 导入 rich 版本
try:
    from agora.cli.output import OutputFormatter as _AgoraFormatter  # type: ignore[import-not-found]
    print_success = _AgoraFormatter().print_success
    print_error = _AgoraFormatter().print_error
    print_warning = _AgoraFormatter().print_warning
    print_info = _AgoraFormatter().print_info
    OutputFormatter = _AgoraFormatter
except ImportError:
    # 回退: 独立 ANSI 实现
    pass


class OutputFormatter:
    """ecos 统一 CLI 输出格式化器"""

    def __init__(self, json_mode: bool = False):
        self.json_mode = json_mode

    # ── 图标 (ANSI 无依赖) ──
    @staticmethod
    def _style(text: str, code: str) -> str:
        """简单 ANSI 样式包装"""
        styles = {"green": "32", "red": "31", "yellow": "33", "blue": "34",
                  "cyan": "36", "dim": "2", "bold": "1"}
        c = styles.get(code, "")
        return f"\033[{c}m{text}\033[0m" if c else text

    def print_success(self, msg: str) -> None:
        if self.json_mode:
            self.print_json({"status": "ok", "message": msg})
        else:
            print(f"\033[32m✓\033[0m {msg}")

    def print_error(self, msg: str, suggestion: str = "") -> None:
        if self.json_mode:
            import sys as _sys
            json_str = _json.dumps({"status": "error", "message": msg, "hint": suggestion}, ensure_ascii=False, default=str)
            print(json_str, file=_sys.stderr)
        else:
            print(f"\033[31m✗ Error:\033[0m {msg}", file=sys.stderr)
            if suggestion:
                print(f"  \033[2mHint: {suggestion}\033[0m", file=sys.stderr)

    def print_warning(self, msg: str) -> None:
        if self.json_mode:
            self.print_json({"status": "warning", "message": msg})
        else:
            print(f"\033[33m!\033[0m {msg}")

    def print_info(self, msg: str) -> None:
        if not self.json_mode:
            print(f"\033[34mℹ\033[0m {msg}")

    def print_progress(self, msg: str) -> None:
        if not self.json_mode:
            print(f"\033[36m⏳\033[0m {msg}...")

    def print_header(self, title: str) -> None:
        if not self.json_mode:
            print(f"\n\033[1;36m═══ {title} ═══\033[0m\n")

    def print_section(self, title: str) -> None:
        if not self.json_mode:
            print(f"\n\033[1m── {title} ──\033[0m")

    def print_divider(self) -> None:
        if not self.json_mode:
            print()

    # ── 表格 ──
    def print_table(self, headers: list[str], rows: list[list[Any]],
                    title: str = "") -> None:
        if self.json_mode:
            result = [dict(zip(headers, [str(c) for c in row])) for row in rows]
            self.print_json({"table": result, "title": title, "count": len(rows)})
            return

        if not rows:
            self.print_info(f"(空) — {title}" if title else "(空)")
            return

        widths = []
        for i, h in enumerate(headers):
            cell_widths = [len(str(r[i])) for r in rows]
            widths.append(max(len(h), max(cell_widths, default=0), 8))

        if title:
            print(f"\n{self._style(title, 'bold')}")

        # Header
        header = " │ ".join(("\033[1m" + h.ljust(w) + "\033[0m") for h, w in zip(headers, widths))
        sep = "─┼─".join("─" * w for w in widths)
        print(f"  {header}")
        print(f"  {sep}")

        for row in rows:
            line = " │ ".join(str(c)[:w].ljust(w) for c, w in zip(row, widths))
            print(f"  {line}")

        print(f"  \033[2m共 {len(rows)} 项\033[0m\n")

    def print_list(self, items: list[dict[str, Any]], key_field: str = "name",
                   description_field: str = "description", title: str = "") -> None:
        if self.json_mode:
            self.print_json({"items": items, "title": title, "count": len(items)})
            return
        if not items:
            self.print_info(f"(空) — {title}" if title else "(空)")
            return
        if title:
            print(f"\n\033[1m{title}\033[0m")
        for item in items:
            key = str(item.get(key_field, ""))
            desc = str(item.get(description_field, "")) if description_field else ""
            line = f"  \033[36m{key}\033[0m"
            if desc:
                line += f"  \033[2m{desc}\033[0m"
            print(line)
        print(f"  \033[2m共 {len(items)} 项\033[0m\n")

    def print_key_value(self, data: dict[str, Any], title: str = "") -> None:
        if self.json_mode:
            self.print_json({"details": data, "title": title})
            return
        if title:
            print(f"\n\033[1m{title}\033[0m")
        max_key = max(len(k) for k in data) if data else 10
        for k, v in data.items():
            print(f"  \033[2m{k.ljust(max_key)}\033[0m  {v}")
        if title:
            print()

    def print_json(self, data: Any) -> None:
        print(_json.dumps(data, ensure_ascii=False, default=str))


# ── 便捷函数 ──
_default = OutputFormatter()

def print_success(msg: str): _default.print_success(msg)
def print_error(msg: str, suggestion: str = ""): _default.print_error(msg, suggestion)
def print_warning(msg: str): _default.print_warning(msg)
def print_info(msg: str): _default.print_info(msg)
