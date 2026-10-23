"""A6 的准入本体是探针/R0 证据/写保护, 不是 Orca 桌面窗口是否开着。

2026-10-23 实测: 窗口关着时 runtime.state = graph_not_ready, 于是 A6 立刻
NOT_ADMITTED, 而 6 个探针全过 —— 判据过严, 让一个 GUI 窗口决定门禁红绿。
`orca open` 能修, 但窗口一关又红, 所以放宽判据并在 detail 里注明窗口状态。
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin/panorama/panorama-collect.py"


class _Completed:
    def __init__(self, payload):
        self.returncode = 0
        self.stdout = json.dumps(payload)
        self.stderr = ""


def _load(monkeypatch, tmp_path, payload):
    spec = importlib.util.spec_from_file_location("panorama_a6_window", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    verifier = module.CODE_ROOT / "bin/gac/orca-r0-verify.py"
    verifier.parent.mkdir(parents=True, exist_ok=True)
    verifier.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    # 采集器直接调 subprocess.run, 不经过模块的 run()
    monkeypatch.setattr(module.subprocess, "run",
                        lambda cmd, **kw: _Completed(payload))
    monkeypatch.setattr("time.sleep", lambda _s: None)
    # 缓存文件不存在 -> 不干扰判定
    monkeypatch.setattr(module, "collect_reference_cell_gate", lambda: {"id": "RC", "verdict": "PASS"})
    return module


def _report(**over):
    base = {
        "schema": "orca-r0-verify/v1",
        "ok": True,
        "runtime_ready": False,
        "probes": {"passed": 6, "total": 6},
        "r0_transactions": {"accepted": 1, "transactions": [{"ok": True}]},
        "trust": {"write_argv_guard": {"ok": True}},
    }
    base.update(over)
    return base


def test_window_closed_still_passes_with_reason(monkeypatch, tmp_path):
    module = _load(monkeypatch, tmp_path, _report(runtime_ready=False))
    gate = module.collect_a6_gate()
    assert gate["verdict"] == "PASS", gate
    assert "window closed" in gate["detail"]
    assert "probes 6/6" in gate["detail"]


def test_window_open_passes_without_the_note(monkeypatch, tmp_path):
    module = _load(monkeypatch, tmp_path, _report(runtime_ready=True))
    gate = module.collect_a6_gate()
    assert gate["verdict"] == "PASS"
    assert "window closed" not in gate["detail"]


def test_probes_failing_still_blocks(monkeypatch, tmp_path):
    module = _load(monkeypatch, tmp_path, _report(probes={"passed": 5, "total": 6}))
    gate = module.collect_a6_gate()
    assert gate["verdict"] == "NOT_ADMITTED", gate


def test_missing_r0_evidence_still_blocks(monkeypatch, tmp_path):
    module = _load(monkeypatch, tmp_path, _report(r0_transactions={"accepted": 0, "transactions": []}))
    gate = module.collect_a6_gate()
    assert gate["verdict"] == "NOT_ADMITTED", gate


def test_write_guard_failing_still_blocks(monkeypatch, tmp_path):
    module = _load(monkeypatch, tmp_path, _report(trust={"write_argv_guard": {"ok": False}}))
    gate = module.collect_a6_gate()
    assert gate["verdict"] == "NOT_ADMITTED", gate


def test_missing_verifier_still_not_admitted(monkeypatch, tmp_path):
    """verifier 文件不存在时仍报 missing —— 不能被放宽的判据带跑。"""
    spec = importlib.util.spec_from_file_location("panorama_a6_missing", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "CODE_ROOT", tmp_path)  # 无 bin/gac/orca-r0-verify.py
    gate = module.collect_a6_gate()
    assert gate["verdict"] == "NOT_ADMITTED"
    assert "missing" in gate["detail"]
