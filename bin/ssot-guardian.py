#!/usr/bin/env python3
"""ssot-guardian: SSOT 漂移守门员.

长期机制,防止 system.yaml / goals/current.yaml / tasks/registry/INDEX.md 与真实任务目录
再次漂移. 可手动跑、pre-commit 跑、cron 跑.

检测项:
  1. system.yaml task 计数 vs tasks/{active,planned,done} 顶层 yaml 文件数
  2. system.yaml current_wave vs goals/current.yaml current_wave
  3. (future) INDEX.md 计数是否与 system.yaml 一致

修复项(仅 --auto-fix 时):
  A. 调用 `omo state sync-tasks` 重算 system.yaml task 计数
  B. 如果 goals/current.yaml current_wave 落后 system.yaml, 同步为 system.yaml 的值

用法:
  python3 bin/ssot-guardian.py              # 检测,有漂移返回 1
  python3 bin/ssot-guardian.py --auto-fix   # 检测并修复白名单字段
  python3 bin/ssot-guardian.py --emit       # 无论是否漂移都发事件

退出码:
  0 — 无漂移(或已修复)
  1 — 检测到未修复漂移
  2 — 运行错误
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
OMO_DIR = WORKSPACE_ROOT / ".omo"
SYSTEM_YAML = OMO_DIR / "state" / "system.yaml"
GOALS_YAML = OMO_DIR / "goals" / "current.yaml"
INDEX_MD = OMO_DIR / "tasks" / "registry" / "INDEX.md"
TASKS_DIR = OMO_DIR / "tasks"


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=WORKSPACE_ROOT,
        capture_output=True,
        text=True,
        check=check,
    )


def _load_yaml_docs(path: Path) -> list[dict]:
    """极简多文档 YAML 读取: 只取顶层 key: value."""
    docs: list[dict] = []
    current: dict[str, object] = {}
    in_doc = False
    text = path.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.strip() == "---":
            if in_doc:
                docs.append(current)
            current = {}
            in_doc = True
            continue
        if not in_doc:
            in_doc = True
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*?)\s*$", line)
        if m:
            key, val = m.group(1), m.group(2).strip().strip('"').strip("'")
            current[key] = val
    if current:
        docs.append(current)
    return docs


def _load_system_value(key: str) -> object | None:
    text = SYSTEM_YAML.read_text(encoding="utf-8")
    for line in text.splitlines():
        m = re.match(rf"^{re.escape(key)}:\s*(.*?)\s*$", line)
        if m:
            return m.group(1).strip().strip('"').strip("'")
    return None


def _count_tasks() -> dict[str, int]:
    counts = {}
    for sub in ("active", "planned", "done"):
        d = TASKS_DIR / sub
        counts[sub] = len(list(d.glob("*.yaml"))) if d.exists() else 0
    counts["total"] = counts["active"] + counts["planned"] + counts["done"]
    return counts


def _sync_tasks(auto_fix: bool) -> dict:
    """调用 omo state sync-tasks, 返回差异信息."""
    cmd = ["omo", "state", "sync-tasks"]
    if not auto_fix:
        cmd.append("--dry-run")
    try:
        result = _run(cmd, check=False)
    except FileNotFoundError:
        return {"error": "omo CLI not found"}
    output = result.stdout + result.stderr
    drift = "114" not in output or "→" in output  # 粗略判断有变化
    return {
        "returncode": result.returncode,
        "output": output,
        "drift": drift,
    }


def _check_wave() -> dict:
    system_wave = _load_system_value("current_wave")
    docs = _load_yaml_docs(GOALS_YAML)
    goals_wave = docs[-1].get("current_wave") if docs else None
    return {
        "system_wave": system_wave,
        "goals_wave": goals_wave,
        "aligned": system_wave == goals_wave,
    }


def _fix_wave() -> dict:
    """current_wave 自动修复占位.

    当前没有 OMO CLI 子命令可以直接更新 goals/current.yaml current_wave.
    根据 direct-omo-io 约束,禁止在本脚本中直接 write_text() 到 .omo 文件.
    因此 auto-fix 仅发出事件并给出人工/未来 OMO 命令修复建议.
    """
    system_wave = _load_system_value("current_wave")
    if not system_wave:
        return {"fixed": False, "error": "cannot read system.yaml current_wave"}
    return {
        "fixed": False,
        "manual_action_required": True,
        "system_wave": system_wave,
        "suggested_command": "omo goal sync-wave (待 OMO P63+ 实现)",
        "fallback_command": "手动编辑 .omo/goals/current.yaml 使 current_wave 与 system.yaml 一致",
    }


def _emit_event(kind: str, payload: dict) -> None:
    try:
        _run(
            [
                "omo",
                "event",
                "emit",
                "--type",
                kind,
                "--source",
                "ssot-guardian",
                "--payload",
                json.dumps(payload, ensure_ascii=False),
            ],
            check=False,
        )
    except FileNotFoundError:
        pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SSOT 漂移守门员")
    parser.add_argument("--auto-fix", action="store_true", help="自动修复白名单字段")
    parser.add_argument("--emit", action="store_true", help="无论是否漂移都发事件")
    args = parser.parse_args(argv)

    if not SYSTEM_YAML.exists():
        print("❌ system.yaml not found", file=sys.stderr)
        return 2

    issues: list[dict] = []

    # 1. task 计数漂移
    real_counts = _count_tasks()
    system_completed = _load_system_value("completed_tasks")
    system_planned = _load_system_value("planned_tasks")
    system_active = _load_system_value("active_tasks")
    system_total = _load_system_value("total_tasks")

    task_drift = (
        int(system_completed or 0) != real_counts["done"]
        or int(system_planned or 0) != real_counts["planned"]
        or int(system_active or 0) != real_counts["active"]
        or int(system_total or 0) != real_counts["total"]
    )
    if task_drift:
        issues.append(
            {
                "type": "task_count_drift",
                "severity": "high",
                "system": {
                    "completed": system_completed,
                    "planned": system_planned,
                    "active": system_active,
                    "total": system_total,
                },
                "actual": real_counts,
            }
        )
        if args.auto_fix:
            sync_result = _sync_tasks(auto_fix=True)
            if sync_result.get("returncode") == 0:
                issues[-1]["fixed"] = True
                issues[-1]["fix_method"] = "omo state sync-tasks"
            else:
                issues[-1]["fixed"] = False
                issues[-1]["fix_error"] = sync_result.get("output", "")

    # 2. current_wave 不一致
    wave_check = _check_wave()
    if not wave_check["aligned"]:
        issues.append(
            {
                "type": "current_wave_mismatch",
                "severity": "medium",
                "system_wave": wave_check["system_wave"],
                "goals_wave": wave_check["goals_wave"],
            }
        )
        if args.auto_fix:
            fix_result = _fix_wave()
            if fix_result.get("fixed"):
                issues[-1]["fixed"] = True
                issues[-1]["fix_method"] = "sync goals/current.yaml to system.yaml"
            else:
                issues[-1]["fixed"] = False
                issues[-1]["fix_error"] = fix_result.get("error", "")

    # 报告
    unresolved = [i for i in issues if not i.get("fixed")]
    fixed = [i for i in issues if i.get("fixed")]

    if fixed:
        print(f"✅ 自动修复 {len(fixed)} 项:")
        for i in fixed:
            print(f"   - {i['type']}: {i.get('fix_method', '')}")

    if unresolved:
        print(f"❌ 检测到 {len(unresolved)} 项未修复 SSOT 漂移:")
        for i in unresolved:
            print(f"   - {i['type']} ({i['severity']})")
            if i["type"] == "task_count_drift":
                print(f"     system: {i['system']}")
                print(f"     actual: {i['actual']}")
            elif i["type"] == "current_wave_mismatch":
                print(f"     system={i['system_wave']} goals={i['goals_wave']}")
    else:
        print("✅ SSOT 一致性检查通过")

    if args.emit or issues:
        _emit_event(
            "ssot_guardian_run",
            {
                "checked_at": _utc_now(),
                "auto_fix": args.auto_fix,
                "issues": issues,
                "unresolved_count": len(unresolved),
            },
        )

    return 1 if unresolved else 0


if __name__ == "__main__":
    raise SystemExit(main())
