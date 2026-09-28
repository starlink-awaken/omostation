"""Hermetic tests for bin/lib/gh_query.py — 重试 + 空保护语义 (BET-Y2Q4-T10-08).

debt TOOL-GRAPHQL-FLAKY-EMPTY-MEANS-UNKNOWN 的规则钉:
  - 瞬态失败 (EOF/timeout/network) 重试, 耗尽 → GhQueryUnknown
  - rc=0 + 空输出 = 抖动签名, 同样重试; 耗尽后按 treat_empty_as_unknown 分流
  - 非瞬态失败 (权限/参数) → GhQueryFailed, 不重试
  - 成功 + 非空 JSON → 原样解析返回
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

_WS = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location(
        "gh_query_under_test", _WS / "bin" / "lib" / "gh_query.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def gq(monkeypatch):
    mod = _load()
    calls = []

    def _set(run_results: list[tuple[int, str, str]]):
        seq = iter(run_results)

        def fake_run(*a, **k):
            rc, out, err = next(seq)
            calls.append(a)
            return subprocess.CompletedProcess(a[0] if a else [], rc, stdout=out, stderr=err)

        monkeypatch.setattr(mod.subprocess, "run", fake_run)

    mod._calls = calls
    mod._set = _set
    return mod


def test_success_passthrough(gq, monkeypatch):
    gq._set([(0, json.dumps({"n": 1}), "")])
    assert gq.gh_json("pr", "list", "--json", "n") == {"n": 1}
    assert len(gq._calls) == 1  # 成功不重试


def test_transient_failure_retries_then_succeeds(gq, monkeypatch):
    gq._set([
        (1, "", "http: i/o timeout"),
        (1, "", "EOF occurred"),
        (0, json.dumps([{"number": 7}]), ""),
    ])
    assert gq.gh_json("pr", "list") == [{"number": 7}]
    assert len(gq._calls) == 3


def test_transient_exhausted_raises_unknown(gq, monkeypatch):
    gq._set([(1, "", "i/o timeout")] * 3)
    with pytest.raises(gq.GhQueryUnknown):
        gq.gh_json("pr", "list", retries=3)


def test_non_transient_fails_fast(gq, monkeypatch):
    gq._set([(1, "", "gh: Not Found (HTTP 404)")] * 5)
    with pytest.raises(gq.GhQueryFailed):
        gq.gh_json("pr", "list", retries=3)
    assert len(gq._calls) == 1  # 非瞬态不重试


def test_empty_is_flake_signature_retries_then_legit(gq, monkeypatch):
    """rc=0 + 空 = 抖动签名: 重试; 耗尽仍空且 treat_empty_as_unknown=False → [] (真无 PR)."""
    gq._set([(0, "", ""), (0, "", ""), (0, "", "")])
    assert gq.gh_json("pr", "list", retries=3, treat_empty_as_unknown=False) == []
    assert len(gq._calls) == 3


def test_empty_exhausted_unknown_when_required(gq, monkeypatch):
    gq._set([(0, "", "")] * 3)
    with pytest.raises(gq.GhQueryUnknown):
        gq.gh_json("pr", "list", retries=3, treat_empty_as_unknown=True)


def test_invalid_json_is_hard_failure(gq, monkeypatch):
    gq._set([(0, "{not json", "")])
    with pytest.raises(gq.GhQueryFailed):
        gq.gh_json("pr", "list")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
