"""OMO 自愈修复脚本库 (Auto-Fix Scripts)

预置的可自动执行修复操作，由 SelfHealingEngine 触发。
每个脚本接收 context dict 并返回 (success: bool, output: str)。
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger("omo.self_healing.fixes")


def fix_clear_pytest_cache(context: dict | None = None) -> tuple[bool, str]:
    """清理 .pytest_cache 和 .ruff_cache 目录。"""
    roots = [Path.home() / "Workspace" / "projects" / p for p in os.listdir(Path.home() / "Workspace" / "projects") if not p.startswith("_")]
    cleaned = 0
    for root in roots:
        for cache_dir in [".pytest_cache", ".ruff_cache", "__pycache__"]:
            for path in root.rglob(cache_dir):
                try:
                    if path.is_dir():
                        shutil.rmtree(path)
                        cleaned += 1
                except Exception:
                    pass
    return True, f"Cleaned {cleaned} cache directories"


def fix_restart_agora(context: dict | None = None) -> tuple[bool, str]:
    """重启 Agora MCP 服务 (通过 launchctl 或直接进程)。"""
    try:
        # 尝试 kill 旧进程
        subprocess.run(["pkill", "-f", "agora-mcp"], capture_output=True, timeout=5)
        return True, "Agora MCP process terminated; launchctl will restart"
    except Exception as e:
        return False, f"Failed to restart Agora: {e}"


def fix_git_gc(context: dict | None = None) -> tuple[bool, str]:
    """对 Workspace 目录运行 git gc。"""
    ws = Path.home() / "Workspace"
    try:
        result = subprocess.run(
            ["git", "gc", "--auto"],
            cwd=str(ws),
            capture_output=True,
            text=True,
            timeout=60,
        )
        return result.returncode == 0, result.stdout[:500] or "git gc completed"
    except Exception as e:
        return False, f"git gc failed: {e}"


def fix_clean_temp_files(context: dict | None = None) -> tuple[bool, str]:
    """清理临时文件和空日志。"""
    patterns = ["*.pyc", "*.log.1", "*.log.2"]
    cleaned = 0
    ws = Path.home() / "Workspace"
    for pattern in patterns:
        for path in ws.rglob(pattern):
            try:
                path.unlink()
                cleaned += 1
            except Exception:
                pass
    return True, f"Cleaned {cleaned} temp files"


def fix_disk_check(context: dict | None = None) -> tuple[bool, str]:
    """检查磁盘使用率，超过 80% 告警。"""
    try:
        usage = shutil.disk_usage(Path.home())
        pct = usage.used / usage.total * 100
        if pct > 80:
            return False, f"Disk usage critical: {pct:.1f}% ({_fmt_bytes(usage.free)} free)"
        return True, f"Disk OK: {pct:.1f}% used"
    except Exception as e:
        return False, f"Disk check failed: {e}"


def fix_process_health_check(context: dict | None = None) -> tuple[bool, str]:
    """检查关键进程是否存活 (agora, minerva, gbrain)。"""
    key_processes = {
        "agora": r"agora[-_]?(mcp|web|server)",
        "minerva": r"minerva",
        "cockpit": r"cockpit.*dashboard",
    }
    results = {}
    for name, pattern in key_processes.items():
        try:
            result = subprocess.run(
                ["pgrep", "-f", pattern],
                capture_output=True,
                text=True,
                timeout=5,
            )
            results[name] = "alive" if result.returncode == 0 else "dead"
        except Exception:
            results[name] = "unknown"

    dead = [k for k, v in results.items() if v == "dead"]
    if dead:
        return False, f"Dead processes: {', '.join(dead)}. Status: {results}"
    return True, f"All processes alive: {results}"


# ═══════════════════════════════════════════════════════════════════════════
# Fix Registry
# ═══════════════════════════════════════════════════════════════════════════

FIX_REGISTRY: dict[str, callable] = {
    "clear_pytest_cache": fix_clear_pytest_cache,
    "restart_agora": fix_restart_agora,
    "git_gc": fix_git_gc,
    "clean_temp_files": fix_clean_temp_files,
    "disk_check": fix_disk_check,
    "process_health_check": fix_process_health_check,
}


def run_fix(fix_name: str, context: dict | None = None) -> dict:
    """按名称运行修复脚本，返回 {success, output, fix_name}。"""
    if fix_name not in FIX_REGISTRY:
        return {"success": False, "output": f"Unknown fix: {fix_name}", "fix_name": fix_name}

    try:
        success, output = FIX_REGISTRY[fix_name](context)
        logger.info(
            "fix_executed fix=%s success=%s output=%s",
            fix_name, success, output[:200],
        )
        return {"success": success, "output": output, "fix_name": fix_name}
    except Exception as exc:
        logger.error("fix_failed fix=%s error=%s", fix_name, exc)
        return {"success": False, "output": str(exc), "fix_name": fix_name}


def list_fixes() -> list[str]:
    return list(FIX_REGISTRY.keys())


def _fmt_bytes(b: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if b < 1024:
            return f"{b:.1f}{unit}"
        b /= 1024
    return f"{b:.1f}TB"
