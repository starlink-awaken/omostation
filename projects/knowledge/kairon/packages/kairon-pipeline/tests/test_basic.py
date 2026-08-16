"""kairon-pipeline 基础测试"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

import kairon_pipeline


class TestPipeline:
    """流水线测试"""

    def test_import(self):
        """测试导入"""
        assert kairon_pipeline is not None
