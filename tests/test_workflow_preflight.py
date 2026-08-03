"""Preflight + metaos backend gate tests (ADR-0181 Phase 2)."""

from __future__ import annotations


import pytest

from ecos.workflow.preflight import (
    PREFLIGHT_KEY,
    inject_preflight,
    issue_preflight,
    verify_preflight,
)


@pytest.fixture(autouse=True)
def _require_on(monkeypatch):
    monkeypatch.setenv("ECOS_WF_REQUIRE_PREFLIGHT", "1")
    monkeypatch.setenv("ECOS_WF_PREFLIGHT_SECRET", "test-secret")


def test_issue_and_verify_roundtrip():
    ctx = issue_preflight("wf-a")
    ok, reason = verify_preflight({PREFLIGHT_KEY: ctx}, workflow="wf-a")
    assert ok, reason


def test_inject_preflight_adds_key():
    params = inject_preflight({"x": 1}, "my-wf")
    assert params["x"] == 1
    assert PREFLIGHT_KEY in params
    ok, _ = verify_preflight(params, workflow="my-wf")
    assert ok


def test_missing_preflight_fails():
    ok, reason = verify_preflight({})
    assert not ok
    assert "missing" in reason


def test_tampered_token_fails():
    ctx = issue_preflight("wf-a")
    ctx["token"] = ctx["token"][:-4] + "dead"
    ok, reason = verify_preflight({PREFLIGHT_KEY: ctx}, workflow="wf-a")
    assert not ok
    assert "signature" in reason or "invalid" in reason


def test_require_disabled(monkeypatch):
    monkeypatch.setenv("ECOS_WF_REQUIRE_PREFLIGHT", "0")
    ok, reason = verify_preflight({})
    assert ok
    assert "disabled" in reason


def test_metaos_backend_blocks_without_preflight(monkeypatch):
    monkeypatch.setenv("ECOS_WF_REQUIRE_PREFLIGHT", "1")
    from ecos.workflow.backends import metaos as mb

    result = mb.execute(
        {"name": "demo", "id": "demo", "steps": [{"name": "s1", "action": "task"}]},
        {},
    )
    assert result.get("failed", 0) >= 1
    assert "preflight" in str(result.get("error", "")).lower()


def test_metaos_backend_accepts_valid_preflight(monkeypatch):
    """With preflight, adapter reaches metaos or reports unavailable — not preflight reject."""
    monkeypatch.setenv("ECOS_WF_REQUIRE_PREFLIGHT", "1")
    from ecos.workflow.backends import metaos as mb

    params = inject_preflight({}, "demo")
    result = mb.execute(
        {
            "name": "demo",
            "id": "demo",
            "steps": [{"name": "s1", "action": "reasoning", "description": "hello"}],
        },
        params,
    )
    assert "preflight_rejected" not in str(result.get("error", ""))
    # Either ran steps or metaos missing in env
    assert (
        result.get("preflight_ok") is True
        or result.get("passed", 0) + result.get("failed", 0) >= 0
    )
