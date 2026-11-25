"""Unit tests for bin/panorama/assets/host/collectors.multica.py.asset."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import subprocess
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ASSET = ROOT / "bin/panorama/assets/host/collectors.multica.py.asset"


def _load_collector_module(monkeypatch):
    collectors_pkg = types.ModuleType("collectors")
    collectors_pkg.__path__ = []

    base_mod = types.ModuleType("collectors.base")

    class CollectionError(Exception):
        def __init__(self, source: str, reason: str, cause: Exception | None = None):
            self.source = source
            self.reason = reason
            self.cause = cause
            super().__init__(f"Collection failed for '{source}': {reason}")

    class DataCollector:
        name = ""
        timeout = 48

        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                if not hasattr(self, key):
                    raise TypeError(f"{self.__class__.__name__} got unexpected keyword argument '{key}'")
                setattr(self, key, value)

        def run(self):
            try:
                data = self.collect()
                if not self.validate(data):
                    return self.name, None, "Validation failed (0.0s)"
                return self.name, data, None
            except CollectionError as exc:
                return self.name, None, exc.reason

    base_mod.CollectionError = CollectionError
    base_mod.DataCollector = DataCollector

    registry_mod = types.ModuleType("collectors.registry")
    registry_mod.COLLECTORS = []

    def register(name: str, timeout: int = 48):
        def decorator(cls):
            cls.name = name
            cls.timeout = timeout
            registry_mod.COLLECTORS.append((name, cls, timeout))
            return cls
        return decorator

    registry_mod.register = register

    monkeypatch.setitem(sys.modules, "collectors", collectors_pkg)
    monkeypatch.setitem(sys.modules, "collectors.base", base_mod)
    monkeypatch.setitem(sys.modules, "collectors.registry", registry_mod)

    loader = importlib.machinery.SourceFileLoader("collectors.multica", str(ASSET))
    spec = importlib.util.spec_from_loader("collectors.multica", loader)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["collectors.multica"] = module
    loader.exec_module(module)
    return module


def test_collect_projects_lists_and_sets_direct_tls_env(monkeypatch):
    mod = _load_collector_module(monkeypatch)
    seen_calls: list[tuple[list[str], dict[str, str]]] = []
    payloads = {
        "runtime": [{
            "id": "rt-1", "name": "mbp", "custom_name": "MacbookPro-M5",
            "provider": "agy", "status": "online", "last_seen_at": "2026-11-25T07:00:00Z",
            "extra_secret_field": "drop-me",
        }],
        "agent": [{
            "id": "ag-1", "name": "reviewer", "model": "claude",
            "runtime_id": "rt-1", "runtime_mode": "local", "status": "active",
            "permission_mode": "auto", "instructions": "drop-me",
        }],
        "squad": [{
            "id": "sq-1", "name": "delivery", "member_count": 3, "leader_id": "ag-1",
            "unused": True,
        }],
    }

    def fake_run(argv, *, env=None, capture_output=True, text=True, timeout=18):
        seen_calls.append((argv, dict(env or {})))
        entity = argv[1]
        return subprocess.CompletedProcess(argv, 0, json.dumps(payloads[entity]), "")

    monkeypatch.setenv("NO_PROXY", "localhost,api.multica.ai")
    monkeypatch.delenv("no_proxy", raising=False)
    monkeypatch.setenv("GODEBUG", "http2debug=0")
    monkeypatch.setattr(mod.subprocess, "run", fake_run)

    collector = mod.MulticaCollector(multica_bin="/usr/local/bin/multica")
    name, data, err = collector.run()

    assert name == "multica"
    assert err is None
    assert data is not None
    assert data["state"] == "OBSERVED"
    assert data["runtimes"] == [{
        "id": "rt-1", "name": "mbp", "custom_name": "MacbookPro-M5",
        "provider": "agy", "status": "online", "last_seen_at": "2026-11-25T07:00:00Z",
    }]
    assert data["agents"] == [{
        "id": "ag-1", "name": "reviewer", "model": "claude",
        "runtime_id": "rt-1", "runtime_mode": "local", "status": "active",
        "permission_mode": "auto",
    }]
    assert data["squads"] == [{
        "id": "sq-1", "name": "delivery", "member_count": 3, "leader_id": "ag-1",
    }]
    assert len(seen_calls) == 3
    for argv, env in seen_calls:
        assert argv[0] == "/usr/local/bin/multica"
        assert "api.multica.ai" in env["NO_PROXY"].split(",")
        assert ".multica.ai" in env["NO_PROXY"].split(",")
        assert env["NO_PROXY"].split(",").count("api.multica.ai") == 1
        assert "api.multica.ai" in env["no_proxy"].split(",")
        assert ".multica.ai" in env["no_proxy"].split(",")
        assert "tlsmlkem=0" in env["GODEBUG"].split(",")
        assert "http2debug=0" in env["GODEBUG"].split(",")


def test_validate_handles_plural_lists_rejects_bad_and_keeps_legacy_compat(monkeypatch):
    mod = _load_collector_module(monkeypatch)
    collector = mod.MulticaCollector()

    assert collector.validate({"runtimes": [], "agents": [], "squads": []}) is True
    assert collector.validate({"runtimes": [{}], "agents": "bad", "squads": []}) is False
    assert collector.validate({}) is False
    assert collector.validate("not-a-dict") is False
    # Legacy compatibility for host tests checking runtime=None / runtime={data: []}
    assert collector.validate({"runtime": None}) is True
    assert collector.validate({"runtime": {"data": []}}) is True


def test_collect_raises_collection_error_on_nonzero_or_non_list(monkeypatch):
    mod = _load_collector_module(monkeypatch)
    collector = mod.MulticaCollector(multica_bin="/usr/local/bin/multica")

    monkeypatch.setattr(
        mod.subprocess,
        "run",
        lambda argv, **kwargs: subprocess.CompletedProcess(argv, 1, "", "network timeout"),
    )
    _, data, err = collector.run()
    assert data is None
    assert err is not None and "multica runtime list failed: network timeout" in err

    monkeypatch.setattr(
        mod.subprocess,
        "run",
        lambda argv, **kwargs: subprocess.CompletedProcess(argv, 0, '{"unexpected": true}', ""),
    )
    _, data2, err2 = collector.run()
    assert data2 is None
    assert err2 is not None and "expected list" in err2
