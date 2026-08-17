"""sophia 基础测试"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from sophia import cli
from sophia.compiler import compile_paradigm_sync


class TestCompiler:
    """编译器测试"""

    def test_import(self):
        """测试导入"""
        assert compile_paradigm_sync is not None


class TestCLI:
    """CLI 测试"""

    def test_import(self):
        """测试 CLI 导入"""
        assert cli is not None
