#!/usr/bin/env python3
"""scheduler-compile.py — 调度编译器: 单一登记源 → 校验三格式一致性 (ADR-A).

读取 .omo/cron/registry.yaml 登记源, 校验 crontab -l 安装态是否与登记一致.
发现漂移即报告 (unregistered/orphan), exit 1 = 存在漂移.

用法:
  python3 bin/scheduler-compile.py --check    # 校验模式 (CI/cron)
  python3 bin/scheduler-compile.py --report   # 报告模式 (人类审阅)
"""
from __future__ import annotations
import argparse, json, subprocess, sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
REGISTRY = WORKSPACE / ".omo" / "cron" / "registry.yaml"


def _load_registry() -> list[dict]:
    """从 registry.yaml 加载登记条目."""
    import yaml
    if not REGISTRY.exists():
        return []
    docs = [d for d in yaml.safe_load_all(REGISTRY.read_text()) if d]
    main = docs[-1] if docs else {}
    return main.get("jobs", [])


def _load_crontab_lines() -> list[str]:
    r = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=10)
    return r.stdout.splitlines() if r.returncode == 0 else []


def _job_fingerprint(cmd_snippet: str) -> str:
    """取命令核心部分作为 job 指纹 (跳过环境变量前缀)."""
    for sep in ("&&", ";"):
        if sep in cmd_snippet:
            cmd_snippet = cmd_snippet.split(sep)[-1].strip()
    return cmd_snippet[:120]


def check_drift() -> dict:
    registered = _load_registry()
    installed_raw = _load_crontab_lines()

    reg_jobs: set[str] = set()
    for job in registered:
        cmd = job.get("command", "")
        sched = job.get("schedule", "")
        reg_jobs.add(_job_fingerprint(f"{sched} {cmd}"))

    inst_jobs: set[str] = set()
    for line in installed_raw:
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        parts = s.split(None, 5)
        if len(parts) >= 6:
            inst_jobs.add(_job_fingerprint(parts[5]))

    unregistered = sorted(reg_jobs - inst_jobs)
    orphan = sorted(inst_jobs - reg_jobs)

    return {
        "registered_count": len(registered),
        "installed_count": len(installed_raw),
        "unregistered_drift": [{"command": c} for c in unregistered],
        "orphan_install": [{"command": c} for c in orphan],
        "ok": not unregistered and not orphan,
    }


def main():
    ap = argparse.ArgumentParser(description="调度编译器: 登记↔安装一致性校验")
    ap.add_argument("--check", action="store_true", help="校验模式 (CI/cron)")
    ap.add_argument("--report", action="store_true", help="报告模式")
    args = ap.parse_args()

    result = check_drift()
    output = json.dumps(result, ensure_ascii=False, indent=2 if args.report else None)
    print(output)
    if args.check or not args.report:
        return 0 if result["ok"] else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
