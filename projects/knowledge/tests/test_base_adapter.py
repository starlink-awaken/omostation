"""Tests for BaseKnowledgeAdapter and Circuit Breaker logic."""

import pytest
from knowledge.adapter import AdapterHealth, BaseKnowledgeAdapter
from knowledge.models import KnowledgeDocument


class MockIrisAdapter(BaseKnowledgeAdapter):
    """Mock implementation of iris external connector adapter."""

    def __init__(self, should_fail: bool = False):
        super().__init__(name="iris_weijian", domain="work-weijian", config={"failure_threshold": 3, "recovery_timeout_sec": 1.0})
        self.should_fail = should_fail

    def health_check(self) -> AdapterHealth:
        return AdapterHealth(name=self.name, is_alive=not self.should_fail, latency_ms=12.5)

    def ingest(self, raw_input: str) -> list[KnowledgeDocument]:
        if self.should_fail:
            raise ConnectionError("Remote endpoint unreachable")
        return [
            KnowledgeDocument(
                doc_id="doc-iris-001",
                title="医疗数据中心接口标准",
                body=raw_input,
                zone=self.domain,
            )
        ]


def test_adapter_normal_ingest():
    """Verify normal ingestion flow."""
    adapter = MockIrisAdapter(should_fail=False)
    docs = adapter.ingest("全国医疗健康信息互联互通标准化成熟度测评方案")
    assert len(docs) == 1
    assert docs[0].zone == "work-weijian"
    assert "互联互通" in docs[0].body


def test_adapter_circuit_breaker_tripping():
    """Verify circuit breaker trips open after reaching failure threshold."""
    adapter = MockIrisAdapter(should_fail=True)

    # 连续执行触发熔断
    for _ in range(3):
        res = adapter.execute_safe("fetch", lambda: adapter.ingest("test"), fallback=[])
        assert res == []

    assert adapter._circuit_open is True
    # 熔断开启状态直接返回 fallback，不重复抛出异常
    res_tripped = adapter.execute_safe("fetch", lambda: adapter.ingest("test"), fallback=["fallback_val"])
    assert res_tripped == ["fallback_val"]
