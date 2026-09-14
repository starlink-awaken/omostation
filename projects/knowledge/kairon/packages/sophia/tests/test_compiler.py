"""Tests for sophia.compiler — 范式编译器"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from sophia.compiler import _default_ops, _template_compile, compile_paradigm_sync
from sophia.symbols import ParadigmProgram


class TestCompiler:
    def test_template_compile(self):
        prog = _template_compile("分析某技术趋势")
        assert isinstance(prog, ParadigmProgram)
        assert len(prog.operations) >= 2

    def test_template_compile_empty(self):
        prog = _template_compile("")
        assert isinstance(prog, ParadigmProgram)

    def test_default_ops(self):
        ops = _default_ops("测试")
        assert len(ops) >= 2

    def test_compile_paradigm_sync(self):
        prog = compile_paradigm_sync("比较 Python 和 Go")
        assert isinstance(prog, ParadigmProgram)
        assert len(prog.operations) >= 2

    def test_compile_paradigm_sync_long_query(self):
        query = "分析" + "测试" * 50
        prog = compile_paradigm_sync(query)
        assert isinstance(prog, ParadigmProgram)
