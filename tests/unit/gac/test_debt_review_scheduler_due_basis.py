"""债务复审调度器的到期日口径必须与 kernel 对齐。

契约来源：2026-11-15 实测 —— 两条复审道读**不同字段**：
  - kernel `omo_debt_review_queue.build_review_queue` 读条目自带的 `next_review_at`
  - bin `bin/gac/debt-review-scheduler.py`（cron `omostation-debt-review` 接线）
    只按 `last_reviewed_at` + severity 间隔重算

同一份案面 45 条非终态里 **44 条**两条道算出不同到期日（差 16~60 天），
于是 cron 日志说「没到期」而 dashboard 的 review queue 说「已到期」，反之亦然。

判据：**两条道必须读同一个字段**。`next_review_at` 是条目自带的显式排期，
kernel 已把它当权威，故 bin 道优先读它；缺失时才回退间隔口径，
并在输出里用 `basis` 标明用了哪一套。
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "bin" / "gac" / "debt-review-scheduler.py"


def _load():
    spec = importlib.util.spec_from_file_location("debt_review_scheduler_due", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _now() -> datetime:
    return datetime(2026, 11, 15, tzinfo=UTC)


def _tmp_root(tmp_path: Path) -> Path:
    (tmp_path / ".omo" / "_truth" / "registry").mkdir(parents=True)
    return tmp_path


def test_next_review_at_is_authoritative(tmp_path: Path) -> None:
    """last_reviewed_at 很近但 next_review_at 已过期 ⇒ 必须报 overdue。

    这正是分歧最大的一类：间隔口径会算成「还早」（11-15 + 90d），
    kernel 口径算成「已过期」。改前的 bin 道走前者。
    """
    module = _load()
    root = _tmp_root(tmp_path)
    items = [
        {
            "id": "X-1",
            "lifecycle_state": "identified",
            "severity": "low",
            "last_reviewed_at": "2026-11-15",
            "next_review_at": "2026-11-01",
            "opened_at": "2026-11-01",
            "_file": ".omo/debt/items/X-1.yaml",
        }
    ]
    result = module.assess(items, root, _now())
    assert [x["id"] for x in result["overdue"]] == ["X-1"]
    entry = result["overdue"][0]
    assert entry["basis"] == "next_review_at"
    assert entry["overdue_days"] == 14
    assert entry["due_at"] == "2026-11-01"


def test_next_review_at_in_future_is_not_overdue(tmp_path: Path) -> None:
    module = _load()
    root = _tmp_root(tmp_path)
    items = [
        {
            "id": "X-2",
            "lifecycle_state": "identified",
            "severity": "high",
            "last_reviewed_at": "2026-09-01",  # 间隔口径早该到期了
            "next_review_at": "2026-12-01",
            "opened_at": "2026-09-01",
            "_file": ".omo/debt/items/X-2.yaml",
        }
    ]
    result = module.assess(items, root, _now())
    assert result["overdue"] == []


def test_falls_back_to_interval_when_next_review_at_absent(tmp_path: Path) -> None:
    module = _load()
    root = _tmp_root(tmp_path)
    items = [
        {
            "id": "X-3",
            "lifecycle_state": "identified",
            "severity": "high",  # interval 30
            "last_reviewed_at": "2026-09-01",
            "next_review_at": None,
            "opened_at": "2026-09-01",
            "_file": ".omo/debt/items/X-3.yaml",
        }
    ]
    result = module.assess(items, root, _now())
    assert [x["id"] for x in result["overdue"]] == ["X-3"]
    entry = result["overdue"][0]
    assert entry["basis"] == "last_reviewed_at+interval"
    assert entry["due_at"] == "2026-10-01"


def test_never_reviewed_when_both_dates_absent(tmp_path: Path) -> None:
    module = _load()
    root = _tmp_root(tmp_path)
    items = [
        {
            "id": "X-4",
            "lifecycle_state": "identified",
            "severity": "low",
            "last_reviewed_at": None,
            "next_review_at": None,
            "opened_at": None,
            "_file": ".omo/debt/items/X-4.yaml",
        }
    ]
    result = module.assess(items, root, _now())
    assert [x["id"] for x in result["overdue"]] == ["X-4"]
    assert result["overdue"][0]["basis"] == "none"


def test_terminal_items_still_check_evidence(tmp_path: Path) -> None:
    """终态分支不得被本次改动破坏（终态仍按「证据可核」复查）。"""
    module = _load()
    root = _tmp_root(tmp_path)
    (root / "EVIDENCE.md").write_text("# evidence\n", encoding="utf-8")
    items = [
        {
            "id": "X-5",
            "lifecycle_state": "resolved",
            "severity": "low",
            "evidence_refs": ["EVIDENCE.md"],
            "_file": ".omo/debt/items/X-5.yaml",
        },
        {
            "id": "X-6",
            "lifecycle_state": "resolved",
            "severity": "low",
            "evidence_refs": ["does-not-exist-xyz.md"],
            "_file": ".omo/debt/items/X-6.yaml",
        },
    ]
    result = module.assess(items, root, _now())
    assert [x["id"] for x in result["needs_reassessment"]] == ["X-6"]
    assert result["overdue"] == []


def _overlong_ref() -> str:
    """构造一个 >1024 字节的 ref —— macOS PATH_MAX，实测 main 上有 1155 / 1661 字节两条。"""
    prose = "去重: GAP-SEED-DISPATCH 处理的是反方向 —— gap_seed_items 声明但物理不存在; " * 20
    assert len(prose.encode("utf-8")) > 1024, len(prose.encode("utf-8"))
    return prose


def test_overlong_evidence_ref_is_not_verifiable_but_not_fatal(tmp_path: Path) -> None:
    """超长 evidence ref 必须判为「不可核」并继续出报告，而不是打断整轮。

    py<3.14 的 Path.exists() 只吞 ENOENT/ENOTDIR/EBADF/ELOOP，遇到 ENAMETOOLONG
    (errno 63) 直接抛 OSError —— 2026-11-23 在 origin/main 内容上用 3.13.18/3.9.6
    实跑本脚本即 rc=1 崩溃，3.14.8/3.15.2 则隐式返回 False，同一份案面两种结局。
    """
    module = _load()
    root = _tmp_root(tmp_path)
    items = [
        {
            "id": "X-7",
            "lifecycle_state": "resolved",
            "severity": "low",
            "evidence_refs": [_overlong_ref()],
            "_file": ".omo/debt/items/X-7.yaml",
        },
        {
            "id": "X-8",
            "lifecycle_state": "resolved",
            "severity": "low",
            "evidence_refs": [_overlong_ref()],
            "resolution_evidence": "PR #5465 订正扫描总体口径",
            "_file": ".omo/debt/items/X-8.yaml",
        },
    ]
    result = module.assess(items, root, _now())
    assert [x["id"] for x in result["needs_reassessment"]] == ["X-7"]
    assert result["overdue"] == []


def test_load_items_skips_overlong_seed_entry(tmp_path: Path) -> None:
    """registry 里的超长 seed_items 条目同样不得把 load_items 打断。"""
    module = _load()
    root = _tmp_root(tmp_path)
    items_dir = root / ".omo" / "debt" / "items"
    items_dir.mkdir(parents=True)
    (items_dir / "OK-1.yaml").write_text("id: OK-1\nlifecycle_state: identified\n", encoding="utf-8")
    (root / ".omo" / "_truth" / "registry" / "debt.yaml").write_text(
        "seed_items:\n"
        f"  - '.omo/debt/items/{_overlong_ref()}.yaml'\n"
        "  - .omo/debt/items/OK-1.yaml\n"
        "  - .omo/debt/items/GONE.yaml\n",
        encoding="utf-8",
    )
    loaded = module.load_items(root)
    assert [i["id"] for i in loaded] == ["OK-1"]
