"""Unit tests for scheduler-compile (A4 调度真相收尾).

Covers TASK-B3229A65 残留问题:
  1. registry.yaml 不能有重名 jobs (A4 v1/v2 段误复制)
  2. compile_crontab 不应再包 cd / log 重定向 (避免与 registry command 字段嵌套)
  3. compile_crontab 输出应与 registry command 字段一致 (只加 schedule 前缀)
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

import yaml

WORKSPACE = Path(__file__).resolve().parents[1]
SCHEDULER_COMPILE = WORKSPACE / "bin" / "scheduler-compile.py"
REGISTRY = WORKSPACE / ".omo" / "cron" / "registry.yaml"


def _load_compile_module():
    spec = importlib.util.spec_from_file_location(
        "scheduler_compile_under_test", SCHEDULER_COMPILE
    )
    if spec is None:
        raise RuntimeError(f"cannot load {SCHEDULER_COMPILE}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_registry_jobs():
    docs = [d for d in yaml.safe_load_all(REGISTRY.read_text(encoding="utf-8")) if d]
    return docs[-1].get("jobs", []) if docs else []


def test_registry_no_duplicate_job_names() -> None:
    """A4 收尾: registry.yaml 不得有重名 jobs.

    历史: v1 段 (line 28-) 与 v2 段 (line 213+ 孤儿补登段) 之间有
    4 个误复制: worktree-hygiene-daily / hygiene-dir-daily /
    ssot-guardian-weekly / capability-registry-sync-daily.
    """
    jobs = _load_registry_jobs()
    names = [j.get("name", "") for j in jobs]
    c = Counter(names)
    dups = {k: v for k, v in c.items() if v > 1}
    assert not dups, (
        f"registry.yaml 含重名 jobs (A4 v1/v2 段误复制残留): {dups}. "
        f"只保留 v2 段 (与 crontab -l 实际一致) 即可, 删 v1 段重复块."
    )


def test_registry_job_names_unique_preserved() -> None:
    """dedup 后, 关键 job 仍在 (回归保护)."""
    jobs = _load_registry_jobs()
    names = {j.get("name", "") for j in jobs}
    must_keep = {
        "log-rotate-daily",
        "worktree-hygiene-daily",
        "worktree-prune-daily",
        "hygiene-dir-daily",
        "ssot-guardian-weekly",
        "capability-registry-sync-daily",
        "remote-hygiene-hourly",
        "panorama-dashboard",
        "zhixing-dashboard-refresh",
    }
    missing = must_keep - names
    assert not missing, f"dedup 误删关键 job: {missing}"


def test_compile_crontab_does_not_double_cd() -> None:
    """A4 收尾: compile_crontab 不应在 command 已含 cd 的条目上再包一层 cd."""
    module = _load_compile_module()
    jobs = _load_registry_jobs()
    out = module.compile_crontab(jobs)
    assert out, "compile_crontab 产出为空"
    for line in out:
        if not line.strip() or line.startswith("#"):
            continue
        # schedule 是前 5 token
        parts = line.split(maxsplit=5)
        assert len(parts) == 6, f"行格式异常: {line}"
        schedule = " ".join(parts[:5])
        cmd = parts[5]
        nested_cd = 'cd "$HOME/Workspace" && cd' in cmd
        assert not nested_cd, (
            f"compile_crontab 嵌套 cd (旧 bug): schedule={schedule} cmd={cmd}"
        )


def test_compile_crontab_does_not_double_log_redirect() -> None:
    """A4 收尾: 编译器行为契约 — 输出行 = f'{schedule} {command}'.

    旧 bug 特征: 'cd "$HOME/Workspace" && cd' (双 cd) 或
    ' 2>&1 >> runtime/cron/' (链式双重重定向). 新版应只输出 schedule + command.
    """
    module = _load_compile_module()
    jobs = _load_registry_jobs()
    out = module.compile_crontab(jobs)
    # 旧版 bug 特征检测
    for line in out:
        if not line.strip() or line.startswith("#"):
            continue
        assert 'cd "$HOME/Workspace" && cd' not in line, (
            f"compile_crontab 双 cd (旧 bug):\n  {line}"
        )
        assert " 2>&1 >> " not in line, (
            f"compile_crontab 链式双重重定向 (旧 bug):\n  {line}"
        )
    # 契约: 对每条 active crontab job, 输出行 = schedule + ' ' + command
    active_cron = [
        j for j in jobs
        if j.get("status") == "active" and "crontab" in j.get("planes", [])
    ]
    for j in active_cron:
        expected = f'{j["schedule"]} {j["command"]}'
        assert expected in out, (
            f"编译输出与契约不符: job={j['name']}\n  expected: {expected}"
        )


def test_compile_crontab_output_matches_registry_command_with_schedule_prefix() -> None:
    """核心契约: compile_crontab 输出 = schedule + ' ' + command.

    注册表 command 字段已是自包含 (含 cd 与 log 重定向),
    编译器只加 schedule 前缀, 不再二次包装.
    """
    module = _load_compile_module()
    jobs = _load_registry_jobs()
    out = module.compile_crontab(jobs)
    active_jobs = [
        j for j in jobs
        if j.get("status") == "active" and "crontab" in j.get("planes", [])
    ]
    for j in active_jobs[:5]:
        expected = f'{j["schedule"]} {j["command"]}'
        assert any(expected in line for line in out), (
            f"未找到预期行: {expected}"
        )


def test_scheduler_check_no_drift_after_dedup() -> None:
    """dedup 后 scheduler-compile --check 仍应保持 0 drift.

    已知: 1 个 orphan 是 ~/.local/share/zhixing-dashboard/panorama_cache.py
    (本地运维 cron, 配置在 ~/.local 不在本仓, 不在本任务范围).
    """
    r = subprocess.run(
        ["python3", str(SCHEDULER_COMPILE), "--check"],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(WORKSPACE),
        check=False,
    )
    data = json.loads(r.stdout.strip())
    assert data.get("drift_count", -1) == 0, (
        f"dedup 引入 drift: {data}"
    )


def test_compile_crontab_excludes_non_crontab_plane_jobs() -> None:
    """平面过滤契约: compile_crontab 只输出 active + crontab 平面条目.

    历史 bug (2026-09-19): 未过滤 planes 时, launchd-only 的
    schedule=always 条目 (如 panorama-serve) 会混进 crontab 产物,
    cron 因非法 schedule 拒绝整文件安装.
    """
    module = _load_compile_module()
    jobs = _load_registry_jobs()
    out = module.compile_crontab(jobs)
    for j in jobs:
        if j.get("status", "active") != "active":
            continue
        if "crontab" in j.get("planes", []):
            continue
        expected = f'{j.get("schedule", "")} {j.get("command", "")}'
        assert expected not in out, (
            f"非 crontab 平面条目泄漏进产物: job={j.get('name')}\n  {expected}"
        )
    # 产物中不允许出现非 5 字段 cron 表达式 (always/@ 系除外)
    for line in out:
        if not line.strip() or line.startswith("#"):
            continue
        schedule = line.split(maxsplit=5)[:5]
        if schedule and schedule[0].startswith("@"):
            continue
        assert len(schedule) == 5, f"非法 schedule 字段数: {line}"
