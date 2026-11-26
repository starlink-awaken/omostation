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


# ── 策略内 id 重复（集合口径会把重复折叠成一条，覆盖读数因此少算）──
# 发现经过: 报告说 default_total=74 而手数条目 75, 差 1 追出 state-freshness-check 重复。


def test_coverage_exposes_entry_counts_and_duplicate_ids(mod):
    cov = mod.gate_coverage_report()
    effective_entries = [g["id"] for g in mod.GATES_LIST]
    default_entries = [g["id"] for g in mod.DEFAULT_POLICY["gates"]]

    assert cov["entries"]["effective"] == len(effective_entries)
    assert cov["entries"]["default"] == len(default_entries)
    # 条目数 >= id 数, 差值就是重复折叠掉的条数
    assert cov["entries"]["effective"] >= cov["effective"]
    assert cov["entries"]["default"] >= cov["default_total"]

    def dups(ids):
        return sorted({i for i in ids if ids.count(i) > 1})

    assert set(cov["duplicate_ids"]["effective"]) == set(dups(effective_entries))
    assert set(cov["duplicate_ids"]["default"]) == set(dups(default_entries))


def test_default_duplicate_was_merged_into_one_entry(mod):
    """原先 DEFAULT 里 state-freshness-check 有两条（命令不同）。合并后：无重复、
    保留机器可读的 --json 形式、并继承 ci_only 以保住原执行面。"""
    cov = mod.gate_coverage_report()
    assert cov["duplicate_ids"]["default"] == []
    assert cov["entries"]["default"] == cov["default_total"]

    entries = [g for g in mod.DEFAULT_POLICY["gates"] if g.get("id") == "state-freshness-check"]
    assert len(entries) == 1
    assert entries[0]["command"] == ["bin/gac/state-freshness-check.py", "--json"]
    assert entries[0].get("ci_only") is True


def test_duplicate_detector_fires_on_injected_duplicate(mod, monkeypatch):
    """合成违规自证: 往 DEFAULT 塞一条重复, 报告必须点名 —— 否则上面两条可能只是空转。"""
    base = mod.DEFAULT_POLICY["gates"]
    before = mod.gate_coverage_report()
    before_gap = before["entries"]["default"] - before["default_total"]

    clone = dict(next(g for g in base if g.get("id") == "doc-ssot-snapshots"))
    monkeypatch.setattr(mod, "DEFAULT_POLICY", {**mod.DEFAULT_POLICY, "gates": [*base, clone]})

    cov = mod.gate_coverage_report()

    assert "doc-ssot-snapshots" in cov["duplicate_ids"]["default"]
    assert cov["entries"]["default"] - cov["default_total"] == before_gap + 1


def test_printer_names_duplicates(mod, capsys):
    mod._print_gate_coverage(
        {
            "gate_coverage": {
                "source": "sgf_policy",
                "effective": 96,
                "default_total": 74,
                "only_in_default": [],
                "duplicate_ids": {"default": ["state-freshness-check"], "effective": []},
            }
        }
    )
    err = capsys.readouterr().err
    assert "id 重复" in err
    assert "state-freshness-check" in err


# ── 并集底座（DEFAULT 独有的 gate 在齐备树也要执行）──
# 债条目 GATE-POLICY-SOURCE-COVERAGE-SKEW：这 5 条在 submodule 策略里没有等价命令，
# 此前 CI/齐备树从不执行；现在由 gac-local-gate 从 DEFAULT 回填。


def test_default_only_gates_are_backfilled_into_the_live_set(mod):
    cov = mod.gate_coverage_report()
    live_ids = {g["id"] for g in mod.GATES_LIST}

    assert set(mod.DEFAULT_BACKFILL_IDS) <= live_ids
    assert not (set(cov["only_in_default"]) & set(mod.DEFAULT_BACKFILL_IDS))
    # 回填的是 DEFAULT 里的**同一个对象**, 不是拷贝 —— 避免两处定义漂移
    for bid in mod.DEFAULT_BACKFILL_IDS:
        assert next(g for g in mod.GATES_LIST if g["id"] == bid) is next(
            g for g in mod.DEFAULT_POLICY["gates"] if g["id"] == bid
        )


def test_renamed_submodule_gate_is_not_backfilled(mod):
    """`submodule-ancestry-gate` 与 sgf-policy 的 `check-submodule-rewind` 是同一脚本,
    回填等于把同一个检查跑两遍 —— 必须留在 only_in_default 里。"""
    cov = mod.gate_coverage_report()
    assert "submodule-ancestry-gate" in cov["only_in_default"]
    assert "submodule-ancestry-gate" not in mod.DEFAULT_BACKFILL_IDS
