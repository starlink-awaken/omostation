import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from llm_provider import llm_classify


def test_none_backend_returns_none():
    note = llm_classify({"name": "adr", "count": 10, "dimension": "X3"}, backend="none")
    assert note is None


def test_auto_backend_degrades_to_none_when_down(monkeypatch):
    # aetherforge + omlxc 都不可达 → 返回 None（保持规则式基线）
    monkeypatch.setenv("AGORA_BASE_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("OMLXC_BASE_URL", "http://127.0.0.1:1/v1")
    note = llm_classify({"name": "adr", "count": 10, "dimension": "X3"})
    assert note is None


def test_aetherforge_backend_returns_none_when_down(monkeypatch):
    monkeypatch.setenv("AGORA_BASE_URL", "http://127.0.0.1:1")
    note = llm_classify({"name": "adr", "count": 10, "dimension": "X3"},
                        backend="aetherforge")
    assert note is None
