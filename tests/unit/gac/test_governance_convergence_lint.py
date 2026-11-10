"""governance-convergence-lint 的自证测试 —— 判据必须真的能命中。

缺陷背景 (2026-11-10 实证): R-GOV-5 用正则 `(\\d+)\\s+条规则` 去
`docs/generated/agent-gac-rules.md` 数规则条数, 但生成器
`bin/gac/gac-export-agents.py` 实际写出的文本是:

    ### GaC 规则速览 (136 条)
    <!-- ... Source: governance-checks.yaml (136 rules) -->

三者都不含「条规则」⇒ **这条判据从未真正命中过**: 文档写着 136 条而注册表
只有 87 条, 判据照样绿 (空绿)。

本测试锁两件事:
1. **匹配口径与生成器一致**: 用生成器真实写出的两种句式做正反面 ——
   计数不符必须报 WARN, 计数一致必须不报;
2. **旧口径确实失效**: 直接对旧正则做反证, 防止有人再把它改回去
   (改回 `条规则` 就等于把判据重新打成空绿)。
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
LINT = ROOT / "bin" / "gac" / "governance-convergence-lint.py"


@pytest.fixture()
def lint_module():
    spec = importlib.util.spec_from_file_location("governance_convergence_lint", LINT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_rgov5(module, tmp_path: Path, doc_text: str) -> list[str]:
    gen = tmp_path / "docs" / "generated" / "agent-gac-rules.md"
    gen.parent.mkdir(parents=True, exist_ok=True)
    gen.write_text(doc_text, encoding="utf-8")
    module.WORKSPACE = tmp_path
    errors, warnings = module.check_rules_count()
    return errors + warnings


GENERATOR_HEADING = "### GaC 规则速览 ({n} 条)"
GENERATOR_COMMENT = "<!-- Run: python3 bin/gac/gac-export-agents.py to regenerate. Source: governance-checks.yaml ({n} rules) -->"


def test_generator_phrase_is_matched(lint_module, tmp_path: Path) -> None:
    """生成器真实句式 (中文「N 条」+ 英文「(N rules)」) 都必须能被读到。"""
    actual = len(lint_module._extract_registered_cr_ids())
    # 计数一致 → 不报
    doc = GENERATOR_HEADING.format(n=actual) + "\n" + GENERATOR_COMMENT.format(n=actual) + "\n"
    assert _run_rgov5(lint_module, tmp_path, doc) == []

    # 计数不符 → 报, 且报的是文档里的那个数
    stale = actual + 49
    doc = GENERATOR_HEADING.format(n=stale) + "\n" + GENERATOR_COMMENT.format(n=stale) + "\n"
    out = _run_rgov5(lint_module, tmp_path, doc)
    assert any("R-GOV-5" in w and str(stale) in w for w in out), out


def test_english_comment_alone_is_matched(lint_module, tmp_path: Path) -> None:
    """只有英文 comment 时也要能读到 (两种句式独立可用)。"""
    actual = len(lint_module._extract_registered_cr_ids())
    doc = GENERATOR_COMMENT.format(n=actual + 10) + "\n"
    out = _run_rgov5(lint_module, tmp_path, doc)
    assert any("R-GOV-5" in w for w in out), out


def test_old_blind_regex_is_gone() -> None:
    """旧口径对生成器真实文本零命中 —— 反证它确实是个空绿的尺。

    这是「判据自证」的反面: 判据必须与被检对象**不共享失效模式**。
    这里不读源码 (注释里本就引用旧口径来解释缺陷), 只证旧尺读不出数。
    """
    old_pattern = re.compile(r"(\d+)\s+条规则")
    assert old_pattern.search(GENERATOR_HEADING.format(n=136)) is None
    assert old_pattern.search(GENERATOR_COMMENT.format(n=136)) is None
    # 新口径读得出
    assert re.search(r"GaC 规则速览\s*\((\d+)\s*条\)", GENERATOR_HEADING.format(n=136))
    assert re.search(r"\((\d+)\s+rules\)", GENERATOR_COMMENT.format(n=136))
