"""KOS test conftest — 索引依赖 test 自动 skip.

部分 test 依赖 KOS 索引有数据 (domains/entities/count > 0).
测试环境若索引未建, 这些 test 自动 skip (区分"环境缺数据" vs "代码坏", 保持 CI 信号干净).
建索引: python -m kos.indexer.engine  (或 kos-indexer index).
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

# 依赖 KOS 索引数据的 test (nodeid 后缀匹配, 索引空时自动 skip).
# 名单源自 test-diff 失败列表 (全 count=0/entities=0 索引空依赖, 非代码 bug).
_NEEDS_INDEX: list[str] = [
    "test_cache.py::TestSearchCache::test_search_with_cache",
    "test_cache.py::TestSearchCache::test_search_with_cache_hit",
    "test_cache.py::TestCacheIntegration::test_engine_caching",
    "test_cache.py::TestCacheIntegration::test_no_cache_option",
    "test_hybrid_search.py::TestHybridSearchEngine::test_keyword_search",
    "test_integration.py::TestGbrainBridge::test_context_manager",
    "test_integration.py::TestGbrainBridge::test_sync_status",
    "test_maintenance.py::TestAlertService::test_check_index_integrity",
    "test_new_features.py::TestGraphRAG::test_multi_hop_search",
    "test_search_quality.py::TestIndexHealth::test_index_has_zones",
    "test_search_quality.py::TestIndexHealth::test_index_document_count",
]


def _kos_index_has_data() -> bool:
    """检查 KOS 索引是否有数据 (domains count > 0). session 级缓存."""
    if getattr(_kos_index_has_data, "_cached", None) is not None:
        return _kos_index_has_data._cached  # type: ignore[no-any-return]
    cached = False
    try:
        r = subprocess.run(
            [sys.executable, "-m", "kos", "domains", "--format", "json"],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if r.returncode == 0:
            data = json.loads(r.stdout)
            count = data.get("data", {}).get("count", 0) if isinstance(data, dict) else 0
            cached = count > 0
    except Exception:
        cached = False
    _kos_index_has_data._cached = cached  # type: ignore[attr-defined]
    return cached


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:  # config 是 pytest hookspec 必需参数名 (改名 _config 会破坏 hook, PluginValidationError)
    """索引无数据时, 自动 skip _NEEDS_INDEX 列出的 test (环境性, 非代码 bug)."""
    if _kos_index_has_data():
        return
    skip = pytest.mark.skip(reason="KOS 索引无数据 (环境性, 非代码 bug). 建索引: kos-indexer index")
    for item in items:
        if any(suffix in item.nodeid for suffix in _NEEDS_INDEX):
            item.add_marker(skip)
