"""采集器不得用裸 `python3` 起子进程 —— PATH 决定解释器，会静默跑到旧 Python。

缺陷（2026-11-10 实测）：`com.omostation.zhixing-dashboard-refresh` 的 plist
`EnvironmentVariables` **没有 `PATH`** ⇒ launchd 的
`default environment PATH => /usr/bin:/bin:/usr/sbin:/sbin` 生效 ⇒ 采集器里
`subprocess.run(["python3", …])` 解析到 `/usr/bin/python3`（Xcode CLT Python 3.9）
⇒ `from datetime import UTC`（3.11 才有）抛 ImportError ⇒ `reference_cell` 自
2026-10-23 起恒 FAIL、`ruflo` 同样 FAIL（`output` 为空）。

同类风险面：任何依赖 `PATH` 解析解释器的调用。同仓的 `panorama-collect.py` 早已用
`sys.executable`，宿主资产里却留着 4 处裸 `python3`。

判据：宿主资产与采集器源码里，`subprocess` 的 argv 首元素不得是裸 `python3`/`python`。
自证：本文件末尾的用例把一处违规注入临时副本，断言检测器能报出 —— 否则「全部合规」
可能只是检测器没接上（AGENTS.md §7「按构造就绿」同族）。
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOST_ASSETS = ROOT / "bin/panorama/assets/host"
SOURCES = [
    ROOT / "bin/panorama/panorama-collect.py",
    *sorted(HOST_ASSETS.glob("*.py.asset")),
]

# subprocess argv 首元素是裸解释器（带引号、紧跟逗号或右括号）
_BARE_INTERPRETER = re.compile(r"""[\(\[]\s*["']python3?["']\s*[,)]""")


def _violations(path: Path) -> list[str]:
    return [m.group(0).strip() for m in _BARE_INTERPRETER.finditer(path.read_text(encoding="utf-8", errors="ignore"))]


def test_sources_exist():
    missing = [str(p) for p in SOURCES if not p.is_file()]
    assert not missing, f"扫描面里的文件不存在: {missing}"


def test_no_bare_python_in_subprocess_argv():
    offenders = {str(p): _violations(p) for p in SOURCES if _violations(p)}
    assert not offenders, (
        "采集器用裸 python3/python 起子进程 —— 解释器由 PATH 决定, "
        f"会静默跑到旧 Python。改用 sys.executable。命中: {offenders}"
    )


def test_detector_is_not_a_no_op(tmp_path):
    """注入一处违规, 检测器必须报出, 否则上面那条断言可能只是空转。"""
    sample = tmp_path / "collector.py"
    sample.write_text(
        "import subprocess\nsubprocess.run(['python3', '-B', 'x.py', '--json'])\n",
        encoding="utf-8",
    )
    assert _violations(sample), "检测器对合成违规样本零命中 —— 判据空转"
