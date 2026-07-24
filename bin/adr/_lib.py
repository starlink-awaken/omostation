"""ADR shared helpers — pure functions reused by adr-coverage + compass_radar.

抽离自 bin/adr/adr-coverage.py::list_adrs + duplicate 检测, 消除与
bin/compass_radar.py::_count_adr_renumber_signals 的重复 (/simplify finding a DRY).
单一真相源: ADR 编号格式 = NNNN- 前缀 (4 位数字).
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

ADR_NUMBER_RE = re.compile(r"^(\d{4})-")


def list_adrs(decisions_dir: Path) -> list[tuple[int, Path]]:
    """列出所有 ADR 文件, 返回 (编号, 路径), 按文件名排序."""
    adrs: list[tuple[int, Path]] = []
    if not decisions_dir.exists():
        return adrs
    for f in sorted(decisions_dir.glob("*.md")):
        m = ADR_NUMBER_RE.match(f.name)
        if m:
            adrs.append((int(m.group(1)), f))
    return adrs


def duplicate_adr_numbers(decisions_dir: Path) -> list[int]:
    """Return duplicate ADR numbers (collisions). Empty if none / dir missing.

    单一真相源 for ADR 编号冲突检测 — 被 adr-coverage.check_coverage
    与 compass_radar._count_adr_renumber_signals 共用.
    """
    numbers = [n for n, _ in list_adrs(decisions_dir)]
    return [n for n, c in Counter(numbers).items() if c > 1]
