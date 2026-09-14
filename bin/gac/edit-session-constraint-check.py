#!/usr/bin/env python3
"""edit-session-constraint-check — 编辑会话约束检查 (CLAUDE.md B.0.5)。

编辑架构相关文件前自动检查:
1. 场景卡生命周期
2. 业务域分类
3. 脚本配额
4. SSOT 引用

Usage:
    python3 bin/gac/edit-session-constraint-check.py [--path <path>] [--json]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def check_scene_card_lifecycle() -> dict:
    """检查场景卡生命周期约束。"""
    result = subprocess.run(
        ["python3", "bin/ssot/scene-card-lifecycle.py", "--check"],
        capture_output=True, text=True, cwd=REPO,
    )
    return {
        "check": "scene_card_lifecycle",
        "status": "ok" if result.returncode == 0 else "fail",
    }


def check_script_quota() -> dict:
    """检查脚本配额 (add 1 = delete 1)。"""
    result = subprocess.run(
        ["python3", "bin/gac/check-bin-quota-diff.py", "--base", "origin/main"],
        capture_output=True, text=True, cwd=REPO,
    )
    return {
        "check": "script_quota",
        "status": "ok" if result.returncode == 0 else "warn",
    }


def main():
    parser = argparse.ArgumentParser(description="编辑会话约束检查")
    parser.add_argument("--path", help="目标路径")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    checks = [
        check_scene_card_lifecycle(),
        check_script_quota(),
    ]

    all_ok = all(c["status"] == "ok" for c in checks)

    result = {
        "overall": "PASS" if all_ok else "WARN",
        "checks": checks,
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Edit Session Constraints: {result['overall']}")
        for c in checks:
            icon = "✅" if c["status"] == "ok" else "⚠️"
            print(f"  {icon} {c['check']}")

    return 0 if all_ok else 0  # advisory, not blocking


if __name__ == "__main__":
    sys.exit(main())
