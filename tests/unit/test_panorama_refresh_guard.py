"""Panorama refresh guard: the snapshot artifact is the liveness contract.

Hermetic: launchctl and the real snapshot are never touched.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parents[2] / "bin/gac/panorama-refresh-guard.py"


def _load():
    spec = importlib.util.spec_from_file_location("panorama_refresh_guard", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["panorama_refresh_guard"] = module
    spec.loader.exec_module(module)
    return module


class _Completed:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


@pytest.fixture
def guard(tmp_path, monkeypatch):
    module = _load()
    root = tmp_path / "ws"
    (root / "runtime" / "dashboard").mkdir(parents=True)
    monkeypatch.setattr(module, "code_root", lambda: root)
    monkeypatch.setattr(module.subprocess, "run", lambda *a, **k: _Completed())
    monkeypatch.setattr(os, "getuid", lambda: 501)
    monkeypatch.setenv("PANORAMA_REFRESH_MAX_AGE", "")
    return module, root


def _touch(root: Path, age: float) -> Path:
    data = root / "runtime" / "dashboard" / "data.json"
    data.write_text("{}", encoding="utf-8")
    stamp = time.time() - age
    os.utime(data, (stamp, stamp))
    return data


def test_fresh_snapshot_needs_no_action(guard, capsys):
    module, root = guard
    _touch(root, 60)
    assert module.main(["--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["stale"] is False and payload["action"] == "none"
    assert payload["age_seconds"] < 120


def test_stale_snapshot_is_kickstarted(guard, capsys):
    module, root = guard
    _touch(root, module.DEFAULT_MAX_AGE + 60)
    assert module.main(["--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["stale"] is True and payload["action"] == "kickstarted"


def test_missing_snapshot_is_kickstarted(guard, capsys):
    module, root = guard
    assert not (root / "runtime" / "dashboard" / "data.json").exists()
    assert module.main(["--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["stale"] is True and payload["age_seconds"] is None


def test_dry_run_reports_without_claiming_the_action(guard, capsys):
    module, root = guard
    _touch(root, module.DEFAULT_MAX_AGE + 60)
    module.main(["--json", "--dry-run"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["action"] == "kickstarted" and "DRY_RUN" in payload["detail"]


def test_failed_kickstart_is_an_error(guard, monkeypatch):
    module, root = guard
    monkeypatch.setattr(module.subprocess, "run",
                        lambda *a, **k: _Completed(returncode=1, stderr="no such job"))
    _touch(root, module.DEFAULT_MAX_AGE + 60)
    assert module.main(["--json"]) == 1


def test_budget_is_configurable(guard):
    module, root = guard
    _touch(root, 100)
    assert module.main(["--json", "--max-age", "50"]) == 0
    assert module.main(["--json", "--max-age", "500"]) == 0


@pytest.mark.parametrize("raw", ["abc", "0", "-1", "inf", "nan"])
def test_invalid_budget_is_rejected(guard, monkeypatch, raw):
    module, _ = guard
    monkeypatch.setenv("PANORAMA_REFRESH_MAX_AGE", raw)
    with pytest.raises(SystemExit):
        module.main([])


def test_guard_log_records_the_action(guard):
    module, root = guard
    _touch(root, module.DEFAULT_MAX_AGE + 60)
    module.main([])
    log = root / "runtime" / "cron" / "panorama-refresh-guard.log"
    assert log.is_file() and "kickstarted" in log.read_text(encoding="utf-8")
