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

FOREIGN = [
    "0 6 * * * cd /home/u/my-tool",
    "# my comment",
    "*/5 * * * * some-other-tool",
]


def _run(tmp_path: Path, spool: Path, *args: str) -> subprocess.CompletedProcess:
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
    return subprocess.run(
        ["bash", str(SCRIPT), *args], env=env, capture_output=True, text=True, check=False
    )


def _spool_lines(spool: Path) -> list[str]:
    return spool.read_text(encoding="utf-8").splitlines()


def test_install_preserves_foreign_line_order(tmp_path: Path) -> None:
    """用户自己的行必须保持原序 —— 原实现会被 sort -u 按字母重排。"""
    spool = tmp_path / "crontab.txt"
    spool.write_text("\n".join(FOREIGN) + "\n", encoding="utf-8")
    assert _run(tmp_path, spool, "--install").returncode == 0

    lines = _spool_lines(spool)
    foreign_idx = [lines.index(f) for f in FOREIGN]
    assert foreign_idx == sorted(foreign_idx), f"外部行被重排了: {lines}"
    managed = [l for l in lines if l.endswith(TAG)]
    assert len(managed) == 5, f"应装入 5 条, 实得 {len(managed)}"


def test_install_is_idempotent(tmp_path: Path) -> None:
    """连装两次, 内容逐字节相同。"""
    spool = tmp_path / "crontab.txt"
    spool.write_text("\n".join(FOREIGN) + "\n", encoding="utf-8")
    assert _run(tmp_path, spool, "--install").returncode == 0
    first = spool.read_text(encoding="utf-8")
    assert _run(tmp_path, spool, "--install").returncode == 0
    assert spool.read_text(encoding="utf-8") == first


def test_dry_run_does_not_write(tmp_path: Path) -> None:
    """--dry-run 只打印, 不写 crontab。"""
    spool = tmp_path / "crontab.txt"
    spool.write_text("\n".join(FOREIGN) + "\n", encoding="utf-8")
    before = spool.read_text(encoding="utf-8")
    result = _run(tmp_path, spool, "--dry-run")
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
    assert _run(tmp_path, spool, "--install").returncode == 0
    for line in _spool_lines(spool):
        if not line.endswith(TAG):
            continue
        rel = line.split(" && ")[1].split()[1]  # "python3 <script> ..."
        assert (WORKSPACE / rel).is_file(), f"脚本不存在: {rel}"
