"""bin/gac/ops-cron-install.py 的用例 —— 它生成的命令必须真的能跑.

**为什么** (2026-11-07 实测): `REPO = Path(__file__).resolve().parents[1]` 解析成
`bin/` (本脚本在 `bin/gac/` 下), 于是 4 条命令全变成
`cd <root>/bin && python3 bin/ops/...` => 指向不存在的 `<root>/bin/bin/ops/...`。
而 `--dry-run` 只打印 schedule + comment、**不打印 command** ⇒ 装之前完全看不见。
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location(
    "ops_cron_install", WORKSPACE / "bin" / "gac" / "ops-cron-install.py"
)
assert _spec and _spec.loader
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


def test_repo_is_the_checkout_root_not_bin() -> None:
    """REPO 必须是检出根 —— 写成 parents[1] 会解析成 bin/ (命令全废)。"""
    assert mod.REPO == WORKSPACE, f"REPO 解析到 {mod.REPO}, 应为检出根 {WORKSPACE}"
    assert (mod.REPO / "bin" / "ops").is_dir(), "REPO/bin/ops 不存在 —— REPO 不是检出根"


def test_every_job_command_points_at_an_existing_script() -> None:
    """每条命令里的脚本路径必须真实存在 —— 否则装上去就是每周期失败。"""
    for job in mod.JOBS:
        m = re.search(r"python3 (\S+)", job["command"])
        assert m, f"命令里找不到 python3 脚本: {job['command']}"
        script = mod.REPO / m.group(1)
        assert script.is_file(), f"{job['comment']}: 脚本不存在 {script}"


def test_dry_run_shows_the_command_not_just_the_comment(capsys) -> None:
    """dry-run 必须打印 command —— 路径写错时这是装之前唯一的可见面。"""
    mod.dry_run()
    out = capsys.readouterr().out
    for job in mod.JOBS:
        assert job["command"] in out, f"dry-run 未展示命令: {job['command']}"


def test_render_preserves_foreign_lines_and_replaces_its_own_block() -> None:
    """render: 保留非本工具的行, 用 tag 块包住自己管理的行, 旧块不叠加。"""
    foreign = "*/20 * * * * python3 /home/u/.local/bin/clash-speed active"
    out = mod.render(foreign + "\n")
    assert foreign in out
    assert f"{mod.CRONTAG}-start" in out and f"{mod.CRONTAG}-end" in out
    assert out.count(mod.CRONTAG) == len(mod.JOBS) + 2, "tag 数量 = start/end + 每行一个"

    stale = (
        foreign
        + f"\n{mod.CRONTAG}-start\n0 0 * * * old {mod.CRONTAG}\n{mod.CRONTAG}-end\n"
    )
    out2 = mod.render(stale)
    assert "old" not in out2, "旧的 tag 块没有被替换掉"
    assert out2.count(mod.CRONTAG) == len(mod.JOBS) + 2


class _FakeSubprocess:
    """只接管 crontab 读写, 不碰全局 subprocess 模块 (避免污染同进程的其他用例)。"""

    CompletedProcess = subprocess.CompletedProcess

    @staticmethod
    def run(args, **kwargs):
        return subprocess.CompletedProcess(args, 0, "", "")


def test_install_refuses_jobs_missing_from_the_registry(tmp_path, monkeypatch, capsys) -> None:
    """登记面里没有的作业必须拒绝安装 —— 否则 scheduler-compile --check 报 orphan。"""
    mod.REGISTRY = tmp_path / "registry.yaml"
    (tmp_path / "registry.yaml").write_text("jobs: []\n", encoding="utf-8")
    monkeypatch.setattr(mod, "subprocess", _FakeSubprocess)
    monkeypatch.setattr(sys, "argv", ["ops-cron-install.py", "--install"])
    assert mod.main() == 1
    err = capsys.readouterr().err
    assert "不在 .omo/cron/registry.yaml" in err
    assert "--install 会被拒" not in err, "install 路径不该打印 dry-run 的告警文案"


def test_registered_job_is_accepted(tmp_path, monkeypatch, capsys) -> None:
    """正控制: 作业一旦进了登记面 active crontab 就放行。

    没有这条, 「把 unregistered_jobs() 改成恒返回全部」也能让上一条变绿。
    """
    import yaml

    jobs = []
    for i, job in enumerate(mod.JOBS):
        script = job["command"].split("python3 ", 1)[-1].split(" ", 1)[0]
        jobs.append(
            {
                "name": f"j{i}",
                "schedule": "*/5 * * * *",
                "command": f"cd /x && python3 {script}",
                "planes": ["crontab"],
                "status": "active",
            }
        )
    reg = tmp_path / "registry.yaml"
    reg.write_text(yaml.safe_dump({"jobs": jobs}), encoding="utf-8")
    monkeypatch.setattr(mod, "REGISTRY", reg)
    monkeypatch.setattr(mod, "subprocess", _FakeSubprocess)
    monkeypatch.setattr(sys, "argv", ["ops-cron-install.py", "--install"])
    assert mod.main() == 0, capsys.readouterr().err


def test_dry_run_reports_unregistered_jobs(tmp_path, monkeypatch, capsys) -> None:
    """dry-run 也要把「会被拒」显式说出来 —— 这是装之前唯一的可见面。"""
    mod.REGISTRY = tmp_path / "registry.yaml"
    (tmp_path / "registry.yaml").write_text("jobs: []\n", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["ops-cron-install.py", "--dry-run"])
    assert mod.main() == 1
    err = capsys.readouterr().err
    assert "会被拒" in err
    assert mod.JOBS[0]["comment"] in err
