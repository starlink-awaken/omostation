"""lane 隔离欠账台账 (ADR-0122 §46) 的合同测试。

**为什么有这个面**: lane 隔离规则在 2026-10-30 之前从未真正生效 (三条执行路径全空转),
期间 main 上积累了混 lane 的 commit。本台账把它们显形, 供后续人判断哪些该消化。

**本测试锁住三件事**:
1. **台账是记录面, 不是豁免** —— advisory_only 必须为真。若被做成豁免, 它就成了新提交
   的逃逸口, 与规则本意相反。
2. **--check 验内在自洽, 不验等值** —— 等值校验依赖完整历史 (CI 的 checkout depth=1 拿不到)
   => 在 CI 上必然误报。台账数字滞后是设计如此 (提交台账本身会 +1 total)。
3. **成因分类正确** —— 决定「这笔该由谁消化」: 分类器边界偏碎 vs 真正的多面混合。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LEDGER_TOOL = ROOT / "bin" / "ops" / "lane-debt-ledger.py"
LEDGER_FILE = ROOT / ".omo" / "_truth" / "registry" / "lane-debt-ledger.yaml"


def _load():
    spec = importlib.util.spec_from_file_location("lane_debt_ledger", str(LEDGER_TOOL))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["lane_debt_ledger"] = module
    spec.loader.exec_module(module)
    return module


def test_cause_classification_distinguishes_boundary_gaps_from_real_mixtures():
    """成因分类: 分类器边界偏碎 vs 真正的多面混合。"""
    module = _load()

    assert module.classify_cause({"code", "other"}) == "classifier-gap-other"
    assert (
        module.classify_cause({"governance_code", "governance_state"})
        == "boundary-governance-registration"
    )
    assert (
        module.classify_cause({"code", "governance_code"})
        == "boundary-code-vs-governance-code"
    )
    assert module.classify_cause({"code", "config"}) == "boundary-code-vs-config"
    assert module.classify_cause({"docs", "submodule_pointer"}) == "submodule-pointer-mixed"
    assert (
        module.classify_cause({"code", "docs", "docs_data", "governance_state"})
        == "multi-surface"
    )


def test_committed_ledger_is_advisory_only_and_self_consistent():
    """已入库的台账: advisory_only 为真, 且内在自洽。"""
    import yaml

    assert LEDGER_FILE.is_file(), "台账未入库"
    data = yaml.safe_load(LEDGER_FILE.read_text(encoding="utf-8"))
    assert data["advisory_only"] is True, "台账必须声明为纯记录面 (不得成为豁免)"
    assert data["main_commits_mixed_lane"] <= data["main_commits_total"]
    causes = data["mixed_lane_causes"] or {}
    assert sum(int(v) for v in causes.values()) == data["main_commits_mixed_lane"]


def test_check_mode_validates_ledger_self_consistency():
    """--check 验内在自洽 —— 不要求与实际历史等值 (CI 的 depth=1 拿不到完整历史)。"""
    module = _load()
    assert module._check_ledger() == 0, "已入库台账应通过内在自洽校验"


def test_ledger_records_the_squash_vs_real_debt_distinction():
    """台账必须写明「main 上的混 lane commit 是 squash 结构性产物, 不是欠账」。

    这条区分是本台账的全部意义: 逐条登记几千个 squash 产物是登记「squash 的记录方式」,
    而非登记「欠账」。可消化的真实欠账 = PR 分支上某个 commit 自身混 lane。
    """
    assert LEDGER_FILE.is_file()
    text = LEDGER_FILE.read_text(encoding="utf-8")
    assert "squash" in text, "台账须说明 squash 结构性产物这件事"
    assert "结构性产物" in text
    assert "非欠账指标" in text or "不是欠账指标" in text
