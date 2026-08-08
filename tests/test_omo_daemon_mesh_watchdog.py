from __future__ import annotations

from types import SimpleNamespace

from omo import omo_daemon


def test_daemon_tick_passes_explicit_watchdog_mode(monkeypatch, tmp_path):
    calls: list[dict] = []
    monkeypatch.setattr(
        omo_daemon,
        "run_governance_audit",
        lambda: SimpleNamespace(total_score=100.0, grade="A", watchlist=[], checks=[]),
    )
    monkeypatch.setattr(
        omo_daemon,
        "_ensure_sync_module",
        lambda: {
            "collect": dict,
            "read": lambda _: {},
            "diff": lambda *_: [],
            "system_yaml": tmp_path / "system.yaml",
        },
    )

    def fake_runner(root, *, now=None, apply=False, reason="lease_expired"):
        calls.append({"root": root, "now": now, "apply": apply, "reason": reason})
        return {"status": "completed", "errors": [], "scan": {}}

    monkeypatch.setattr(omo_daemon, "run_mesh_watchdog_once", fake_runner)
    monkeypatch.setattr(omo_daemon, "_publish_tick_event", lambda _: None)

    result = omo_daemon.run_once(
        history_path=tmp_path / "history.jsonl",
        mesh_watchdog=True,
        mesh_watchdog_apply=True,
        mesh_watchdog_now="2026-08-02T00:01:00Z",
    )

    assert result.error is None
    assert result.mesh_watchdog == {"status": "completed", "errors": [], "scan": {}}
    assert calls[0]["apply"] is True
    assert calls[0]["now"] == "2026-08-02T00:01:00Z"
