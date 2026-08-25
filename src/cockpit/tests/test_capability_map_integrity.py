"""CAPABILITY-MAP.md 完整性测试 (t1-12) — 不得残留合并冲突标记或已退役条目。

d8af11c2 提交时 CAPABILITY-MAP.md 留下了一段未清干净的 daemon 合并冲突块，
本文件锁定：冲突标记为零、退役入口无孤儿条目。
"""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]  # src/cockpit/tests/ -> repo root
CAPABILITY_MAP = PROJECT_ROOT / "CAPABILITY-MAP.md"

CONFLICT_MARKERS = ("<<<<<<<", "|||||||", "=======", ">>>>>>>")


def test_capability_map_has_no_conflict_markers() -> None:
    content = CAPABILITY_MAP.read_text(encoding="utf-8")
    for marker in CONFLICT_MARKERS:
        assert marker not in content, f"CAPABILITY-MAP.md 残留冲突标记 {marker!r}"


def test_capability_map_has_no_retired_daemon_entry() -> None:
    content = CAPABILITY_MAP.read_text(encoding="utf-8")
    assert "`cockpit daemon`" not in content, "退役的 `cockpit daemon` 条目应从能力地图移除"
