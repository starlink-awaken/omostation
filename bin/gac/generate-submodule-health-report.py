#!/usr/bin/env python3
"""
机制 22d (2026-09-06): 子模块健康度报告生成器.

使用:
  python bin/gac/generate-submodule-health-report.py           # 生成报告
  python bin/gac/generate-submodule-health-report.py --json    # JSON 输出
"""
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
REPORT_PATH = WORKSPACE / "docs/submodule-health.md"


def run_cmd(cmd, cwd="."):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd, timeout=30)
        return result.stdout.strip()
    except Exception:
        return ""


def gather_submodule_info():
    """收集所有子模块信息."""
    # 获取子模块路径
    result = run_cmd("grep 'path = ' .gitmodules | awk '{print $3}'", cwd=str(WORKSPACE))
    if not result:
        return []
    
    submodules = []
    for path in result.splitlines():
        path = path.strip()
        if not path:
            continue
        
        info = {"path": path, "name": path.split("/")-[-1] if "/" in path else path}
        
        # 远程分支数
        branches = run_cmd(f"git -C {path} branch -r 2>/dev/null | grep -v HEAD | wc -l", cwd=str(WORKSPACE))
        info["remote_branches"] = int(branches) if branches else 0
        
        # Tags 数
        tags = run_cmd(f"git -C {path} tag 2>/dev/null | wc -l", cwd=str(WORKSPACE))
        info["tags"] = int(tags) if tags else 0
        
        # 指针状态
        main_tip = run_cmd(f"git -C {path} rev-parse --verify origin/main 2>/dev/null", cwd=str(WORKSPACE))
        head_tip = run_cmd(f"git -C {path} rev-parse HEAD 2>/dev/null", cwd=str(WORKSPACE))
        
        if main_tip and head_tip:
            if main_tip == head_tip:
                info["status"] = "✅ 对齐"
            else:
                # 检查是否 ahead/behind
                ahead = run_cmd(f"git -C {path} rev-list --count origin/main..HEAD 2>/dev/null", cwd=str(WORKSPACE))
                behind = run_cmd(f"git -C {path} rev-list --count HEAD..origin/main 2>/dev/null", cwd=str(WORKSPACE))
                ahead_count = int(ahead) if ahead else 0
                behind_count = int(behind) if behind else 0
                
                if ahead_count > 0 and behind_count > 0:
                    info["status"] = f"⚠️ DIVERGED (+{ahead_count}/-{behind_count})"
                elif ahead_count > 0:
                    info["status"] = f"⬆️ +{ahead_count}"
                elif behind_count > 0:
                    info["status"] = f"⬇️ -{behind_count}"
                else:
                    info["status"] = "✅ 对齐"
        else:
            info["status"] = "❌ 未初始化"
        
        # 最后 commit 时间
        last_commit = run_cmd(f"git -C {path} log -1 --format='%ci' 2>/dev/null", cwd=str(WORKSPACE))
        info["last_commit"] = last_commit[:10] if last_commit else "N/A"
        
        submodules.append(info)
    
    return submodules


def generate_report(submodules):
    """生成 Markdown 报告."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    
    total_branches = sum(s["remote_branches"] for s in submodules)
    total_tags = sum(s["tags"] for s in submodules)
    drift_count = sum(1 for s in submodules if "DIVERGED" in s.get("status", ""))
    uninitialized = sum(1 for s in submodules if "未初始化" in s.get("status", ""))
    
    lines = [
        f"# 子模块健康度报告",
        "",
        f"> 生成时间: {now}",
        f"> 自动生成: `bin/gac/generate-submodule-health-report.py`",
        "",
        "## 概览",
        "",
        "| 指标 | 数值 |",
        "|------|------:|",
        f"| 子模块总数 | {len(submodules)} |",
        f"| 远程分支总数 | {total_branches} |",
        f"| Tags 总数 | {total_tags} |",
        f"| 指针漂移 | {drift_count} |",
        f"| 未初始化 | {uninitialized} |",
        "",
        "## 子模块详情",
        "",
        "| 子模块 | 远程分支 | Tags | 指针状态 | 最后同步 |",
        "|--------|----------|------|----------|----------|",
    ]
    
    for s in submodules:
        lines.append(f"| {s['name']} | {s['remote_branches']} | {s['tags']} | {s['status']} | {s['last_commit']} |")
    
    lines.extend([
        "",
        "## 建议",
        "",
        "- 定期清理已合入 main 的远程分支",
        "- 清理过期 tags，保留最近 20 个",
        "- 同步子模块指针到最新 origin/main",
        "- 清理悬空 tracking 分支",
        "",
        "---",
        "",
        "*本报告由 `bin/gac/generate-submodule-health-report.py` 自动生成.*",
    ])
    
    return "\n".join(lines)


def main() -> int:
    print("[generate-submodule-health-report] 开始生成报告...")
    submodules = gather_submodule_info()
    report = generate_report(submodules)
    
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    
    print(f"[generate-submodule-health-report] 已生成 {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
