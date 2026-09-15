#!/usr/bin/env python3
"""
cron_manager — Forge 定时任务统一管理

统一管理所有定时任务的注册、启停与状态查询。
任务类型:
  - launchd: macOS launchd plist 管理
  - reminder: macOS Reminders 提醒事项

数据源: assets/registry.json → entities.cron

用法:
  python3 src/cron_manager.py list              # 列出所有定时任务
  python3 src/cron_manager.py register <id> ...  # 注册新任务
  python3 src/cron_manager.py enable <id>        # 启用任务
  python3 src/cron_manager.py disable <id>       # 禁用任务
  python3 src/cron_manager.py status [id]        # 查看状态
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime

from forge.cron_utils import (
    DISABLED_DIR,
    LAUNCH_AGENTS,
    REGISTRY_FILE,
    disabled_plist_path,
    find_cron_item,
    generate_plist_xml,
    get_cron_items,
    launchctl_bootout,
    launchctl_bootstrap,
    launchctl_is_loaded,
    load_registry,
    plist_path,
    save_registry,
    schedule_display,
    validate_script_name,
    validate_task_name,
)
from forge.forge_config import FORGE_ROOT  # type: ignore[import-not-found]

# ── cron-manager 特有助手 ──

FORGE_SCRIPTS = FORGE_ROOT / "scripts"


def _generate_plist_from_item(name: str, item: dict) -> bytes:
    """从 registry 条目生成 plist（薄包装→cron_utils.generate_plist_xml）。"""
    script = item.get("script", "")
    working_dir = item.get("working_dir") or str(FORGE_ROOT)
    script_cmd = script if script.startswith("/") else f"cd {working_dir} && bash scripts/{script}"
    return generate_plist_xml(name, script_cmd, working_dir, item.get("schedule"), item.get("description", ""))


# ── 命令行 ──


def cmd_list(_args: list[str]) -> int:
    """列出所有定时任务。"""
    reg = load_registry()
    if not reg:
        return 1
    items = get_cron_items(reg)

    if not items:
        print("  ⏰ 无定时任务注册")
        return 0

    print(f"\n  Forge 定时任务一览 ({len(items)} 个)")
    print(f"  {'─' * 65}")
    print(f"  {'名称':<28} {'调度':<18} {'状态':<8} {'脚本'}")
    print(f"  {'─' * 65}")

    loaded_cache: dict[str, bool] = {}
    for item in items:
        name = item.get("name", "?")
        sched = schedule_display(item.get("schedule", "?"))
        script = item.get("script", "")[:20]
        enabled = item.get("enabled", False)
        loaded = launchctl_is_loaded(name) if enabled else False
        loaded_cache[name] = loaded

        if loaded:
            status_icon = "✅ 运行"
        elif enabled:
            status_icon = "⏸️ 已注册"
        else:
            status_icon = "❌ 禁用"

        print(f"  {name:<28} {sched:<18} {status_icon:<8} {script}")

    registered = sum(1 for i in items if i.get("enabled", False))
    running = sum(1 for name in loaded_cache.values() if name)
    print(f"\n  总计: {len(items)}  |  已注册: {registered}  |  运行中: {running}")

    return 0


def cmd_register(args: list[str]) -> int:
    """注册新定时任务到 registry。"""
    if not args:
        print(
            "用法: forge cron register <name> --schedule '<cron>' --script '<script>' [--desc '<desc>'] [--working-dir '<dir>']"
        )
        print("  <name>        任务 ID（kebab-case，如 forge-daily-maintenance）")
        print("  --schedule    cron 表达式 (如 '5 6 * * *') 或 '{\"Hour\":6,\"Minute\":5}'")
        print("  --script      脚本文件名 (.sh/.py)")
        print("  --desc        描述")
        print("  --working-dir 工作目录（默认 Forge 根目录）")
        return 1

    name = args[0]
    if not validate_task_name(name):
        print(f"❌ 非法任务名称: {name}")
        print("   只允许字母、数字、下划线、连字符和点号")
        return 1

    cmd_args = args[1:]

    kwargs = {}
    i = 0
    while i < len(cmd_args):
        if cmd_args[i] == "--schedule" and i + 1 < len(cmd_args):
            try:
                kwargs["schedule"] = json.loads(cmd_args[i + 1])
            except json.JSONDecodeError:
                kwargs["schedule"] = cmd_args[i + 1]
            i += 2
        elif cmd_args[i] == "--script" and i + 1 < len(cmd_args):
            kwargs["script"] = cmd_args[i + 1]
            i += 2
        elif cmd_args[i] == "--desc" and i + 1 < len(cmd_args):
            kwargs["description"] = cmd_args[i + 1]
            i += 2
        elif cmd_args[i] == "--working-dir" and i + 1 < len(cmd_args):
            kwargs["working_dir"] = cmd_args[i + 1]
            i += 2
        else:
            print(f"未知选项: {cmd_args[i]}")
            return 1

    reg = load_registry()
    if not reg:
        return 1
    if reg.get("version") != 4 or "entities" not in reg:
        print("❌ registry 不是 v4 格式")
        return 1

    script = kwargs.get("script", "")
    if not validate_script_name(script):
        print(f"❌ 非法脚本名: {script}")
        print("   只允许 .sh/.py 后缀的基本文件名")
        return 1

    cron_entity = reg["entities"].setdefault("cron", {"$schema": {}, "items": []})
    items = cron_entity.setdefault("items", [])

    idx = find_cron_item(items, name)
    item: dict = {
        "name": name,
        "schedule": kwargs.get("schedule", "0 0 * * *"),
        "script": script,
        "description": kwargs.get("description", ""),
        "enabled": False,
    }
    if "working_dir" in kwargs:
        item["working_dir"] = kwargs["working_dir"]

    if idx is not None:
        old = items[idx]
        old.update(item)
        old["updated"] = datetime.now().strftime("%Y-%m-%d")
        items[idx] = old
        save_registry(reg)
        print(f"🔄 已更新定时任务: {name}")
    else:
        item["added"] = datetime.now().strftime("%Y-%m-%d")
        items.append(item)
        save_registry(reg)
        print(f"✅ 已注册定时任务: {name}")

    return 0


def cmd_enable(args: list[str]) -> int:
    """启用定时任务（生成 plist + launchctl bootstrap）。"""
    if not args:
        print("用法: forge cron enable <name>")
        return 1

    name = args[0]
    if not validate_task_name(name):
        print(f"❌ 非法任务名称: {name}")
        return 1

    reg = load_registry()
    if not reg:
        return 1
    items = get_cron_items(reg)
    idx = find_cron_item(items, name)

    if idx is None:
        print(f"❌ 未找到定时任务: {name}")
        print("   先用 forge cron register 注册")
        return 1

    item = items[idx]
    DISABLED_DIR.mkdir(parents=True, exist_ok=True)
    LAUNCH_AGENTS.mkdir(parents=True, exist_ok=True)

    disabled_path = disabled_plist_path(name)
    ppath = plist_path(name)
    if disabled_path.exists():
        disabled_path.rename(ppath)
        print(f"  📦 恢复 plist: {disabled_path} → {ppath}")
    elif not ppath.exists():
        try:
            plist_data = _generate_plist_from_item(name, item)
            ppath.write_bytes(plist_data)
            print(f"  📄 生成 plist: {ppath}")
        except Exception as e:
            print(f"❌ 生成 plist 失败: {e}")
            return 1

    ok, msg = launchctl_bootstrap(name)
    if ok:
        item["enabled"] = True
        save_registry(reg)
        print(f"✅ 已启用定时任务: {name}  ({msg})")
        return 0
    else:
        print(f"❌ 启用失败 ({name}): {msg}")
        return 1


def cmd_disable(args: list[str]) -> int:
    """禁用定时任务（launchctl bootout + 移走 plist）。"""
    if not args:
        print("用法: forge cron disable <name>")
        return 1

    name = args[0]
    if not validate_task_name(name):
        print(f"❌ 非法任务名称: {name}")
        return 1

    reg = load_registry()
    if not reg:
        return 1
    items = get_cron_items(reg)
    idx = find_cron_item(items, name)

    if idx is None:
        print(f"  ⚠️ registry 中未找到 {name}，尝试直接卸载...")
        ok, msg = launchctl_bootout(name)
        if ok:
            print(f"✅ 已卸载: {name}  ({msg})")
        else:
            print(f"⚠️  {msg}")
        ppath = plist_path(name)
        if ppath.exists():
            DISABLED_DIR.mkdir(parents=True, exist_ok=True)
            ppath.rename(disabled_plist_path(name))
            print(f"  📦 plist 已移走: {disabled_plist_path(name)}")
        return 0

    ok, msg = launchctl_bootout(name)
    if ok:
        print(f"  ✅ launchd 已卸载 ({msg})")
    else:
        print(f"  ⚠️  卸载 launchd: {msg}")

    ppath = plist_path(name)
    if ppath.exists():
        DISABLED_DIR.mkdir(parents=True, exist_ok=True)
        ppath.rename(disabled_plist_path(name))
        print(f"  📦 plist 已移走: {disabled_plist_path(name)}")

    item = items[idx]
    item["enabled"] = False
    save_registry(reg)
    print(f"✅ 已禁用定时任务: {name}")

    return 0


def cmd_status(args: list[str]) -> int:
    """查看定时任务状态。"""
    reg = load_registry()
    if not reg:
        return 1
    items = get_cron_items(reg)

    if args:
        name = args[0]
        if not validate_task_name(name):
            print(f"❌ 非法任务名称: {name}")
            return 1
        idx = find_cron_item(items, name)
        if idx is None:
            print(f"❌ 未找到定时任务: {name}")
            return 1
        items = [items[idx]]

    for item in items:
        name = item.get("name", "?")
        enabled = item.get("enabled", False)
        loaded = launchctl_is_loaded(name) if enabled else False
        sched = schedule_display(item.get("schedule", "?"))
        script = item.get("script", "")
        desc = item.get("description", "")

        print(f"\n  ⏰ {name}")
        print(f"  {'─' * 40}")
        print(f"  调度:    {sched}")
        print(f"  脚本:    {script}")
        print(f"  描述:    {desc or '—'}")
        print(f"  启用:    {'✅ 是' if enabled else '❌ 否'}")
        print(f"  运行:    {'✅ 是' if loaded else ('❌ 否' if enabled else '—')}")

        if loaded:
            ppath = plist_path(name)
            print(f"  plist:   {ppath}")

    return 0


# ── AppleScript 辅助 ──


def _escape_as(s: str) -> str:
    s = s.replace('"', '""')
    return "".join(c for c in s if c not in "\n\r\t")


# ── Reminders ──


def cmd_reminder_add(args: list[str]) -> int:
    """创建 macOS Reminders 提醒。"""
    if len(args) < 2:
        print("用法: forge cron reminder <name> --schedule '<desc>' --title '<title>'")
        print("  --schedule  调度描述（人类可读，如 '每周五 9:00'）")
        print("  --title     提醒标题")
        print("  --body      提醒正文")
        return 1

    name = args[0]
    cmd_args = args[1:]

    kwargs = {}
    i = 0
    while i < len(cmd_args):
        if cmd_args[i] == "--schedule" and i + 1 < len(cmd_args):
            kwargs["schedule"] = cmd_args[i + 1]
            i += 2
        elif cmd_args[i] == "--title" and i + 1 < len(cmd_args):
            kwargs["title"] = cmd_args[i + 1]
            i += 2
        elif cmd_args[i] == "--body" and i + 1 < len(cmd_args):
            kwargs["body"] = cmd_args[i + 1]
            i += 2
        else:
            print(f"未知选项: {cmd_args[i]}")
            return 1

    title = kwargs.get("title", name)
    body = kwargs.get("body", "")
    sched = kwargs.get("schedule", "")

    script_parts = [
        'tell application "Reminders"',
        '    tell list "定时任务"',
        f'        set r to make new reminder with properties {{name:"{_escape_as(title)}", body:"{_escape_as(body)}"}}',
    ]

    if "每月" in sched:
        script_parts.append("        set recurrence of r to monthly")
    elif "每周" in sched or "周" in sched:
        script_parts.append("        set recurrence of r to weekly")
    elif "季度" in sched:
        script_parts.append("        set recurrence of r to quarterly")

    if "9:" in sched and "分" not in sched:
        script_parts.append("        set hour of dueDate to 9")
        script_parts.append("        set minute of dueDate to 0")

    script_parts.extend(
        [
            "        set remind me date of r to current date",
            "    end tell",
            "end tell",
            'return "done"',
        ]
    )

    script = "\n".join(script_parts)

    try:
        r = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode == 0:
            print(f"✅ 已创建提醒: {title}")
            return 0
        else:
            print(f"❌ 创建提醒失败: {r.stderr.strip()}")
            return 1
    except Exception as e:
        print(f"❌ 创建提醒失败: {e}")
        return 1


def cmd_reminder_remove(args: list[str]) -> int:
    """删除 macOS Reminders 提醒。"""
    if not args:
        print("用法: forge cron reminder-remove <title或关键词>")
        return 1

    keyword = _escape_as(args[0])
    script = f'''
tell application "Reminders"
    set allLists to name of every list
    repeat with listName in allLists
        tell list listName
            set remindersToDelete to every reminder whose name contains "{keyword}"
            repeat with r in remindersToDelete
                delete r
            end repeat
        end tell
    end repeat
end tell
return "done"
'''

    try:
        r = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode == 0:
            print(f"✅ 已删除包含「{keyword}」的提醒")
            return 0
        else:
            print(f"❌ 删除提醒失败: {r.stderr.strip()}")
            return 1
    except Exception as e:
        print(f"❌ 删除提醒失败: {e}")
        return 1


def cmd_cron_script(args: list[str]) -> int:
    """创建/管理 Forge 定时任务脚本。"""
    if not args or args[0] == "list":
        wf_scripts = sorted(FORGE_SCRIPTS.glob("wf-*.sh"))
        if not wf_scripts:
            print("  ⏰ 无 wf-* 定时任务脚本")
            return 0
        print(f"\n  Forge 定时脚本 ({min(len(wf_scripts), 50)} 个)")
        for f in wf_scripts[:50]:
            print(f"  📜 {f.name}")
        if len(wf_scripts) > 50:
            print(f"  ... 还有 {len(wf_scripts) - 50} 个未显示")
        return 0

    if args[0] == "create" and len(args) >= 3:
        name = args[1]
        if not validate_task_name(name):
            print(f"❌ 非法脚本文件名: {name}")
            print("   只允许字母、数字、下划线、连字符和点号")
            return 1
        if not name.endswith(".sh"):
            print(f"❌ 脚本必须以 .sh 结尾: {name}")
            return 1
        content = args[2]
        script_path = FORGE_SCRIPTS / name
        script_path.write_text("#!/bin/bash\nset -euo pipefail\n\n" + content + "\n")
        script_path.chmod(0o755)
        print(f"✅ 已创建脚本: {script_path}")
        return 0

    print("用法: forge cron script [list|create <name> <content>]")
    return 1


# ════════════════════════════════════════════════════════════════
# CLI Entry
# ════════════════════════════════════════════════════════════════


def run(args: list[str]) -> int:
    if not args or args[0] in ("-h", "--help", "help"):
        print(f"""Forge Cron — 定时任务统一管理

