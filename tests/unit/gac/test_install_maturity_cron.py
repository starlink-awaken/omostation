"""`bin/ssot/install-maturity-cron.sh` 的用例 —— 装机不许重排用户的 crontab.

**为什么** (2026-11-07): 原实现每加一行就 `(crontab -l; echo ...) | sort -u | crontab -`
全表重写一遍 —— 5 行 = **5 次写盘**, 而且每次 `sort -u` 会把整份 crontab 按字母重排,
用户自己写的行与注释全被挪动。改为: 渲染一次 → 保序去重 → 写一次。

假 crontab 必须先落到临时文件再 `mv`: 直接 `cat > "$SPOOL"` 会在管道里与读端竞态
(读端看到空文件), 真 crontab 是读完 stdin 才落盘, 没有这个问题。
"""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[3]
SCRIPT = WORKSPACE / "bin" / "ssot" / "install-maturity-cron.sh"
TAG = "# omostation-maturity-ops"

SCRIPTS = [
    "bin/ssot/signal-poller.py",
    "bin/gac/remediation-engine.py",
    "bin/gac/anti-corrosion-check.py",
    "bin/gac/unified-health-score.py",
    "bin/ssot/north-star-weekly.py",
]


def _complete_registry(tmp_path: Path) -> dict:
    """注入缝: 一份把 5 个作业都登记为 active 的 registry。

    真登记面现状是 4 个不在 (见 test_install_refuses_jobs_missing_from_the_registry),
    guard 会拒 —— 其余用例要测的是「登记面完整时安装器的行为」, 故走注入缝。
    """
    reg = tmp_path / "registry.yaml"
    reg.write_text(
        "jobs:\n"
        + "\n".join(
            f"  - name: j{i}\n    schedule: '*/5 * * * *'\n"
            f"    command: 'cd /x && python3 {s}'\n    planes: [crontab]\n    status: active\n"
            for i, s in enumerate(SCRIPTS)
        ),
        encoding="utf-8",
    )
    return {"CRON_REGISTRY_OVERRIDE": str(reg)}

FOREIGN = [
    "0 6 * * * cd /home/u/my-tool",
    "# my comment",
    "*/5 * * * * some-other-tool",
]


def _run(tmp_path: Path, spool: Path, *args: str, extra_env: dict | None = None) -> subprocess.CompletedProcess:
    """跑安装脚本, 用假 crontab 接住读写。"""
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir(exist_ok=True)
    fake = fake_bin / "crontab"
    fake.write_text(
        '#!/bin/sh\n'
        'if [ "$1" = "-l" ]; then cat "$SPOOL" 2>/dev/null; exit 0; fi\n'
        'tmp="$(mktemp)"\n'
        "cat > \"$tmp\"\n"
        'mv "$tmp" "$SPOOL"\n',
        encoding="utf-8",
    )
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    env = {
        **os.environ,
        "PATH": f"{fake_bin}:{os.environ.get('PATH', '')}",
        "SPOOL": str(spool),
    }
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        ["bash", str(SCRIPT), *args], env=env, capture_output=True, text=True, check=False
    )


def _spool_lines(spool: Path) -> list[str]:
    return spool.read_text(encoding="utf-8").splitlines()


def test_install_preserves_foreign_line_order(tmp_path: Path) -> None:
    """用户自己的行必须保持原序 —— 原实现会被 sort -u 按字母重排。"""
    spool = tmp_path / "crontab.txt"
    spool.write_text("\n".join(FOREIGN) + "\n", encoding="utf-8")
    assert (
        _run(tmp_path, spool, "--install", extra_env=_complete_registry(tmp_path)).returncode
        == 0
    )

    lines = _spool_lines(spool)
    foreign_idx = [lines.index(f) for f in FOREIGN]
    assert foreign_idx == sorted(foreign_idx), f"外部行被重排了: {lines}"
    managed = [l for l in lines if l.endswith(TAG)]
    assert len(managed) == 5, f"应装入 5 条, 实得 {len(managed)}"


def test_install_is_idempotent(tmp_path: Path) -> None:
    """连装两次, 内容逐字节相同。"""
    spool = tmp_path / "crontab.txt"
    spool.write_text("\n".join(FOREIGN) + "\n", encoding="utf-8")
    assert (
        _run(tmp_path, spool, "--install", extra_env=_complete_registry(tmp_path)).returncode
        == 0
    )
    first = spool.read_text(encoding="utf-8")
    assert (
        _run(tmp_path, spool, "--install", extra_env=_complete_registry(tmp_path)).returncode
        == 0
    )
    assert spool.read_text(encoding="utf-8") == first


