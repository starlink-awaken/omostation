#!/usr/bin/env python3
"""
cron_utils — Forge 定时任务共享工具库

被 cron_manager.py (CLI) 和 mcp_server.py (MCP) 共同导入，
消除 plist 生成、launchctl 操作、schedule 解析的重复代码。
"""

from __future__ import annotations

import fcntl
import json
import os
import plistlib
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, cast

# ── 安全校验 ──

_SAFE_NAME = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$")
_SAFE_SCRIPT = re.compile(r"^[a-zA-Z0-9/_.-]+\.(sh|py)$")


def validate_task_name(name: str) -> bool:
    return bool(_SAFE_NAME.match(name))


def validate_working_dir(path_str: str) -> bool:
    """Validate that a working directory path is safe to use in launchd plists."""
    if not path_str or not path_str.strip():
        return False
    # Reject shell metacharacters
    unsafe = set(";|&`$(){}<>")
    if any(c in path_str for c in unsafe):
        return False
    try:
        resolved = Path(path_str).resolve()
    except (RuntimeError, OSError):
        return False
    if not resolved.exists() or not resolved.is_dir():
        return False
    # Must be an absolute path under home dir or root (no relative traversal)
    home = Path.home()
    if resolved == home:
        return True
    try:
        resolved.relative_to(home)
        return True
    except ValueError:
        pass
    try:
        resolved.relative_to("/")
        return True
    except ValueError:
        return False


def validate_script_name(script: str) -> bool:
    if not script:
        return True
    if script.startswith("/"):
        return False
    return bool(_SAFE_SCRIPT.match(script))


# ── 路径 ──
from forge.forge_config import ASSET_REGISTRY as REGISTRY_FILE  # type: ignore[import-not-found]
from forge.forge_config import DISABLED_DIR, LAUNCH_AGENTS, LOG_DIR


def plist_path(name: str) -> Path:
    return LAUNCH_AGENTS / f"local.{name}.plist"


def disabled_plist_path(name: str) -> Path:
    return DISABLED_DIR / f"local.{name}.plist"


def plist_label(name: str) -> str:
    return f"local.{name}"


def log_file(name: str) -> str:
    return str(LOG_DIR / f"{name}.log")


def err_file(name: str) -> str:
    return str(LOG_DIR / f"{name}.err")


# ── Registry IO ──

MAX_REGISTRY_BYTES = 100 * 1024 * 1024  # 100MB


def load_registry() -> dict:
    try:
        if REGISTRY_FILE.stat().st_size > MAX_REGISTRY_BYTES:
            print(f"❌ registry 过大 ({REGISTRY_FILE.stat().st_size / 1024 / 1024:.0f}MB > 100MB)")
            return {}
        with REGISTRY_FILE.open("rb") as f:
            fcntl.flock(f, fcntl.LOCK_SH)
            return cast("dict", json.load(f))
    except FileNotFoundError:
        print(f"❌ registry 不存在: {REGISTRY_FILE}")
        return {}
    except json.JSONDecodeError:
        print(f"❌ registry 文件损坏: {REGISTRY_FILE}")
        return {}


def save_registry(reg: dict) -> None:
    reg["updated"] = datetime.now().isoformat()
    tmp = REGISTRY_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(reg, indent=2, ensure_ascii=False) + "\n")
    with REGISTRY_FILE.open("rb") as lock_f:
        fcntl.flock(lock_f, fcntl.LOCK_EX)
        tmp.rename(REGISTRY_FILE)


def get_cron_items(reg: dict) -> list[dict]:
    if reg.get("version") == 4 and "entities" in reg:
        return cast("list[dict]", reg["entities"].get("cron", {}).get("items", []))
    return []


def find_cron_item(items: list[dict], name: str) -> int | None:
    for i, item in enumerate(items):
        if item.get("name") == name:
            return i
    return None


# ── 调度解析 ──


