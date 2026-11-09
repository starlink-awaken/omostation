"""Unit tests for scheduler-compile (A4 调度真相收尾).

Covers TASK-B3229A65 残留问题:
  1. registry.yaml 不能有重名 jobs (A4 v1/v2 段误复制)
  2. compile_crontab 不应再包 cd / log 重定向 (避免与 registry command 字段嵌套)
  3. compile_crontab 输出应与 registry command 字段一致 (只加 schedule 前缀)
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
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


def test_registry_no_duplicate_schedule_command_pairs() -> None:
    """同一 (schedule, 归一化 command) 不得有两条 active crontab 登记 —— 否则作业跑多遍.

    **为什么重名判据不够** (test_registry_no_duplicate_job_names): 重复登记往往
    **名字不同**. 实测五例:

    - `l4-harness-6h` vs `l4-harness-6h-active` —— 同 schedule 同 command, 一个写
      `$HOME/Workspace`、一个写死本机用户根 (PR #5110 修);
    - `branch-prune-daily` vs `worktree-prune-daily` —— #3518 登记 vs #3658
      「补齐登记」, 名字不同、command 逐字相同;
    - `weekly-hygiene-patrol` vs `hygiene-patrol-weekly` —— 同上;
    - `ecos-kems-freshness-daily` vs `kems-freshness-daily`、
      `mof-sla-m0-snapshot-daily` vs `mof-sla-snapshot-daily` —— 同 schedule,
      command 只差 `$HOME/Workspace` vs 写死本机根 (PR #5136 修)。

    **判据必须自己先展开 `$HOME`**: 只用 `comparison_key` 时, 后两例的两种写法
    归一化后**仍不同** (`$HOME/Workspace` 不被展开), 于是漏网 —— 本用例的 docstring
    一度声称「裸字符串查不出两种写法」, 实测那是**没有验证过的断言**。
    """
    jobs = _load_registry_jobs()
    seen: dict[str, str] = {}
    dups: dict[str, list[str]] = {}
    for j in jobs:
        if j.get("status") != "active":
            continue
        if "crontab" not in (j.get("planes") or []):
            continue
        key = _comparison_key(
            _expand_workspace(f"{j.get('schedule', '')} {j.get('command', '')}")
        )
        if not key:
            continue
        name = j.get("name", "")
        if key in seen:
            dups.setdefault(key, [seen[key]]).append(name)
        else:
            seen[key] = name
    assert not dups, (
        f"registry.yaml 含同 (schedule, command) 的多条 active crontab 登记: "
        f"{list(dups.values())} —— 同一作业会执行多遍, 请合并成一条。"
    )


def test_registry_job_names_unique_preserved() -> None:
    """dedup 后, 关键 job 仍在 (回归保护)."""
    jobs = _load_registry_jobs()
    names = {j.get("name", "") for j in jobs}
    must_keep = {
        "log-rotate-daily",
        "worktree-hygiene-daily",
        "branch-prune-daily",
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
    # 契约: 对每条本机该编译的 active crontab job, 输出行 = schedule + ' ' + command
    # (hosts 字段 scoping 到别机的条目合法缺席 —— CRON-REGISTRY-NO-HOST-SCOPE)
    active_cron = [
        j for j in module._host_scoped(jobs)
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
    """dedup 后, 登记面 vs 自身编译产物必须 0 drift —— 走注入缝, 不读本机 crontab.

    原实现直接跑 `scheduler-compile --check` 读**真机 crontab**: 那是 host 运行态,
    不是被测性质 (AGENTS.md §7「用例断言 host 运行态 = 结构性失明」) —— 本机 crontab
    一旦与登记面不同步 (装机失败 / 并发 agent 改行 / legacy 安装器), 本用例就红,
    而它想量的其实是「登记 ↔ 编译产物」是否自洽。改用 `check_drift(injected)`
    注入缝 (与 test_scheduler_compile_launchd_plane 同形)。
    """
    sc = _load_compile_module()
    installed = [sc._expand_workspace(line) for line in sc.compile_crontab(sc._load_jobs())]
    data = sc.check_drift(installed_lines=installed)
    assert data.get("drift_count", -1) == 0, f"dedup 引入 drift: {data}"


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


def _load_normalize_module():
    spec = importlib.util.spec_from_file_location(
        "cron_normalize_under_test", WORKSPACE / "bin" / "lib" / "cron_normalize.py"
    )
    if spec is None:
        raise RuntimeError("cannot load bin/lib/cron_normalize.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _comparison_key(line: str) -> str:
    """与生产同一份比较键 (bin/lib/cron_normalize.comparison_key)。"""
    return _load_normalize_module().comparison_key(line)


def _expand_workspace(line: str) -> str:
    """与生产同一份 `$HOME/Workspace` 展开 (bin/lib/cron_normalize.expand_workspace)。

    判据必须过这一层: 只过 `comparison_key` 时 `$HOME/Workspace` 不被展开,
    「同一个根、两种写法」的重复登记会漏网 (实证见
    test_registry_no_duplicate_schedule_command_pairs 的 docstring)。
    """
    return _load_normalize_module().expand_workspace(line)


def _normalize(cmd: str) -> str:
    """直接用 bin/lib/cron_normalize.py —— 不再维护本地副本。

    这里曾有一份「同语义的本地副本」, 与生产码一起漂移: 「末段不归一化」这个
    off-by-one 就是两边同形继承下来的 (见 cron_normalize.normalize_interpreter)。
    判据与被检对象同源时无法发现漂移, 必须引用同一份实现。
    """
    return _load_normalize_module().normalize_interpreter(cmd)


class InterpreterNormalizationTests(unittest.TestCase):
    """声明用 `python3`，安装态可能写绝对路径 —— 语义相同, 不该算 drift。

    2026-10-22: cron 环境里裸 `python3` 解析到 Xcode 的 3.9(缺 `datetime.UTC`),
    4 条 cron 因此连续失败数周; 修法是让 crontab 写绝对路径, 于是声明与安装态
    字面不同但语义相同 —— 检查必须归一化。
    """

    def test_absolute_path_normalizes_to_bare(self) -> None:
        self.assertEqual(_normalize("cd /x && /opt/homebrew/bin/python3.13 bin/a.py"),
                         "cd /x && python3 bin/a.py")

    def test_bare_is_unchanged(self) -> None:
        self.assertEqual(_normalize("cd /x && python3 bin/a.py"), "cd /x && python3 bin/a.py")

    def test_command_start_normalizes(self) -> None:
        self.assertEqual(_normalize("/opt/homebrew/bin/python3.13 -B bin/a.py --daily"),
                         "python3 -B bin/a.py --daily")

    def test_non_python_commands_untouched(self) -> None:
        self.assertEqual(_normalize("cd /x && bash bin/a.sh"), "cd /x && bash bin/a.sh")


def _watchdog_job() -> dict:
    for j in _load_registry_jobs():
        if j.get("name") == "work-agent-respire-mbp-watchdog":
            return j
    raise AssertionError("registry 里找不到 work-agent-respire-mbp-watchdog")


def test_host_scope_excludes_other_hosts_jobs(monkeypatch) -> None:
    """`hosts` 维度: 别机的专用条目不得出现在本机产物里.

    CRON-REGISTRY-NO-HOST-SCOPE 的结构性修法。实证: work-agent-respire-mbp-watchdog
    的 reconciliation_note 明写 mini 专用, 没有主机维度时它在 mbp 上永远 drift=1
    ⇒ 本机健康门禁 A4 常红。
    """
    sc = _load_compile_module()
    jobs = _load_registry_jobs()
    assert _watchdog_job().get("hosts") == ["mini"]

    monkeypatch.setenv("CRON_HOST", "mbp")
    out_mbp = sc.compile_crontab(jobs)
    assert not any("respire_mbp_supervisor_watchdog" in line for line in out_mbp)

    monkeypatch.setenv("CRON_HOST", "mini")
    out_mini = sc.compile_crontab(jobs)
    assert any("respire_mbp_supervisor_watchdog" in line for line in out_mini)


def test_host_scope_keeps_unscoped_and_matching_jobs(monkeypatch) -> None:
    """无 `hosts` 的条目永远保留; 列出本机的条目也保留 (不是只留 unscoped)."""
    sc = _load_compile_module()
    jobs = [
        {"name": "always", "schedule": "1 * * * *", "command": "cmd-always",
         "planes": ["crontab"], "status": "active"},
        {"name": "here", "schedule": "2 * * * *", "command": "cmd-here",
         "planes": ["crontab"], "status": "active", "hosts": ["mbp"]},
        {"name": "there", "schedule": "3 * * * *", "command": "cmd-there",
         "planes": ["crontab"], "status": "active", "hosts": ["mini"]},
    ]
    monkeypatch.setenv("CRON_HOST", "mbp")
    out = "\n".join(sc.compile_crontab(jobs))
    assert "cmd-always" in out
    assert "cmd-here" in out
    assert "cmd-there" not in out


def test_check_drift_is_host_scoped_consistently(monkeypatch) -> None:
    """check_drift 与 compile_crontab 同口径过滤 —— 自洽性 (drift=0) 不被破坏.

    只过滤一侧会当场造出 drift: 登记侧留了别机条目而已装侧没有, 或反之。
    """
    sc = _load_compile_module()
    monkeypatch.setenv("CRON_HOST", "mbp")
    installed = [sc._expand_workspace(line) for line in sc.compile_crontab(sc._load_jobs())]
    data = sc.check_drift(installed_lines=installed)
    assert data.get("drift_count", -1) == 0, data



def test_compile_launchd_uses_same_active_filter_as_crontab() -> None:
    """launchd 平面与 crontab 平面必须给出一致的「活跃集」口径.

    此前 `compile_launchd` **只过滤 planes**, 不过 `status` 也不过 `hosts` ⇒ 实测把
    6 条 `proposed` 条目 (resident-launchd-sediment/monitor/heartbeat、
    knowledge-foundry-6h、panorama-dashboard、panorama-refresh-guard) 也编译进产物,
    而 `--generate crontab` 会排除它们 —— 同一份登记面在两个平面上给出不同的活跃集。
    """
    sc = _load_compile_module()
    jobs = _load_registry_jobs()
    agents = sc.compile_launchd(jobs)
    assert agents, "registry 应编译出 launchd agent, 否则本用例恒绿"
    by_name = {j.get("name"): j for j in jobs}
    for label in agents:
        job = by_name.get(label.removeprefix("com.omostation."))
        assert job is not None, f"编译产物里的 {label} 不在登记面"
        assert job.get("status", "active") == "active", f"{label} 不是 active 却被编译"
        assert "launchd" in (job.get("planes") or []), f"{label} 不含 launchd 平面"

    proposed = [
        j["name"] for j in jobs
        if j.get("status") != "active" and "launchd" in (j.get("planes") or [])
    ]
    assert proposed, "registry 里应有 proposed 的 launchd 条目, 否则反证恒绿"
    for name in proposed:
        assert f"com.omostation.{name}" not in agents, f"proposed 条目 {name} 被编译进产物"
