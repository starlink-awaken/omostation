"""
Tests for model_driven.toolchain.mof_* — MOF 操作工具
"""

import pytest
import tempfile
from pathlib import Path
from model_driven.toolchain.mof_scan import (
    scan_project_dir,
    scan_workspace,
    scan_system,
    scan_yaml_configs,
    scan_agent_contracts,
)
from model_driven.toolchain.mof_model import (
    model_project,
    model_workspace,
    classify_by_lifecycle_stage,
)
from model_driven.toolchain.mof_extract import (
    extract_lessons_from_markdown,
    extract_decisions_from_markdown,
    extract_specs_from_agent_contract,
    extract_all,
)


class TestMofScan:
    def test_scan_project_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "pyproject.toml").write_text("[project]\nname='test'")
            src = root / "src"
            src.mkdir()
            (src / "main.py").write_text("print('hello')")
            tests = root / "tests"
            tests.mkdir()
            (tests / "test_main.py").write_text("def test(): pass")

            result = scan_project_dir(root, "test-project")
            assert len(result.nodes) >= 1  # at least the component node

    def test_scan_empty_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = scan_project_dir(Path(tmpdir))
            assert len(result.nodes) == 0

    def test_scan_nonexistent_dir(self):
        result = scan_project_dir("/nonexistent/path")
        assert len(result.errors) > 0

    def test_scan_yaml_configs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "config.yaml").write_text("key: value")
            result = scan_yaml_configs(root)
            assert len(result.nodes) == 1
            assert result.nodes[0]["type"] == "deployment_config"

    def test_scan_agent_contracts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "AGENTS.md").write_text("# Agents Guide")
            (root / "CLAUDE.md").write_text("# Claude Config")
            result = scan_agent_contracts(root)
            assert len(result.nodes) == 2

    def test_scan_system(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "pyproject.toml").write_text("[project]\nname='test'")
            src = root / "src"
            src.mkdir()
            (src / "main.py").write_text("print('hello')")

            result = scan_system(
                paths=[str(root)],
                workspace_dir=None,
                scan_projects=True,
                scan_configs=False,
                scan_contracts=False,
            )
            assert result["success"]
            assert result["total_nodes"] >= 2  # component + code_module


class TestMofModel:
    def test_model_project(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "pyproject.toml").write_text("[project]\nname='test'")
            src = root / "src"
            src.mkdir()
            (src / "main.py").write_text("print('hello')")
            tests = root / "tests"
            tests.mkdir()
            (tests / "test_main.py").write_text("def test(): pass")
            (root / "CLAUDE.md").write_text("# Claude")

            result = model_project(root, "test-project")
            assert result["success"]
            model = result["model"]
            assert len(model["modules"]) == 1
            assert len(model["tests"]) == 1
            assert len(model["specs"]) == 1
            assert model["total"] >= 3

    def test_model_nonexistent(self):
        result = model_project("/nonexistent")
        assert not result["success"]

    def test_classify_by_lifecycle_stage(self):
        model = {
            "models": [{
                "model": {
                    "modules": [{"id": "MOD-1"}],
                    "tests": [{"id": "TEST-1"}],
                    "configs": [{"id": "CFG-1"}],
                    "specs": [{"id": "SPEC-1"}],
                    "services": [{"id": "SVC-1"}],
                },
            }],
        }
        result = classify_by_lifecycle_stage(model)
        assert "MOD-1" in result["development"]
        assert "TEST-1" in result["development"]
        assert "CFG-1" in result["deployment"]
        assert "SPEC-1" in result["design"]
        assert "SVC-1" in result["runtime"]


class TestMofExtract:
    def test_extract_lessons(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("## 教训: 不应该使用全局变量\n")
            f.write("全局变量导致测试隔离问题。\n")
            f.write("解决方案: 使用依赖注入。\n")
            f.write("\n## 普通章节\n")
            f.write("这是普通内容。\n")
            fpath = f.name

        try:
            result = extract_lessons_from_markdown(fpath)
            assert len(result.nodes) >= 1
            assert result.nodes[0]["type"] == "lesson"
        finally:
            Path(fpath).unlink()

    def test_extract_decisions(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("## 决策: 使用 Python 作为主要语言\n")
            f.write("基于团队技能和生态考虑。\n")
            f.write("选择 Python 3.13+。\n")
            fpath = f.name

        try:
            result = extract_decisions_from_markdown(fpath)
            assert len(result.nodes) >= 1
            assert result.nodes[0]["type"] == "decision"
        finally:
            Path(fpath).unlink()

    def test_extract_specs(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# AGENTS.md\n")
            f.write("## 规则组\n")
            f.write("- 规则1: 所有修改必须测试\n")
            f.write("- 规则2: 提交前运行 lint\n")
            f.write("- 规则3: 使用语义化提交\n")
            f.write("- 规则4: 更新文档\n")
            fpath = f.name

        try:
            result = extract_specs_from_agent_contract(fpath)
            if result.nodes:
                assert result.nodes[0]["type"] == "specification"
                assert result.nodes[0]["properties"]["rule_count"] >= 3
        finally:
            Path(fpath).unlink()

    def test_extract_all(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "lessons.md").write_text("## 教训: 测试\n内容。\n")
            (root / "decisions.md").write_text("## 决策: 选型\n内容。\n")

            result = extract_all(root, extract_lessons=True, extract_decisions=True, extract_specs=False)
            assert result["success"]
            assert result["total_nodes"] >= 1

    def test_extract_empty_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = extract_all(tmpdir)
            assert result["success"]
            assert result["total_nodes"] == 0