def parse_schedule(schedule: Any) -> dict | None:
    """将 cron 表达式或 dict 转为 launchd StartCalendarInterval 格式。"""
    if isinstance(schedule, dict):
        return {k: int(v) for k, v in schedule.items() if k in ("Minute", "Hour", "Day", "Weekday", "Month")}
    if isinstance(schedule, str):
        parts = schedule.strip().split()
        if len(parts) < 2:
            return None
        result = {}
        if parts[0] != "*" and "/" not in parts[0] and "," not in parts[0]:
            try:
                result["Minute"] = int(parts[0])
            except ValueError:
                pass
        if len(parts) > 1 and parts[1] != "*" and "/" not in parts[1] and "," not in parts[1]:
            try:
                result["Hour"] = int(parts[1])
            except ValueError:
                pass
        if len(parts) > 4 and parts[4] != "*" and "/" not in parts[4] and "," not in parts[4]:
            try:
                result["Weekday"] = int(parts[4])
            except ValueError:
                pass
        return result if result else None
    return None


def schedule_display(schedule: Any) -> str:
    """返回人类可读的调度描述。"""
    if isinstance(schedule, dict):
        parts = []
        if "Minute" in schedule:
            parts.append(f"{schedule['Minute']}分")
        if "Hour" in schedule:
            parts.append(f"{schedule['Hour']}时")
        if "Weekday" in schedule:
            days = ["日", "一", "二", "三", "四", "五", "六"]
            parts.append(f"周{days[schedule['Weekday']]}")
        return " ".join(parts) if parts else str(schedule)
    if isinstance(schedule, str):
        parts = schedule.strip().split()
        if len(parts) < 2:
            return schedule
        minute = parts[0]
        hour = parts[1]
        weekday = parts[4] if len(parts) > 4 else "*"
        result = []
        if hour != "*":
            result.append(f"{hour}时")
        if minute != "*" and "/" not in minute:
            result.append(f"{minute}分")
        if "/" in minute:
            result.append(f"每{minute.split('/')[1]}分钟")
        if weekday != "*":
            day_names = {"0": "周日", "1": "周一", "2": "周二", "3": "周三", "4": "周四", "5": "周五", "6": "周六"}
            result.append(day_names.get(weekday, f"周{weekday}"))
        return " ".join(result) if result else schedule
    return str(schedule)


# ── launchctl 操作 ──


def launchctl_is_loaded(name: str) -> bool:
    label = plist_label(name)
    try:
        r = subprocess.run(
            ["launchctl", "print", f"gui/{os.getuid()}/{label}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return r.returncode == 0
    except Exception:
        return False


def launchctl_bootstrap(name: str) -> tuple[bool, str]:
    plist = plist_path(name)
    try:
        r = subprocess.run(
            ["launchctl", "bootstrap", f"gui/{os.getuid()}", str(plist)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode == 0:
            return True, "已加载"
        if r.returncode == 36:
            return True, "已加载（之前已存在）"
        if r.returncode == 2 and "No such file" in r.stderr:
            return False, f"plist 不存在: {plist}"
        return False, r.stderr.strip() or f"exit code {r.returncode}"
    except Exception as e:
        return False, str(e)


def launchctl_bootout(name: str) -> tuple[bool, str]:
    label = plist_label(name)
    try:
        r = subprocess.run(
            ["launchctl", "bootout", f"gui/{os.getuid()}/{label}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode == 0:
            return True, "已卸载"
        if r.returncode == 36:
            return True, "未加载（无需卸载）"
        return False, r.stderr.strip() or f"exit code {r.returncode}"
    except Exception as e:
        return False, str(e)


# ── plist 生成 ──


def generate_plist_xml(
    name: str, script_cmd: str, working_dir: str | None, schedule: dict | str | None, description: str = ""
) -> bytes:
    plist: dict = {
        "Label": plist_label(name),
        "ProgramArguments": ["/bin/bash", "-c", script_cmd],
        "RunAtLoad": False,
        "KeepAlive": False,
        "StandardOutPath": log_file(name),
        "StandardErrorPath": err_file(name),
    }
    if schedule is not None:
        parsed = parse_schedule(schedule)
        if parsed:
            plist["StartCalendarInterval"] = parsed
    if working_dir:
        if not validate_working_dir(working_dir):
            raise ValueError(f"不安全的工作目录: {working_dir}")
        plist["WorkingDirectory"] = working_dir
    if description:
        plist["Description"] = description[:255]
    return plistlib.dumps(plist)