用法: forge cron <子命令> [参数]

子命令:
  list                        列出所有定时任务
  register <name> [选项...]   注册新任务
       --schedule '<cron>'    cron 表达式 (如 '5 6 * * *')
       --script '<file>'      脚本文件名
       --desc '<text>'        描述
       --working-dir '<path>' 工作目录

  enable <name>               启用任务（生成 plist + 加载）
  disable <name>              禁用任务（卸载 + 移走 plist）
  status [name]               查看任务状态

  提醒事项 (macOS Reminders):
  reminder <name> [选项...]   创建提醒
       --title '<text>'       标题
       --body '<text>'        正文
       --schedule '<desc>'    调度描述 (如 '每周五 9:00')
  reminder-remove <keyword>   按关键词删除提醒

数据存储: {REGISTRY_FILE} → entities.cron
""")
        return 0

    cmd = args[0]
    cmd_args = args[1:]

    cmds = {
        "list": cmd_list,
        "ls": cmd_list,
        "register": cmd_register,
        "enable": cmd_enable,
        "start": cmd_enable,
        "disable": cmd_disable,
        "stop": cmd_disable,
        "status": cmd_status,
        "reminder": cmd_reminder_add,
        "reminder-remove": cmd_reminder_remove,
        "script": cmd_cron_script,
    }

    if cmd not in cmds:
        print(f"未知命令: {cmd}")
        print("运行 forge cron help 查看可用命令")
        return 1

    return cmds[cmd](cmd_args)


if __name__ == "__main__":
    sys.exit(run(sys.argv[1:]))
