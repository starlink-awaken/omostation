"""cockpit.commands.profile — identity/profile commands."""

from __future__ import annotations

import argparse
import os
import subprocess
from datetime import datetime

from .base import _PROFILE_PATH, _get_console, _get_err, _load_profile, _panel


def cmd_profile(args: argparse.Namespace) -> int:
    c, _e = _get_console(), _get_err()
    if args.edit:
        import yaml

        editor = os.environ.get("EDITOR", "vim")
        profile_dir = _PROFILE_PATH.parent
        profile_dir.mkdir(parents=True, exist_ok=True)
        if not _PROFILE_PATH.exists():
            template = {
                "name": "你的名字",
                "role": "你的角色",
                "timezone": "Asia/Shanghai",
                "active_domain": "你的领域",
                "principles": ["原则1", "原则2"],
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            with open(_PROFILE_PATH, "w") as f:
                yaml.dump(template, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
            c.print(f"[green]✅ 已创建默认档案:[/green] [cyan]{_PROFILE_PATH}[/]")
        subprocess.run([editor, str(_PROFILE_PATH)])
        updated = _load_profile()
        if updated:
            created = updated.get("created_at", "未知")
            c.print(
                _panel(
                    f"[bold cyan]👤 {updated.get('name', '未命名')}[/bold cyan]\n"
                    f"[dim]{updated.get('role', '')}[/dim]\n\n"
                    f"[bold]时区:[/bold] {updated.get('timezone', '未设置')}\n"
                    f"[bold]活跃领域:[/bold] {updated.get('active_domain', '未设置')}\n"
                    f"[bold]原则:[/bold]\n"
                    + "\n".join(f"  · {p}" for p in updated.get("principles", []))
                    + f"\n\n[dim]档案创建: {created}[/dim]",
                    "green",
                    title="📋 已更新身份档案",
                )
            )
        else:
            c.print("[yellow]⚠️ 档案内容为空或格式错误，请检查 YAML 语法。[/yellow]")
        return 0
    profile = _load_profile()
    if not profile:
        c.print(
            _panel(
                "[bold yellow]⚠️ 未设置身份档案[/bold yellow]\n\n"
                "创建 [cyan]~/.workspace/persona.yaml[/] 来定义你的身份、角色和原则。\n\n"
                "示例:\n"
                '  [dim]name: "你的名字"\n'
                '  role: "你的角色"\n'
                '  timezone: "Asia/Shanghai"\n'
                '  active_domain: "你的领域"\n'
                "  principles:\n"
                '    - "原则1"\n'
                '    - "原则2"[/]\n\n'
                "[bold yellow]🎯 快速启动:[/bold yellow]\n"
                "  [cyan]workspace status[/] — 打开工作台\n"
                '  [cyan]workspace research "主题"[/] — 开始研究\n'
                "  [cyan]workspace demo[/] — 体验完整闭环",
                "yellow",
            )
        )
        return 0
    created = profile.get("created_at", "未知")
    c.print(
        _panel(
            f"[bold cyan]👤 {profile.get('name', '未命名')}[/bold cyan]\n"
            f"[dim]{profile.get('role', '')}[/dim]\n\n"
            f"[bold]时区:[/bold] {profile.get('timezone', '未设置')}\n"
            f"[bold]活跃领域:[/bold] {profile.get('active_domain', '未设置')}\n"
            f"[bold]原则:[/bold]\n"
            + "\n".join(f"  · {p}" for p in profile.get("principles", []))
            + f"\n\n[dim]档案创建: {created}[/dim]",
            "cyan",
            title="📋 身份档案",
        )
    )
    c.print(
        _panel(
            "下一步:\n"
            "- [cyan]workspace status[/] 打开工作台\n"
            "- [cyan]workspace profile --edit[/] 编辑档案\n"
            '- [cyan]workspace research "主题"[/] 开始研究',
            "cyan",
        )
    )
    return 0
