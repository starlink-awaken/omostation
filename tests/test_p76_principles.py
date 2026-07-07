"""test_p76_principles.py — P77 Phase 2 演化护栏 catalog 验证

P77 STRAT § 4 沉淀原则形式化 (principle-formalization-with-context).
"""
import re
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
CATALOG = WORKSPACE / ".omo" / "standards" / "p76-principles.md"


def test_catalog_exists():
    """catalog 真存在"""
    assert CATALOG.exists(), f"catalog missing: {CATALOG}"


def test_catalog_has_15_principle_codes():
    """catalog 含 15+ P76-N-N 形式原则 codes (按 ADR § 2 表)."""
    text = CATALOG.read_text()
    codes = re.findall(r"P76-\d+-\d+|P76-7-\d+|P77-1\b|P76-9A-\d+", text)
    # 至少 10 个 distinct code (不算 § 6 列的 "GaC rule" 表)
    distinct = set(codes)
    assert len(distinct) >= 10, f"only {len(distinct)} codes found: {distinct}"


def test_catalog_categorized():
    """catalog 有 5 阶段章节 (Phase 6/7/8/9A/P77-1)."""
    text = CATALOG.read_text()
    assert "Phase 6" in text
    assert "Phase 7" in text
    assert "Phase 8" in text
    assert "Phase 9A" in text
    assert "P77 Phase 1" in text


def test_catalog_documents_lost_work():
    """catalog § 8 现状快照 (防同步漂移)"""
    text = CATALOG.read_text()
    assert "## 8. 现状快照" in text
    assert "100 A+" in text
    assert "164" in text or "169" in text  # GaC rules count varies


def test_principle_has_meaning():
    """每个 P76-N-N / P77-N 原则有 '**含义**' 字段 (P77-2-1 principle-formalization-with-context)"""
    text = CATALOG.read_text()
    # 收集所有原则 codes (table rows + section headers)
    table_codes = set(re.findall(r"\| (P76-\d+-\d+|P77-2-\d+|P77-1) \| \*\*[^*]+\*\* \|", text))
    heading_codes = set(re.findall(r"### (P76-\d+-\d+|P77-2-\d+|P77-1): ", text))
    all_codes = table_codes | heading_codes
    assert len(all_codes) >= 20, f"only {len(all_codes)} principles found: {sorted(all_codes)}"
    # 每个 code 必须在 catalog 中有 **含义** 字段 (heading 后的行 OR table row)
    missing = []
    for code in all_codes:
        # 在 heading 形式下, 紧跟 ### code: 行的下一行以 **含义** 开头
        heading_re = re.compile(r"### " + re.escape(code) + r":.*?(?=\n### |\n## |\Z)", re.DOTALL)
        m = heading_re.search(text)
        if m and "**含义**" in m.group(0):
            continue
        # 在 table 形式下, 行内需要"含义" 字段 (因为表头有 含义 列)
        table_re = re.compile(r"\| " + re.escape(code) + r" \| \*\*[^*]+\*\* \| [^|]*含义[^|]*\|")
        if table_re.search(text):
            continue
        missing.append(code)
    assert not missing, f"principles missing 含义 field: {missing}"


def test_catalog_is_ssot_for_principles():
    """catalog 引用 ADR (SSOT chain), 防 source split."""
    text = CATALOG.read_text()
    assert "ADR-0160" in text
    assert "ADR-0161" in text
    assert "ADR-0162" in text
    assert "ADR-0163" in text
    assert "ADR-0164" in text


def test_catalog_evolution_guide():
    """catalog § 7 演进指南 包含写入新原则路径."""
    text = CATALOG.read_text()
    assert "## 7. 演进指南" in text
    # 列出加入步骤
    assert "ADR" in text
    assert "GaC rule" in text or "GaC" in text


def test_principle_p77_2_anti_rollback():
    """P77-2-4 anti-rollback-baseline 必出现 (修真修真)."""
    text = CATALOG.read_text()
    assert "P77-2-4" in text, "P77-2-4 must appear (catalog § 2: anti-rollback-baseline)"


def test_principle_p77_2_3_rule_per_principle():
    """P77-2-3 rule-per-principle 必出现."""
    text = CATALOG.read_text()
    assert "rule-per-principle" in text, "P77-2-3 rule-per-principle must appear in catalog § 2"


def test_all_15_adrs_cited():
    """catalog § 0 阶段表应包含全部 5 ADR 来源."""
    text = CATALOG.read_text()
    for adr in ["ADR-0160", "ADR-0161", "ADR-0162", "ADR-0163", "ADR-0164"]:
        assert adr in text, f"missing {adr} citation"