def test_dry_run_does_not_write(tmp_path: Path) -> None:
    """--dry-run 只打印, 不写 crontab。"""
    spool = tmp_path / "crontab.txt"
    spool.write_text("\n".join(FOREIGN) + "\n", encoding="utf-8")
    before = spool.read_text(encoding="utf-8")
    result = _run(tmp_path, spool, "--dry-run", extra_env=_complete_registry(tmp_path))
    assert result.returncode == 0
    assert spool.read_text(encoding="utf-8") == before, "--dry-run 写了 crontab"
    assert TAG in result.stdout, "dry-run 应展示将写入的行"


def test_remove_keeps_foreign_lines(tmp_path: Path) -> None:
    """--remove 只摘自己的行 (无 tag 行时不得因 grep 无匹配而中止)。"""
    spool = tmp_path / "crontab.txt"
    spool.write_text("\n".join(FOREIGN) + "\n", encoding="utf-8")
    assert _run(tmp_path, spool, "--remove").returncode == 0, "空 tag 场景下 --remove 崩了"
    assert _spool_lines(spool) == FOREIGN


def test_managed_lines_point_at_real_scripts(tmp_path: Path) -> None:
    """渲染出的每条 managed 行, 其脚本路径必须真实存在。"""
    spool = tmp_path / "crontab.txt"
    spool.write_text("", encoding="utf-8")
    assert (
        _run(tmp_path, spool, "--install", extra_env=_complete_registry(tmp_path)).returncode
        == 0
    )
    for line in _spool_lines(spool):
        if not line.endswith(TAG):
            continue
        rel = line.split(" && ")[1].split()[1]  # "python3 <script> ..."
        assert (WORKSPACE / rel).is_file(), f"脚本不存在: {rel}"


def test_install_refuses_jobs_missing_from_the_registry(tmp_path: Path) -> None:
    """登记面里没有的作业必须拒绝安装 —— 装上去就是 orphan (门禁红)。

    真登记面现状: 5 个作业里 4 个完全不在 (signal-poller / remediation-engine /
    anti-corrosion-check / north-star-weekly), 第 5 个 (unified-health-score) 只在
    参数不同的 proposed 条目里。判据取脚本路径子串, 所以第 5 个不触发 —— 另 4 个
    足以让 guard 拒绝。
    """
    spool = tmp_path / "crontab.txt"
    spool.write_text("AAA\n", encoding="utf-8")
    before = spool.read_text(encoding="utf-8")
    result = _run(tmp_path, spool, "--install")
    assert result.returncode == 1
    assert "不在 .omo/cron/registry.yaml 里" in result.stderr
    assert "bin/ssot/signal-poller.py" in result.stderr
    assert spool.read_text(encoding="utf-8") == before, "被拒后仍写了 crontab"


def test_registered_jobs_are_accepted(tmp_path: Path) -> None:
    """正控制: 作业都在登记面里就放行 (经 CRON_REGISTRY_OVERRIDE 注入缝)。

    没有这条, 「把 check_registry_coverage 改成恒返回 1」也能让上一条变绿。
    """
    scripts = [
        "bin/ssot/signal-poller.py",
        "bin/gac/remediation-engine.py",
        "bin/gac/anti-corrosion-check.py",
        "bin/gac/unified-health-score.py",
        "bin/ssot/north-star-weekly.py",
    ]
    registry = tmp_path / "registry.yaml"
    registry.write_text(
        "jobs:\n"
        + "\n".join(
            f"  - name: j{i}\n    schedule: '*/5 * * * *'\n"
            f"    command: 'cd /x && python3 {s}'\n    planes: [crontab]\n    status: active\n"
            for i, s in enumerate(scripts)
        ),
        encoding="utf-8",
    )
    spool = tmp_path / "crontab.txt"
    spool.write_text("", encoding="utf-8")
    result = _run(tmp_path, spool, "--dry-run", extra_env={"CRON_REGISTRY_OVERRIDE": str(registry)})
    assert result.returncode == 0, result.stderr
    assert TAG in result.stdout
