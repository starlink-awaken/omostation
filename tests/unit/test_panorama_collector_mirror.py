"""宿主镜像 `panorama-collect-main.py.asset` 必须是采集器的逐字节副本。

2026-10-23 实证: 该镜像曾**漂移 1710 行**而无人察觉 —— 仓库里改的是
`bin/panorama/panorama-collect.py`, 而 release 树里跑的是镜像, 于是部署路径
长期执行旧代码 (b31a16430 才补同步)。本用例把「逐字节一致」钉成判据, 防止
同类漂移再次静默积累。

判据自证: 用例自己先对一份副本注入差异, 断言比较器能报出 —— 否则「一致」
可能只是比较器没生效 (与 AGENTS.md §7「按构造就绿」同族)。
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "bin/panorama/panorama-collect.py"
MIRROR = ROOT / "bin/panorama/assets/host/panorama-collect-main.py.asset"


def _differs(left: bytes, right: bytes) -> bool:
    return left != right


def test_mirror_exists():
    assert SOURCE.is_file(), f"采集器源码不存在: {SOURCE}"
    assert MIRROR.is_file(), f"宿主镜像不存在: {MIRROR}"


def test_mirror_is_verbatim_copy():
    assert not _differs(SOURCE.read_bytes(), MIRROR.read_bytes()), (
        "宿主镜像与采集器源码不一致 —— release 树跑的是旧副本。"
        f"同步: cp {SOURCE} {MIRROR}"
    )


def test_diff_detector_is_not_a_no_op():
    """比较器必须能报出差异, 否则上面那条断言可能只是空转。"""
    payload = SOURCE.read_bytes()
    assert not _differs(payload, payload)
    assert _differs(payload, payload + b"\n# drift\n")


def test_neither_side_is_a_symlink():
    """符号链接会让「逐字节一致」退化成「指向别处」。"""
    assert not SOURCE.is_symlink()
    assert not MIRROR.is_symlink()
