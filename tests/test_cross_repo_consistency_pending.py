"""bos-pending-registrations.yaml 作已知积压基线: 单列计数不阻断, 只拦新增未登记 URI."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

WORKSPACE = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location(
        "xrepo", WORKSPACE / "bin" / "ssot" / "check-cross-repo-consistency.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run(mod, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, pending: list[str], capsys) -> tuple[int, dict]:
    (tmp_path / "pending.yaml").write_text(
        "pending_registrations:\n" + "".join(f"  - uri: {u}\n    source: t\n" for u in pending), encoding="utf-8"
    )
    monkeypatch.setattr(mod, "PENDING_REGISTRATIONS", tmp_path / "pending.yaml")
    monkeypatch.setattr(mod, "load_agora_registered_uris", lambda: {"bos://known/svc/run": {}})
    monkeypatch.setattr(
        mod, "collect_referenced_uris", lambda: {"bos://known/svc/run", "bos://old/x/y", "bos://new/x/y"}
    )
    monkeypatch.setattr(mod, "load_ecos_ports", lambda: {})
    monkeypatch.setattr(mod, "load_protocols_ports", lambda: {})
    monkeypatch.setattr(mod, "find_port_conflicts", lambda: [])
    monkeypatch.setattr(sys, "argv", ["x", "--json"])
    rc = mod.main()
    return rc, json.loads(capsys.readouterr().out)


def test_new_unregistered_uri_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys) -> None:
    rc, out = _run(_load(), monkeypatch, tmp_path, ["bos://old/x/y"], capsys)
    assert rc == 1 and out["ok"] is False
    assert out["unregistered"] == 2 and out["unregistered_pending"] == 1
    assert out["unregistered_new_list"] == ["bos://new/x/y"]


def test_known_backlog_only_passes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys) -> None:
    rc, out = _run(_load(), monkeypatch, tmp_path, ["bos://old/x/y", "bos://new/x/y"], capsys)
    assert rc == 0 and out["ok"] is True
    assert out["unregistered"] == 2 and out["unregistered_new"] == 0
