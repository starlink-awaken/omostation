"""health-profile 基础测试"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

import health_profile


class TestHealthProfile:
    """健康档案测试"""

    def test_import(self):
        """测试导入"""
        assert health_profile is not None
