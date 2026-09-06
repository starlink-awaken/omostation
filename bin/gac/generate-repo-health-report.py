#!/usr/bin/env python3
"""
机制 22d (2026-09-06): 仓库健康度周报生成器.
"""
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
AUDIT_HEALTH = WORKSPACE / "bin/ssot/audit-repo-health.sh"
REPORT_PATH = WORKSPACE / "docs/repository-health.md"


def run_audit() -> dict:
    try:
        result = subprocess.run(
            ["bash", str(AUDIT_HEALTH), "--json", "--limit", "5"],
            cwd=str(WORKSPACE), capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)
    except Exception:
        pass
    return {}


def gather_local_stats() -> dict:
    stats = {}
    try:
        result = subprocess.run(["git", "branch", "-r"], cwd=str(WORKSPACE), capture_output=True, text=True)
        stats["remote_branches"] = len([l for l in result.stdout.splitlines() if l.strip() and "HEAD" not in l])
    except Exception:
        stats["remote_branches"] = -1
    try:
        result = subprocess.run(["git", "branch"], cwd=str(WORKSPACE), capture_output=True, text=True)
        stats["local_branches"] = len([l for l in result.stdout.splitlines() if l.strip()])
    except Exception:
        stats["local_branches"] = -1
    try:
        result = subprocess.run(["git", "tag"], cwd=str(WORKSPACE), capture_output=True, text=True)
        stats["tags"] = len([l for l in result.stdout.splitlines() if l.strip()])
    except Exception:
        stats["tags"] = -1
    try:
        result = subprocess.run(["git", "worktree", "list"], cwd=str(WORKSPACE), capture_output=True, text=True)
        stats["worktrees"] = len([l for l in result.stdout.splitlines() if l.strip()])
    except Exception:
        stats["worktrees"] = -1
    try:
        result = subprocess.run(["git", "count-objects"], cwd=str(WORKSPACE), capture_output=True, text=True)
        stats["loose_objects"] = result.stdout.strip()
    except Exception:
        stats["loose_objects"] = "unknown"
    try:
        result = subprocess.run(["git", "submodule", "status"], cwd=str(WORKSPACE), capture_output=True, text=True)
        submodules = [l for l in result.stdout.splitlines() if l.strip()]
        stats["submodules"] = len(submodules)
        stats["submodule_drift"] = len([l for l in submodules if l.startswith("+") or l.startswith("-")])
    except Exception:
        stats["submodules"] = -1
        stats["submodule_drift"] = 0
    return stats


def generate_report(audit: dict, stats: dict) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# 仓库健康度周报",
        "",
        f"> 生成时间: {now}",
        f"> 自动生成: `bin/gac/generate-repo-health-report.py`",
        "",
        "## 本地仓库统计",
        "",
        "| 指标 | 数值 |",
        "|------|------:|",
        f"| 远程分支 | {stats.get('remote_branches', '-')} |",
        f"| 本地分支 | {stats.get('local_branches', '-')} |",
        f"| Tags | {stats.get('tags', '-')} |",
        f"| Worktrees | {stats.get('worktrees', '-')} |",
        f"| 子模块 | {stats.get('submodules', '-')} |",
        f"| 子模块漂移 | {stats.get('submodule_drift', '-')} |",
        f"| 松散对象 | {stats.get('loose_objects', '-')} |",
        "",
        "## 多仓库 CI 状态",
        "",
    ]
    if audit:
        for repo, data in audit.items():
            lines.append(f"### {repo}")
            lines.append("")
            if isinstance(data, dict):
                workflows = data.get("workflows", [])
                if workflows:
                    lines.append("| Workflow | 状态 |")
                    lines.append("|----------|------|")
                    for wf in workflows:
                        name = wf.get("name", "unknown")
                        status = wf.get("status", "unknown")
                        icon = "✅" if status == "green" else "❌"
                        lines.append(f"| {name} | {icon} {status} |")
                    lines.append("")
    lines.extend([
        "",
        "## 维护建议",
        "",
        "- 定期清理已合并的 work 分支",
        "- 清理过期的 tags",
        "- 同步子模块指针到最新 main",
        "- 清理僵尸 worktree",
        "",
        "---",
        "",
        "*本报告由 `bin/gac/generate-repo-health-report.py` 自动生成.*",
    ])
    return "\n".join(lines)


def main() -> int:
    print("[generate-repo-health-report] 开始生成周报...")
    audit = run_audit()
    stats = gather_local_stats()
    report = generate_report(audit, stats)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(f"[generate-repo-health-report] 已生成 {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
