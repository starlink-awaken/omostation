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
    # Point CODE_ROOT at a scratch tree: the collector only checks
    # `<CODE_ROOT>/bin/gac/orca-r0-verify.py` for existence and then stubs
    # subprocess.run, so the stub must never overwrite the real source file.
    code_root = tmp_path / "code-root"
    verifier = code_root / "bin/gac/orca-r0-verify.py"
    verifier.parent.mkdir(parents=True, exist_ok=True)
    verifier.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    monkeypatch.setattr(module, "CODE_ROOT", code_root)
    # 采集器直接调 subprocess.run, 不经过模块的 run()
    monkeypatch.setattr(module.subprocess, "run",
                        lambda cmd, **kw: _Completed(payload))
    monkeypatch.setattr("time.sleep", lambda _s: None)
    # 缓存文件不存在 -> 不干扰判定
    monkeypatch.setattr(module, "collect_reference_cell_gate", lambda: {"id": "RC", "verdict": "PASS"})
    return module


def _report(**over):
    """Mirror the real verifier: `ok` folds runtime_ready into the verdict.

    bin/gac/orca-r0-verify.py emits
    ``"ok": bool(runtime_ready and probe_ok and accepted == 1 and guard_ok)``.
    Hand-writing ``ok: True`` here hid that, which is why #4873's relaxation
    shipped as dead code (2026-10-26: window closed, probes 6/6, A6 still red).
    """
    probes = over.get("probes", {"passed": 6, "total": 6})
    r0 = over.get("r0_transactions", {"accepted": 1, "transactions": [{"ok": True}]})
    trust = over.get("trust", {"write_argv_guard": {"ok": True}})
    runtime_ready = over.get("runtime_ready", False)
    derived_ok = bool(
        runtime_ready
        and probes.get("passed") == probes.get("total")
        and probes.get("total", 0) > 0
        and r0.get("accepted", 0) >= 1
        and all(t.get("ok") for t in r0.get("transactions") or [])
        and trust.get("write_argv_guard", {}).get("ok") is True
    )
    base = {
        "schema": "orca-r0-verify/v1",
        "ok": derived_ok,
        "runtime_ready": runtime_ready,
        "probes": probes,
        "r0_transactions": r0,
        "trust": trust,
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


def test_fixture_does_not_clobber_the_real_verifier(monkeypatch, tmp_path):
    """用例不得改写仓库里的真实校验器。

    `_load` 曾把桩写进 `module.CODE_ROOT/bin/gac/orca-r0-verify.py` —— 那就是
    仓库里的真文件, 跑完用例工作树就多一个 governance_code 脏文件。2026-10-26 实测。
    """
    real = ROOT / "bin/gac/orca-r0-verify.py"
    before = real.read_bytes()
    _load(monkeypatch, tmp_path, _report(runtime_ready=True))
    assert real.read_bytes() == before


def test_report_ok_false_merely_because_the_window_is_closed_still_passes(monkeypatch, tmp_path):
    """#4873 的放宽分支曾因 report.ok 恒为 False 而永不触发。

    真实校验器把 runtime_ready 折进 ok, 于是「关窗」会让 report.ok=False;
    若 A6 直接拿 report.ok 当判据, 探针全过也照样红。这条用例把那个形状
    钉住 —— 判据只认 probes / R0 evidence / write_guard。
    """
    report = _report(runtime_ready=False)
    assert report["ok"] is False, "fixture 必须复现真实校验器的 ok 语义"
    module = _load(monkeypatch, tmp_path, report)
    gate = module.collect_a6_gate()
    assert gate["verdict"] == "PASS", gate


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
