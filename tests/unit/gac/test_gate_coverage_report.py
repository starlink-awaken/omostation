"""门禁策略来源的覆盖差异必须**显形**（只读报告 + 人读一行）。

`POLICY = load_sgf_policy() or DEFAULT_POLICY` 是整体二选一，所以「只在另一边存在的
条目」会无声消失：齐备树/CI 用 submodule 策略时会丢 5 条（见债条目
GATE-POLICY-SOURCE-COVERAGE-SKEW），partial 树走 fallback 时丢 28 条。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "bin" / "gac" / "gac-local-gate.py"


@pytest.fixture(scope="module")
def mod():
    spec = importlib.util.spec_from_file_location("gate_coverage", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_coverage_reports_source_and_both_diffs(mod):
    cov = mod.gate_coverage_report()
    effective = {g["id"] for g in mod.GATES_LIST}
    default_ids = {g["id"] for g in mod.DEFAULT_POLICY["gates"]}
    assert cov["source"] == ("sgf_policy" if mod.POLICY is not mod.DEFAULT_POLICY else "default_policy")
    assert cov["effective"] == len(effective)
    assert cov["default_total"] == len(default_ids)
    assert set(cov["only_in_default"]) == default_ids - effective
    assert set(cov["only_in_effective"]) == effective - default_ids


def test_source_reflects_which_policy_won(mod):
    """来源标记必须与实际生效的策略一致（不能恒报一个）。"""
    expected = "sgf_policy" if mod.POLICY is not mod.DEFAULT_POLICY else "default_policy"
    assert mod.gate_coverage_report()["source"] == expected


def test_printer_is_silent_when_nothing_missing(mod, capsys):
    mod._print_gate_coverage({"gate_coverage": {"only_in_default": []}})
    assert "本树不执行" not in capsys.readouterr().err


def test_printer_names_the_unexecuted_gates(mod, capsys):
    mod._print_gate_coverage(
        {
            "gate_coverage": {
                "source": "sgf_policy",
                "effective": 96,
                "default_total": 74,
                "only_in_default": ["debt-integrity-check", "sweep-index-check"],
            }
        }
    )
    err = capsys.readouterr().err
    assert "debt-integrity-check" in err and "sweep-index-check" in err
    assert "96" in err
