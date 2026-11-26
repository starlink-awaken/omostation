"""「没测成」的原因必须出自显式词汇表 —— 新原因是一次显式动作。

2026-11-26 收口时的实测：部分检出树上 **17 条红全部带标注**（无标注 = 0）。
这条测试把「原因集合显式化 + 未登记即告警」钉住，防止下一个新原因无声漂进来。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "bin" / "gac" / "gac-local-gate.py"


@pytest.fixture(scope="module")
def mod():
    spec = importlib.util.spec_from_file_location("gate_reasons", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_vocabulary_is_non_empty_and_unique(mod):
    assert mod.KNOWN_NOT_MEASURED_REASONS
    assert len(mod.KNOWN_NOT_MEASURED_REASONS) == len(set(mod.KNOWN_NOT_MEASURED_REASONS))


def test_known_reason_is_silent(mod, capsys):
    mod.warn_if_unknown_reason("some-check", "entrypoint_missing")
    assert capsys.readouterr().err == ""


def test_unknown_reason_warns_with_both_names(mod, capsys):
    mod.warn_if_unknown_reason("some-check", "brand_new_reason")
    err = capsys.readouterr().err
    assert "brand_new_reason" in err and "KNOWN_NOT_MEASURED_REASONS" in err


def test_each_reason_traces_to_a_real_source(mod):
    """每个登记原因都要有出处 —— 与实际产生它的地方一一对应。"""
    sources = {
        "missing_input": "current-state-coherence 自报",
        "entrypoint_missing": "_missing_entrypoint（#5371）",
        "dependencies_unchecked": "REQUIRED_SUBMODULES（#5588）",
        "targets_absent": "doc-link-check（#5579）",
        "paths_absent": "capability-ownership / auto-fix-loop（#5582）",
        "scan_incomplete": "gen-dependency-baseline（#5585）",
        "generation_failed": "check-evidence-freshness（#5557）",
        "launchd_observer_unavailable": (
            "gen-service-configs --check（本机 ~/Library/LaunchAgents 缺席；"
            "债条目 OMO-DEBT-GATE-SERVICE-CONFIG-DRIFT-HOST-STATE-INPUT-NO-PROVENANCE）"
        ),
    }
    assert set(mod.KNOWN_NOT_MEASURED_REASONS) == set(sources), (
        "词汇表与出处清单不一致 —— 改这里时必须同步"
    )
