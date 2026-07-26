"""P0-5 — check-doc-claims 文档宣称失真防复发门测试 (workorder 2026-07-25).

验证 CR-X4-DOC-CLAIMS: 注入裸数字/裸通过率宣称均检出, 指针化干净态全绿.
防 P0-3 指针化退化.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_BIN = Path(__file__).resolve().parent.parent / "bin" / "mof"
_spec = importlib.util.spec_from_file_location(
    "doc_claims", _BIN / "check-doc-claims.py"
)
assert _spec is not None and _spec.loader is not None, "无法加载 doc_claims 模块"
doc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(doc)


def test_interface_bare_number_detected():
    """注入 'tests: 188' 无注释 → 检出 (P0-3 前 metaos 状态复现)."""
    findings = doc.check_interface_tests_has_pointer("tests: 188\ncli: x\n")
    assert len(findings) == 1
    assert findings[0]["check"] == "interface_tests_bare_number"


def test_interface_with_pointer_clean():
    """'tests: 260  # as_of ...' 带指针 → 无漂移."""
    findings = doc.check_interface_tests_has_pointer(
        "tests: 260  # as_of 2026-07-26, 见 pytest tests/\n"
    )
    assert findings == []


def test_bare_pass_claim_detected():
    """注入 '100% 通过' → 检出."""
    findings = doc.check_no_bare_pass_claim(
        "# 测试 (100% 通过, 188 tests)", "AGENTS.md"
    )
    assert len(findings) == 1
    assert findings[0]["check"] == "bare_pass_claim"
    assert findings[0]["file"] == "AGENTS.md"


def test_pointerized_md_clean():
    """指针化表述 (无裸数字) → 无漂移."""
    findings = doc.check_no_bare_pass_claim(
        "# 测试 (计数见 pytest tests/ 实际输出 / CI, 不复制数字)", "CLAUDE.md"
    )
    assert findings == []


def test_detect_metaos_no_findings():
    """端到端: 真实 metaos 文档 (P0-3 已指针化) → 0 findings."""
    repo = Path(__file__).resolve().parent.parent
    result = doc.detect_doc_claim_drift(repo / "projects" / "metaos")
    assert result["total_findings"] == 0, (
        f"metaos 文档仍有裸宣称: {result['findings']}"
    )
