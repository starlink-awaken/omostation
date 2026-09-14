# pyright: reportAttributeAccessIssue=false

import os
from pathlib import Path

import pytest

os.environ.setdefault("ONTODERIVE_LLM_BACKEND", "none")


@pytest.fixture(scope="session")
def project_root():
    return Path(__file__).parent.parent


@pytest.fixture(scope="session")
def z_park_path(project_root):
    return project_root / "examples" / "z-park"


@pytest.fixture
def tmp_project(tmp_path):
    for d in ["facts", "entities", "inferences", "protocols", "scheme", "_logs"]:
        (tmp_path / d).mkdir(parents=True, exist_ok=True)
    (tmp_path / "facts" / "data.md").write_text(
        "| 编号 | 数据 | 数值 | 来源 |\n|------|------|------|------|\n| D-F1 | 测试事实 | 100 | 测试 |\n"
    )
    return tmp_path


@pytest.fixture
def mock_enhancer():
    """返回一个模拟的 LLM enhancer，供 test_analytics.py / test_insight.py 使用"""

    class _MockEnhancer:
        available = True
        model = "mock-model"

        def _call(self, prompt, system="", temperature=0.3):
            return "模拟分析结论：建议增加事实引用"

    return _MockEnhancer()
