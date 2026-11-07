#!/usr/bin/env python3
"""运维自动化 — Cron 任务安装器.

统一管理所有定时任务:
- 系统健康检查 (每 5 分钟)
- 周进化报告 (每周一 09:00)
- 周价值回顾 (每周五 17:00)
- 架构漂移检测 (每天 06:00)

Usage:
    python3 bin/gac/ops-cron-install.py --install   # 安装所有 cron
    python3 bin/gac/ops-cron-install.py --remove    # 移除所有 cron
    python3 bin/gac/ops-cron-install.py --list      # 列出已安装 cron
    python3 bin/gac/ops-cron-install.py --dry-run   # 显示将要安装的任务
"""
import subprocess
import sys
from pathlib import Path

# parents[1] 是 bin/ (命令会变成 cd bin && python3 bin/ops/... => bin/bin/ops/...);
# 本脚本在 bin/gac/ 下, 仓库根是 parents[2]。
REPO = Path(__file__).resolve().parents[2]
CRONTAG = "# omostation-ops"

JOBS = [
    {
        "schedule": "*/5 * * * *",
        "command": f"cd {REPO} && python3 bin/ops/health-check-cron.py --quiet",
        "comment": "系统健康检查 (5min)",
    },
    {
        "schedule": "0 9 * * 1",
        "command": f"cd {REPO} && python3 bin/gac/weekly-evolution-report.py",
        "comment": "周进化报告 (Mon 09:00)",
    },
    {
        "schedule": "0 17 * * 5",
        "command": f"cd {REPO} && python3 bin/gac/weekly-review.py --generate",
        "comment": "周价值回顾 (Fri 17:00)",
    },
    {
        "schedule": "0 6 * * *",
        "command": f"cd {REPO} && python3 bin/gac/architecture-drift.py",
        "comment": "架构漂移检测 (daily 06:00)",
    },
]


def get_current_crontab():
    r = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""


REGISTRY = Path(__file__).resolve().parents[2] / ".omo" / "cron" / "registry.yaml"


def registered_active_commands() -> list[str]:
    """登记面里 status=active 且 planes 含 crontab 的命令 (空白归一化)。

    `.omo/cron/registry.yaml` 是 cron 作业的唯一 SSOT —— 装登记面外的作业会让
    scheduler-compile --check 报 orphan。
    """
    import yaml

    if not REGISTRY.is_file():
        return []
    docs = [d for d in yaml.safe_load_all(REGISTRY.read_text(encoding="utf-8")) if d]
    if not docs:
        return []
    out = []
    for job in docs[-1].get("jobs", []):
        if job.get("status") != "active":
            continue
        if "crontab" not in (job.get("planes") or []):
            continue
        out.append(" ".join((job.get("command") or "").split()))
    return out


def unregistered_jobs() -> list[dict]:
    """本工具 JOBS 里未出现在登记面 active crontab 条目中的作业。

    判据取「命令里的脚本路径是否出现在任一条登记面命令里」而不是整行相等:
    登记面写 `$HOME/Workspace`、本工具写绝对路径, 整行永远不相等。
    """
    registered = registered_active_commands()
    missing = []
    for job in JOBS:
        marker = "python3 "
        script = job["command"].split(marker, 1)[-1].split(" ", 1)[0] if marker in job["command"] else ""
        if script and not any(script in cmd for cmd in registered):
            missing.append(job)
    return missing


def render(crontab: str) -> str:
    """渲染要写入的 crontab 全文。

    dry-run 与 install **共用这一份**: 此前 dry-run 只打印 schedule + comment、
    不打印 command, 于是「命令里的路径写错了」在装之前完全看不见 (实证: REPO
    曾解析成 bin/, 4 条命令全指向不存在的 bin/bin/..., 而 --dry-run 一切正常)。
    """
    lines = [l for l in crontab.splitlines() if CRONTAG not in l and l.strip()]
    lines.append(f"\n{CRONTAG}-start")
    for job in JOBS:
        lines.append(f"# {job['comment']}")
        lines.append(f"{job['schedule']} {job['command']} {CRONTAG}")
    lines.append(f"{CRONTAG}-end\n")
    return "\n".join(lines)


def install() -> int:
    missing = unregistered_jobs()
    if missing:
        print(
            "❌ 以下作业不在 .omo/cron/registry.yaml 的 active crontab 条目里:",
            file=sys.stderr,
        )
        for job in missing:
            print(f"   - {job['comment']}: {job['command']}", file=sys.stderr)
        print(
            "   装它们会让 scheduler-compile --check 报 orphan (门禁红)。",
            file=sys.stderr,
        )
        print(
            "   请先把它们登记进 registry 并置 active, 或用 bin/ops/install-cron-plane.py。",
            file=sys.stderr,
        )
        return 1
    new_crontab = render(get_current_crontab())
    subprocess.run(["crontab", "-"], input=new_crontab, text=True, check=True)
    print(f"Installed {len(JOBS)} cron jobs")
    return 0


def remove():
    current = get_current_crontab()
    lines = [l for l in current.splitlines() if CRONTAG not in l]
    new_crontab = "\n".join(lines)
    subprocess.run(["crontab", "-"], input=new_crontab, text=True, check=True)
    print("Removed all omostation cron jobs")


def list_jobs():
    current = get_current_crontab()
    in_block = False
    count = 0
    for line in current.splitlines():
        if f"{CRONTAG}-start" in line:
            in_block = True
            continue
        if f"{CRONTAG}-end" in line:
            in_block = False
            continue
        if in_block and not line.startswith("#"):
            print(f"  {line}")
            count += 1
    print(f"\nTotal: {count} jobs installed")


def dry_run() -> int:
    missing = unregistered_jobs()
    if missing:
        print(
            f"⚠️  {len(missing)}/{len(JOBS)} 个作业不在登记面的 active crontab 条目里 —— --install 会被拒:",
            file=sys.stderr,
        )
        for job in missing:
            print(f"   - {job['comment']}", file=sys.stderr)
    print("Would install:")
    for line in render("").splitlines():
        if line.strip():
            print(f"  {line}")
    return 1 if missing else 0


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="运维 Cron 安装器")
    parser.add_argument("--install", action="store_true")
    parser.add_argument("--remove", action="store_true")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.install:
        return install()
    if args.remove:
        remove()
        return 0
    if args.list:
        list_jobs()
        return 0
    if args.dry_run:
        return dry_run()
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
