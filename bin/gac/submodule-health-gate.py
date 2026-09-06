#!/usr/bin/env python3
"""
子模块健康门禁 — 检测漂移/未初始化/指针不一致.
"""
import json
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]


def run_cmd(cmd, cwd=str(WORKSPACE)):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd, timeout=30)
        return result.stdout.strip(), result.returncode
    except Exception as e:
        return "", 1


def check_submodule(sub_path):
    """检查单个子模块状态."""
    full_path = WORKSPACE / sub_path
    if not full_path.exists():
        return {"path": sub_path, "status": "missing"}

    info = {"path": sub_path, "status": "ok"}

    # 检查初始化
    rc = run_cmd(f"test -d {sub_path}/.git || test -f {sub_path}/.git")
    if rc[1] != 0:
        info["status"] = "uninitialized"
        return info

    # 远程分支数
    branches, _ = run_cmd(f"git -C {sub_path} branch -r 2>/dev/null | grep -v HEAD | wc -l")
    info["remote_branches"] = int(branches) if branches else 0

    # Tags 数
    tags, _ = run_cmd(f"git -C {sub_path} tag 2>/dev/null | wc -l")
    info["tags"] = int(tags) if tags else 0

    # 指针状态
    main_tip, _ = run_cmd(f"git -C {sub_path} rev-parse --verify origin/main 2>/dev/null")
    head_tip, _ = run_cmd(f"git -C {sub_path} rev-parse HEAD 2>/dev/null")

    if main_tip and head_tip:
        if main_tip == head_tip:
            info["pointer"] = "aligned"
        else:
            ahead, _ = run_cmd(f"git -C {sub_path} rev-list --count origin/main..HEAD 2>/dev/null")
            behind, _ = run_cmd(f"git -C {sub_path} rev-list --count HEAD..origin/main 2>/dev/null")
            ahead_count = int(ahead) if ahead else 0
            behind_count = int(behind) if behind else 0
            if ahead_count > 0 and behind_count > 0:
                info["pointer"] = f"diverged(+{ahead_count}/-{behind_count})"
            elif ahead_count > 0:
                info["pointer"] = f"ahead(+{ahead_count})"
            elif behind_count > 0:
                info["pointer"] = f"behind(-{behind_count})"
            else:
                info["pointer"] = "aligned"
    else:
        info["pointer"] = "no-remote"

    return info


def main():
    result = subprocess.run(
        ["git", "config", "--file", ".gitmodules", "--get-regexp", "path"],
        capture_output=True, text=True, cwd=str(WORKSPACE)
    )
    if result.returncode != 0:
        print("无子模块")
        return 0

    submodules = []
    for line in result.stdout.splitlines():
        if not line:
            continue
        parts = line.split()
        if len(parts) >= 2:
            submodules.append(parts[1])

    report = []
    failed = 0
    for sub in submodules:
        info = check_submodule(sub)
        report.append(info)
        if info["status"] != "ok":
            failed += 1

    output = {"submodules": report, "failed": failed, "total": len(report)}

    if "--json" in sys.argv:
        print(json.dumps(output, indent=2))
    else:
        print(f"子模块检查: {len(report)} 个, {failed} 个异常")
        for r in report:
            status_icon = "✓" if r["status"] == "ok" else "✗"
            print(f"  {status_icon} {r['path']}: {r['status']} branches={r.get('remote_branches', '-')} tags={r.get('tags', '-')}")

    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
