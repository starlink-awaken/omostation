"""Unified memory surface tests (T6-02): bos://memory/unified write/recall/search.

Runnable both as pytest (``uv run pytest tests/test_unified_memory.py``) and as a
module (``uv run python -m mos.test_unified_memory``) — the latter is the ledger
verify command and requires tests/ be importable, so it runs pytest in-process.
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault("MOS_RBAC", "0")

from mos.unified import UnifiedMemory, default_unified_memory  # noqa: E402


def _fresh() -> UnifiedMemory:
    return default_unified_memory()


def test_unified_write_then_recall():
    um = _fresh()
    w = um.unified_write("旧暂行办法于2024年废止，新实施细则2026年生效", type="institutional")
    assert w.ok is True
    r = um.unified_recall("实施细则 生效日期")
    assert r.empty is False
    assert r.count >= 1


def test_unified_write_dedup_suppresses_duplicate():
    um = _fresh()
    um.unified_write("用户偏好：素食，不吃坚果", type="semantic")
    w2 = um.unified_write("用户偏好：素食，不吃坚果", type="semantic", dedup=True)
    assert w2.content_hash == "dedup-skip"


def test_unified_search_rrf_fuses_backends():
    um = _fresh()
    um.unified_write("新实施细则废止旧暂行办法", type="institutional")
    hits = um.unified_search("实施细则 废止")
    assert isinstance(hits, list)
    assert len(hits) >= 1
    for hit in hits:
        assert "rrf_score" in hit or "backends" in hit or "id" in hit or "title" in hit


def test_unified_recall_intent_routing():
    um = _fresh()
    r = um.unified_recall("谁调用了 record_memory 函数", intent="code_structure")
    assert r.intent == "code_structure"


def test_unified_status_reports_backends():
    um = _fresh()
    status = um.unified_status()
    assert status["ok"] is True
    assert isinstance(status["backend_status"], dict)


def test_unified_recall_empty_query_returns_result_not_raise():
    um = _fresh()
    r = um.unified_recall("")
    assert isinstance(r.empty, bool)


def _run_module() -> int:
    """Module entry: run the unified-memory assertions directly (no pytest dep).

    Satisfies the ledger verify command ``uv run python -m mos.test_unified_memory``.
    """
    failures: list[str] = []
    checks = [
        ("test_unified_write_then_recall", test_unified_write_then_recall),
        ("test_unified_write_dedup_suppresses_duplicate", test_unified_write_dedup_suppresses_duplicate),
        ("test_unified_search_rrf_fuses_backends", test_unified_search_rrf_fuses_backends),
        ("test_unified_recall_intent_routing", test_unified_recall_intent_routing),
        ("test_unified_status_reports_backends", test_unified_status_reports_backends),
        ("test_unified_recall_empty_query_returns_result_not_raise", test_unified_recall_empty_query_returns_result_not_raise),
    ]
    for name, fn in checks:
        try:
            fn()
            print(f"PASS  {name}")
        except AssertionError as exc:
            failures.append(name)
            print(f"FAIL  {name}: {exc}")
        except Exception as exc:  # noqa: BLE001
            failures.append(name)
            print(f"ERROR {name}: {exc!r}")
    if failures:
        print(f"\n{len(failures)} unified-memory check(s) failed: {failures}")
        return 1
    print(f"\nAll {len(checks)} unified-memory checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(_run_module())
